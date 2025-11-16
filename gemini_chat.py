# gemini_chat.py
"""
Módulo para integración con Google Gemini API.
Permite mantener conversaciones con el asistente usando IA generativa.
"""
import json
from typing import Any, Optional
from user_storage import get_user_settings_file

try:
    import google.generativeai as genai  # type: ignore
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None  # type: ignore

# Configuración
SETTINGS_FILE = get_user_settings_file()

class GeminiChat:
    """Gestor de conversaciones con Gemini."""
    
    def __init__(self):
        self.model: Any = None
        self.chat: Any = None
        self.conversation_active = False
        self.history = []
        self._load_api_key()
    
    def _load_api_key(self):
        """Carga la API key de Gemini desde settings.json"""
        try:
            if SETTINGS_FILE.exists():
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    api_key = settings.get('gemini_api_key', '')
                    if api_key and GEMINI_AVAILABLE and genai is not None:
                        configure = getattr(genai, "configure", None)
                        model_cls = getattr(genai, "GenerativeModel", None)
                        if callable(configure) and model_cls is not None:
                            configure(api_key=api_key)
                            # Usar el modelo Gemini 2.0 Flash estable
                            self.model = model_cls('gemini-2.0-flash-001')
                            return True
        except Exception as e:
            print(f"Error cargando API key de Gemini: {e}")
        return False
    
    def is_available(self):
        """Verifica si Gemini está disponible y configurado."""
        return GEMINI_AVAILABLE and self.model is not None
    
    def start_conversation(self):
        """Inicia una nueva conversación con Gemini."""
        if not self.is_available():
            return False
        
        try:
            # Iniciar chat con contexto del asistente
            start_chat = getattr(self.model, "start_chat", None)
            if not callable(start_chat):
                return False
            self.chat = start_chat(history=[])
            self.conversation_active = True
            self.history = []
            
            # Mensaje de sistema para dar contexto
            system_prompt = (
                "Eres Neno, un asistente virtual amigable y servicial. "
                "Respondes en español de forma natural, concisa y útil. "
                "Eres parte de un sistema de asistente de escritorio que ayuda con recordatorios y tareas."
            )
            # Enviar contexto inicial (no se mostrará al usuario)
            try:
                if self.chat is not None:
                    send_initial = getattr(self.chat, "send_message", None)
                    if callable(send_initial):
                        send_initial(system_prompt)
            except Exception:
                pass
            
            return True
        except Exception as e:
            print(f"Error iniciando conversación con Gemini: {e}")
            self.conversation_active = False
            return False
    
    def send_message(self, message):
        """
        Envía un mensaje a Gemini y obtiene la respuesta.
        
        Args:
            message: Texto del mensaje del usuario
            
        Returns:
            str: Respuesta de Gemini o mensaje de error
        """
        if not self.is_available():
            return "Lo siento, Gemini no está disponible. Por favor, configura tu API key en Preferencias."
        
        if not self.conversation_active:
            if not self.start_conversation():
                return "No pude iniciar la conversación con Gemini. Verifica tu conexión a internet."
        
        try:
            # Enviar mensaje y obtener respuesta
            if self.chat is None:
                return "No pude hablar con Gemini en este momento."
            send_message = getattr(self.chat, "send_message", None)
            if not callable(send_message):
                return "La conversación de Gemini no está lista todavía."
            response = send_message(message)
            
            # Guardar en historial
            self.history.append({
                'user': message,
                'assistant': getattr(response, 'text', '')
            })
            
            return getattr(response, 'text', '')
            
        except Exception as e:
            error_msg = str(e)
            print(f"Error comunicándose con Gemini: {error_msg}")
            
            # Mensajes de error más amigables
            if "API key" in error_msg or "authentication" in error_msg.lower():
                return "Error de autenticación. Por favor, verifica tu API key de Gemini en Preferencias."
            elif "quota" in error_msg.lower() or "limit" in error_msg.lower():
                return "Has alcanzado el límite de uso de la API. Intenta más tarde o verifica tu cuenta de Google."
            elif "network" in error_msg.lower() or "connection" in error_msg.lower():
                return "Error de conexión. Verifica tu conexión a internet."
            else:
                return f"Lo siento, hubo un error al procesar tu mensaje. Intenta de nuevo."
    
    def end_conversation(self):
        """Finaliza la conversación actual."""
        self.conversation_active = False
        self.chat = None
        return "Conversación finalizada. Fue un placer charlar contigo."
    
    def get_history(self):
        """Obtiene el historial de la conversación actual."""
        return self.history
    
    def clear_history(self):
        """Limpia el historial de conversación."""
        self.history = []
        if self.conversation_active:
            # Reiniciar chat
            self.start_conversation()


# Instancia global del gestor de chat
_gemini_chat = None

def get_gemini_chat():
    """Obtiene la instancia global del gestor de chat con Gemini."""
    global _gemini_chat
    if _gemini_chat is None:
        _gemini_chat = GeminiChat()
    return _gemini_chat


def is_gemini_available():
    """Verifica si Gemini está disponible."""
    return get_gemini_chat().is_available()


def start_gemini_conversation():
    """Inicia una conversación con Gemini."""
    return get_gemini_chat().start_conversation()


def send_gemini_message(message):
    """Envía un mensaje a Gemini."""
    return get_gemini_chat().send_message(message)


def end_gemini_conversation():
    """Finaliza la conversación con Gemini."""
    return get_gemini_chat().end_conversation()
