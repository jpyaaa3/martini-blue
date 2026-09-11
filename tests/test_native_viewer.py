import time
import json
import shutil
import subprocess
import numpy as np
import pytest

from vision_demo.native_viewer import Mp4Recorder
from vision_demo import viewer


def test_ubuntu_requires_display(monkeypatch):
    monkeypatch.setattr(viewer.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(viewer.platform, 'freedesktop_os_release', lambda: {'ID':'ubuntu'})
    monkeypatch.delenv('DISPLAY', raising=False)
    assert not viewer.prefer_native()
    monkeypatch.setenv('DISPLAY', ':1')
    assert viewer.prefer_native()
    monkeypatch.setattr(viewer.platform, 'freedesktop_os_release', lambda: {'ID':'debian'})
    assert not viewer.prefer_native()


def test_mp4_recording_and_no_overwrite(tmp_path):
    pytest.importorskip('imageio_ffmpeg')
    path = tmp_path/'video.mp4'
    recorder = Mp4Recorder(path, np.zeros((48,64,3), dtype=np.uint8))
    time.sleep(.15)
    recorder.update(np.full((48,64,3), 255, dtype=np.uint8))
    time.sleep(.15)
    recorder.stop()
    recorder.thread.join(timeout=10)
    assert not recorder.thread.is_alive()
    assert recorder.error is None
    assert path.read_bytes()[4:8] == b'ftyp'
    if shutil.which('ffprobe'):
        info = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(path)]))
        assert info['streams'][0]['codec_name'] == 'h264'
        assert info['streams'][0]['width'] == 64
    with pytest.raises(FileExistsError):
        Mp4Recorder(path, np.zeros((48,64,3), dtype=np.uint8))


def test_auto_falls_back_and_explicit_native_reports_failure(monkeypatch):
    from vision_demo.native_viewer import NativeViewer
    from vision_demo.web_viewer import WebViewer
    monkeypatch.setattr(viewer, 'prefer_native', lambda: True)
    def fail(self):
        raise RuntimeError('no display')
    monkeypatch.setattr(NativeViewer, 'start', fail)
    monkeypatch.setattr(WebViewer, '__init__', lambda self, **kw: None)
    monkeypatch.setattr(WebViewer, 'start', lambda self: None)
    monkeypatch.setattr(WebViewer, 'port', 8765)
    assert isinstance(viewer.start_viewer('auto','localhost',8765), WebViewer)
    with pytest.raises(RuntimeError, match='no display'):
        viewer.start_viewer('native','localhost',8765)
