# gui.py
import tkinter as tk
from tkinter import ttk, messagebox
import time, threading
from scheduler import load_reminders, add_reminder, save_reminders
from reminder_events import register_reminders_listener, notify_reminders_updated
from datetime import datetime
import voice
import speech_recognition as sr
import os
import signal
from typing import Any, Optional
from uuid import uuid4

_IMAGE_CACHE: list[Any] = []

# ===== Utilidades de Tema (claro/oscuro) =====
def _get_theme():
    try:
        return voice.get_theme()
    except Exception:
        return "light"

def _get_theme_palette(theme: str | None = None):
    t = theme or _get_theme()
    if t == "dark":
        return {
            "window_bg": "#121212",
            "panel_bg": "#1a1a1a",
            "text_fg": "#e0e0e0",
            "canvas_bg": "#1e1e1e",
            "entry_bg": "#252525",
            "entry_fg": "#e0e0e0",
            "muted_fg": "#aaaaaa",
            "accent_green": "#2e7d32",
            "accent_blue": "#1565C0",
            "danger_red": "#F44336",
            "warn_yellow": "#FFC107",
        }
    return {
        "window_bg": "#f5f5f5",
        "panel_bg": "#ffffff",
        "text_fg": "#111111",
        "canvas_bg": "#f0f0f0",
        "entry_bg": "#ffffff",
        "entry_fg": "#111111",
        "muted_fg": "#6b6b6b",
        "accent_green": "#4CAF50",
        "accent_blue": "#2196F3",
        "danger_red": "#F44336",
        "warn_yellow": "#FFC107",
    }

def apply_theme_to_window(window: tk.Misc, theme: str | None = None):
    """Aplica el tema de colores a una ventana y sus hijos."""
    p = _get_theme_palette(theme)

    def _apply(widget: tk.Misc):
        try:
            if isinstance(widget, (tk.Tk, tk.Toplevel)):
                widget.configure(bg=p["window_bg"])
            elif isinstance(widget, (tk.Frame, tk.LabelFrame)):
                widget.configure(bg=p["panel_bg"])
            elif isinstance(widget, tk.Label):
                # Mantener colores de botonería especial fuera
                widget.configure(bg=p["panel_bg"], fg=p["text_fg"])
            elif isinstance(widget, (tk.Entry,)):
                widget.configure(bg=p["entry_bg"], fg=p["entry_fg"], insertbackground=p["entry_fg"])
            elif isinstance(widget, (tk.Text,)):
                widget.configure(bg=p["panel_bg"], fg=p["text_fg"], insertbackground=p["text_fg"])
            elif isinstance(widget, tk.Canvas):
                widget.configure(bg=p["canvas_bg"])
            elif isinstance(widget, tk.Listbox):
                widget.configure(bg=p["panel_bg"], fg=p["text_fg"])
            elif isinstance(widget, (tk.Radiobutton, tk.Checkbutton)):
                widget.configure(bg=p["panel_bg"], fg=p["text_fg"], selectcolor=p["panel_bg"])
            elif isinstance(widget, tk.Button):
                # Ajuste de botones de acción por texto/colores conocidos
                txt = widget.cget("text")
                bg = widget.cget("bg")
                # Mapear acciones comunes a acentos
                green_actions = {"Enviar", "Buscar", "Añadir Recordatorio", "💾 Guardar"}
                blue_actions = {"Voz", "Buscar por voz", "🔊 Probar Voz"}
                cancel_actions = {"Cancelar", "Cerrar", "Minimizar"}

                if txt in green_actions or bg in ("#4CAF50", "#2e7d32"):
                    widget.configure(bg=p["accent_green"], fg="#ffffff", activebackground=p["accent_green"], activeforeground="#ffffff")
                elif txt in blue_actions or bg in ("#2196F3", "#1565C0"):
                    widget.configure(bg=p["accent_blue"], fg="#ffffff", activebackground=p["accent_blue"], activeforeground="#ffffff")
                elif txt in cancel_actions:
                    widget.configure(bg=p["panel_bg"], fg=p["text_fg"], activebackground=p["panel_bg"], activeforeground=p["text_fg"])
                else:
                    # Botón neutro: armonizar con panel si es default
                    if bg in ("SystemButtonFace", "#f0f0f0", "#FFFFFF", "white"):
                        widget.configure(bg=p["panel_bg"], fg=p["text_fg"], activebackground=p["panel_bg"], activeforeground=p["text_fg"])
        except Exception:
            pass
        # Recursivo
        try:
            for child in widget.winfo_children():
                _apply(child)
        except Exception:
            pass

    _apply(window)

def _format_rem(rem):
    return f"{rem.get('when')} — {rem.get('text')} {'(repite diariamente)' if rem.get('repeat')=='daily' else ''}"

def launch_gui():
    root = tk.Tk()
    root.title("Asistente de Escritorio - Recordatorios")
    root.geometry("700x500")
    # Fuentes por defecto más modernas
    try:
        import tkinter.font as tkfont
        tkfont.nametofont("TkDefaultFont").configure(family="Segoe UI", size=10)
        tkfont.nametofont("TkTextFont").configure(family="Segoe UI", size=10)
        tkfont.nametofont("TkHeadingFont").configure(family="Segoe UI", size=11, weight="bold")
        tkfont.nametofont("TkMenuFont").configure(family="Segoe UI", size=10)
    except Exception:
        pass
    
    # Variable global para el avatar
    avatar_shown = [False]  # Usar lista para modificar desde funciones anidadas
    
    reminder_listener_remove = None

    # Menú superior
    menubar = tk.Menu(root)
    root.config(menu=menubar)
    
    # Menú Archivo
    file_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Archivo", menu=file_menu)
    
    def exit_program():
        nonlocal reminder_listener_remove
        # Detener VU meter y cancelar callbacks pendientes con seguridad
        try:
            meter_running[0] = False
        except Exception:
            pass
        try:
            if after_vu_id[0]:
                root.after_cancel(after_vu_id[0])
                after_vu_id[0] = None
        except Exception:
            pass
        try:
            root.quit()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass
        if reminder_listener_remove:
            try:
                reminder_listener_remove()
            except Exception:
                pass
            reminder_listener_remove = None
        # Terminar proceso sin señales para evitar Tcl_AsyncDelete
        os._exit(0)
    
    file_menu.add_command(label="Salir", command=exit_program)

    root.protocol("WM_DELETE_WINDOW", exit_program)
    
    # Menú Preferencias
    preferences_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Preferencias", menu=preferences_menu)
    
    def toggle_avatar():
        if avatar_shown[0]:
            # Ocultar avatar
            try:
                from avatar import get_avatar
                get_avatar().hide_window()
                avatar_shown[0] = False
            except:
                pass
        else:
            # Mostrar avatar
            show_avatar_window()
            avatar_shown[0] = True
    
    preferences_menu.add_command(label="Mostrar/Ocultar Avatar", command=toggle_avatar)
    # Etiqueta micrófono (se actualiza después de abrir config voz)
    mic_label = ttk.Label(root, text="Micrófono: (detectando)")
    mic_label.pack(pady=(4,0))

    # VU meter micrófono
    vu_frame = ttk.Frame(root)
    vu_frame.pack(pady=2)
    ttk.Label(vu_frame, text="Nivel mic:").pack(side=tk.LEFT)
    vu_canvas = tk.Canvas(vu_frame, width=120, height=12, bg="#222", highlightthickness=0)
    vu_canvas.pack(side=tk.LEFT, padx=5)
    vu_bar = vu_canvas.create_rectangle(0, 0, 0, 12, fill="#4CAF50")
    vu_level_var = {"rms": 0.0}
    meter_running = [True]
    meter_thread: dict[str, Optional[threading.Thread]] = {"t": None}
    after_vu_id: list[Optional[str]] = [None]

    def start_meter_thread():
        try:
            import pyaudio, math, struct, speech_recognition as sr
            pa = pyaudio.PyAudio()
            device_index = voice.get_microphone_device() if hasattr(voice, 'get_microphone_device') else None
            # Elegir índice válido o None
            if device_index is not None and (device_index < 0 or device_index >= pa.get_device_count()):
                device_index = None
            stream = pa.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True,
                             frames_per_buffer=1024, input_device_index=device_index)
        except Exception as e:
            print(f"No se pudo iniciar VU meter: {e}")
            return

        def run():
            while meter_running[0]:
                try:
                    data = stream.read(1024, exception_on_overflow=False)
                    # Calcular RMS
                    if data:
                        count = len(data) // 2
                        fmt = f"{count}h"
                        samples = struct.unpack(fmt, data)
                        sum_squares = 0.0
                        for s in samples:
                            sum_squares += (s/32768.0) * (s/32768.0)
                        rms = math.sqrt(sum_squares / count)
                        vu_level_var["rms"] = rms
                except Exception:
                    pass
                time.sleep(0.1)
            try:
                stream.stop_stream(); stream.close(); pa.terminate()
            except Exception:
                pass
        t = threading.Thread(target=run, daemon=True)
        meter_thread["t"] = t
        t.start()

    def update_vu_canvas():
        # Evitar ejecutar si la ventana ya no existe o se está cerrando
        if not meter_running[0] or not root.winfo_exists():
            return
        try:
            # Convertir RMS (0-1) a pixel ancho (0-120)
            rms = vu_level_var.get("rms", 0.0)
            width = int(max(0, min(1.0, rms * 3.0)) * 120)  # amplificar para visibilidad
            vu_canvas.coords(vu_bar, 0, 0, width, 12)
            color = "#4CAF50" if width < 60 else ("#FFC107" if width < 90 else "#F44336")
            vu_canvas.itemconfig(vu_bar, fill=color)
        except Exception:
            return
        if meter_running[0] and root.winfo_exists():
            after_vu_id[0] = root.after(200, update_vu_canvas)

    start_meter_thread()
    update_vu_canvas()

    def update_mic_label():
        try:
            import speech_recognition as sr
            current_index = voice.get_microphone_device() if hasattr(voice, 'get_microphone_device') else None
            names = []
            try:
                names = sr.Microphone.list_microphone_names()
            except Exception:
                names = []
            if current_index is None:
                mic_label.config(text="Micrófono: Automático")
            else:
                if 0 <= current_index < len(names):
                    mic_label.config(text=f"Micrófono: {names[current_index]}")
                else:
                    mic_label.config(text=f"Micrófono: Índice {current_index}")
        except Exception as e:
            mic_label.config(text=f"Micrófono: error ({e})")

    update_mic_label()

    preferences_menu.add_command(label="Configurar Voz", command=lambda: voice_config_window(on_close=update_mic_label))
    preferences_menu.add_command(label="Configurar Gemini API", command=lambda: gemini_config_window())

    # Submenú Micrófono rápido
    mic_menu = tk.Menu(preferences_menu, tearoff=0)
    preferences_menu.add_cascade(label="Micrófono", menu=mic_menu)
    try:
        import speech_recognition as sr
        mic_names = sr.Microphone.list_microphone_names()
    except Exception:
        mic_names = []
    mic_choice_var = tk.IntVar(value=-1 if voice.get_microphone_device() is None else voice.get_microphone_device())

    def choose_mic(idx):
        try:
            if idx < 0:
                voice.set_microphone_device(None)
            else:
                voice.set_microphone_device(idx)
            update_mic_label()
        except Exception as e:
            messagebox.showerror("Micrófono", f"No se pudo establecer micrófono: {e}")

    mic_menu.add_radiobutton(label="Automático", variable=mic_choice_var, value=-1, command=lambda: choose_mic(-1))
    for i, name in enumerate(mic_names):
        mic_menu.add_radiobutton(label=name[:60], variable=mic_choice_var, value=i, command=lambda ii=i: choose_mic(ii))
    
    # Submenú Motor de Búsqueda
    search_engine_menu = tk.Menu(preferences_menu, tearoff=0)
    preferences_menu.add_cascade(label="Motor de Búsqueda", menu=search_engine_menu)
    search_engine_var = tk.StringVar(value=voice._load_settings().get("search_engine", "google"))

    def set_engine(value):
        try:
            voice.set_search_engine(value)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar motor: {e}")
        else:
            messagebox.showinfo("Motor de búsqueda", f"Motor establecido: {value}")

    search_engine_menu.add_radiobutton(label="Google", variable=search_engine_var, value="google", command=lambda: set_engine("google"))
    search_engine_menu.add_radiobutton(label="DuckDuckGo", variable=search_engine_var, value="duckduckgo", command=lambda: set_engine("duckduckgo"))

    # Submenú Tema (Claro/Oscuro)
    theme_menu = tk.Menu(preferences_menu, tearoff=0)
    preferences_menu.add_cascade(label="Tema", menu=theme_menu)
    theme_var = tk.StringVar(value=getattr(voice, 'get_theme', lambda: 'light')())

    def apply_theme_all():
        # Aplicar al root y a ventanas hijas conocidas
        try:
            apply_theme_to_window(root)
        except Exception as e:
            print(f"No se pudo aplicar tema a la ventana principal: {e}")
        # Estilos ttk y colores de menú
        try:
            p = _get_theme_palette()
            style = ttk.Style()
            # Forzar tema 'clam' para mejor control de colores
            try:
                style.theme_use('clam')
            except Exception:
                pass
            # Base
            style.configure('TFrame', background=p['panel_bg'])
            style.configure('TLabelframe', background=p['panel_bg'], foreground=p['text_fg'])
            style.configure('TLabelframe.Label', background=p['panel_bg'], foreground=p['text_fg'])
            style.configure('TLabel', background=p['panel_bg'], foreground=p['text_fg'])
            style.configure('TButton', background=p['panel_bg'], foreground=p['text_fg'])
            style.map('TButton', background=[('active', p['panel_bg'])], foreground=[('active', p['text_fg'])])
            style.configure('TEntry', fieldbackground=p['entry_bg'], foreground=p['entry_fg'])
            style.map('TEntry', fieldbackground=[('focus', p['entry_bg'])])
            style.configure('Treeview', background=p['panel_bg'], fieldbackground=p['panel_bg'], foreground=p['text_fg'])
            style.map('Treeview', background=[('selected', p['canvas_bg'])], foreground=[('selected', p['text_fg'])])
            # Especiales
            style.configure('Title.TLabel', font=('Segoe UI', 16, 'bold'), background=p['panel_bg'], foreground=p['text_fg'])
            style.configure('Muted.TLabel', background=p['panel_bg'], foreground=p['muted_fg'])
            style.configure('Primary.TButton', background=p['accent_green'], foreground='#ffffff')
            style.map('Primary.TButton', background=[('active', p['accent_green'])], foreground=[('active', '#ffffff')])
            style.configure('Accent.TButton', background=p['accent_blue'], foreground='#ffffff')
            style.map('Accent.TButton', background=[('active', p['accent_blue'])], foreground=[('active', '#ffffff')])
            style.configure('Secondary.TButton', background=p['panel_bg'], foreground=p['text_fg'])
            style.map('Secondary.TButton', background=[('active', p['panel_bg'])], foreground=[('active', p['text_fg'])])
            # Colores de menús (tk)
            try:
                root.option_add('*Menu.background', p['panel_bg'])
                root.option_add('*Menu.foreground', p['text_fg'])
                root.option_add('*Menu.activeBackground', p['canvas_bg'])
                root.option_add('*Menu.activeForeground', p['text_fg'])
            except Exception:
                pass
        except Exception:
            pass
        # Intentar aplicar a Toplevels abiertos
        try:
            for w in root.winfo_children():
                if isinstance(w, tk.Toplevel):
                    try:
                        apply_theme_to_window(w)
                    except Exception:
                        pass
        except Exception:
            pass
        # Ajustes específicos (VU meter, etiquetas)
        try:
            p = _get_theme_palette()
            vu_canvas.configure(bg=p["canvas_bg"])
            # mic_label es ttk.Label -> usar estilo 'Muted.TLabel'
            mic_label.configure(style='Muted.TLabel')
        except Exception:
            pass
        # Aplicar al avatar si está abierto
        try:
            from avatar import get_avatar
            av = get_avatar()
            if av.is_visible():
                av.apply_theme()
        except Exception as e:
            print(f"No se pudo aplicar tema al avatar: {e}")

    def set_theme_cmd(value):
        try:
            voice.set_theme(value)
            apply_theme_all()
            messagebox.showinfo("Tema", f"Tema aplicado: {value}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo aplicar tema: {e}")

    theme_menu.add_radiobutton(label="Claro", variable=theme_var, value="light", command=lambda: set_theme_cmd("light"))
    theme_menu.add_radiobutton(label="Oscuro", variable=theme_var, value="dark", command=lambda: set_theme_cmd("dark"))

    # Menú Tema rápido (en la barra principal)
    theme_quick_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Tema", menu=theme_quick_menu)
    theme_quick_menu.add_radiobutton(label="Claro", variable=theme_var, value="light", command=lambda: set_theme_cmd("light"))
    theme_quick_menu.add_radiobutton(label="Oscuro", variable=theme_var, value="dark", command=lambda: set_theme_cmd("dark"))

    # Menú Buscar
    search_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Buscar", menu=search_menu)

    def open_search_dialog():
        dlg = tk.Toplevel(root)
        dlg.title("Buscar en la Web")
        dlg.geometry("400x140")
        ttk.Label(dlg, text="Término a buscar:").pack(pady=6, anchor="w", padx=10)
        entry = ttk.Entry(dlg)
        entry.pack(fill=tk.X, padx=10)
        entry.focus_set()

        def do_search():
            q = entry.get().strip()
            if not q:
                messagebox.showwarning("Advertencia", "Introduce un término de búsqueda.")
                return
            try:
                from urllib.parse import quote_plus
                import webbrowser
                engine = voice.get_search_engine() if hasattr(voice, 'get_search_engine') else voice._load_settings().get('search_engine', 'google')
                qq = quote_plus(q)
                url = f"https://duckduckgo.com/?q={qq}" if engine == 'duckduckgo' else f"https://www.google.com/search?q={qq}"
                webbrowser.open_new_tab(url)
                messagebox.showinfo("Búsqueda", f"Abriendo '{q}' en {engine}.")
                dlg.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo abrir búsqueda: {e}")

        def do_voice():
            try:
                from voice import escuchar
                texto = escuchar().strip()
            except Exception as e:
                messagebox.showerror("Error", f"Error reconocimiento de voz: {e}")
                return
            if texto.lower().startswith("buscar "):
                entry.delete(0, tk.END)
                entry.insert(0, texto.split(" ", 1)[1])
                do_search()
            else:
                messagebox.showinfo("Info", "Debe empezar diciendo 'buscar ...'")

        btn_frame = ttk.Frame(dlg)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Buscar", command=do_search, style="Primary.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Voz", command=do_voice, style="Accent.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancelar", command=dlg.destroy, style="Secondary.TButton").pack(side=tk.LEFT, padx=5)
        try:
            apply_theme_to_window(dlg)
        except Exception:
            pass

    search_menu.add_command(label="Buscar en la Web...", command=open_search_dialog)
    
    # Menú Ayuda
    help_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Ayuda", menu=help_menu)
    help_menu.add_command(label="Acerca de", command=lambda: about_window())
    
    # Título
    title_label = ttk.Label(root, text="Asistente de Escritorio - Recordatorios", style="Title.TLabel")
    title_label.pack(pady=8)
    
    # Lista de recordatorios
    list_frame = ttk.Frame(root, padding=(12,8))
    list_frame.pack(pady=4, padx=12, fill=tk.BOTH, expand=True)

    columns = ("when", "text", "repeat")
    tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=10)
    tree.heading("when", text="Fecha/Hora")
    tree.heading("text", text="Mensaje")
    tree.heading("repeat", text="Repite")
    tree.column("when", width=160, anchor="w")
    tree.column("text", width=380, anchor="w")
    tree.column("repeat", width=90, anchor="center")
    vsb = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    vsb.pack(side=tk.RIGHT, fill=tk.Y)

    def _load_reminders_with_ids():
        reminders = load_reminders()
        changed = False
        for rem in reminders:
            if not rem.get("id"):
                rem["id"] = str(uuid4())
                changed = True
        if changed:
            save_reminders(reminders)
            try:
                notify_reminders_updated()
            except Exception:
                pass
        return reminders

    def _validate_when_str(when: str) -> bool:
        try:
            if "/" in when and " " in when:
                datetime.strptime(when, "%d/%m/%Y %H:%M")
                return True
            if ":" in when and "/" not in when:
                hour, minute = map(int, when.split(":"))
                return 0 <= hour <= 23 and 0 <= minute <= 59
        except Exception:
            return False
        return False

    def _get_selected_reminder():
        selection = tree.selection()
        if not selection:
            return None
        reminder_id = selection[0]
        for rem in _load_reminders_with_ids():
            if rem.get("id") == reminder_id:
                return rem
        return None
    
    # Actualizar lista inicial
    def update_list():
        if not tree.winfo_exists():
            return
        for i in tree.get_children():
            tree.delete(i)
        for rem in _load_reminders_with_ids():
            when = rem.get('when')
            text = rem.get('text')
            rep = 'Diario' if rem.get('repeat')=='daily' else '-'
            tree.insert('', tk.END, iid=rem.get('id'), values=(when, text, rep))
    
    update_list()

    def _schedule_remote_update():
        if not root.winfo_exists():
            return
        try:
            root.after(0, update_list)
        except Exception:
            pass

    reminder_listener_remove = register_reminders_listener(_schedule_remote_update)
    
    # Formulario
    form_frame = ttk.Frame(root, padding=(12,0))
    form_frame.pack(pady=6, padx=12, fill=tk.X)

    ttk.Label(form_frame, text="Mensaje:").grid(row=0, column=0, sticky="w", pady=4)
    text_entry = ttk.Entry(form_frame, width=50)
    text_entry.grid(row=0, column=1, pady=5, padx=10)

    ttk.Label(form_frame, text="Fecha/Hora (DD/MM/YYYY HH:MM o solo HH:MM):").grid(row=1, column=0, sticky="w", pady=4)
    when_entry = ttk.Entry(form_frame, width=30)
    when_entry.grid(row=1, column=1, pady=5, padx=10, sticky="w")
    
    # Ejemplo de formato
    ttk.Label(form_frame, text="Ejemplo: 25/12/2025 14:30 o 14:30").grid(row=2, column=1, sticky="w", padx=10)

    daily_var = tk.BooleanVar()
    daily_check = ttk.Checkbutton(form_frame, text="Repetir diariamente", variable=daily_var)
    daily_check.grid(row=3, column=1, sticky="w", pady=5, padx=10)
    
    # Botones
    def on_add():
        texto = text_entry.get().strip()
        when = when_entry.get().strip()
        repeat = "daily" if daily_var.get() else None
        
        if not texto or not when:
            messagebox.showwarning("Advertencia", "Rellena mensaje y hora.")
            return
        
        # Validación básica del formato
        valid = False
        try:
            if "/" in when and " " in when:
                # Formato completo DD/MM/YYYY HH:MM
                datetime.strptime(when, "%d/%m/%Y %H:%M")
                valid = True
            elif ":" in when and "/" not in when:
                # Solo hora HH:MM
                hour, minute = map(int, when.split(":"))
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    valid = True
        except Exception as e:
            messagebox.showerror("Error", f"Formato de fecha/hora inválido.\nUsa: DD/MM/YYYY HH:MM o HH:MM\nEjemplo: 25/12/2025 14:30 o 14:30")
            return
        
        if not valid:
            messagebox.showerror("Error", "Formato de fecha/hora inválido.\nUsa: DD/MM/YYYY HH:MM o HH:MM")
            return
        
        add_reminder(texto, when, repeat)
        messagebox.showinfo("Éxito", "Recordatorio añadido.")
        update_list()
        text_entry.delete(0, tk.END)
        when_entry.delete(0, tk.END)
        daily_var.set(False)
    
    button_frame = ttk.Frame(root)
    button_frame.pack(pady=8)

    add_button = ttk.Button(button_frame, text="Añadir Recordatorio", command=on_add, style="Primary.TButton")
    add_button.pack(side=tk.LEFT, padx=8)

    update_button = ttk.Button(button_frame, text="🔄 Actualizar Lista", command=update_list, style="Secondary.TButton")
    update_button.pack(side=tk.LEFT, padx=8)

    def on_edit():
        rem = _get_selected_reminder()
        if rem is None:
            messagebox.showinfo("Editar", "Selecciona un recordatorio de la lista.")
            return

        dlg = tk.Toplevel(root)
        dlg.title("Editar Recordatorio")
        dlg.geometry("420x260")
        dlg.transient(root)
        dlg.grab_set()

        ttk.Label(dlg, text="Mensaje:").pack(anchor="w", padx=10, pady=(10, 2))
        msg_entry = ttk.Entry(dlg)
        msg_entry.pack(fill=tk.X, padx=10)
        msg_entry.insert(0, rem.get("text", ""))

        ttk.Label(dlg, text="Fecha/Hora (DD/MM/YYYY HH:MM o HH:MM):").pack(anchor="w", padx=10, pady=(10, 2))
        when_entry = ttk.Entry(dlg)
        when_entry.pack(fill=tk.X, padx=10)
        when_entry.insert(0, rem.get("when", ""))

        repeat_var = tk.BooleanVar(value=rem.get("repeat") == "daily")
        ttk.Checkbutton(dlg, text="Repetir diariamente", variable=repeat_var).pack(anchor="w", padx=10, pady=8)

        def save_changes():
            new_text = msg_entry.get().strip()
            new_when = when_entry.get().strip()
            new_repeat = "daily" if repeat_var.get() else None
            if not new_text or not new_when:
                messagebox.showwarning("Advertencia", "Mensaje y fecha/hora son obligatorios.")
                return
            if not _validate_when_str(new_when):
                messagebox.showerror(
                    "Error",
                    "Formato de fecha/hora inválido. Usa DD/MM/YYYY HH:MM o HH:MM"
                )
                return
            reminders = _load_reminders_with_ids()
            updated = False
            for stored in reminders:
                if stored.get("id") == rem.get("id"):
                    has_changed = (
                        stored.get("text") != new_text or
                        stored.get("when") != new_when or
                        stored.get("repeat") != new_repeat
                    )
                    stored["text"] = new_text
                    stored["when"] = new_when
                    stored["repeat"] = new_repeat
                    if has_changed:
                        stored["notified"] = False
                    updated = True
                    break
            if updated:
                save_reminders(reminders)
                try:
                    notify_reminders_updated()
                except Exception:
                    pass
                update_list()
            dlg.destroy()

        ttk.Button(dlg, text="Guardar", command=save_changes, style="Primary.TButton").pack(side=tk.LEFT, padx=10, pady=15)
        ttk.Button(dlg, text="Cancelar", command=dlg.destroy, style="Secondary.TButton").pack(side=tk.LEFT, padx=10, pady=15)
        try:
            apply_theme_to_window(dlg)
        except Exception:
            pass

    def on_delete():
        rem = _get_selected_reminder()
        if rem is None:
            messagebox.showinfo("Eliminar", "Selecciona un recordatorio de la lista.")
            return
        if not messagebox.askyesno("Confirmar", "¿Eliminar el recordatorio seleccionado?"):
            return
        reminders = _load_reminders_with_ids()
        new_list = [r for r in reminders if r.get("id") != rem.get("id")]
        if len(new_list) == len(reminders):
            messagebox.showerror("Error", "No se pudo eliminar el recordatorio seleccionado.")
            return
        save_reminders(new_list)
        try:
            notify_reminders_updated()
        except Exception:
            pass
        update_list()

    edit_button = ttk.Button(button_frame, text="✏️ Editar", command=on_edit, style="Secondary.TButton")
    edit_button.pack(side=tk.LEFT, padx=8)

    delete_button = ttk.Button(button_frame, text="🗑 Eliminar", command=on_delete, style="Secondary.TButton")
    delete_button.pack(side=tk.LEFT, padx=8)

    # Aplicar tema inicial a la ventana principal y elementos
    try:
        apply_theme_all()
    except Exception:
        pass

    root.mainloop()
    # Al salir detener meter
    meter_running[0] = False
    if meter_thread["t"] and meter_thread["t"].is_alive():
        meter_thread["t"].join(timeout=1)

def voice_config_window(on_close=None):
    """Ventana para configurar el motor de voz con scroll vertical general."""
    window = tk.Toplevel()
    window.title("Configuración de Voz")
    window.geometry("600x520")

    # Contenedor con canvas + scrollbar para permitir scroll global
    try:
        p = _get_theme_palette()
        bg_color = p["panel_bg"]
    except Exception:
        bg_color = "#ffffff"

    container = ttk.Frame(window)
    container.pack(fill=tk.BOTH, expand=True)
    canvas = tk.Canvas(container, highlightthickness=0, bg=bg_color)
    vsb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vsb.set)
    vsb.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    content = ttk.Frame(canvas)
    content_id = canvas.create_window((0, 0), window=content, anchor="nw")

    def _on_content_configure(event):
        try:
            canvas.configure(scrollregion=canvas.bbox("all"))
        except Exception:
            pass
    content.bind("<Configure>", _on_content_configure)

    def _on_canvas_configure(event):
        try:
            canvas.itemconfigure(content_id, width=event.width)
        except Exception:
            pass
    canvas.bind("<Configure>", _on_canvas_configure)

    ttk.Label(content, text="Configuración de Voz", style="Title.TLabel").pack(pady=10)
    
    # Motor de voz
    motor_frame = ttk.LabelFrame(content, text="Motor de Voz")
    motor_frame.pack(pady=10, padx=20, fill=tk.X)
    
    engine_var = tk.StringVar(value=voice._load_settings().get("voice_engine", "gtts"))
    
    ttk.Radiobutton(
        motor_frame, 
        text="Google TTS (gTTS) - Voz natural (requiere internet)", 
        variable=engine_var, 
        value="gtts",
    ).pack(anchor="w", pady=5)
    
    ttk.Radiobutton(
        motor_frame, 
        text="pyttsx3 - Voz offline (robótica)", 
        variable=engine_var, 
        value="pyttsx3",
    ).pack(anchor="w", pady=5)
    
    # Género de voz
    gender_frame = ttk.LabelFrame(content, text="Género de Voz")
    gender_frame.pack(pady=10, padx=20, fill=tk.X)
    
    gender_var = tk.StringVar(value=voice._load_settings().get("voice_gender", "female"))
    
    ttk.Radiobutton(
        gender_frame, 
        text="👩 Voz Femenina", 
        variable=gender_var, 
        value="female"
    ).pack(anchor="w", pady=5)
    
    ttk.Radiobutton(
        gender_frame, 
        text="👨 Voz Masculina", 
        variable=gender_var, 
        value="male"
    ).pack(anchor="w", pady=5)
    
    # Lista de voces pyttsx3
    voices_frame = ttk.LabelFrame(content, text="Voces disponibles (pyttsx3)")
    voices_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
    # Contenedor con scrollbar vertical para voces
    voices_list_container = ttk.Frame(voices_frame)
    voices_list_container.pack(fill=tk.BOTH, expand=True)
    voices_vsb = ttk.Scrollbar(voices_list_container, orient="vertical")
    voices_listbox = tk.Listbox(voices_list_container, height=8, yscrollcommand=voices_vsb.set)
    voices_vsb.config(command=voices_listbox.yview)
    voices_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    voices_vsb.pack(side=tk.RIGHT, fill=tk.Y)
    
    available_voices = voice.get_available_voices()
    current_voice_id = voice._load_settings().get("voice_id")
    
    for idx, v in enumerate(available_voices):
        display_text = f"{v['name']} ({v['id'][:50]}...)"
        voices_listbox.insert(tk.END, display_text)
        if v['id'] == current_voice_id:
            voices_listbox.selection_set(idx)

    # Micrófono de entrada
    mic_frame = ttk.LabelFrame(content, text="Dispositivo de Micrófono")
    mic_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
    ttk.Label(mic_frame, text="Selecciona el micrófono (o deja Automático)").pack(anchor="w", pady=2)

    mic_devices = []
    try:
        mic_devices = sr.Microphone.list_microphone_names()
    except Exception as e:
        mic_devices = []
        tk.Label(mic_frame, text=f"No se pudieron listar micrófonos: {e}", fg="red", font=("Arial", 8)).pack(anchor="w")

    # Contenedor con scrollbar vertical para micrófonos
    mic_list_container = ttk.Frame(mic_frame)
    mic_list_container.pack(fill=tk.BOTH, expand=True)
    mic_vsb = ttk.Scrollbar(mic_list_container, orient="vertical")
    mic_listbox = tk.Listbox(mic_list_container, height=10, yscrollcommand=mic_vsb.set)
    mic_vsb.config(command=mic_listbox.yview)
    mic_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    mic_vsb.pack(side=tk.RIGHT, fill=tk.Y)
    ttk.Label(mic_frame, text="Doble clic en un micrófono para probar nivel de ruido.").pack(anchor="w")
    # Botón adicional para probar el micrófono seleccionado
    mic_btn_frame = ttk.Frame(mic_frame)
    mic_btn_frame.pack(anchor="w", pady=4)
    test_btn = ttk.Button(mic_btn_frame, text="Probar micrófono", style="Accent.TButton")
    test_btn.pack(side=tk.LEFT)

    current_mic_index = voice.get_microphone_device()
    mic_listbox.insert(tk.END, "(Automático)")
    for i, name in enumerate(mic_devices):
        mic_listbox.insert(tk.END, f"[{i}] {name}")
        if current_mic_index is not None and i == current_mic_index:
            mic_listbox.selection_set(i+1)

    def test_mic(event=None):
        # Determinar micrófono seleccionado
        sel = mic_listbox.curselection()
        idx = None
        if sel:
            if sel[0] == 0:
                idx = None
            else:
                idx = sel[0]-1

        # Ventana de progreso no bloqueante
        progress_win = tk.Toplevel(window)
        progress_win.title("Midiendo ruido...")
        progress_win.transient(window)
        progress_win.grab_set()
        progress_win.resizable(False, False)
        ttk.Label(progress_win, text="Midiendo ruido ambiental (0,6 s)...").pack(padx=16, pady=(12, 6))
        pb = ttk.Progressbar(progress_win, mode="indeterminate", length=220)
        pb.pack(padx=16, pady=(0, 12))
        pb.start(10)
        try:
            # Centrar sobre la ventana principal
            window.update_idletasks()
            x = window.winfo_rootx() + (window.winfo_width()//2 - progress_win.winfo_reqwidth()//2)
            y = window.winfo_rooty() + (window.winfo_height()//2 - progress_win.winfo_reqheight()//2)
            progress_win.geometry(f"+{x}+{y}")
        except Exception:
            pass

        def worker():
            try:
                import pyaudio, struct, math
                pa = pyaudio.PyAudio()
                stream = pa.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True,
                                 frames_per_buffer=1024, input_device_index=idx)
                frames = 0
                sum_squares = 0.0
                target_frames = 10
                while frames < target_frames:
                    data = stream.read(1024, exception_on_overflow=False)
                    if data:
                        count = len(data) // 2
                        samples = struct.unpack(f"{count}h", data)
                        for s in samples:
                            v = (s/32768.0)
                            sum_squares += v*v
                        frames += 1
                try:
                    stream.stop_stream(); stream.close(); pa.terminate()
                except Exception:
                    pass
                total_samples = target_frames * 1024
                rms = (sum_squares / max(1, total_samples)) ** 0.5
                import math as _math
                dbfs = -90.0 if rms <= 1e-6 else 20.0 * _math.log10(rms)
                calidad = "bajo" if dbfs < -45 else ("medio" if dbfs < -30 else "alto")
                mensaje = (
                    f"Micrófono {'automático' if idx is None else idx} listo.\n"
                    f"Nivel de ruido: {dbfs:.1f} dBFS ({calidad}).\n"
                    f"Consejo: valores por debajo de -35 dBFS suelen ser adecuados."
                )
                def done_ok():
                    try:
                        pb.stop(); progress_win.destroy()
                    except Exception:
                        pass
                    messagebox.showinfo("Micrófono", mensaje)
                window.after(0, done_ok)
            except Exception as e:
                def done_err():
                    try:
                        pb.stop(); progress_win.destroy()
                    except Exception:
                        pass
                    messagebox.showerror("Error", f"No se pudo probar micrófono: {e}")
                window.after(0, done_err)

        threading.Thread(target=worker, daemon=True).start()

    mic_listbox.bind("<Double-Button-1>", test_mic)
    test_btn.configure(command=test_mic)
    
    # Botones de prueba y guardar
    def test_voice():
        texto = "Hola, esta es una prueba de voz en español."
        voice.hablar(texto)
        messagebox.showinfo("Prueba", "Reproduciendo voz de prueba...")
    
    def save_config():
        selected_engine = engine_var.get()
        selected_gender = gender_var.get()
        selected_voice_id = None
        # Mic selection
        sel = mic_listbox.curselection()
        mic_index_to_save = None
        if sel:
            if sel[0] == 0:
                mic_index_to_save = None
            else:
                mic_index_to_save = sel[0]-1
        
        if selected_engine == "pyttsx3":
            selection = voices_listbox.curselection()
            if selection:
                selected_voice_id = available_voices[selection[0]]['id']
        
        voice.set_voice_engine(selected_engine, selected_voice_id, selected_gender)
        try:
            voice.set_microphone_device(mic_index_to_save)
        except Exception as e:
            messagebox.showwarning("Micrófono", f"No se pudo guardar dispositivo: {e}")
        # Si el avatar está visible, aplicar efecto de cambio de género (apagado → nueva imagen → encendido)
        try:
            from avatar import get_avatar
            av = get_avatar()
            if av.is_visible():
                av.apply_gender_change_effect()
        except Exception as e:
            print(f"No se pudo refrescar avatar tras cambio de género: {e}")
        messagebox.showinfo("Éxito", "Configuración guardada correctamente.")
        if on_close:
            try:
                on_close()
            except Exception as e:
                print(f"Error callback on_close: {e}")
        window.destroy()
    
    btn_frame = ttk.Frame(content)
    btn_frame.pack(pady=10)
    
    ttk.Button(btn_frame, text="🔊 Probar Voz", command=test_voice, style="Accent.TButton").pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="💾 Guardar", command=save_config, style="Primary.TButton").pack(side=tk.LEFT, padx=5)
    def cancel():
        if on_close:
            try:
                on_close()
            except Exception as e:
                print(f"Error callback on_close (cancelar): {e}")
        window.destroy()
    ttk.Button(btn_frame, text="Cancelar", command=cancel, style="Secondary.TButton").pack(side=tk.LEFT, padx=5)
    # Aplicar tema a esta ventana
    try:
        apply_theme_to_window(window)
    except Exception:
        pass

def gemini_config_window():
    """Ventana para configurar la API key de Gemini."""
    window = tk.Toplevel()
    window.title("Configuración de Gemini API")
    window.geometry("550x520")
    
    try:
        p = _get_theme_palette()
        bg_color = p["panel_bg"]
    except Exception:
        bg_color = "#ffffff"
    
    # Título
    ttk.Label(window, text="Configuración de Google Gemini", style="Title.TLabel").pack(pady=15)
    
    # Instrucciones
    instructions_frame = ttk.Frame(window)
    instructions_frame.pack(pady=10, padx=20, fill=tk.X)
    
    instructions_text = (
        "Para usar el modo de conversación con Gemini, necesitas una API key de Google.\n\n"
        "1. Ve a https://aistudio.google.com/app/api-keys\n"
        "2. Inicia sesión con tu cuenta de Google\n"
        "3. Crea una nueva API key\n"
        "4. Copia y pega la clave aquí abajo\n\n"
        "Una vez configurada, di 'Neno, charlemos' para iniciar una conversación."
    )
    
    instructions_label = ttk.Label(
        instructions_frame,
        text=instructions_text,
        justify=tk.LEFT,
        wraplength=500
    )
    instructions_label.pack(anchor="w")
    
    # Campo para API key
    api_frame = ttk.LabelFrame(window, text="API Key de Gemini")
    api_frame.pack(pady=15, padx=20, fill=tk.X)
    
    current_key = voice.get_gemini_api_key()
    
    api_entry = ttk.Entry(api_frame, width=50, show="*")
    api_entry.pack(padx=10, pady=10, fill=tk.X)
    if current_key:
        api_entry.insert(0, current_key)
    
    # Checkbox para mostrar/ocultar clave
    show_key_var = tk.BooleanVar(value=False)
    
    def toggle_show_key():
        if show_key_var.get():
            api_entry.config(show="")
        else:
            api_entry.config(show="*")
    
    show_check = ttk.Checkbutton(
        api_frame,
        text="Mostrar clave",
        variable=show_key_var,
        command=toggle_show_key
    )
    show_check.pack(anchor="w", padx=10)
    
    # Botón para abrir URL
    def open_api_url():
        import webbrowser
        webbrowser.open("https://aistudio.google.com/app/api-keys")
    
    ttk.Button(
        api_frame,
        text="🌐 Obtener API Key",
        command=open_api_url,
        style="Accent.TButton"
    ).pack(pady=5)
    
    # Botones de acción
    btn_frame = ttk.Frame(window)
    btn_frame.pack(pady=15)
    
    def save_key():
        api_key = api_entry.get().strip()
        if not api_key:
            messagebox.showwarning("Advertencia", "Por favor, introduce una API key.")
            return
        
        try:
            voice.set_gemini_api_key(api_key)
            # Reinicializar conexión con Gemini
            try:
                from gemini_chat import get_gemini_chat
                gemini = get_gemini_chat()
                gemini._load_api_key()
                if gemini.is_available():
                    messagebox.showinfo("Éxito", "API key guardada correctamente.\n\nYa puedes usar 'Neno, charlemos' en el avatar.")
                else:
                    messagebox.showwarning("Advertencia", "API key guardada, pero no se pudo conectar con Gemini.\n\nVerifica que la clave sea correcta.")
            except Exception as e:
                messagebox.showwarning("Advertencia", f"API key guardada, pero hubo un error al conectar:\n{e}")
            window.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar la API key: {e}")
    
    def test_key():
        api_key = api_entry.get().strip()
        if not api_key:
            messagebox.showwarning("Advertencia", "Por favor, introduce una API key para probar.")
            return
        
        # Probar conexión en hilo separado
        def test_worker():
            try:
                import google.generativeai as genai  # type: ignore
                configure = getattr(genai, "configure", None)
                model_cls = getattr(genai, "GenerativeModel", None)
                if not callable(configure) or model_cls is None:
                    raise RuntimeError("La librería google-generativeai instalada no soporta configure/GenerativeModel.")
                configure(api_key=api_key)
                model = model_cls('gemini-2.0-flash-001')
                generate_content = getattr(model, "generate_content", None)
                if not callable(generate_content):
                    raise RuntimeError("El modelo Gemini no soporta generate_content.")
                response = generate_content("Di hola")
                response_text = getattr(response, 'text', '')[:100]
                def show_success():
                    messagebox.showinfo("Éxito", f"¡Conexión exitosa!\n\nRespuesta de prueba: {response_text}")
                window.after(0, show_success)
            except Exception as e:
                error_msg = str(e)[:200]
                def show_error():
                    messagebox.showerror("Error", f"No se pudo conectar con Gemini:\n\n{error_msg}")
                window.after(0, show_error)
        
        threading.Thread(target=test_worker, daemon=True).start()
    
    ttk.Button(btn_frame, text="🔍 Probar Conexión", command=test_key, style="Accent.TButton").pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="💾 Guardar", command=save_key, style="Primary.TButton").pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Cancelar", command=window.destroy, style="Secondary.TButton").pack(side=tk.LEFT, padx=5)
    
    # Aplicar tema
    try:
        apply_theme_to_window(window)
    except Exception:
        pass

def about_window():
    """Ventana Acerca de con información del programa."""
    import webbrowser
    from pathlib import Path
    from PIL import Image, ImageTk
    
    # Obtener color de fondo por defecto del sistema
    temp_frame = tk.Frame()
    bg_color = temp_frame.cget("bg")
    temp_frame.destroy()
    
    window = tk.Toplevel()
    window.title("Acerca de - Asistente de Escritorio")
    window.geometry("500x600")
    window.resizable(False, False)
    window.configure(bg=bg_color)
    
    # Canvas y scrollbar para scroll vertical
    canvas = tk.Canvas(window, bg=bg_color, highlightthickness=0)
    scrollbar = tk.Scrollbar(window, orient="vertical", command=canvas.yview)
    scrollable_frame = tk.Frame(canvas, bg=bg_color)
    
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    
    canvas.create_window((250, 0), window=scrollable_frame, anchor="n")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    # Empaquetar canvas y scrollbar
    canvas.pack(side="left", fill="both", expand=True, padx=0, pady=0)
    scrollbar.pack(side="right", fill="y")
    
    # Contenedor principal dentro del frame scrollable
    main_frame = tk.Frame(scrollable_frame, bg=bg_color)
    main_frame.pack(fill=tk.BOTH, expand=True, pady=20)
    
    # Logo
    logo_path = Path(__file__).parent / "assets" / "logo.png"
    if logo_path.exists():
        try:
            logo_img = Image.open(logo_path)
            # Redimensionar el logo si es muy grande
            max_size = (200, 200)
            logo_img.thumbnail(max_size, Image.Resampling.LANCZOS)
            logo_photo = ImageTk.PhotoImage(logo_img)
            
            logo_label = tk.Label(main_frame, image=logo_photo, bg=bg_color)
            logo_label.pack(pady=10)
            _IMAGE_CACHE.append(logo_photo)
        except Exception as e:
            print(f"Error cargando logo: {e}")
    
    # Título
    tk.Label(
        main_frame, 
        text="Asistente de Escritorio", 
        font=("Arial", 18, "bold"),
        bg=bg_color,
        fg="#1976D2"
    ).pack(pady=10)
    
    tk.Label(
        main_frame, 
        text="Versión 1.0.0", 
        font=("Arial", 10),
        bg=bg_color,
        fg="gray"
    ).pack()
    
    # Separador
    separator_frame = tk.Frame(main_frame, bg=bg_color)
    separator_frame.pack(fill=tk.X, pady=15)
    tk.Frame(separator_frame, height=2, bg="#CCCCCC", width=400).pack()
    
    # Descripción
    description = """Neno es tu asistente de escritorio para gestionar tareas,
recordatorios y conversaciones desde un avatar animado.

✓ Recordatorios con fecha y hora o repetitivos
✓ Historial de conversación por usuario (con opción de borrado seguro)
✓ Avatar con control por voz, búsquedas web y atajos (terminal/editor)
✓ Respuestas locales editables y modo Gemini opcional
✓ Icono en la bandeja, notificaciones por voz y configuración por usuario

Configura todo desde la interfaz y deja que el asistente te recuerde lo
importante con voz natural."""
    
    desc_label = tk.Label(
        main_frame,
        text=description,
        font=("Arial", 10),
        bg=bg_color,
        justify=tk.CENTER,
        wraplength=420
    )
    desc_label.pack(pady=10)
    
    # Separador
    separator_frame2 = tk.Frame(main_frame, bg=bg_color)
    separator_frame2.pack(fill=tk.X, pady=15)
    tk.Frame(separator_frame2, height=2, bg="#CCCCCC", width=400).pack()
    
    # Información adicional
    tk.Label(
        main_frame,
        text="Desarrollado con ❤️ usando Python, tkinter y pyttsx3 por entreunosyceros.net",
        font=("Arial", 9),
        bg=bg_color,
        fg="gray"
    ).pack(pady=5)
    
    # Botón de GitHub
    def open_github():
        webbrowser.open("https://github.com/sapoclay/neno")
    
    github_button = ttk.Button(
        main_frame,
        text="🌐 Ver en GitHub",
        command=open_github,
        style="Accent.TButton"
    )
    github_button.pack(pady=15)
    
    # Botón cerrar
    ttk.Button(
        main_frame,
        text="Cerrar",
        command=window.destroy,
        style="Secondary.TButton"
    ).pack(pady=10)
    
    # Habilitar scroll con la rueda del mouse
    def on_mousewheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    def on_mousewheel_linux(event):
        if event.num == 4:
            canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            canvas.yview_scroll(1, "units")
    
    # Bind eventos de scroll (Windows/Mac y Linux)
    canvas.bind_all("<MouseWheel>", on_mousewheel)  # Windows/Mac
    canvas.bind_all("<Button-4>", on_mousewheel_linux)  # Linux scroll parriba
    canvas.bind_all("<Button-5>", on_mousewheel_linux)  # Linux scroll pabajo
    
    # Limpiar bindings al cerrar la ventana
    def on_closing():
        canvas.unbind_all("<MouseWheel>")
        canvas.unbind_all("<Button-4>")
        canvas.unbind_all("<Button-5>")
        window.destroy()
    
    window.protocol("WM_DELETE_WINDOW", on_closing)
    # Aplicar tema a esta ventana
    try:
        apply_theme_to_window(window)
    except Exception:
        pass

def show_avatar_window():
    """Muestra una ventana con el avatar animado del asistente."""
    from avatar import get_avatar
    
    avatar = get_avatar()
    avatar.show_window()
