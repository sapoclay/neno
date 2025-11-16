from queue import Queue
from typing import Optional

from .commands import AvatarCommandMixin
from .ui import AvatarUIMixin
from .visuals import AvatarVisualsMixin


class AvatarWindow(AvatarCommandMixin, AvatarVisualsMixin, AvatarUIMixin):
    """Ventana principal del avatar animado."""

    def __init__(self):
        super().__init__()
        self.window = None
        self.canvas = None
        self.conversation = None
        self.text_input = None
        self.send_button = None
        self.voice_button = None
        self.stop_voice_button = None
        self.instructions_button = None
        self.close_button = None
        self._status_label = None

        self.is_speaking = False
        self.animation_thread = None
        self.mouth_state = 0
        self.command_queue = Queue()
        self.window_created = False
        self.head_image = None
        self.head_photo = None
        self._greeted_once = False
        self.gemini_mode = False
        self.transparent_color = "#010101"
        self._supports_true_transparency = False
        self._dragging = False
        self._drag_offset = (0, 0)
        self._month_names = (
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
        )
        self._instructions_window = None
        self._instructions_text_widget = None
        self._head_drawn = False
        self._action_locked = False
        self._style = None
        self._internal_editor_event = None
        self._envelope_index = 0
        self._envelope_data: list[int] = []
        self._loading_history = False


_avatar_instance: Optional[AvatarWindow] = None


def get_avatar():
    global _avatar_instance
    if _avatar_instance is None:
        _avatar_instance = AvatarWindow()
    return _avatar_instance
