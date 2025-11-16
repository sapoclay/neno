# actions.py
import datetime
import platform
import subprocess
from voice import hablar

def ejecutar_accion(comando: str) -> str:
    comando = comando.lower()
    if "hora" in comando:
        ahora = datetime.datetime.now().strftime("%H:%M")
        texto = f"Son las {ahora}"
        hablar(texto)
        return texto
    if "navegador" in comando or "internet" in comando:
        abrir_navegador()
        return "Abriendo navegador..."
    if "salir" in comando:
        hablar("Saliendo.")
        # la app residente debe cerrarse vía menú systray; aquí devolvemos mensaje
        return "Pide cierre desde la bandeja."
    return "No entiendo ese comando."

def abrir_navegador():
    sistema = platform.system()
    try:
        if sistema == "Windows":
            subprocess.run(["start", "https://www.google.com"], shell=True)
        elif sistema == "Darwin":
            subprocess.run(["open", "https://www.google.com"])
        else:
            subprocess.run(["xdg-open", "https://www.google.com"])
    except Exception as e:
        print("Error abriendo navegador:", e)
