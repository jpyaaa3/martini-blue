"""GLFW/ImGui window that displays the block-mounted camera."""

from __future__ import annotations

from typing import Any

import glfw
import imgui
from imgui.integrations.glfw import GlfwRenderer
from OpenGL import GL

from .vehicle import ControlInput, VehicleState


class CameraWindow:
    def __init__(self, width: int = 960, height: int = 720) -> None:
        if not glfw.init():
            raise RuntimeError("glfw.init() failed; check DISPLAY/X11 forwarding")
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.RESIZABLE, glfw.TRUE)
        self.window = glfw.create_window(width, height, "Mounted Camera", None, None)
        if not self.window:
            glfw.terminate()
            raise RuntimeError("failed to create mounted-camera GLFW window")
        glfw.make_context_current(self.window)
        glfw.swap_interval(1)
        imgui.create_context()
        self.renderer = GlfwRenderer(self.window)
        self.texture = int(GL.glGenTextures(1))
        self.texture_size: tuple[int, int] | None = None
        self._closed = False
        self._configure_texture()

    def _configure_texture(self) -> None:
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.texture)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)

    def should_close(self) -> bool:
        return self._closed or bool(glfw.window_should_close(self.window))

    def poll_controls(self) -> ControlInput:
        glfw.poll_events()
        self.renderer.process_inputs()
        if glfw.get_key(self.window, glfw.KEY_ESCAPE) == glfw.PRESS:
            glfw.set_window_should_close(self.window, glfw.TRUE)
        focused = glfw.get_window_attrib(self.window, glfw.FOCUSED) == glfw.TRUE
        if not focused or bool(getattr(imgui.get_io(), "want_text_input", False)):
            return ControlInput()

        down = lambda key: glfw.get_key(self.window, key) == glfw.PRESS
        return ControlInput(
            throttle=down(glfw.KEY_W),
            brake_reverse=down(glfw.KEY_S),
            steer_left=down(glfw.KEY_A),
            steer_right=down(glfw.KEY_D),
        )

    def reset_requested(self) -> bool:
        return glfw.get_key(self.window, glfw.KEY_R) == glfw.PRESS

    def upload(self, frame: Any) -> None:
        height, width = int(frame.shape[0]), int(frame.shape[1])
        glfw.make_context_current(self.window)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.texture)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
        if self.texture_size == (width, height):
            GL.glTexSubImage2D(
                GL.GL_TEXTURE_2D,
                0,
                0,
                0,
                width,
                height,
                GL.GL_RGB,
                GL.GL_UNSIGNED_BYTE,
                frame,
            )
        else:
            GL.glTexImage2D(
                GL.GL_TEXTURE_2D,
                0,
                GL.GL_RGB,
                width,
                height,
                0,
                GL.GL_RGB,
                GL.GL_UNSIGNED_BYTE,
                frame,
            )
            self.texture_size = (width, height)

    def draw(self, state: VehicleState, *, camera_fps: float) -> None:
        glfw.make_context_current(self.window)
        imgui.new_frame()
        viewport_w, viewport_h = glfw.get_framebuffer_size(self.window)
        imgui.set_next_window_position(0.0, 0.0)
        imgui.set_next_window_size(float(viewport_w), float(viewport_h))
        flags = (
            imgui.WINDOW_NO_TITLE_BAR
            | imgui.WINDOW_NO_RESIZE
            | imgui.WINDOW_NO_MOVE
            | imgui.WINDOW_NO_COLLAPSE
        )
        imgui.begin("Mounted Camera###root", flags=flags)
        imgui.text("W accelerator | S brake/reverse | A/D steer | R reset | Esc quit")
        imgui.text(
            f"speed {state.speed_mps:+.2f} m/s   steering {state.steering:+.2f}   "
            f"camera {camera_fps:.1f} fps"
        )
        available_w, available_h = imgui.get_content_region_available()
        if self.texture_size is None:
            imgui.text_disabled("Waiting for the first Genesis camera frame...")
        else:
            image_w, image_h = self.texture_size
            scale = min(available_w / image_w, available_h / image_h)
            draw_w, draw_h = image_w * scale, image_h * scale
            cursor_x, cursor_y = imgui.get_cursor_pos()
            imgui.set_cursor_pos((cursor_x + (available_w - draw_w) * 0.5, cursor_y))
            imgui.image(
                self.texture,
                draw_w,
                draw_h,
                uv0=(0.0, 1.0),
                uv1=(1.0, 0.0),
            )
        imgui.end()
        imgui.render()
        width, height = glfw.get_framebuffer_size(self.window)
        GL.glViewport(0, 0, width, height)
        GL.glClearColor(0.08, 0.09, 0.11, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        self.renderer.render(imgui.get_draw_data())
        glfw.swap_buffers(self.window)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            glfw.make_context_current(self.window)
            if self.texture:
                GL.glDeleteTextures([self.texture])
            self.renderer.shutdown()
            glfw.destroy_window(self.window)
        finally:
            glfw.terminate()

