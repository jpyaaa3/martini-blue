"""Optional real-browser recording checks: install playwright + chromium to run."""

import json
from pathlib import Path
import shutil
import subprocess
import threading

import numpy as np
import pytest

playwright = pytest.importorskip("playwright.sync_api")

from vision_demo.web_viewer import WebViewer


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as engine:
        if not Path(engine.chromium.executable_path).exists():
            pytest.skip("Run: python -m playwright install chromium")
        browser = engine.chromium.launch(channel="chromium", args=["--no-sandbox"])
        yield browser
        browser.close()


@pytest.fixture
def viewer_page(browser):
    viewer = WebViewer(host="127.0.0.1", port=0)
    viewer.start()
    done = threading.Event()

    def publish():
        tick = 0
        while not done.is_set():
            for name, color in (("observer", (20, 40, 230)), ("mounted", (230, 40, 20))):
                frame = np.full((54, 96, 3), color, dtype=np.uint8)
                frame[:, tick % 96] = 255
                viewer.publish_frame(name, frame)
            tick += 1
            done.wait(0.05)

    thread = threading.Thread(target=publish)
    thread.start()
    context = browser.new_context(accept_downloads=True)
    page = context.new_page()
    yield page, viewer, f"http://127.0.0.1:{viewer.port}"
    context.close()
    done.set()
    thread.join(timeout=2)
    viewer.close()


def ready(page, base):
    page.goto(base)
    page.wait_for_selector('#mounted[data-ready="true"]')
    page.wait_for_selector('#observer[data-ready="true"]')
    assert page.locator('#recording-start').is_enabled(), page.locator('#recording-status').inner_text()


def verify_mp4(path, width):
    assert path.read_bytes()[4:8] == b"ftyp"
    assert path.stat().st_size > 500
    if shutil.which("ffprobe"):
        result = subprocess.run([
            "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path),
        ], check=True, capture_output=True, text=True)
        info = json.loads(result.stdout)
        video = info["streams"][0]
        assert video["codec_type"] == "video"
        assert video["width"] == width
        assert video["height"] == 54
        assert float(info["format"]["duration"]) >= 0.5


def test_download_real_mp4_and_ignore_driving_keys_in_filename(viewer_page, tmp_path):
    page, viewer, base = viewer_page
    # Exercise download fallback independently of native-picker availability.
    page.add_init_script("window.showSaveFilePicker = undefined;")
    ready(page, base)
    page.locator('#recording-file').fill('')
    page.locator('#recording-file').press_sequentially('wasdr recording.mp4')
    assert not viewer.controls().throttle
    assert not viewer.consume_reset()
    page.locator('#recording-start').click()
    assert page.locator('#recording-file').is_disabled()
    page.screenshot(path=str(tmp_path / 'recording-ui.png'))
    page.keyboard.down('w')
    page.wait_for_timeout(100)
    assert viewer.controls().throttle
    page.keyboard.up('w')
    page.wait_for_timeout(1100)
    with page.expect_download() as downloaded:
        page.locator('#recording-stop').click()
    path = tmp_path / 'both.mp4'
    downloaded.value.save_as(path)
    assert downloaded.value.suggested_filename == 'wasdr recording.mp4'
    verify_mp4(path, 192)
    assert page.locator('#recording-start').is_enabled()
    assert page.locator('#recording-stop').is_disabled()


def test_browse_saves_selected_file_and_simulation_stop_flushes(viewer_page, tmp_path):
    page, viewer, base = viewer_page
    page.add_init_script("""
        window.showSaveFilePicker = async options => {
          window.pickerOptions = options;
          const root = await navigator.storage.getDirectory();
          window.pickedFile = await root.getFileHandle('chosen.mp4', {create: true});
          return window.pickedFile;
        };
    """)
    ready(page, base)
    page.locator('#recording-browse').click()
    page.wait_for_function("document.getElementById('recording-file').value === 'chosen.mp4'")
    page.locator('#recording-source').select_option('mounted')
    page.locator('#recording-start').click()
    page.wait_for_timeout(1200)
    page.locator('#stop').click()
    page.wait_for_function("document.getElementById('recording-status').textContent.startsWith('Saved:')")
    page.wait_for_function("document.body.classList.contains('offline')")
    assert viewer.stop_requested()
    content = page.evaluate("async () => Array.from(new Uint8Array(await (await window.pickedFile.getFile()).arrayBuffer()))")
    path = tmp_path / 'chosen.mp4'
    path.write_bytes(bytes(content))
    verify_mp4(path, 96)


def test_picker_cancel_and_write_failure_keep_ui_usable(viewer_page):
    page, _, base = viewer_page
    page.add_init_script("""
        window.showSaveFilePicker = async () => {
          if (!window.failWrite) throw new DOMException('Cancelled', 'AbortError');
          return {name: 'blocked.mp4', createWritable: async () => {throw new Error('Disk full');}};
        };
    """)
    ready(page, base)
    name = page.locator('#recording-file').input_value()
    page.locator('#recording-browse').click()
    page.wait_for_function("!document.getElementById('recording-start').disabled")
    assert page.locator('#recording-file').input_value() == name
    page.evaluate('window.failWrite = true')
    page.locator('#recording-browse').click()
    page.wait_for_function("document.getElementById('recording-file').value === 'blocked.mp4'")
    page.locator('#recording-start').click()
    page.wait_for_timeout(1100)
    page.locator('#recording-stop').click()
    page.wait_for_function("document.getElementById('recording-status').textContent.includes('Disk full')")
    assert page.locator('#recording-download').is_visible()
    assert page.locator('#recording-start').is_enabled()


def test_unsupported_mp4_is_reported_without_webm_disguised_as_mp4(viewer_page):
    page, _, base = viewer_page
    page.add_init_script('MediaRecorder.isTypeSupported = () => false;')
    page.goto(base)
    assert page.locator('#recording-start').is_disabled()
    assert 'cannot record MP4' in page.locator('#recording-status').inner_text()
