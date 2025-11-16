# main.py
from scheduler import run_scheduler
from tray import start_tray
from voice import hablar
import time
import sys
import os


def main():
    print("=" * 60)
    print("Iniciando Asistente de Escritorio")
    print("=" * 60)
    
    # Iniciar scheduler (comprobador residente)
    print("\n1. Iniciando scheduler de recordatorios...")
    run_scheduler(poll_interval=20)  # comprueba cada 20s
    print("   ✓ Scheduler iniciado (comprueba cada 20 segundos)")

    # Iniciar icono de bandeja
    print("\n2. Iniciando icono en la bandeja del sistema...")
    icon = start_tray()
    print("   ✓ Icono iniciado en la bandeja")
    print("\n   → Busca el icono en tu bandeja del sistema (área de notificaciones)")
    print("   → Haz CLIC DERECHO en el icono para ver el menú")
    print("   → Opciones disponibles:")
    print("     • Abrir Asistente - Ver y gestionar recordatorios")
    print("     • Configurar Voz - Cambiar motor de voz (Google TTS o pyttsx3)")
    print("     • Añadir Recordatorio de Prueba - Prueba rápida")
    print("     • Probar Voz - Escuchar la voz actual")
    print("     • Salir - Cerrar la aplicación")

    # Mensaje de bienvenida (voz) después de un breve delay
    time.sleep(2)
    print("\n3. Reproduciendo mensaje de bienvenida...")
    nombre_usuario = os.getenv("USER") or os.getenv("USERNAME") or "Usuario"
    hablar(f"Asistente iniciado. Hola {nombre_usuario}, usa el icono de la bandeja para configurar este asistente.")
    
    print("\n" + "=" * 60)
    print("✓ Asistente funcionando en segundo plano")
    print("  Presiona Ctrl+C para detener el programa")
    print("=" * 60 + "\n")

    # Mantener el proceso vivo
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n")
        print("=" * 60)
        print("🛑 Cerrando Asistente de Escritorio...")
        print("=" * 60)
        print("\n✓ Aplicación cerrada correctamente")
        print("  Todos los recordatorios han sido guardados")
        print("  ¡Hasta pronto!\n")
        sys.exit(0)

if __name__ == "__main__":
    main()
