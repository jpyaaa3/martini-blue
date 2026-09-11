"""GLFW/ImGui viewer in an isolated process (Genesis owns its EGL context)."""

from dataclasses import asdict
import multiprocessing as mp
import os
from pathlib import Path
from queue import Empty, Full
import threading
import time

import numpy as np

from .motion_blur import BlurSettings
from .vehicle import ControlInput


class Mp4Recorder:
    """Encode the latest frame at wall-clock 30 fps without blocking the UI."""
    def __init__(self, path, frame):
        self.path = Path(path).expanduser().absolute()
        if self.path.suffix.lower() != '.mp4':
            raise ValueError('Choose a .mp4 file')
        if not self.path.parent.is_dir():
            raise ValueError('Save folder does not exist')
        # Exclusive reservation: never silently overwrite a previous recording.
        with self.path.open('xb'):
            pass
        self.frame = frame.copy()
        self.lock = threading.Lock()
        self.done = threading.Event()
        self.error = None
        self.frames = 0
        self.thread = threading.Thread(target=self._encode, daemon=True)
        self.thread.start()

    def _encode(self):
        writer = None
        try:
            import imageio_ffmpeg
            h, w = self.frame.shape[:2]
            writer = imageio_ffmpeg.write_frames(str(self.path), (w, h), fps=30,
                codec='libx264', pix_fmt_in='rgb24', pix_fmt_out='yuv420p',
                macro_block_size=2, output_params=['-preset', 'ultrafast', '-movflags', '+faststart'])
            writer.send(None)
            started = time.monotonic()
            while True:
                with self.lock:
                    frame = self.frame
                writer.send(frame)
                self.frames += 1
                if self.done.wait(max(0, started+self.frames/30-time.monotonic())):
                    break
        except Exception as exc:
            self.error = str(exc)
        finally:
            if writer is not None:
                try:
                    writer.close()
                except Exception as exc:
                    self.error = str(exc)

    def update(self, frame):
        with self.lock:
            self.frame = frame.copy()

    def stop(self):
        self.done.set()


class NativeViewer:
    def __init__(self):
        ctx = mp.get_context('spawn')
        self.frames = ctx.Queue(maxsize=2)
        self.events = ctx.Queue(maxsize=2)
        self.shutdown = ctx.Event()
        self.reset_event = ctx.Event()
        self.ready_parent, child = ctx.Pipe(duplex=False)
        self.process = ctx.Process(target=_window, args=(self.frames, self.events, self.shutdown, self.reset_event, child), daemon=True)
        self.keys = {}
        self.blur = BlurSettings()
        self.last_event = 0.
        self.pending = {}

    def start(self):
        self.process.start()
        if not self.ready_parent.poll(12):
            self.close()
            raise RuntimeError('Native window startup timed out')
        try:
            ok, message = self.ready_parent.recv()
        except EOFError as exc:
            self.close()
            raise RuntimeError('Native window process exited during startup') from exc
        if not ok:
            self.close()
            raise RuntimeError(message)
        print('[vision] GLFW / ImGui viewer ready', flush=True)

    def _poll(self):
        while True:
            try:
                self.keys, settings, self.last_event = self.events.get_nowait()
                self.blur = BlurSettings(**settings)
            except Empty:
                break

    def controls(self):
        self._poll()
        return ControlInput(**self.keys) if time.monotonic()-self.last_event < .3 else ControlInput()

    def blur_settings(self):
        self._poll()
        return self.blur

    def consume_reset(self):
        reset = self.reset_event.is_set()
        if reset:
            self.reset_event.clear()
        return reset

    def stop_requested(self):
        return self.shutdown.is_set() or not self.process.is_alive()

    def frame_requested(self):
        return not self.stop_requested()

    def publish_frame(self, stream, frame):
        self.pending[stream] = frame

    def publish_state(self, state, *, camera_fps):
        if len(self.pending) == 2:
            try:
                self.frames.put_nowait((self.pending, {**asdict(state), 'camera_fps': camera_fps}))
            except Full:
                pass
            self.pending = {}

    def close(self):
        self.shutdown.set()
        if self.process.pid:
            self.process.join(timeout=15)
            if self.process.is_alive():
                print('[vision] Native viewer did not finish closing; recording may be incomplete', flush=True)
                self.process.terminate()
                self.process.join(timeout=2)
        for queue in (self.frames, self.events):
            queue.cancel_join_thread()
            queue.close()
        self.ready_parent.close()


def _window(frames_queue, events, shutdown, reset_event, ready):
    # PyOpenGL's platform choice is process-global; do not change Genesis' EGL.
    os.environ['PYOPENGL_PLATFORM'] = 'glx'
    window = renderer = recorder = None
    textures = {}
    try:
        import glfw
        import imgui
        from OpenGL import GL
        from imgui.integrations.glfw import GlfwRenderer
        if not glfw.init():
            raise RuntimeError('GLFW could not connect to the display')
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        window = glfw.create_window(1440, 850, 'Genesis Camera Viewer', None, None)
        if not window:
            raise RuntimeError('Could not create an OpenGL 3.3 window')
        glfw.make_context_current(window)
        glfw.swap_interval(1)
        imgui.create_context()
        imgui.get_io().ini_file_name = None
        imgui.style_colors_dark()
        style = imgui.get_style()
        style.window_rounding = 10
        style.frame_rounding = 6
        style.colors[imgui.COLOR_WINDOW_BACKGROUND] = (.05, .08, .125, 1)
        style.colors[imgui.COLOR_BUTTON] = (.20, .27, .37, 1)
        renderer = GlfwRenderer(window)
        ready.send((True, ''))
        ready.close()
        frames, telemetry = {}, {}
        enabled, denominator, source = False, 120, 0
        filename = str(Path.cwd() / ('vision-'+time.strftime('%Y%m%d-%H%M%S')+'.mp4'))
        status = 'Choose a new MP4 filename. Existing files are not overwritten.'
        browse = False
        folder = Path.cwd()
        reset_held = False
        recording_source = 0

        def recording_frame(which):
            if which == 0:
                return np.concatenate((frames['observer'], frames['mounted']), axis=1)
            return frames['mounted' if which == 1 else 'observer']

        while not shutdown.is_set() and not glfw.window_should_close(window):
            glfw.poll_events()
            renderer.process_inputs()
            fresh = False
            try:
                while True:
                    frames, telemetry = frames_queue.get_nowait()
                    fresh = True
            except Empty:
                pass
            if fresh:
                for stream, frame in frames.items():
                    if stream not in textures:
                        textures[stream] = GL.glGenTextures(1)
                    GL.glBindTexture(GL.GL_TEXTURE_2D, textures[stream])
                    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
                    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
                    GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
                    GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGB, frame.shape[1], frame.shape[0], 0, GL.GL_RGB, GL.GL_UNSIGNED_BYTE, np.ascontiguousarray(frame))
                if recorder and not recorder.done.is_set():
                    recorder.update(recording_frame(recording_source))
            if recorder and not recorder.thread.is_alive():
                status = ('Recording failed: '+recorder.error) if recorder.error else 'Saved: '+str(recorder.path)
                recorder = None
            imgui.new_frame()
            width, height = glfw.get_window_size(window)
            flags = imgui.WINDOW_NO_MOVE | imgui.WINDOW_NO_RESIZE | imgui.WINDOW_NO_COLLAPSE | imgui.WINDOW_NO_TITLE_BAR
            imgui.set_next_window_position(0, 0)
            imgui.set_next_window_size(width, max(100, height-170))
            imgui.begin('Cameras', flags=flags)
            imgui.text('speed %.2f m/s  |  steer %.2f  |  position %.2f, %.2f  |  camera %.1f fps' % tuple(telemetry.get(k,0) for k in ('speed_mps','steering','x','y','camera_fps')))
            imgui.text_colored('W accelerate | S brake/reverse | A/D steer | Space handbrake | R reset | Esc stop', .71,.77,.85)
            if imgui.button('Stop simulation'):
                shutdown.set()
            imgui.columns(2, 'views', False)
            for stream, title in (('observer','Third-person chase'), ('mounted','Mounted camera')):
                imgui.text(title)
                if stream in textures:
                    h,w = frames[stream].shape[:2]
                    scale = min(max(1,imgui.get_column_width()-20)/w, max(1,height-280)/h)
                    imgui.image(textures[stream], w*scale, h*scale)
                else:
                    imgui.text('Waiting for simulation...')
                imgui.next_column()
            imgui.columns(1)
            imgui.end()
            imgui.set_next_window_position(0, max(100,height-170))
            imgui.set_next_window_size(width, 170)
            imgui.begin('Controls', flags=flags)
            _, enabled = imgui.checkbox('Mounted motion blur', enabled)
            imgui.same_line()
            imgui.push_item_width(110)
            _, denominator = imgui.input_int('Shutter 1 / s', denominator)
            denominator = min(4000,max(15,denominator))
            imgui.pop_item_width()
            imgui.same_line()
            imgui.text('%.2f ms' % (1000/denominator))
            imgui.push_item_width(max(150,width-380))
            _, filename = imgui.input_text('MP4 file', filename, 2048)
            imgui.pop_item_width()
            imgui.same_line()
            if imgui.button('Browse...'):
                browse = True
                candidate = Path(filename).expanduser().parent
                folder = candidate if candidate.is_dir() else Path.cwd()
            imgui.push_item_width(200)
            _, source = imgui.combo('Camera', source, ['Both cameras','Mounted camera','Third-person chase'])
            imgui.pop_item_width()
            imgui.same_line()
            if recorder is None:
                if imgui.button('Start recording'):
                    try:
                        if len(frames) != 2:
                            raise ValueError('Wait for camera frames')
                        recorder = Mp4Recorder(filename, recording_frame(source))
                        recording_source = source
                        status = 'Recording: '+str(recorder.path)
                    except Exception as exc:
                        status = str(exc)
            elif not recorder.done.is_set():
                if imgui.button('Stop recording'):
                    recorder.stop()
                    status = 'Saving MP4...'
            else:
                imgui.text('Saving MP4...')
            imgui.text_wrapped(status)
            imgui.end()
            if browse:
                imgui.set_next_window_size(640,400, condition=imgui.FIRST_USE_EVER)
                _, opened = imgui.begin('Save folder', True)
                browse = bool(opened)
                imgui.text_wrapped(str(folder))
                if imgui.button('Parent folder'):
                    folder = folder.parent
                imgui.same_line()
                if imgui.button('Use this folder'):
                    filename = str(folder / (Path(filename).name or 'recording.mp4'))
                    browse = False
                imgui.begin_child('folders', 0, 280, border=True)
                try:
                    for entry in sorted(folder.iterdir()):
                        if entry.is_dir() and imgui.selectable(entry.name+'/')[0]:
                            folder = entry
                            break
                except OSError as exc:
                    imgui.text_wrapped(str(exc))
                imgui.end_child()
                imgui.end()
            focused = glfw.get_window_attrib(window, glfw.FOCUSED)
            keyboard = focused and not imgui.get_io().want_capture_keyboard and not browse
            def pressed(key):
                return bool(keyboard and glfw.get_key(window,key) == glfw.PRESS)
            keys = dict(throttle=pressed(glfw.KEY_W), brake_reverse=pressed(glfw.KEY_S), steer_left=pressed(glfw.KEY_A), steer_right=pressed(glfw.KEY_D), handbrake=pressed(glfw.KEY_SPACE))
            reset = pressed(glfw.KEY_R)
            if reset and not reset_held:
                reset_event.set()
            reset_held = reset
            if pressed(glfw.KEY_ESCAPE):
                shutdown.set()
            try:
                events.put_nowait((keys, asdict(BlurSettings(enabled,1/denominator)), time.monotonic()))
            except Full:
                pass
            imgui.render()
            fw,fh = glfw.get_framebuffer_size(window)
            GL.glViewport(0,0,fw,fh)
            GL.glClearColor(.03,.04,.065,1)
            GL.glClear(GL.GL_COLOR_BUFFER_BIT)
            renderer.render(imgui.get_draw_data())
            glfw.swap_buffers(window)
            time.sleep(.005)
    except Exception as exc:
        try:
            ready.send((False,str(exc)))
        except (OSError, BrokenPipeError):
            print('[vision] Native viewer error:', exc, flush=True)
    finally:
        shutdown.set()
        if recorder:
            recorder.stop()
            recorder.thread.join(timeout=12)
            if recorder.error:
                print('[vision] Recording error:', recorder.error, flush=True)
        if renderer:
            renderer.shutdown()
        if window:
            glfw.destroy_window(window)
        if 'glfw' in locals():
            glfw.terminate()
