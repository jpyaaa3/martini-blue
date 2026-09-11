"""Select a display-capable Ubuntu native viewer, or the browser fallback."""
import os
import platform


def prefer_native():
    if platform.system() != 'Linux' or not os.environ.get('DISPLAY'):
        return False
    try:
        return platform.freedesktop_os_release().get('ID') == 'ubuntu'
    except OSError:
        return False


def start_viewer(mode, host, port):
    if mode == 'native' or (mode == 'auto' and prefer_native()):
        try:
            from .native_viewer import NativeViewer
            viewer = NativeViewer()
            viewer.start()
            return viewer
        except Exception as exc:
            if mode == 'native':
                raise RuntimeError(f'Native viewer unavailable: {exc}. Try --viewer web.') from exc
            print(f'[vision] Native viewer unavailable ({exc}); using web viewer', flush=True)
    from .web_viewer import WebViewer
    viewer = WebViewer(host=host, port=port)
    viewer.start()
    print(f'[vision] HTML viewer: http://localhost:{viewer.port}', flush=True)
    return viewer
