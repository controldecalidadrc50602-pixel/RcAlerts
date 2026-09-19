import sys
import os

# Asegurar que el root del proyecto esté en PYTHONPATH para Vercel
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
