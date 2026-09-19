import sys
import os
import time
import socket
import webbrowser
import threading
import uvicorn

# Si corre empaquetado por PyInstaller, ajustar ruta al directorio temporal
if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS
    os.chdir(os.path.dirname(sys.executable))
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, base_dir)

from main import app

def find_free_port(start_port=8000, max_attempts=50):
    """Busca automáticamente un puerto libre a partir de start_port."""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start_port

def open_browser(port):
    time.sleep(1.2)
    url = f"http://127.0.0.1:{port}"
    print(f"\n[OmniPulse] Abriendo navegador en: {url}")
    webbrowser.open(url)

def run():
    port = find_free_port(8000)
    
    print("=" * 60)
    print("  OMNIPULSE INTELLIGENCE HUB (MODO LOCAL)")
    print(f"  Servidor activo en: http://127.0.0.1:{port}")
    print("  Base de Datos: SQLite local (omnipulse.db)")
    print("  Cierre esta ventana para apagar la aplicación.")
    print("=" * 60)

    # Iniciar apertura automática del navegador en un hilo paralelo
    threading.Thread(target=open_browser, args=(port,), daemon=True).start()

    # Iniciar servidor Uvicorn en el puerto libre detectado
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

if __name__ == "__main__":
    run()
