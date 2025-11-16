# tray.py
import pystray
from PIL import Image, ImageDraw, ImageFont
import threading
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Ruta al icono personalizado
ICON_PATH = Path(__file__).parent / "assets" / "icon.png"

def _load_custom_icon():
    """Intenta cargar el icono personalizado desde assets/icon.png"""
    if ICON_PATH.exists():
        try:
            img = Image.open(ICON_PATH)
            # Redimensionar si es necesario (tamaño recomendado: 64x64 o 128x128)
            if img.size != (64, 64):
                img = img.resize((64, 64), Image.Resampling.LANCZOS)
            return img
        except Exception as e:
            print(f"Error cargando icono personalizado: {e}")
            return None
    return None

def _create_image(width=64, height=64, color1=(30,144,255), color2=(255,255,255)):
    """Crea un icono simple: círculo con letra A"""
    image = Image.new("RGB", (width, height), color1)
    draw = ImageDraw.Draw(image)
    
    # Dibujar círculo
    draw.ellipse((2, 2, width-2, height-2), fill=color1, outline=color2, width=3)
    
    # Dibujar texto "A" en el centro
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
    except:
        font = ImageFont.load_default()
    
    # Centrar el texto
    bbox = draw.textbbox((0, 0), "A", font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    position = ((width - text_width) // 2, (height - text_height) // 2 - 5)
    
    draw.text(position, "A", fill=color2, font=font)
    return image

def _open_gui(icon):
    """Abre la interfaz gráfica de recordatorios"""
    from gui import launch_gui
    print("Abriendo interfaz gráfica...")
    # Ejecutar en el hilo principal si es posible, si no, en nuevo hilo
    try:
        launch_gui()
    except Exception as e:
        print(f"Error al abrir GUI: {e}")
        t = threading.Thread(target=launch_gui, daemon=False)
        t.start()

def _open_voice_config(icon):
    """Abre la configuración de voz"""
    from gui import voice_config_window
    print("Abriendo configuración de voz...")
    try:
        voice_config_window()
    except Exception as e:
        print(f"Error al abrir configuración de voz: {e}")
        t = threading.Thread(target=voice_config_window, daemon=False)
        t.start()

def _add_sample_reminder(icon, item):
    """Añade un recordatorio de prueba para dentro de 1 minuto"""
    from scheduler import add_reminder
    from voice import hablar
    try:
        # Formato español: DD/MM/YYYY HH:MM
        when_dt = (datetime.now() + timedelta(minutes=1)).replace(second=0, microsecond=0)
        when = when_dt.strftime("%d/%m/%Y %H:%M")
        add_reminder("Recordatorio de prueba: ¡Hola!", when)
        hablar("Recordatorio de prueba añadido para dentro de un minuto.")
        print(f"Recordatorio de prueba añadido para: {when}")
    except Exception as e:
        print(f"Error al añadir recordatorio: {e}")

def _test_voice(icon, item):
    """Prueba la voz actual"""
    from voice import hablar
    hablar("Hola, esta es una prueba de voz del asistente.")
    print("Probando voz...")

def _open_about(icon):
    """Abre la ventana Acerca de"""
    from gui import about_window
    print("Abriendo ventana Acerca de...")
    try:
        about_window()
    except Exception as e:
        print(f"Error al abrir ventana Acerca de: {e}")
        t = threading.Thread(target=about_window, daemon=False)
        t.start()

def _toggle_avatar(icon):
    """Muestra/oculta el avatar"""
    from gui import show_avatar_window
    print("Mostrando ventana del avatar...")
    try:
        show_avatar_window()
    except Exception as e:
        print(f"Error al mostrar avatar: {e}")
        t = threading.Thread(target=show_avatar_window, daemon=False)
        t.start()

def _quit_app(icon, item):
    """Cierra la aplicación"""
    print("Cerrando aplicación...")
    icon.stop()
    sys.exit(0)

def start_tray():
    """Inicia el icono de la bandeja del sistema con menú"""
    # Intentar cargar icono personalizado primero
    image = _load_custom_icon()
    if image is None:
        # Si no hay icono personalizado, usar el generado
        image = _create_image()
        print("Usando icono por defecto (no se encontró assets/icon.png)")
    else:
        print(f"Usando icono personalizado: {ICON_PATH}")
    
    # Crear menú con todas las opciones
    menu = pystray.Menu(
        pystray.MenuItem("📋 Abrir Asistente", _open_gui, default=True),
        pystray.MenuItem("⚙️ Configurar Voz", _open_voice_config),
        pystray.MenuItem("👤 Mostrar/Ocultar Avatar", _toggle_avatar),
        pystray.MenuItem("ℹ️ Acerca de", _open_about),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("➕ Añadir Recordatorio de Prueba", _add_sample_reminder),
        pystray.MenuItem("🔊 Probar Voz", _test_voice),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("❌ Salir", _quit_app)
    )
    
    icon = pystray.Icon("asistente", image, "Asistente de Escritorio", menu)
    
    print("Iniciando icono en la bandeja del sistema...")
    print("Haz clic derecho en el icono para ver el menú")
    
    # Ejecutar en un hilo separado para no bloquear
    def run_icon():
        try:
            icon.run()
        except Exception as e:
            print(f"Error en el icono de la bandeja: {e}")
    
    t = threading.Thread(target=run_icon, daemon=True)
    t.start()
    
    return icon
