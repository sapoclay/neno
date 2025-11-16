import os
import random
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import quote_plus

import tkinter as tk

from knowledge_base import find_answer, knowledge_file_path
from scheduler import add_reminder
from conversation_memory import (
    extract_age_from_text,
    extract_doctor_from_text,
    extract_hospital_from_text,
    extract_medical_condition_from_text,
    extract_medication_from_text,
    extract_name_from_text,
    extract_treatment_from_text,
    find_user_age_from_history,
    find_user_doctor_from_history,
    find_user_hospital_from_history,
    find_user_medical_condition_from_history,
    find_user_medication_from_history,
    find_user_name_from_history,
    find_user_treatment_from_history,
)
from .shared_refs import AvatarWidgetRefs

PROJECT_ROOT = Path(__file__).resolve().parent.parent

FALLBACK_RESPONSES = [
    "Puedo ayudarte con recordatorios, la hora o charlar un poco. ¿Te gustaría abrir la ventana principal?",
    "Todavía no tengo información sobre eso, pero sí puedo crear recordatorios o indicarte la hora actual.",
    "Ese dato no lo sé aún. Puedes enseñármelo editando mis respuestas locales guardadas en : {kb_file} ... para añadir una respuesta personalizada.",
    "No estoy seguro de cómo responder a eso. Si quieres, dime: Neno, busca ... para abrir una búsqueda web."
]

try:
    from gemini_chat import get_gemini_chat, is_gemini_available

    GEMINI_ENABLED = True
except ImportError:  # pragma: no cover - dependencias opcionales
    GEMINI_ENABLED = False
    get_gemini_chat = None
    is_gemini_available = lambda: False  # type: ignore[assignment]


class AvatarCommandMixin(AvatarWidgetRefs):
    """Lógica de comandos, recordatorios y acciones del sistema."""

    gemini_mode: bool
    _month_names: tuple[str, ...]
    _internal_editor_event: Optional[threading.Event]
    _action_locked: bool
    _append_conversation: Callable[[str, str], None]
    _start_blocking_action: Callable[..., bool]
    _lock_controls: Callable[[str], None]
    _unlock_controls: Callable[[], None]

    def generate_response(self, message):
        message_lower = message.lower()

        introduced_name = extract_name_from_text(message)
        if introduced_name:
            return f"Encantado, {introduced_name}. Haré lo posible por recordarlo."

        introduced_age = extract_age_from_text(message)
        if introduced_age is not None:
            return f"Perfecto, tomo nota: tienes {introduced_age} años."

        introduced_doctor = extract_doctor_from_text(message)
        if introduced_doctor:
            return f"Entendido, tu profesional de cabecera es {introduced_doctor}."

        introduced_medication = extract_medication_from_text(message)
        if introduced_medication:
            return f"Gracias por avisarme. Recordaré que tu medicación incluye {introduced_medication}."

        introduced_hospital = extract_hospital_from_text(message)
        if introduced_hospital:
            return f"Perfecto, tendré presente que te atienden en {introduced_hospital}."

        introduced_condition = extract_medical_condition_from_text(message)
        if introduced_condition:
            return f"Lo siento, cuidaré de recordarte que padeces {introduced_condition}."

        introduced_treatment = extract_treatment_from_text(message)
        if introduced_treatment:
            return f"De acuerdo, tomaré nota de que sigues el tratamiento {introduced_treatment}."

        if self._is_name_question(message_lower):
            remembered_name = find_user_name_from_history()
            if remembered_name:
                return f"Me dijiste que te llamas {remembered_name}."
            return "Aún no me has dicho tu nombre. Puedes decirme: 'Mi nombre es ...'."

        if self._is_age_question(message_lower):
            remembered_age = find_user_age_from_history()
            if remembered_age is not None:
                return f"Recuerdo que me dijiste que tienes {remembered_age} años."
            return "Todavía no sé tu edad. Puedes decirme: 'Tengo X años'."

        if self._is_doctor_question(message_lower):
            remembered_doctor = find_user_doctor_from_history()
            if remembered_doctor:
                return f"Me comentaste que tu médico es {remembered_doctor}."
            return "Aún no me has contado quién es tu médico habitual."

        if self._is_medication_question(message_lower):
            remembered_medication = find_user_medication_from_history()
            if remembered_medication:
                return f"Sé que tu medicación incluye {remembered_medication}."
            return "Todavía no sé qué medicación tomas. Puedes decirme: 'Mi medicación es ...'."

        if self._is_hospital_question(message_lower):
            remembered_hospital = find_user_hospital_from_history()
            if remembered_hospital:
                return f"Me dijiste que te atienden en {remembered_hospital}."
            return "No recuerdo que me hayas mencionado tu hospital o clínica habitual."

        if self._is_condition_question(message_lower):
            remembered_condition = find_user_medical_condition_from_history()
            if remembered_condition:
                return f"Recuerdo que padeces {remembered_condition}."
            return "Aún no me has contado qué dolencia o enfermedad tienes."

        if self._is_treatment_question(message_lower):
            remembered_treatment = find_user_treatment_from_history()
            if remembered_treatment:
                return f"Sé que sigues el tratamiento {remembered_treatment}."
            return "Todavía no me has contado qué tratamiento sigues."

        if self._is_email_command(message_lower):
            if self.open_mail_client():
                return "Abriendo tu gestor de correo predeterminado."
            return "No pude abrir tu gestor de correo en este sistema."

        if self._is_document_command(message_lower):
            if self.open_text_editor():
                return "Abriendo un documento en tu editor de texto predeterminado."
            return "No pude abrir el editor de texto en este sistema."

        if "neno" in message_lower and "charlemos" in message_lower:
            if GEMINI_ENABLED and get_gemini_chat is not None and is_gemini_available():
                self.gemini_mode = True
                gemini = get_gemini_chat()
                if gemini.start_conversation():
                    return (
                        "¡Claro! Estoy listo para charlar. Pregúntame lo que quieras. "
                        "(Di Neno, termina ... para salir del modo conversación)"
                    )
                return "Lo siento, no pude conectarme con Gemini. Verifica tu conexión a internet y tu API key."
            return "Lo siento, necesito que configures tu API key de Gemini en Preferencias para poder charlar."

        if self.gemini_mode and ("neno" in message_lower and "termina" in message_lower):
            self.gemini_mode = False
            if GEMINI_ENABLED and get_gemini_chat is not None:
                gemini = get_gemini_chat()
                return gemini.end_conversation()
            return "Modo conversación finalizado."

        if self.gemini_mode:
            try:
                if GEMINI_ENABLED and get_gemini_chat is not None:
                    gemini = get_gemini_chat()
                    return gemini.send_message(message)
                return "No puedo conectar con Gemini en este momento."
            except Exception as exc:
                print(f"Error con Gemini: {exc}")
                self.gemini_mode = False
                return "Lo siento, hubo un error con Gemini. Volviendo al modo normal."

        handled_reminder, reminder_response = self._handle_reminder_request(message)
        if handled_reminder:
            return reminder_response

        if self._is_document_command(message_lower):
            started = self._start_blocking_action(
                self.open_text_editor_blocking,
                "Editor abierto. Cierra la ventana para continuar.",
                followup_success="Editor cerrado. Ya puedes seguir hablando conmigo.",
                followup_failure="No pude abrir el editor de texto."
            )
            if started:
                return "Abriendo un documento en tu editor de texto predeterminado..."
            return "Termina la tarea que está en curso antes de pedirme otra cosa."

        if self._is_terminal_command(message_lower):
            started = self._start_blocking_action(
                self.open_system_terminal,
                "Abriendo la terminal...",
                followup_success="Terminal abierta. Avísame cuando necesites otra cosa.",
                followup_failure="No pude abrir una terminal en este sistema."
            )
            if started:
                return "Abriendo la terminal predeterminada del sistema..."
            return "Termina la tarea que está en curso antes de pedirme otra cosa."

        search_trigger = self._extract_veno_search(message)
        if search_trigger:
            self.open_web_search(search_trigger)
            return f"Buscando '{search_trigger}' en tu navegador predeterminado."
        if message_lower.startswith("buscar ") or message_lower.startswith("busca ") or "buscar en la web" in message_lower:
            return "Empieza la orden con 'Neno,' por ejemplo: 'Neno, busca clima en Madrid'."

        if "hola" in message_lower or "buenos días" in message_lower or "buenas tardes" in message_lower:
            return "¡Hola! ¿En qué puedo ayudarte?"
        if "cómo estás" in message_lower or "como estas" in message_lower:
            return "Estoy funcionando perfectamente, gracias por preguntar. ¿Y tú?"
        if "qué hora" in message_lower or "que hora" in message_lower:
            now = datetime.now()
            return f"Son las {now.strftime('%H:%M')} del {now.strftime('%d/%m/%Y')}"
        if "recordatorio" in message_lower:
            return "Para gestionar recordatorios, abre la ventana principal desde la bandeja del sistema."
        if "gracias" in message_lower:
            return "De nada, estoy aquí para ayudarte."
        if "adiós" in message_lower or "adios" in message_lower or "chao" in message_lower:
            return "¡Hasta pronto! Que tengas un buen día."
        if "ayuda" in message_lower:
            return "Puedo ayudarte con recordatorios, la hora actual, o simplemente charlar contigo. ¿Qué necesitas?"

        kb_answer = find_answer(message)
        if kb_answer:
            return kb_answer

        try:
            kb_relative = knowledge_file_path().relative_to(PROJECT_ROOT).as_posix()
        except Exception:
            kb_relative = str(knowledge_file_path())

        fallback = random.choice(FALLBACK_RESPONSES)
        if "{kb_file}" in fallback:
            fallback = fallback.format(kb_file=kb_relative)
        return fallback

    def _handle_reminder_request(self, message: str):
        lower = message.lower()
        trigger_words = ("recordatorio", "recordarme", "recuerdame", "recuérdame")
        if not any(word in lower for word in trigger_words):
            return False, ""

        parsed = self._parse_reminder_command(message)
        if not parsed.get("success"):
            return True, parsed.get("error", "Necesito más datos para crear el recordatorio.")

        try:
            reminder = add_reminder(parsed["text"], parsed["when"], parsed.get("repeat"))
        except Exception as exc:
            return True, f"No pude guardar el recordatorio: {exc}"

        cuando = reminder.get("when", parsed["when"])
        texto = reminder.get("text", parsed["text"])
        extra = " diariamente" if reminder.get("repeat") == "daily" else ""
        friendly_when = self._format_when_for_speech(cuando)
        return True, f"Listo, recordaré '{texto}' {friendly_when}{extra}."

    def _parse_reminder_command(self, message: str):
        full_dt = re.search(r"(\d{1,2}/\d{1,2}/\d{4})\s*(?:a\s+las\s+)?(\d{1,2}:\d{2})", message, re.IGNORECASE)
        when_str = None
        span = None
        if full_dt:
            when_str = f"{full_dt.group(1)} {full_dt.group(2)}"
            span = full_dt.span()
        else:
            time_only = re.search(r"(?:a\s+las\s+)?(\d{1,2}:\d{2})", message, re.IGNORECASE)
            if time_only:
                when_str = time_only.group(1)
                span = time_only.span()

        if not when_str:
            return {
                "success": False,
                "error": "Dime la hora como HH:MM (y opcionalmente la fecha DD/MM/YYYY)."
            }

        if span is None:
            return {
                "success": False,
                "error": "No pude interpretar la hora del recordatorio."
            }

        remaining = (message[:span[0]] + message[span[1]:]).strip()
        keywords = (
            r"recordatorio",
            r"recordarme",
            r"recuerdame",
            r"recu[é]rdame",
            r"añade",
            r"agrega",
            r"pon",
            r"crea",
            r"añadir",
            r"agregar",
            r"crear"
        )
        for pattern in keywords:
            remaining = re.sub(pattern, "", remaining, count=1, flags=re.IGNORECASE).strip()
        remaining = remaining.strip(",.;:- ")
        if not remaining:
            remaining = "Recordatorio"

        lower = message.lower()
        repeat = None
        if any(phrase in lower for phrase in ("cada dia", "cada día", "diario", "diariamente")):
            repeat = "daily"

        return {
            "success": True,
            "text": remaining,
            "when": when_str,
            "repeat": repeat
        }

    def _extract_veno_search(self, message: str) -> str | None:
        text = (message or "").strip()
        pattern = re.compile(r"^neno[\s,]+(?:busca|buscar en la web)\s+(.+)$", re.IGNORECASE)
        match = pattern.match(text)
        if not match:
            return None
        content = match.group(1).strip()
        if not content:
            return None
        if (content.startswith('"') and content.endswith('"')) or (content.startswith("'") and content.endswith("'")):
            content = content[1:-1].strip()
        return content or None

    def _is_email_command(self, message_lower: str) -> bool:
        normalized = (message_lower or "").strip()
        return normalized.startswith("neno, escribe un correo") or normalized.startswith("neno escribe un correo")

    def _is_document_command(self, message_lower: str) -> bool:
        normalized = (message_lower or "").strip()
        return (
            normalized.startswith("neno, escribe un documento")
            or normalized.startswith("neno escribe un documento")
            or normalized.startswith("neno, escribe un texto")
            or normalized.startswith("neno escribe un texto")
        )

    def _is_terminal_command(self, message_lower: str) -> bool:
        normalized = (message_lower or "").strip()
        if not normalized.startswith("neno"):
            return False
        return "terminal" in normalized or "consola" in normalized or "cmd" in normalized or "powershell" in normalized

    def _is_name_question(self, message_lower: str) -> bool:
        normalized = (message_lower or "").strip()
        triggers = (
            "cual es mi nombre",
            "cuál es mi nombre",
            "como me llamo",
            "cómo me llamo",
            "recuerdas mi nombre",
            "te acuerdas de mi nombre",
            "sabes como me llamo",
            "sabes cuál es mi nombre",
        )
        return any(trigger in normalized for trigger in triggers)

    def _is_age_question(self, message_lower: str) -> bool:
        normalized = (message_lower or "").strip()
        triggers = (
            "cuantos años tengo",
            "cuántos años tengo",
            "cual es mi edad",
            "cuál es mi edad",
            "recuerdas mi edad",
            "sabes cuantos años tengo",
            "sabes cuántos años tengo",
            "como cuantos años tengo",
            "cómo cuantos años tengo",
        )
        return any(trigger in normalized for trigger in triggers)

    def _is_doctor_question(self, message_lower: str) -> bool:
        normalized = (message_lower or "").strip()
        triggers = (
            "quien es mi medico",
            "quién es mi médico",
            "cuál es mi médico",
            "cual es mi medico",
            "recuerdas mi medico",
            "recuerdas mi médico",
            "sabes quien es mi medico",
            "como se llama mi doctor",
            "cómo se llama mi doctor",
        )
        return any(trigger in normalized for trigger in triggers)

    def _is_medication_question(self, message_lower: str) -> bool:
        normalized = (message_lower or "").strip()
        triggers = (
            "que medicacion tomo",
            "qué medicación tomo",
            "cual es mi medicacion",
            "cuál es mi medicación",
            "que pastillas tomo",
            "qué pastillas tomo",
            "recuerdas mi medicacion",
            "recuerdas mi medicación",
            "sabes que medicinas",
            "que medicina uso",
            "cual es mi tratamiento",
            "cuál es mi tratamiento",
        )
        return any(trigger in normalized for trigger in triggers)

    def _is_hospital_question(self, message_lower: str) -> bool:
        normalized = (message_lower or "").strip()
        triggers = (
            "cual es mi hospital",
            "cuál es mi hospital",
            "a que hospital voy",
            "a qué hospital voy",
            "que clinica me atiende",
            "qué clínica me atiende",
            "recuerdas mi hospital",
        )
        return any(trigger in normalized for trigger in triggers)

    def _is_condition_question(self, message_lower: str) -> bool:
        normalized = (message_lower or "").strip()
        triggers = (
            "que enfermedad tengo",
            "qué enfermedad tengo",
            "cual es mi enfermedad",
            "cuál es mi enfermedad",
            "que dolencia tengo",
            "qué dolencia tengo",
            "sabes que padezco",
            "recuerdas mi dolencia",
        )
        return any(trigger in normalized for trigger in triggers)

    def _is_treatment_question(self, message_lower: str) -> bool:
        normalized = (message_lower or "").strip()
        triggers = (
            "cual es mi tratamiento",
            "cuál es mi tratamiento",
            "que terapia sigo",
            "qué terapia sigo",
            "recuerdas mi tratamiento",
            "que tratamiento sigo",
            "qué tratamiento sigo",
        )
        return any(trigger in normalized for trigger in triggers)

    def open_system_terminal(self) -> bool:
        platform = sys.platform
        try:
            if platform == "win32":
                creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
                commands = [
                    ["wt.exe"],
                    ["powershell.exe", "-NoExit"],
                    ["cmd.exe", "/k"]
                ]
                for cmd in commands:
                    try:
                        subprocess.Popen(cmd, creationflags=creationflags)
                        return True
                    except FileNotFoundError:
                        continue
                    except Exception as exc:
                        print(f"Error abriendo terminal ({cmd}): {exc}")
                try:
                    os.startfile("cmd.exe")  # type: ignore[attr-defined]
                    return True
                except Exception as exc:
                    print(f"os.startfile cmd.exe falló: {exc}")
                    return False

            if platform == "darwin":
                try:
                    subprocess.Popen(["open", "-a", "Terminal"])
                    return True
                except Exception as exc:
                    print(f"Error abriendo Terminal en macOS: {exc}")
                    return False

            env = os.environ.copy()
            if "GTK_PATH" in env:
                env.pop("GTK_PATH", None)
            candidates: list[list[str]] = []
            env_terminal = os.environ.get("TERMINAL")
            if env_terminal:
                try:
                    candidates.append(shlex.split(env_terminal))
                except Exception:
                    candidates.append([env_terminal])
            candidates.extend([
                ["x-terminal-emulator"],
                ["gnome-terminal"],
                ["konsole"],
                ["xfce4-terminal"],
                ["lxterminal"],
                ["mate-terminal"],
                ["tilix"],
                ["kitty"],
                ["alacritty"],
                ["urxvt"],
                ["xterm"]
            ])
            for cmd in candidates:
                if not cmd:
                    continue
                try:
                    subprocess.Popen(cmd, env=env)
                    return True
                except FileNotFoundError:
                    continue
                except Exception as exc:
                    print(f"Error abriendo terminal ({cmd}): {exc}")
            return False
        except Exception as exc:
            print(f"Error general abriendo terminal: {exc}")
            return False

    def _format_when_for_speech(self, when_str: str) -> str:
        when_str = (when_str or "").strip()
        if not when_str:
            return "a la hora indicada"
        try:
            if "/" in when_str and " " in when_str:
                dt = datetime.strptime(when_str, "%d/%m/%Y %H:%M")
                date_text = f"el {dt.day} de {self._month_names[dt.month-1]} de {dt.year}"
                time_text = self._format_time_phrase(dt.hour, dt.minute)
                return f"{date_text} a las {time_text}"
        except Exception:
            pass

        try:
            if ":" in when_str:
                hour, minute = when_str.split(":", 1)
                time_text = self._format_time_phrase(int(hour), int(minute))
                return f"a las {time_text}"
        except Exception:
            pass

        return when_str

    def _format_time_phrase(self, hour: int, minute: int) -> str:
        hour = max(0, min(23, int(hour)))
        minute = max(0, min(59, int(minute)))
        hour_word = "hora" if hour == 1 else "horas"
        if minute == 0:
            return f"{hour} {hour_word} en punto"
        return f"{hour} {hour_word} con {minute:02d} minutos"

    def open_web_search(self, query: str, engine: str = "google"):
        try:
            from voice import get_search_engine
            engine = get_search_engine()
        except Exception:
            pass
        q = quote_plus(query)
        if engine == "duckduckgo":
            url = f"https://duckduckgo.com/?q={q}"
        else:
            url = f"https://www.google.com/search?q={q}"

        def _open():
            try:
                webbrowser.open_new_tab(url)
            except Exception as exc:
                print(f"Error abriendo navegador: {exc}")

        threading.Thread(target=_open, daemon=True).start()

    def open_mail_client(self) -> bool:
        try:
            if shutil.which("xdg-email"):
                subprocess.Popen(["xdg-email"])
                return True
        except Exception as exc:
            print(f"xdg-email falló: {exc}")
        try:
            if shutil.which("xdg-open"):
                subprocess.Popen(["xdg-open", "mailto:"])
                return True
        except Exception as exc:
            print(f"xdg-open mailto falló: {exc}")
        try:
            return webbrowser.open("mailto:")
        except Exception as exc:
            print(f"Error abriendo mailto: {exc}")
            return False

    def open_text_editor_blocking(self) -> bool:
        file_path = self._prepare_document_file()
        if file_path is None:
            return False
        command = self._resolve_text_editor_command(file_path)
        if command:
            try:
                proc = subprocess.Popen(command)
                proc.wait()
                return True
            except Exception as exc:
                print(f"Error lanzando editor predeterminado: {exc}")
        return self._open_text_editor_fallback(file_path)

    def _prepare_document_file(self) -> Path | None:
        try:
            documents_dir = Path.home() / "Documentos"
            documents_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            documents_dir = Path(tempfile.gettempdir())
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        file_path = Path(documents_dir) / f"nota-{timestamp}.txt"
        try:
            file_path.write_text("Escribe tu texto aquí...\n", encoding="utf-8")
        except Exception as exc:
            print(f"No se pudo crear archivo de notas: {exc}")
            return None
        return file_path

    def _resolve_text_editor_command(self, file_path: Path) -> list[str] | None:
        editor_env = os.environ.get("VISUAL") or os.environ.get("EDITOR")
        if editor_env:
            return shlex.split(editor_env) + [str(file_path)]
        if sys.platform == "darwin":
            return ["open", "-W", str(file_path)]
        if os.name == "nt":
            return ["notepad.exe", str(file_path)]
        if sys.platform.startswith("linux"):
            cmd = self._get_linux_editor_command(file_path)
            if cmd:
                return cmd
        for candidate in ("gedit", "xed", "kate", "mousepad", "leafpad", "pluma", "code", "subl"):
            path = shutil.which(candidate)
            if path:
                return [path, str(file_path)]
        return None

    def _get_linux_editor_command(self, file_path: Path) -> list[str] | None:
        try:
            result = subprocess.run(
                ["xdg-mime", "query", "default", "text/plain"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False
            )
        except Exception as exc:
            print(f"xdg-mime falló: {exc}")
            return None
        desktop_name = (result.stdout or "").strip()
        if not desktop_name:
            return None
        desktop_path = self._find_desktop_file(desktop_name)
        if desktop_path is None:
            return None
        exec_line = self._parse_desktop_exec(desktop_path)
        if not exec_line:
            return None
        cmd = self._build_exec_command(exec_line, file_path)
        if cmd and shutil.which(cmd[0]):
            return cmd
        return None

    def _find_desktop_file(self, desktop_name: str) -> Path | None:
        name = desktop_name if desktop_name.endswith(".desktop") else f"{desktop_name}.desktop"
        search_dirs = [
            Path.home() / ".local" / "share" / "applications",
            Path("/usr/share/applications"),
            Path("/usr/local/share/applications"),
        ]
        for directory in search_dirs:
            candidate = directory / name
            if candidate.exists():
                return candidate
        return None

    def _parse_desktop_exec(self, desktop_path: Path) -> str | None:
        try:
            for line in desktop_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                stripped = line.strip()
                if stripped.startswith("Exec="):
                    return stripped.split("Exec=", 1)[1].strip()
        except Exception as exc:
            print(f"No se pudo leer {desktop_path}: {exc}")
        return None

    def _build_exec_command(self, exec_line: str, file_path: Path) -> list[str] | None:
        try:
            parts = shlex.split(exec_line, posix=True)
        except Exception as exc:
            print(f"No se pudo dividir comando Exec: {exc}")
            return None
        if not parts:
            return None
        command: list[str] = []
        replaced = False
        for part in parts:
            if part in ("%f", "%u", "%F", "%U"):
                if not replaced:
                    command.append(str(file_path))
                    replaced = True
                continue
            if part.startswith("%"):
                continue
            command.append(part)
        if not replaced:
            command.append(str(file_path))
        return command

    def _open_text_editor_fallback(self, file_path: Path) -> bool:
        if self.window is None or not self.window_created:
            return False
        done_event = threading.Event()
        self._internal_editor_event = done_event

        def launch_editor():
            self._launch_internal_editor(file_path, done_event)

        try:
            self.window.after(0, launch_editor)
        except Exception as exc:
            print(f"No se pudo iniciar editor interno: {exc}")
            return False
        done_event.wait()
        self._internal_editor_event = None
        return True

    def _launch_internal_editor(self, file_path: Path, done_event: threading.Event):
        editor = tk.Toplevel(self.window)
        editor.title("Documento rápido")
        editor.geometry("600x400")
        text_widget = tk.Text(editor, wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True)
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            content = "Escribe tu texto aquí...\n"
        text_widget.delete("1.0", tk.END)
        text_widget.insert("1.0", content)

        def close_editor():
            try:
                content_to_save = text_widget.get("1.0", tk.END)
                file_path.write_text(content_to_save, encoding="utf-8")
            except Exception as exc:
                print(f"No se pudo guardar el documento temporal: {exc}")
            finally:
                try:
                    editor.destroy()
                except Exception:
                    pass
                done_event.set()

        editor.protocol("WM_DELETE_WINDOW", close_editor)

    def open_text_editor(self) -> bool:
        try:
            temp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
            path = Path(temp.name)
            temp.write("Escribe tu texto aquí...".encode("utf-8"))
            temp.close()
        except Exception as exc:
            print(f"Error creando archivo temporal: {exc}")
            return False

        try:
            if sys.platform.startswith("linux"):
                opener = shutil.which("xdg-open")
                if opener:
                    subprocess.Popen([opener, str(path)])
                    return True
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
                return True
            elif os.name == "nt":
                os.startfile(str(path))  # type: ignore[attr-defined]
                return True
        except Exception as exc:
            print(f"Error abriendo editor de texto: {exc}")

        try:
            return webbrowser.open(path.as_uri())
        except Exception as exc:
            print(f"Error usando navegador para abrir texto: {exc}")
            return False
