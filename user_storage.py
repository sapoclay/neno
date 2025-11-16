"""Utilidades para delimitar archivos de configuración/memoria por usuario del sistema operativo."""
from __future__ import annotations

from pathlib import Path
import os
import re
import shutil
import getpass
import platform

BASE_CONFIG_DIR = Path(__file__).parent / "config"
LEGACY_SETTINGS_FILE = BASE_CONFIG_DIR / "settings.json"
LEGACY_REMINDERS_FILE = BASE_CONFIG_DIR / "reminders.json"
CONVERSATION_HISTORY_FILE = "conversation_history.json"


def _detect_username() -> str:
    """Intenta múltiples estrategias para averiguar el nombre de usuario actual del sistema operativo."""
    preferred_env = (
        "ASSISTANT_USER",  # custom override if ever set
        "SUDO_USER",
        "USERNAME",  # Windows
        "USER",
        "LOGNAME",
    )
    for env_var in preferred_env:
        value = os.environ.get(env_var)
        if value:
            return value

    # os.getlogin suele funcionar en entornos interactivos (Linux/macOS/Windows)
    try:
        return os.getlogin()
    except Exception:
        pass

    # getpass es más permisivo en servicios/cron
    try:
        return getpass.getuser()
    except Exception:
        pass

    # último recurso: deducir desde HOME en cualquier plataforma
    try:
        return Path.home().name
    except Exception:
        pass

    # si todo falla, usa etiqueta neutral dependiente del sistema operativo
    system_suffix = platform.system().lower() or "generic"
    return f"default_{system_suffix}"


def _sanitize_username(raw_name: str) -> str:
    """Limita el nombre de usuario a caracteres seguros para el sistema de archivos."""
    sanitized = re.sub(r"[^A-Za-z0-9_.-]", "_", raw_name)
    return sanitized or "default"


def get_current_user_slug() -> str:
    """Devolve el nombre de usuario normalizado usado para carpetas por usuario."""
    return _sanitize_username(_detect_username())


def get_user_config_dir() -> Path:
    """Devuelve el directorio asignado a este usuario (creándolo si es necesario)."""
    path = BASE_CONFIG_DIR / "users" / get_current_user_slug()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ensure_user_file(user_file: Path, legacy_file: Path | None) -> Path:
    """Devuelve el archivo específico del usuario, migrando los datos compartidos heredados cuando sea posible."""
    if user_file.exists():
        return user_file
    user_file.parent.mkdir(parents=True, exist_ok=True)
    if legacy_file and legacy_file.exists():
        try:
            shutil.copy2(legacy_file, user_file)
        except Exception as exc:
            print(f"No se pudo migrar {legacy_file} -> {user_file}: {exc}")
    return user_file


def get_user_settings_file() -> Path:
    """Dirección de este usuario settings.json (auto-migrado desde el archivo compartido heredado)."""
    return _ensure_user_file(get_user_config_dir() / "settings.json", LEGACY_SETTINGS_FILE)


def get_user_reminders_file() -> Path:

    """Dirección de este usuario reminders.json (auto-migrado desde el archivo compartido heredado)."""

    return _ensure_user_file(get_user_config_dir() / "reminders.json", LEGACY_REMINDERS_FILE)


def get_user_conversation_file() -> Path:
    """Archivo donde se almacena el historial de conversación de este usuario."""
    path = get_user_config_dir() / CONVERSATION_HISTORY_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        try:
            path.write_text("[]", encoding="utf-8")
        except Exception:
            pass
    return path
