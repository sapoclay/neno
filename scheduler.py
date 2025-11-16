# scheduler.py
import json
import uuid
from datetime import datetime, timedelta
import threading
import time
from voice import hablar
from reminder_events import notify_reminders_updated
from user_storage import get_user_reminders_file

REMINDERS_FILE = get_user_reminders_file()
CONFIG_DIR = REMINDERS_FILE.parent
LOCK = threading.Lock()

def _ensure_file():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not REMINDERS_FILE.exists():
        with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2, ensure_ascii=False)

def load_reminders():
    _ensure_file()
    with LOCK:
        with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []

def save_reminders(reminders):
    _ensure_file()
    with LOCK:
        with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(reminders, f, indent=2, ensure_ascii=False)

def add_reminder(text: str, when_str: str, repeat: str | None = None):
    """
    Añade un recordatorio.
    - text: mensaje
    - when_str: formato 'DD/MM/YYYY HH:MM' o 'HH:MM' (sin segundos)
    - repeat: None o 'daily'
    """
    reminders = load_reminders()
    reminder = {
        "id": str(uuid.uuid4()),
        "text": text,
        "when": when_str,
        "repeat": repeat,   # None o 'daily'
        "notified": False
    }
    reminders.append(reminder)
    save_reminders(reminders)
    try:
        notify_reminders_updated()
    except Exception as exc:
        print(f"No se pudo notificar actualización de recordatorios: {exc}")
    return reminder

def _parse_when(s: str):
    """
    Intenta parsear formato español:
    - 'DD/MM/YYYY HH:MM' - fecha y hora completa
    - 'HH:MM' - solo hora (asume hoy o mañana si ya pasó)
    """
    try:
        s = s.strip()
        
        # Formato completo: DD/MM/YYYY HH:MM
        if "/" in s and " " in s:
            return datetime.strptime(s, "%d/%m/%Y %H:%M")
        
        # Solo hora: HH:MM -> hoy o mañana si ya pasó
        if ":" in s and "/" not in s:
            now = datetime.now()
            hour, minute = map(int, s.split(":"))
            candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if candidate < now:
                candidate += timedelta(days=1)
            return candidate
        
        # Intentar formato ISO por compatibilidad
        if "T" in s:
            return datetime.fromisoformat(s)
            
    except Exception as e:
        print(f"Error parseando fecha '{s}': {e}")
        return None
    
    return None

def _should_trigger(rem):
    when_dt = _parse_when(rem["when"])
    if not when_dt:
        return False
    now = datetime.now()
    # si la hora ha llegado o pasado (dentro de 59s) y no notificado
    if not rem.get("notified", False) and now >= when_dt:
        return True
    return False

def _on_trigger(rem):
    texto = rem.get("text", "Recordatorio")
    hablar(texto)
    # también se puede integrar notificaciones del SO aquí
    # con plyer o notify2 (opcional)

def _reschedule_if_needed(rem):
    # si tiene repeat diario, actualizar 'when' al siguiente día y notificado False
    if rem.get("repeat") == "daily":
        when_dt = _parse_when(rem["when"])
        if when_dt:
            when_dt += timedelta(days=1)
            # Guardar en formato español DD/MM/YYYY HH:MM
            rem["when"] = when_dt.strftime("%d/%m/%Y %H:%M")
            rem["notified"] = False
            return True
    return False

def run_scheduler(poll_interval=30):
    """Loop principal del scheduler: comprueba recordatorios cada poll_interval segundos."""
    _ensure_file()
    def loop():
        while True:
            try:
                reminders = load_reminders()
                changed = False
                for rem in reminders:
                    if _should_trigger(rem):
                        _on_trigger(rem)
                        rem["notified"] = True
                        changed = True
                        # reprogramar si corresponde
                        if _reschedule_if_needed(rem):
                            changed = True
                if changed:
                    save_reminders(reminders)
            except Exception as e:
                # no romper el loop por un error puntual
                print("Error scheduler:", e)
            time.sleep(poll_interval)
    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t
