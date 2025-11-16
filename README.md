# 🖥️ Asistente de Escritorio

Un asistente personal diseñado para ayudarte a gestionar tus recordatorios de forma sencilla con notificaciones por voz.

## ✨ Características

- ✅ **Recordatorios con fecha y hora** (formato español: DD/MM/YYYY HH:MM)
- ✅ **Recordatorios diarios repetitivos**
- ✅ **Historial de conversación por usuario**, con opción de borrado seguro desde la ventana del avatar
- ✅ **Avatar animado** con control por voz, atajos a terminal/editor y búsquedas web con "Neno, ..."
- ✅ **Síntesis de voz natural** con Google TTS (requiere internet)
- ✅ **Síntesis de voz offline** con pyttsx3 (sin internet)
- ✅ **Respuestas locales editables** vía `config/knowledge_base.json` y **modo Gemini** opcional
- ✅ **Icono en la bandeja del sistema** con menú contextual y notificaciones por voz
- ✅ **Configuración independiente por usuario** (voz, recordatorios, historial)
- ✅ **Icono y logo personalizables**

## 🚀 Instalación y Ejecución

### Requisitos previos
```bash
sudo apt-get update
sudo apt-get install -y portaudio19-dev python3-pyaudio python3-tk
```

### Ejecutar la aplicación
```bash
python3 run_app.py
```

El script `run_app.py`:
1. Crea automáticamente un entorno virtual (`.venv`)
2. Instala todas las dependencias necesarias
3. Inicia la aplicación

## 📅 Uso del Asistente

### Formato de Fecha y Hora

El asistente utiliza **formato español**:

- **Fecha completa**: `DD/MM/YYYY HH:MM`
  - Ejemplo: `25/12/2025 14:30`
  
- **Solo hora**: `HH:MM` (asume hoy o mañana si la hora ya pasó)
  - Ejemplo: `14:30`

### Acceder al Asistente

#### Opción 1: Icono en la bandeja del sistema
Busca el icono en tu bandeja del sistema y haz **clic derecho** para ver el menú:
- 📋 **Abrir Asistente** - Gestionar recordatorios
- ⚙️ **Configurar Voz** - Cambiar motor de voz
- ℹ️ **Acerca de** - Información del programa
- ➕ **Añadir Recordatorio de Prueba** - Prueba rápida
- 🔊 **Probar Voz** - Escuchar la voz actual
- ❌ **Salir** - Cerrar la aplicación

#### Opción 2: Desde la terminal
```bash
# Detener la aplicación
Ctrl+C
```

### Configurar la Voz

1. Haz clic en **"⚙️ Configurar Voz"** (en la interfaz o menú del icono)
2. Elige entre:
   - **Google TTS (gTTS)**: Voz natural y clara (requiere internet)
   - **pyttsx3**: Voz offline (robótica, sin internet)
3. Si eliges pyttsx3, puedes seleccionar entre las voces disponibles en tu sistema
4. Haz clic en **"🔊 Probar Voz"** para escuchar
5. Guarda la configuración

### Historial de Conversaciones

- Cada usuario tiene su propio historial en `config/users/<usuario>/conversation_history.json`.
- El avatar carga automáticamente los mensajes recientes al abrirse.
- Usa el botón **"Borrar historial"** en la ventana principal del avatar para eliminar todas las conversaciones (pide confirmación y no se puede deshacer).
- También puedes editar el archivo JSON manualmente si necesitas depurar o migrar información.

## 🎨 Personalización

### Cambiar el Icono de la Bandeja

1. Guarda tu icono como `assets/icon.png`
2. **Tamaño recomendado**: 64x64 o 128x128 píxeles
3. **Formato**: PNG (con transparencia recomendado)
4. Reinicia la aplicación

### Cambiar el Logo (ventana "Acerca de")

1. Guarda tu logo como `assets/logo.png`
2. **Tamaño recomendado**: 256x256 píxeles
3. **Formato**: PNG (con transparencia recomendado)
4. Reinicia la aplicación

## 📁 Estructura del Proyecto

```
Asistente/
├── run_app.py              # Script de inicio (ejecutar este)
├── main.py                 # Aplicación principal
├── gui.py                  # Interfaz gráfica
├── scheduler.py            # Gestión de recordatorios
├── voice.py                # Sistema de voz (TTS)
├── tray.py                 # Icono de la bandeja
├── requirements.txt        # Dependencias
├── assets/
│   ├── icon.png           # Icono de la bandeja (personalizable)
│   ├── logo.png           # Logo para "Acerca de" (personalizable)
│   ├── crear_icono_ejemplo.py
│   └── crear_logo.py
└── config/
  ├── knowledge_base.json   # Respuestas locales personalizadas
  ├── (legacy) settings.json
  ├── (legacy) reminders.json
  └── users/
    └── <tu_usuario>/
      ├── settings.json      # Configuración de voz para ese usuario
      ├── reminders.json     # Recordatorios guardados por usuario
      └── conversation_history.json  # Conversaciones guardadas por usuario
```

## 🔧 Configuración Avanzada

### Archivo `config/users/<usuario>/settings.json`

> Si actualizas desde una versión anterior, el asistente copiará automáticamente tu antiguo `config/settings.json` compartido al directorio correspondiente de tu usuario la primera vez que ejecutes la nueva versión.
```json
{
  "voice_engine": "gtts",      // "gtts" o "pyttsx3"
  "voice_id": null,            // ID de voz para pyttsx3
  "voice_rate": 150,           // Velocidad de habla
  "voice_volume": 1.0          // Volumen (0.0 a 1.0)
}
```

### Archivo `config/users/<usuario>/reminders.json`

> Durante la actualización también se migran los recordatorios existentes desde `config/reminders.json` al directorio del usuario activo para mantener tu historial.
```json
[
  {
    "id": "uuid-aqui",
    "text": "Tomar medicación",
    "when": "13/11/2025 14:30",
    "repeat": null,              // null o "daily"
    "notified": false
  }
]
```

### Archivo `config/knowledge_base.json`

Este archivo es el único punto desde el que el asistente obtiene respuestas locales para preguntas generales (sin tocar archivos ni funciones del sistema). Cada entrada puede incluir varios disparadores:

```json
[
  {
    "triggers": ["quién eres", "quien eres"],
    "answer": "Soy Neno, tu asistente local."
  },
  {
    "keywords": ["capital", "españa"],
    "answer": "La capital de España es Madrid."
  }
]
```

- `triggers`: lista de frases; si el mensaje contiene cualquiera, se usa la respuesta.
- `keywords`: lista de palabras que deben aparecer todas en el mensaje.
- `pattern`: expresión regular opcional para coincidencias avanzadas.
- `question`: coincidencia exacta con la frase completa.

Edita este archivo (sin cambiar su nombre ni ubicación) para añadir tus propias respuestas locales.

### Archivo `config/users/<usuario>/conversation_history.json`

El asistente guarda los últimos 200 mensajes intercambiados con cada usuario en este archivo:

```json
[
  { "role": "Tú", "text": "Recuérdame regar las plantas" },
  { "role": "Asistente", "text": "Listo, te avisaré hoy a las 20:00." }
]
```

- Se actualiza automáticamente cada vez que escribes o el asistente responde.
- Puedes vaciarlo desde el botón **"Borrar historial"** del avatar o eliminar el contenido manualmente.

## 🐛 Solución de Problemas

### Error: "portaudio.h: No existe el archivo"
```bash
sudo apt-get install -y portaudio19-dev python3-pyaudio
```

### No se escucha la voz
1. Verifica que el volumen del sistema esté activado
2. Prueba cambiar el motor de voz en **"⚙️ Configurar Voz"**
3. Para Google TTS, verifica tu conexión a internet

### El icono no aparece en la bandeja
- Asegúrate de tener un gestor de bandeja del sistema instalado
- En GNOME, instala: `gnome-shell-extension-appindicator`

### La aplicación no se cierra con Ctrl+C
- Usa la opción **"❌ Salir"** del menú del icono
- O ejecuta: `pkill -f "python.*main.py"`

## 📝 Ejemplos de Uso

### Recordatorio único
- **Mensaje**: "Reunión con el equipo"
- **Fecha/Hora**: `15/11/2025 10:00`
- **Repetir**: No marcado

### Recordatorio diario
- **Mensaje**: "Tomar vitaminas"
- **Fecha/Hora**: `08:00`
- **Repetir**: ✓ Repetir diariamente

## 🌐 Enlaces

- **GitHub**: https://github.com/sapoclay/neno
- **Documentación**: Ver archivo README.md

## 📜 Licencia

Este proyecto es de código abierto y completamente gratuito.

