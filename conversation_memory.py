"""Gestor de historial de conversación y extracción de datos personales."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set, TypeVar, cast

from user_storage import get_user_conversation_file

MAX_HISTORY_ENTRIES = 200
_USER_ROLE_KEYS: Set[str] = {"tú", "tu", "usuario", "user"}


_NAME_PATTERNS = (
    r"(?:mi\s+nombre\s+es)\s+([^.,;\n]+)",
    r"(?:me\s+llamo)\s+([^.,;\n]+)",
    r"(?:llámame|llamame)\s+([^.,;\n]+)",
)

_AGE_PATTERNS = (
    r"(?:tengo|tendré|tendre)\s+(\d{1,3})\s+años",
    r"mi\s+edad\s+es\s+(\d{1,3})",
    r"cumplo\s+(\d{1,3})\s*(?:años)?",
    r"(?:voy\s+a\s+cumplir|va\s+a\s+cumplir|cumpliré|cumplire)\s+(\d{1,3})",
)

_CITY_PATTERNS = (
    r"(?:soy|somos)\s+de\s+([^.,;\n]+)",
    r"(?:vivo|resido|estoy\s+viviendo)\s+en\s+([^.,;\n]+)",
    r"(?:mi\s+ciudad\s+(?:actual\s+)?es)\s+([^.,;\n]+)",
)

_BIRTHDAY_PATTERNS = (
    r"(?:mi\s+cumpleaños\s+es\s+el)\s+([^.,;\n]+)",
    r"(?:cumplo\s+años\s+el)\s+([^.,;\n]+)",
    r"(?:nací\s+el)\s+([^.,;\n]+)",
)

_PROFESSION_PATTERNS = (
    r"(?:trabajo\s+como)\s+([^.,;\n]+)",
    r"(?:me\s+dedico\s+a)\s+([^.,;\n]+)",
    r"(?:mi\s+profesión\s+es)\s+([^.,;\n]+)",
    r"(?:soy)\s+(?!de\b)(?!del\b)(?!de\sla\b)([^.,;\n]+)",
)

_COLOR_PATTERNS = (
    r"(?:mi\s+color\s+favorito\s+es)\s+([^.,;\n]+)",
)

_FOOD_PATTERNS = (
    r"(?:mi\s+comida\s+favorita\s+es)\s+([^.,;\n]+)",
)

_DRINK_PATTERNS = (
    r"(?:mi\s+bebida\s+favorita\s+es)\s+([^.,;\n]+)",
)

_MUSIC_PATTERNS = (
    r"(?:mi\s+música\s+favorita\s+es)\s+([^.,;\n]+)",
    r"(?:me\s+gusta\s+escuchar)\s+([^.,;\n]+)",
)

_HOBBY_PATTERNS = (
    r"(?:mi\s+pasatiempo\s+favorito\s+es)\s+([^.,;\n]+)",
    r"(?:mi\s+hobby\s+es)\s+([^.,;\n]+)",
)

_DOCTOR_PATTERNS = (
    r"(?:mi\s+(?:m[eé]dico|doctora?|especialista)\s+(?:es|se\s+llama))\s+([^.,;\n]+)",
    r"(?:me\s+atiende)\s+la?\s+(?:doctora?|m[eé]dico)\s+([^.,;\n]+)",
)

_MEDICATION_PATTERNS = (
    r"(?:mi\s+(?:medicaci[oó]n|tratamiento)\s+(?:es|incluye))\s+([^.,;\n]+)",
    r"(?:mis\s+pastillas\s+son)\s+([^.,;\n]+)",
    r"(?:tomo|estoy\s+tomando|me\s+recetaron)\s+([^.,;\n]+)",
)

_HOSPITAL_PATTERNS = (
    r"(?:voy|acudo)\s+al?\s+hospital\s+([^.,;\n]+)",
    r"(?:me\s+atienden)\s+en\s+el?\s+(?:hospital|cl[ií]nica)\s+([^.,;\n]+)",
    r"(?:mi\s+(?:hospital|cl[ií]nica)\s+(?:principal\s+)?es)\s+([^.,;\n]+)",
)

_ILLNESS_PATTERNS = (
    r"(?:tengo|padezco|sufro)\s+(?!\d{1,3}\s*(?:años|k(?:g|ilos)|años\s+de\s+edad))([^.,;\n]+)",
    r"(?:tengo|padezco|sufro)\s+de\s+([^.,;\n]+)",
    r"(?:mi\s+(?:enfermedad|dolencia)\s+es)\s+([^.,;\n]+)",
    r"(?:me\s+diagnosticaron)\s+([^.,;\n]+)",
)

_TREATMENT_PATTERNS = (
    r"(?:mi\s+tratamiento\s+(?:actual\s+)?es)\s+([^.,;\n]+)",
    r"(?:estoy\s+en)\s+tratamiento\s+de\s+([^.,;\n]+)",
    r"(?:sigo)\s+una?\s+terapia\s+([^.,;\n]+)",
)

_ValueT = TypeVar("_ValueT")


def _history_path() -> Path:
    return get_user_conversation_file()


def load_conversation_history() -> List[Dict[str, str]]:
    path = _history_path()
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"No se pudo leer historial de conversación: {exc}")
        return []
    history: List[Dict[str, str]] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role", "")).strip()
            text = str(item.get("text", "")).strip()
            if not role or not text:
                continue
            history.append({"role": role, "text": text})
    return history[-MAX_HISTORY_ENTRIES:]


def _write_history(entries: Iterable[Dict[str, str]]) -> None:
    path = _history_path()
    try:
        path.write_text(json.dumps(list(entries), ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"No se pudo guardar historial de conversación: {exc}")


def append_message_to_history(role: str, text: str) -> None:
    role = (role or "").strip()
    text = (text or "").strip()
    if not role or not text:
        return
    history = load_conversation_history()
    history.append({"role": role, "text": text})
    if len(history) > MAX_HISTORY_ENTRIES:
        history = history[-MAX_HISTORY_ENTRIES:]
    _write_history(history)


def replace_history(entries: List[Dict[str, str]]) -> None:
    if not isinstance(entries, list):
        return
    cleaned: List[Dict[str, str]] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip()
        text = str(item.get("text", "")).strip()
        if not role or not text:
            continue
        cleaned.append({"role": role, "text": text})
    _write_history(cleaned[-MAX_HISTORY_ENTRIES:])


def clear_conversation_history() -> None:
    _write_history([])


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip(" \"'.,;:!?")


def _extract_with_patterns(
    text: str,
    patterns: Sequence[str],
    transform: Optional[Callable[[str], Optional[_ValueT]]] = None,
    validator: Optional[Callable[[_ValueT], bool]] = None
) -> Optional[_ValueT]:
    if not text:
        return None
    normalized = text.strip()
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if not match:
            continue
        candidate = _normalize_text(match.group(1))
        if not candidate:
            continue
        if transform is not None:
            try:
                value = transform(candidate)
            except Exception:
                continue
        else:
            value = cast(_ValueT, candidate)
        if value is None:
            continue
        if validator is not None and not validator(value):
            continue
        return value
    return None


def _find_in_history(
    patterns: Sequence[str],
    transform: Optional[Callable[[str], Optional[_ValueT]]] = None,
    validator: Optional[Callable[[_ValueT], bool]] = None
) -> Optional[_ValueT]:
    history = load_conversation_history()
    for entry in reversed(history):
        role = entry.get("role", "").strip().lower()
        if role not in _USER_ROLE_KEYS:
            continue
        value = _extract_with_patterns(entry.get("text", ""), patterns, transform, validator)
        if value is not None:
            return value
    return None


def _parse_age(value: str) -> Optional[int]:
    try:
        num = int(value)
    except ValueError:
        return None
    if 1 <= num <= 120:
        return num
    return None


def _text_validator(min_len: int = 2, max_len: int = 80) -> Callable[[str], bool]:
    def _validator(value: str) -> bool:
        return min_len <= len(value) <= max_len

    return _validator


def _medical_text_validator(max_len: int = 120) -> Callable[[str], bool]:
    base_validator = _text_validator(max_len=max_len)

    def _validator(value: str) -> bool:
        if not base_validator(value):
            return False
        lowered = value.lower()
        forbidden_tokens = ("años", "año", "horas", "hora")
        return not any(token in lowered for token in forbidden_tokens)

    return _validator


def extract_name_from_text(text: str) -> Optional[str]:
    return _extract_with_patterns(text, _NAME_PATTERNS, validator=_text_validator())


def find_user_name_from_history() -> Optional[str]:
    return _find_in_history(_NAME_PATTERNS, validator=_text_validator())


def extract_age_from_text(text: str) -> Optional[int]:
    return _extract_with_patterns(text, _AGE_PATTERNS, transform=_parse_age)


def find_user_age_from_history() -> Optional[int]:
    return _find_in_history(_AGE_PATTERNS, transform=_parse_age)


def extract_city_from_text(text: str) -> Optional[str]:
    return _extract_with_patterns(text, _CITY_PATTERNS, validator=_text_validator())


def find_user_city_from_history() -> Optional[str]:
    return _find_in_history(_CITY_PATTERNS, validator=_text_validator())


def extract_birthday_from_text(text: str) -> Optional[str]:
    return _extract_with_patterns(text, _BIRTHDAY_PATTERNS, validator=_text_validator(max_len=100))


def find_user_birthday_from_history() -> Optional[str]:
    return _find_in_history(_BIRTHDAY_PATTERNS, validator=_text_validator(max_len=100))


def extract_profession_from_text(text: str) -> Optional[str]:
    return _extract_with_patterns(text, _PROFESSION_PATTERNS, validator=_text_validator(max_len=80))


def find_user_profession_from_history() -> Optional[str]:
    return _find_in_history(_PROFESSION_PATTERNS, validator=_text_validator(max_len=80))


def extract_favorite_color_from_text(text: str) -> Optional[str]:
    return _extract_with_patterns(text, _COLOR_PATTERNS, validator=_text_validator())


def find_user_favorite_color_from_history() -> Optional[str]:
    return _find_in_history(_COLOR_PATTERNS, validator=_text_validator())


def extract_favorite_food_from_text(text: str) -> Optional[str]:
    return _extract_with_patterns(text, _FOOD_PATTERNS, validator=_text_validator())


def find_user_favorite_food_from_history() -> Optional[str]:
    return _find_in_history(_FOOD_PATTERNS, validator=_text_validator())


def extract_favorite_drink_from_text(text: str) -> Optional[str]:
    return _extract_with_patterns(text, _DRINK_PATTERNS, validator=_text_validator())


def find_user_favorite_drink_from_history() -> Optional[str]:
    return _find_in_history(_DRINK_PATTERNS, validator=_text_validator())


def extract_favorite_music_from_text(text: str) -> Optional[str]:
    return _extract_with_patterns(text, _MUSIC_PATTERNS, validator=_text_validator(max_len=80))


def find_user_favorite_music_from_history() -> Optional[str]:
    return _find_in_history(_MUSIC_PATTERNS, validator=_text_validator(max_len=80))


def extract_hobby_from_text(text: str) -> Optional[str]:
    return _extract_with_patterns(text, _HOBBY_PATTERNS, validator=_text_validator(max_len=80))


def find_user_hobby_from_history() -> Optional[str]:
    return _find_in_history(_HOBBY_PATTERNS, validator=_text_validator(max_len=80))


def extract_doctor_from_text(text: str) -> Optional[str]:
    return _extract_with_patterns(text, _DOCTOR_PATTERNS, validator=_text_validator(max_len=80))


def find_user_doctor_from_history() -> Optional[str]:
    return _find_in_history(_DOCTOR_PATTERNS, validator=_text_validator(max_len=80))


def extract_medication_from_text(text: str) -> Optional[str]:
    return _extract_with_patterns(text, _MEDICATION_PATTERNS, validator=_medical_text_validator())


def find_user_medication_from_history() -> Optional[str]:
    return _find_in_history(_MEDICATION_PATTERNS, validator=_medical_text_validator())


def extract_hospital_from_text(text: str) -> Optional[str]:
    return _extract_with_patterns(text, _HOSPITAL_PATTERNS, validator=_text_validator(max_len=120))


def find_user_hospital_from_history() -> Optional[str]:
    return _find_in_history(_HOSPITAL_PATTERNS, validator=_text_validator(max_len=120))


def extract_medical_condition_from_text(text: str) -> Optional[str]:
    return _extract_with_patterns(text, _ILLNESS_PATTERNS, validator=_medical_text_validator())


def find_user_medical_condition_from_history() -> Optional[str]:
    return _find_in_history(_ILLNESS_PATTERNS, validator=_medical_text_validator())


def extract_treatment_from_text(text: str) -> Optional[str]:
    return _extract_with_patterns(text, _TREATMENT_PATTERNS, validator=_medical_text_validator())


def find_user_treatment_from_history() -> Optional[str]:
    return _find_in_history(_TREATMENT_PATTERNS, validator=_medical_text_validator())


__all__ = [
    "append_message_to_history",
    "clear_conversation_history",
    "extract_age_from_text",
    "extract_birthday_from_text",
    "extract_city_from_text",
    "extract_doctor_from_text",
    "extract_favorite_color_from_text",
    "extract_favorite_drink_from_text",
    "extract_favorite_food_from_text",
    "extract_favorite_music_from_text",
    "extract_hobby_from_text",
    "extract_hospital_from_text",
    "extract_medical_condition_from_text",
    "extract_medication_from_text",
    "extract_name_from_text",
    "extract_profession_from_text",
    "extract_treatment_from_text",
    "find_user_age_from_history",
    "find_user_birthday_from_history",
    "find_user_city_from_history",
    "find_user_doctor_from_history",
    "find_user_favorite_color_from_history",
    "find_user_favorite_drink_from_history",
    "find_user_favorite_food_from_history",
    "find_user_favorite_music_from_history",
    "find_user_hobby_from_history",
    "find_user_hospital_from_history",
    "find_user_medical_condition_from_history",
    "find_user_medication_from_history",
    "find_user_name_from_history",
    "find_user_profession_from_history",
    "find_user_treatment_from_history",
    "load_conversation_history",
    "replace_history",
]