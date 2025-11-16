import threading
import time
import tkinter as tk
from pathlib import Path
from typing import Callable, Optional

from PIL import Image, ImageTk

from .shared_refs import AvatarWidgetRefs

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class AvatarVisualsMixin(AvatarWidgetRefs):
    """Funciones relacionadas con la apariencia y animación del avatar."""

    head_image: Optional[Image.Image]
    head_photo: Optional[ImageTk.PhotoImage]
    _head_drawn: bool
    is_speaking: bool
    animation_thread: Optional[threading.Thread]
    _envelope_index: int
    _envelope_data: list[int]
    show_window: Callable[[], None]
    _append_conversation: Callable[[str, str], None]

    def load_head_image(self):
        img_name = "cabeza.png"
        try:
            import voice
            gender = str(voice._load_settings().get("voice_gender", "female")).lower()
            if gender == "female":
                img_name = "cabezafemenina.png"
        except Exception:
            pass
        head_path = PROJECT_ROOT / "assets" / img_name
        if not head_path.exists():
            head_path = PROJECT_ROOT / "assets" / "cabeza.png"
        if head_path.exists():
            try:
                img = Image.open(head_path)
                img = img.resize((280, 280), Image.Resampling.LANCZOS)
                self.head_image = img.copy()
                self.head_photo = ImageTk.PhotoImage(img)
                return True
            except Exception as exc:
                print(f"Error cargando imagen de cabeza: {exc}")
                return False
        return False

    def draw_face(self, mouth_state: int = 0):
        if self.canvas is None or not self.window_created:
            return
        try:
            if self.head_photo is None:
                self.load_head_image()
            if self.head_photo is not None:
                self.canvas.delete("mouth")
                existing_head = bool(self.canvas.find_withtag("head"))
                if not existing_head:
                    self.canvas.create_image(140, 140, image=self.head_photo, tags="head")
                else:
                    try:
                        self.canvas.itemconfig("head", image=self.head_photo)
                    except Exception:
                        self.canvas.delete("head")
                        self.canvas.create_image(140, 140, image=self.head_photo, tags="head")
                self._head_drawn = True
                if mouth_state == 0:
                    self.canvas.create_line(120, 208, 160, 208, fill="black", width=2, tags="mouth")
                elif mouth_state == 1:
                    self.canvas.create_arc(120, 200, 160, 220, start=0, extent=-180, width=2, style=tk.ARC, tags="mouth")
                elif mouth_state == 2:
                    self.canvas.create_oval(125, 200, 155, 215, fill="#cc6666", outline="black", width=2, tags="mouth")
                elif mouth_state == 3:
                    self.canvas.create_oval(120, 195, 160, 220, fill="#cc6666", outline="black", width=2, tags="mouth")
                    self.canvas.create_rectangle(128, 195, 152, 203, fill="white", outline="", tags="mouth")
                elif mouth_state == 4:
                    self.canvas.create_oval(118, 190, 162, 225, fill="#cc5555", outline="black", width=2, tags="mouth")
                    self.canvas.create_rectangle(126, 190, 154, 200, fill="white", outline="", tags="mouth")
                    self.canvas.create_arc(122, 205, 158, 225, start=0, extent=-180, fill="#dd7777", outline="#aa4444", width=1, tags="mouth")
                else:
                    self.canvas.create_oval(112, 188, 168, 228, fill="#cc4444", outline="black", width=2, tags="mouth")
                    self.canvas.create_rectangle(124, 188, 156, 200, fill="white", outline="", tags="mouth")
                    self.canvas.create_arc(118, 206, 162, 228, start=0, extent=-180, fill="#e08080", outline="#aa3030", width=1, tags="mouth")
            else:
                self.canvas.delete("all")
                self.canvas.create_oval(40, 40, 240, 240, fill="#ffd699", outline="#cc9966", width=3)
                self.canvas.create_oval(90, 100, 120, 140, fill="white", outline="black", width=2)
                self.canvas.create_oval(100, 110, 115, 130, fill="black")
                self.canvas.create_oval(160, 100, 190, 140, fill="white", outline="black", width=2)
                self.canvas.create_oval(170, 110, 185, 130, fill="black")
                self.canvas.create_arc(85, 70, 125, 95, start=0, extent=180, width=3, style=tk.ARC)
                self.canvas.create_arc(155, 70, 195, 95, start=0, extent=180, width=3, style=tk.ARC)
                self.canvas.create_line(140, 140, 140, 160, width=2)
                self.canvas.create_line(140, 160, 150, 165, width=2)
                if mouth_state == 0:
                    self.canvas.create_arc(100, 170, 180, 220, start=0, extent=-180, width=3, style=tk.ARC)
                elif mouth_state == 1:
                    self.canvas.create_arc(110, 180, 170, 210, start=0, extent=-180, width=2, style=tk.ARC)
                elif mouth_state == 2:
                    self.canvas.create_oval(120, 185, 160, 205, fill="#cc6666", outline="black", width=2)
                elif mouth_state == 3:
                    self.canvas.create_oval(115, 180, 165, 210, fill="#cc6666", outline="black", width=2)
                    self.canvas.create_rectangle(125, 180, 155, 188, fill="white", outline="")
                elif mouth_state == 4:
                    self.canvas.create_oval(112, 175, 168, 212, fill="#cc5555", outline="black", width=2)
                    self.canvas.create_rectangle(124, 175, 156, 187, fill="white", outline="")
                    self.canvas.create_arc(118, 190, 162, 212, start=0, extent=-180, fill="#dd7777", outline="#aa4444", width=1)
                else:
                    self.canvas.create_oval(108, 170, 172, 215, fill="#cc4444", outline="black", width=2)
                    self.canvas.create_rectangle(122, 170, 158, 185, fill="white", outline="")
                    self.canvas.create_arc(114, 188, 166, 215, start=0, extent=-180, fill="#e08080", outline="#aa3030", width=1)
        except Exception as exc:
            print(f"Error dibujando avatar: {exc}")

    def apply_gender_change_effect(self):
        if not self.window_created or self.window is None:
            try:
                self.head_image = None
                self.head_photo = None
                self._head_drawn = False
            except Exception:
                pass
            self.load_head_image()
            try:
                self._append_conversation("Asistente", "Hola")
                from voice import hablar
                hablar("Hola")
            except Exception:
                pass
            return

        if self.canvas is not None:
            try:
                self.canvas.delete('mouth')
                self.canvas.delete('head')
            except Exception:
                pass
        self.head_image = None
        self.head_photo = None
        try:
            self._head_drawn = False
        except Exception:
            pass
        self.load_head_image()
        try:
            self.draw_face(0)
        except Exception:
            pass
        try:
            self._append_conversation("Asistente", "Hola")
            from voice import hablar
            hablar("Hola")
        except Exception:
            pass

    def start_speaking(self, duration=None):
        if self.is_speaking:
            return
        self.is_speaking = True
        self.show_window()

        def animate():
            start_time = time.time()
            mouth_states = [0, 1, 2, 3, 2, 1]
            state_index = 0
            while self.is_speaking:
                if duration and (time.time() - start_time) > duration:
                    break
                if self.canvas and self.window_created and self.window is not None:
                    current_state = mouth_states[state_index]
                    try:
                        self.window.after(0, lambda s=current_state: self.draw_face(mouth_state=s))
                    except Exception:
                        pass
                    state_index = (state_index + 1) % len(mouth_states)
                time.sleep(0.08)
            try:
                if self.window and self.window_created:
                    self.window.after(0, lambda: self.draw_face(mouth_state=0))
            except Exception:
                pass
            self.is_speaking = False

        self.animation_thread = threading.Thread(target=animate, daemon=True)
        self.animation_thread.start()

    def start_speaking_envelope(self, envelope, frame_interval_ms=60):
        if not envelope:
            self.start_speaking()
            return
        if self.is_speaking:
            return
        self.is_speaking = True
        self.show_window()
        self._envelope_index = 0
        self._envelope_data = envelope

        def update():
            if (not self.is_speaking) or self._envelope_index >= len(self._envelope_data):
                try:
                    self.draw_face(mouth_state=0)
                except Exception:
                    pass
                self.is_speaking = False
                return
            state = self._envelope_data[self._envelope_index]
            try:
                self.draw_face(mouth_state=state)
            except Exception:
                pass
            self._envelope_index += 1
            if self.window is not None and self.window_created:
                try:
                    self.window.after(frame_interval_ms, update)
                except Exception:
                    pass

        if self.window is not None and self.window_created:
            self.window.after(0, update)

    def stop_speaking(self):
        self.is_speaking = False
        if self.animation_thread and self.animation_thread.is_alive():
            try:
                self.animation_thread.join(timeout=1)
            except Exception:
                pass

    def is_visible(self):
        if self.window is None:
            return False
        try:
            return self.window.winfo_viewable()
        except Exception:
            return False
