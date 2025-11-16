from __future__ import annotations

import tkinter as tk
from typing import Optional


class AvatarWidgetRefs:
    """Atributos compartidos que todos los mixins del avatar necesitan."""

    window: Optional[tk.Toplevel]
    canvas: Optional[tk.Canvas]
    window_created: bool
