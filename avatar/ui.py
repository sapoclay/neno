import threading
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import scrolledtext
from typing import Callable, Optional, TYPE_CHECKING, cast

from .shared_refs import AvatarWidgetRefs

from conversation_memory import (
    append_message_to_history,
    clear_conversation_history,
    load_conversation_history,
)

if TYPE_CHECKING:  # Solo para ayudar a los analizadores estáticos
    from .commands import AvatarCommandMixin as _CommandMixin
    from .visuals import AvatarVisualsMixin as _VisualMixin


class AvatarUIMixin(AvatarWidgetRefs):
    """Conjunto de utilidades relacionadas con la interfaz del avatar."""

    conversation: Optional[scrolledtext.ScrolledText]
    text_input: Optional[tk.Entry]
    send_button: Optional[ttk.Button]
    voice_button: Optional[ttk.Button]
    stop_voice_button: Optional[ttk.Button]
    instructions_button: Optional[ttk.Button]
    close_button: Optional[ttk.Button]
    clear_history_button: Optional[ttk.Button]
    _supports_true_transparency: bool
    transparent_color: str

    def _commands(self) -> "_CommandMixin":
        return cast("_CommandMixin", self)

    def _visuals(self) -> "_VisualMixin":
        return cast("_VisualMixin", self)


    def create_window(self):
        """Crea la ventana principal del avatar."""
        if self.window is not None:
            return

        try:
            self.window = tk.Toplevel()
        except RuntimeError:
            root = tk.Tk()
            root.withdraw()
            self.window = tk.Toplevel(root)

        self.window.title("Asistente")
        self.window.geometry("480x820+80+80")
        self.window.resizable(False, False)
        self.window.overrideredirect(True)
        self.window.configure(bg="#1e1e1e", highlightthickness=0, bd=0)
        try:
            self.window.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.window.lift()
        self.window.update_idletasks()
        self.window.bind("<ButtonPress-1>", self._start_drag)
        self.window.bind("<ButtonRelease-1>", self._stop_drag)
        self.window.bind("<B1-Motion>", self._perform_drag)
        self._head_drawn = False
        self.window_created = True

        style = ttk.Style(self.window)
        try:
            active_theme = style.theme_use()
            style.theme_use(active_theme)
        except Exception:
            pass
        floating_bg = "#1e1e1e"
        style.configure("Floating.TFrame", background=floating_bg)
        self._style = style

        canvas_bg = "#f0f0f0"
        self.canvas = tk.Canvas(
            self.window,
            width=280,
            height=280,
            bg=canvas_bg,
            highlightthickness=0,
            bd=0
        )
        self.canvas.pack(pady=10)
        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<ButtonRelease-1>", self._stop_drag)
        self.canvas.bind("<B1-Motion>", self._perform_drag)

        chat_frame = ttk.Frame(self.window, style="Floating.TFrame")
        chat_frame.pack(pady=(5, 10), padx=12, fill=tk.BOTH, expand=True)

        self.conversation = scrolledtext.ScrolledText(
            chat_frame,
            height=12,
            font=("Segoe UI", 10),
            wrap=tk.WORD,
            state=tk.DISABLED,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0
        )
        self.conversation.pack(fill=tk.BOTH, expand=True, pady=(5, 8))

        history_loaded = self._load_conversation_history()

        input_frame = ttk.Frame(chat_frame, style="Floating.TFrame")
        input_frame.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(
            input_frame,
            text="Escribe tu mensaje aquí:",
            style="Muted.TLabel"
        ).pack(anchor="w", pady=(0, 2))

        entry_container = tk.Frame(
            input_frame,
            bg="#ffffff",
            highlightthickness=1,
            highlightbackground="#4a90e2",
            bd=0
        )
        entry_container.pack(fill=tk.X, expand=True)

        self.text_input = tk.Entry(
            entry_container,
            font=("Segoe UI", 10),
            relief=tk.FLAT,
            highlightthickness=0,
            borderwidth=0,
            bg="#ffffff"
        )
        self.text_input.pack(fill=tk.X, expand=True, padx=8, pady=6)
        self.text_input.bind("<Return>", self.on_send_message)

        button_row = ttk.Frame(input_frame, style="Floating.TFrame")
        button_row.pack(fill=tk.X, pady=(6, 0))

        self.send_button = ttk.Button(
            button_row,
            text="Enviar",
            command=lambda: self.on_send_message(None),
            style="Primary.TButton"
        )
        self.send_button.pack(side=tk.LEFT, padx=(0, 6))

        self.voice_button = ttk.Button(
            button_row,
            text="Voz",
            command=self.on_voice_search,
            style="Accent.TButton"
        )
        self.voice_button.pack(side=tk.LEFT)

        self.stop_voice_button = ttk.Button(
            button_row,
            text="Parar voz",
            command=self.on_stop_voice_click,
            style="Secondary.TButton"
        )
        self.stop_voice_button.pack(side=tk.LEFT, padx=(6, 0))

        self.instructions_button = ttk.Button(
            button_row,
            text="Instrucciones",
            command=self._open_instructions_window,
            style="Secondary.TButton"
        )
        self.instructions_button.pack(side=tk.LEFT, padx=(6, 0))

        btn_frame = ttk.Frame(self.window, style="Floating.TFrame")
        btn_frame.pack(pady=(0, 10))

        self.clear_history_button = ttk.Button(
            btn_frame,
            text="Borrar historial",
            command=self._confirm_clear_history_reset,
            style="Secondary.TButton"
        )
        self.clear_history_button.pack(side=tk.LEFT, padx=5)

        self.close_button = ttk.Button(
            btn_frame,
            text="Cerrar",
            command=self.close_window,
            style="Secondary.TButton"
        )
        self.close_button.pack(side=tk.LEFT, padx=5)

        self._status_label = ttk.Label(
            chat_frame,
            text="",
            style="Muted.TLabel",
            wraplength=360,
            justify=tk.LEFT
        )
        self._status_label.pack(fill=tk.X, pady=(4, 0))

        try:
            self._visuals().draw_face(0)
        except Exception:
            pass

        try:
            self.apply_theme()
        except Exception as exc:
            print(f"No se pudo aplicar tema: {exc}")

        try:
            if not self._greeted_once and not history_loaded:
                self._append_conversation("Asistente", "Hola")
                from voice import hablar
                hablar("Hola")
                self._greeted_once = True
        except Exception:
            pass

        self.window.protocol("WM_DELETE_WINDOW", self.close_window)

    def on_send_message(self, event):
        if self._action_locked:
            self._append_conversation(
                "Asistente",
                "Termina la tarea en curso o cierra la ventana del editor antes de pedirme otra cosa."
            )
            return
        if self.text_input is None:
            return

        user_message = self.text_input.get().strip()
        if not user_message:
            return
        self.text_input.delete(0, tk.END)

        commands = self._commands()

        def process_message():
            response = commands.generate_response(user_message)

            def update_ui():
                self._append_conversation("Tú", user_message)
                self._append_conversation("Asistente", response)
                try:
                    from voice import hablar
                    hablar(response)
                except Exception as exc:
                    print(f"Error hablando respuesta: {exc}")

            if self.window is not None and self.window_created:
                try:
                    self.window.after(0, update_ui)
                except Exception:
                    pass

        threading.Thread(target=process_message, daemon=True).start()

    def on_voice_search(self):
        def worker():
            commands = self._commands()
            if self._action_locked:
                msg = "Estoy ocupada con otra tarea. Cierra el editor actual o pulsa Salir."
                if self.window is not None and self.window_created:
                    self.window.after(0, lambda: self._append_conversation("Asistente", msg))
                try:
                    from voice import hablar
                    hablar(msg)
                except Exception:
                    pass
                return
            try:
                from voice import escuchar, hablar
                texto = escuchar().strip()
            except Exception as exc:
                texto = ""
                print(f"Error reconocimiento de voz: {exc}")

            def update_ui():
                if not self.window_created:
                    return
                if not texto:
                    msg = "No se entendió. Di: 'buscar <término>'."
                    self._append_conversation("Asistente", msg)
                    try:
                        from voice import hablar
                        hablar(msg)
                    except Exception:
                        pass
                    return
                lower = texto.lower()
                if commands._is_email_command(lower):
                    opened = commands.open_mail_client()
                    msg = "Abriendo tu gestor de correo predeterminado." if opened else "No pude abrir tu gestor de correo."
                    self._append_conversation("Tú", texto)
                    self._append_conversation("Asistente", msg)
                    try:
                        from voice import hablar
                        hablar(msg)
                    except Exception:
                        pass
                    return
                if commands._is_document_command(lower):
                    self._append_conversation("Tú", texto)
                    started = self._start_blocking_action(
                        commands.open_text_editor_blocking,
                        "Editor abierto. Cierra la ventana para continuar.",
                        followup_success="Editor cerrado. Ya puedes continuar.",
                        followup_failure="No pude abrir el editor de texto."
                    )
                    msg = (
                        "Abriendo un documento en tu editor de texto predeterminado..."
                        if started
                        else "Termina la tarea que está en curso antes de pedirme otra cosa."
                    )
                    self._append_conversation("Asistente", msg)
                    try:
                        from voice import hablar
                        hablar(msg)
                    except Exception:
                        pass
                    return
                search_trigger = commands._extract_veno_search(texto)
                if search_trigger:
                    commands.open_web_search(search_trigger)
                    msg = f"Búsqueda abierta en el navegador para: '{search_trigger}'"
                    self._append_conversation("Tú", texto)
                    self._append_conversation("Asistente", msg)
                    try:
                        from voice import hablar
                        hablar(msg)
                    except Exception:
                        pass
                    return
                if lower.startswith("buscar ") or lower.startswith("busca ") or "buscar en la web" in lower:
                    msg = "Recuerda decir 'Neno, ...' antes de tus órdenes. Por ejemplo: 'Neno, busca clima en Madrid'."
                    self._append_conversation("Asistente", msg)
                    try:
                        from voice import hablar
                        hablar(msg)
                    except Exception:
                        pass
                    return
                response = commands.generate_response(texto)
                self._append_conversation("Tú", texto)
                self._append_conversation("Asistente", response)
                try:
                    from voice import hablar
                    hablar(response)
                except Exception:
                    pass

            if self.window is not None and self.window_created:
                self.window.after(0, update_ui)

        threading.Thread(target=worker, daemon=True).start()

    def on_stop_voice_click(self):
        was_speaking = getattr(self, "is_speaking", False)
        try:
            from voice import stop_speaking as stop_voice_output
            stop_voice_output()
        except Exception as exc:
            print(f"Error deteniendo la voz: {exc}")
        try:
            self._visuals().stop_speaking()
        except Exception:
            pass
        if was_speaking:
            self._append_conversation("Asistente", "He detenido la locución.")

    def _append_conversation(self, role: str, text: str):
        if not getattr(self, "_loading_history", False):
            try:
                append_message_to_history(role, text)
            except Exception as exc:
                print(f"No se pudo guardar la conversación: {exc}")

        widget = getattr(self, "conversation", None)
        if widget is None:
            return
        try:
            widget.config(state=tk.NORMAL)
            widget.insert(tk.END, f"{role}: {text}\n\n")
            widget.see(tk.END)
            widget.config(state=tk.DISABLED)
        except Exception:
            pass

    def _confirm_clear_history_reset(self):
        if not messagebox.askyesno(
            "Borrar historial",
            "¿Seguro que quieres borrar todo el historial de conversación? Esta acción no se puede deshacer.",
            icon=messagebox.WARNING
        ):
            return
        widget = getattr(self, "conversation", None)
        try:
            self._loading_history = True
            clear_conversation_history()
            if widget is not None:
                widget.config(state=tk.NORMAL)
                widget.delete("1.0", tk.END)
                widget.config(state=tk.DISABLED)
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo borrar el historial: {exc}")
        finally:
            self._loading_history = False
        self._greeted_once = False

    def _load_conversation_history(self) -> bool:
        widget = getattr(self, "conversation", None)
        if widget is None:
            return False
        try:
            history = load_conversation_history()
        except Exception as exc:
            print(f"No se pudo cargar la conversación previa: {exc}")
            return False
        if not history:
            return False

        self._loading_history = True
        try:
            widget.config(state=tk.NORMAL)
            for item in history:
                role = (item.get("role", "") if isinstance(item, dict) else "").strip()
                text = (item.get("text", "") if isinstance(item, dict) else "").strip()
                if not role or not text:
                    continue
                widget.insert(tk.END, f"{role}: {text}\n\n")
            widget.see(tk.END)
            widget.config(state=tk.DISABLED)
        except Exception as exc:
            print(f"No se pudo mostrar la conversación previa: {exc}")
            return False
        finally:
            self._loading_history = False
        return True

    def _lock_controls(self, status_text: str):
        self._action_locked = True
        try:
            if self.text_input is not None:
                self.text_input.config(state=tk.DISABLED)
        except Exception:
            pass
        for btn in (self.send_button, self.voice_button, self.instructions_button):
            if btn is not None:
                try:
                    btn.state(["disabled"])
                except Exception:
                    try:
                        btn.config(state=tk.DISABLED)
                    except Exception:
                        pass
        if self._status_label is not None:
            try:
                self._status_label.config(text=status_text)
            except Exception:
                pass

    def _unlock_controls(self):
        self._action_locked = False
        try:
            if self.text_input is not None:
                self.text_input.config(state=tk.NORMAL)
        except Exception:
            pass
        for btn in (self.send_button, self.voice_button, self.instructions_button):
            if btn is not None:
                try:
                    btn.state(["!disabled"])
                except Exception:
                    try:
                        btn.config(state=tk.NORMAL)
                    except Exception:
                        pass
        if self._status_label is not None:
            try:
                self._status_label.config(text="")
            except Exception:
                pass

    def _start_blocking_action(self, action_callable: Callable[[], bool], status_text: str,
                               followup_success: str | None = None,
                               followup_failure: str | None = None):
        if self._action_locked:
            return False
        self._lock_controls(status_text)

        def worker():
            success = False
            try:
                success = bool(action_callable())
            except Exception as exc:
                print(f"Error en acción bloqueante: {exc}")
                success = False
            finally:
                def finish():
                    self._unlock_controls()
                    msg = followup_success if success else followup_failure
                    if msg:
                        self._append_conversation("Asistente", msg)
                        try:
                            from voice import hablar
                            hablar(msg)
                        except Exception:
                            pass
                if self.window is not None and self.window_created:
                    try:
                        self.window.after(0, finish)
                    except Exception:
                        pass
                else:
                    finish()

        threading.Thread(target=worker, daemon=True).start()
        return True

    def apply_theme(self):
        try:
            from voice import get_theme
            theme = get_theme()
        except Exception:
            theme = "light"

        if theme == "dark":
            window_bg = "#121212"
            panel_bg = "#1a1a1a"
            text_fg = "#e0e0e0"
            canvas_bg = "#1e1e1e"
            entry_bg = "#252525"
            entry_fg = "#e0e0e0"
            scroll_bg = panel_bg
            scroll_fg = text_fg
            btn_green = "#2e7d32"
            btn_blue = "#1565C0"
            btn_fg = "#ffffff"
        else:
            window_bg = "#f5f5f5"
            panel_bg = "#ffffff"
            text_fg = "#111111"
            canvas_bg = "#f0f0f0"
            entry_bg = "#ffffff"
            entry_fg = "#111111"
            scroll_bg = panel_bg
            scroll_fg = text_fg
            btn_green = "#4CAF50"
            btn_blue = "#2196F3"
            btn_fg = "#ffffff"

        allow_clear = self._supports_true_transparency
        window_bg_value = self.transparent_color if allow_clear else window_bg
        canvas_bg_value = self.transparent_color if allow_clear else canvas_bg

        if self.window is not None:
            try:
                self.window.configure(bg=window_bg_value)
            except Exception:
                pass
            if self._instructions_window and self._instructions_window.winfo_exists():
                try:
                    self._instructions_window.configure(bg=window_bg_value)
                except Exception:
                    pass
                if self._instructions_text_widget is not None:
                    try:
                        self._instructions_text_widget.configure(bg=panel_bg, fg=text_fg, insertbackground=text_fg)
                    except Exception:
                        pass
        if self.canvas is not None:
            try:
                self.canvas.configure(bg=canvas_bg_value)
            except Exception:
                pass
        if hasattr(self, "_style"):
            try:
                self._style.configure("Floating.TFrame", background=window_bg_value)
            except Exception:
                pass
        if hasattr(self, 'conversation') and self.conversation is not None:
            try:
                self.conversation.configure(bg=scroll_bg, fg=scroll_fg, insertbackground=scroll_fg)
            except Exception:
                pass
        if hasattr(self, 'text_input') and self.text_input is not None:
            try:
                self.text_input.configure(bg=entry_bg, fg=entry_fg, insertbackground=entry_fg)
            except Exception:
                pass
        if self.window is not None:
            try:
                for child in self.window.winfo_children():
                    if isinstance(child, tk.Frame):
                        for button in child.winfo_children():
                            if isinstance(button, tk.Button):
                                txt = button.cget("text")
                                if txt == "Enviar":
                                    button.configure(bg=btn_green, fg=btn_fg, activebackground=btn_green)
                                elif txt in ("Voz", "Buscar por voz"):
                                    button.configure(bg=btn_blue, fg=btn_fg, activebackground=btn_blue)
            except Exception:
                pass

    def _open_instructions_window(self):
        if self._instructions_window and self._instructions_window.winfo_exists():
            try:
                self._instructions_window.lift()
                self._instructions_window.focus_force()
            except Exception:
                pass
            return

        parent = self.window or tk.Tk()
        self._instructions_window = tk.Toplevel(parent)
        self._instructions_window.title("Instrucciones del Avatar")
        try:
            base_width = self.window.winfo_width() if self.window else 420
            base_height = self.window.winfo_height() if self.window else 720
            base_x = self.window.winfo_rootx() if self.window else 100
            base_y = self.window.winfo_rooty() if self.window else 100
            geometry = f"{base_width}x{base_height}+{base_x + base_width + 20}+{base_y}"
            self._instructions_window.geometry(geometry)
        except Exception:
            self._instructions_window.geometry("420x720+520+80")

        container = ttk.Frame(self._instructions_window, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(container, text="¿Qué puedes pedirme?", font=("Segoe UI", 14, "bold"))
        title_label.pack(pady=(0, 10))

        text_widget = scrolledtext.ScrolledText(
            container,
            wrap=tk.WORD,
            height=24,
            font=("Segoe UI", 10),
            relief=tk.FLAT,
            borderwidth=0
        )
        text_widget.pack(fill=tk.BOTH, expand=True)
        text_widget.insert(tk.END, self._get_instruction_text())
        text_widget.config(state=tk.DISABLED)
        self._instructions_text_widget = text_widget

        close_btn = ttk.Button(
            container,
            text="Cerrar",
            command=self._close_instructions_window,
            style="Secondary.TButton"
        )
        close_btn.pack(pady=(10, 0))

        try:
            self._instructions_window.protocol("WM_DELETE_WINDOW", self._close_instructions_window)
        except Exception:
            pass
        self.apply_theme()

    def _close_instructions_window(self):
        if self._instructions_window and self._instructions_window.winfo_exists():
            try:
                self._instructions_window.destroy()
            except Exception:
                pass
        self._instructions_window = None
        self._instructions_text_widget = None

    def _get_instruction_text(self) -> str:
        return (
            "NOTA GENERAL\n"
            "• Empieza tus órdenes diciendo 'Neno,' para que el asistente las ejecute.\n\n"
            "MENSAJES GENERALES\n"
            "• Salúdame o pregúntame cómo estoy para una respuesta rápida.\n"
            "• Pídeme la hora diciendo '¿qué hora es?'.\n\n"
            "RECORDATORIOS\n"
            "• Usa frases como 'recordatorio recuérdame tomar agua a las 14:30'.\n"
            "• Incluye fecha: 'recordatorio 25/12/2025 09:00 comprar regalos'.\n"
            "• Añade 'cada día' o 'diariamente' para repetir automáticamente.\n\n"
            "BÚSQUEDA EN LA WEB\n"
            "• Escribe o di 'Neno, busca clima en Madrid'.\n"
            "• También puedes pedir 'Neno, buscar en la web cómo hacer paella'.\n"
            "• Recuerda que todas las búsquedas empiezan con 'Neno,'.\n\n"
            "CORREO\n"
            "• Di 'Neno, escribe un correo' para abrir tu gestor de correo.\n\n"
            "DOCUMENTOS\n"
            "• Usa 'Neno, escribe un documento' o 'Neno, escribe un texto' para abrir tu editor.\n\n"
            "TERMINAL O CONSOLA\n"
            "• Di 'Neno, abre la terminal' o 'Neno, abre la consola' para abrir la consola del sistema.\n\n"
            "MODO GEMINI\n"
            "• Actívalo con 'Neno, charlemos'.\n"
            "• Finaliza con 'Neno, termina'.\n\n"
            "BOTONES\n"
            "• 'Enviar' manda el texto escrito.\n"
            "• 'Voz' escucha un comando desde el micrófono.\n"
            "• 'Cerrar' oculta el avatar.\n"
            "• 'Instrucciones' abre esta ayuda.\n"
        )

    def show_window(self):
        if self.window is None:
            self.create_window()
        else:
            self.window.deiconify()
        try:
            self._visuals().draw_face(0)
        except Exception:
            pass

    def hide_window(self):
        if self.window is None or not self.window_created:
            return
        try:
            self.window.withdraw()
        except Exception:
            pass

    def close_window(self):
        try:
            from voice import stop_speaking as stop_voice_output
            stop_voice_output()
        except Exception:
            pass
        self._visuals().stop_speaking()
        if self.window is None or not self.window_created:
            return
        try:
            self.window.destroy()
        except Exception:
            pass
        self.window = None
        self.canvas = None
        self.conversation = None
        self.text_input = None
        self.send_button = None
        self.voice_button = None
        self.stop_voice_button = None
        self.instructions_button = None
        self.close_button = None
        self.clear_history_button = None
        self.window_created = False
        self._action_locked = False
        if self._instructions_window and self._instructions_window.winfo_exists():
            try:
                self._instructions_window.destroy()
            except Exception:
                pass
        self._instructions_window = None
        self._instructions_text_widget = None
        if self._status_label is not None:
            try:
                self._status_label.config(text="")
            except Exception:
                pass
        self._greeted_once = False
        if self._internal_editor_event is not None:
            self._internal_editor_event.set()
            self._internal_editor_event = None
        self.head_image = None
        self.head_photo = None
        self._head_drawn = False

    def _start_drag(self, event):
        if self.window is None or not self.window_created:
            return
        widget = event.widget
        allowed = (tk.Tk, tk.Toplevel, tk.Canvas, ttk.Frame)
        if not isinstance(widget, allowed):
            return
        try:
            offset_x = event.x_root - self.window.winfo_x()
            offset_y = event.y_root - self.window.winfo_y()
            self._drag_offset = (offset_x, offset_y)
            self._dragging = True
        except Exception:
            self._dragging = False

    def _perform_drag(self, event):
        if self.window is None or not self._dragging:
            return
        try:
            new_x = event.x_root - self._drag_offset[0]
            new_y = event.y_root - self._drag_offset[1]
            self.window.geometry(f"+{new_x}+{new_y}")
        except Exception:
            pass

    def _stop_drag(self, event):
        self._dragging = False
