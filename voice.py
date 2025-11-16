import speech_recognition as sr
import pyttsx3
import threading
import json
import os
import tempfile
import re
from typing import Any, Iterable, Optional, Callable
from gtts import gTTS
import pygame
from pydub import AudioSegment
from user_storage import get_user_settings_file

_tts_lock = threading.Lock()
_tts_engine = None
_pygame_initialized = False
CONFIG_FILE = get_user_settings_file()

def _sanitize_for_speech(text: str) -> str:
    """Quita marcas como ` o * para que el TTS no las pronuncie literalmente."""
    if not text:
        return ""
    replacements = {
        "`": " ",
        "*": " ",
        "_": " ",
        "~": " ",
    }
    cleaned = text
    for char, repl in replacements.items():
        cleaned = cleaned.replace(char, repl)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

def _load_settings():
    """Carga la configuración de voz."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Asegurar claves por defecto
            if "search_engine" not in data:
                data["search_engine"] = "google"
            if "mic_device_index" not in data:
                data["mic_device_index"] = null_value()
            if "theme" not in data:
                data["theme"] = "light"
            return data
    return {
        "voice_engine": "gtts",
        "voice_id": None,
        "voice_rate": 150,
        "voice_volume": 1.0,
        "voice_gender": "female",
        "search_engine": "google",
        "mic_device_index": null_value(),
        "theme": "light",
        "gemini_api_key": ""
    }

def null_value():
    # Representar None sin romper JSON existente
    return None

def _save_settings(settings):
    """Guarda la configuración de voz."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

def _init_pygame():
    """Inicializa pygame mixer para reproducir audio."""
    global _pygame_initialized
    if not _pygame_initialized:
        pygame.mixer.init()
        _pygame_initialized = True

def _init_pyttsx3_engine():
    """Inicializa el motor de pyttsx3 una sola vez."""
    global _tts_engine
    if _tts_engine is None:
        settings = _load_settings()
        _tts_engine = pyttsx3.init()
        _tts_engine.setProperty("rate", settings.get("voice_rate", 150))
        _tts_engine.setProperty("volume", settings.get("voice_volume", 1.0))
        
        if settings.get("voice_id"):
            _tts_engine.setProperty("voice", settings["voice_id"])
    return _tts_engine

def get_available_voices():
    """Retorna una lista de voces disponibles en pyttsx3."""
    try:
        engine = pyttsx3.init()
        raw_voices: Any = engine.getProperty("voices")
        voices_iter: Iterable[Any]
        if isinstance(raw_voices, (list, tuple)):
            voices_iter = raw_voices
        elif hasattr(raw_voices, "__iter__"):
            voices_iter = raw_voices  # type: ignore[assignment]
        else:
            voices_iter = []
        result = []
        for v in voices_iter:
            vid = getattr(v, "id", None)
            name = getattr(v, "name", "Desconocida")
            languages = getattr(v, "languages", [])
            result.append({"id": vid, "name": name, "languages": languages})
        return result
    except Exception as e:
        print(f"Error obteniendo voces: {e}")
        return []

def set_voice_engine(engine_name: str, voice_id: str | None = None, gender: str | None = None):
    """
    Configura el motor de voz a usar.
    engine_name: 'gtts' o 'pyttsx3'
    voice_id: ID de la voz (solo para pyttsx3)
    gender: 'male' o 'female' (para ambos motores)
    """
    global _tts_engine
    settings = _load_settings()
    settings["voice_engine"] = engine_name
    if voice_id:
        settings["voice_id"] = voice_id
    if gender:
        settings["voice_gender"] = gender
    _save_settings(settings)
    
    # Reiniciar motor si es pyttsx3
    if engine_name == "pyttsx3":
        _tts_engine = None

def set_search_engine(engine_name: str):
    """Configura el motor de búsqueda web (google o duckduckgo)."""
    settings = _load_settings()
    if engine_name not in ("google", "duckduckgo"):
        raise ValueError("Motor de búsqueda inválido")
    settings["search_engine"] = engine_name
    _save_settings(settings)

def get_search_engine() -> str:
    return _load_settings().get("search_engine", "google")

def set_microphone_device(index: int | None):
    """Guarda el índice del dispositivo de micrófono (None para automático)."""
    settings = _load_settings()
    settings["mic_device_index"] = index if index is not None else null_value()
    _save_settings(settings)

def get_microphone_device() -> int | None:
    return _load_settings().get("mic_device_index")

def set_theme(theme: str):
    """Guarda el tema seleccionado."""
    settings = _load_settings()
    settings["theme"] = theme
    _save_settings(settings)

def get_gemini_api_key() -> str:
    """Obtiene la API key de Gemini."""
    settings = _load_settings()
    return settings.get("gemini_api_key", "")

def set_gemini_api_key(api_key: str):
    """Guarda la API key de Gemini."""
    settings = _load_settings()
    settings["gemini_api_key"] = api_key
    _save_settings(settings)

def get_theme() -> str:
    return _load_settings().get("theme", "light")

def hablar(texto: str):
    """Habla el texto usando el motor configurado. Thread-safe."""
    sanitized_text = _sanitize_for_speech(texto) or "..."

    def _speak(text):
        # Iniciar animación del avatar si está visible
        avatar = None
        try:
            from avatar import get_avatar
            avatar = get_avatar()
            # No iniciar aún hasta tener el audio listo
        except:
            pass
        
        with _tts_lock:
            try:
                settings = _load_settings()
                engine_name = settings.get("voice_engine", "gtts")
                
                speech_text = sanitized_text

                if engine_name == "gtts":
                    # Usar Google TTS (más natural)
                    gender = settings.get("voice_gender", "female")
                    
                    # Generar audio con gTTS (siempre femenina base)
                    tts = gTTS(text=speech_text or text, lang='es', slow=False, tld='com')
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as fp:
                        temp_file = fp.name
                        tts.save(temp_file)
                    
                    # Si es voz masculina, modificar el pitch
                    if gender == "male":
                        # Cargar audio con pydub
                        sound = AudioSegment.from_mp3(temp_file)
                        
                        # Reducir pitch para voz más grave (masculina)
                        octaves = -0.25  # Bajar aproximadamente 3 semitonos
                        new_sample_rate = int(sound.frame_rate * (2.0 ** octaves))
                        sound_pitched = sound._spawn(sound.raw_data, overrides={'frame_rate': new_sample_rate})
                        sound_pitched = sound_pitched.set_frame_rate(sound.frame_rate)
                        
                        # Acelerar para mantener velocidad natural
                        sound_pitched = sound_pitched.speedup(playback_speed=1.2)
                        
                        # Guardar audio modificado
                        os.unlink(temp_file)
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as fp:
                            temp_file = fp.name
                            sound_pitched.export(temp_file, format='mp3')
                    
                    # Cargar audio final para análisis de envolvente
                    try:
                        final_sound = AudioSegment.from_mp3(temp_file)
                    except Exception as e:
                        final_sound = None
                        print(f"No se pudo cargar audio para envolvente: {e}")

                    # Construir envolvente de amplitud -> estados de boca
                    envelope_states = []
                    frame_interval_ms = 50  # más fluido (~20 fps)
                    if final_sound:
                        max_rms = 1
                        rms_values = []
                        for ms in range(0, len(final_sound), frame_interval_ms):
                            chunk = final_sound[ms:ms+frame_interval_ms]
                            rms = chunk.rms or 0
                            rms_values.append(rms)
                            if rms > max_rms:
                                max_rms = rms
                        # Suavizado: media móvil ventana 3
                        smoothed = []
                        for i in range(len(rms_values)):
                            vals = [rms_values[i]]
                            if i > 0:
                                vals.append(rms_values[i-1])
                            if i < len(rms_values)-1:
                                vals.append(rms_values[i+1])
                            smoothed.append(sum(vals)/len(vals))
                        # Reajustar max con suavizado
                        max_rms = max(smoothed) if smoothed else max_rms
                        # Umbrales para 6 estados (0-5)
                        t1 = max_rms * 0.10
                        t2 = max_rms * 0.22
                        t3 = max_rms * 0.40
                        t4 = max_rms * 0.60
                        t5 = max_rms * 0.80
                        for v in smoothed:
                            if v < t1:
                                envelope_states.append(0)
                            elif v < t2:
                                envelope_states.append(1)
                            elif v < t3:
                                envelope_states.append(2)
                            elif v < t4:
                                envelope_states.append(3)
                            elif v < t5:
                                envelope_states.append(4)
                            else:
                                envelope_states.append(5)
                    
                    # Iniciar animación sincronizada justo antes de reproducir
                    if avatar is not None and avatar.is_visible():
                        try:
                            if envelope_states:
                                avatar.start_speaking_envelope(envelope_states, frame_interval_ms=frame_interval_ms)
                            else:
                                # Fallback usando duración
                                dur = final_sound.duration_seconds if final_sound else None
                                avatar.start_speaking(duration=dur)
                        except Exception as e:
                            print(f"Error iniciando animación avatar: {e}")

                    # Reproducir con pygame (después de disparar animación)
                    _init_pygame()
                    pygame.mixer.music.load(temp_file)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        pygame.time.Clock().tick(20)
                    
                    # Limpiar archivo temporal
                    try:
                        os.unlink(temp_file)
                    except:
                        pass
                else:
                    # Usar pyttsx3 (offline)
                    engine = _init_pyttsx3_engine()
                    engine.say(speech_text or text)
                    engine.runAndWait()
                    
            except Exception as e:
                print(f"Error al hablar: {e}")
            finally:
                # Detener animación del avatar
                if avatar is not None and avatar.is_speaking:
                    try:
                        avatar.stop_speaking()
                    except Exception:
                        pass

    # Ejecutar en hilo para no bloquear el scheduler
    t = threading.Thread(target=_speak, args=(texto,), daemon=True)
    t.start()

def escuchar() -> str:
    """Escucha por micrófono y devuelve el texto reconocido."""
    recognizer = sr.Recognizer()
    device_index = get_microphone_device()
    try:
        source = sr.Microphone(device_index=device_index) if device_index is not None else sr.Microphone()
    except Exception as e:
        print(f"Fallo usando micrófono configurado ({device_index}). Reintentando automático: {e}")
        source = sr.Microphone()
    with source as source:
        print("Escuchando... habla ahora.")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        audio = recognizer.listen(source)

    try:
        recognize_google: Optional[Callable[..., str]] = getattr(recognizer, "recognize_google", None)
        if not callable(recognize_google):
            return ""
        texto = recognize_google(audio, language="es-ES")
        print(f"Dijiste: {texto}")
        return texto
    except sr.UnknownValueError:
        return ""
    except sr.RequestError:
        return ""


def stop_speaking():
    """Detiene cualquier reproducción de voz en curso."""
    # Detener reproducción gTTS/pygame
    try:
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
    except Exception:
        pass

    # Detener pyttsx3 si está activo
    engine = _tts_engine
    if engine is not None:
        try:
            engine.stop()
        except Exception:
            pass

    # Avisar al avatar para que detenga animación inmediatamente
    try:
        from avatar import get_avatar
        avatar = get_avatar()
        if avatar is not None and avatar.is_speaking:
            avatar.stop_speaking()
    except Exception:
        pass
