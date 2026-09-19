# OmniPulse Intelligence Hub

Plataforma analítica multicanal (CSV & TSV de Botmaker / WhatsApp) para monitoreo de cartera de clientes, detección de riesgo de Churn y generación de reportes cuantitativos estructurados para **NotebookLM**.

## Características
- **Consolidación por Cliente**: Procesa miles de registros de sesiones por cliente y los totaliza automáticamente.
- **Análisis Horizontal**: Variaciones WoW en valor absoluto ($\Delta$) y porcentual ($\% \Delta$).
- **Análisis Vertical**: Estructura de atención (% Bot vs % Agente humano) y concentración en cartera global.
- **Matriz de Cuadrantes**: Gráfica de dispersión interactiva (Automatización vs Conversión a plantillas).
- **Arquitectura Híbrida**: Compatible con SQLite en local y PostgreSQL en la nube (Vercel + Supabase/Neon).

## Estructura
- `backend/`: Capa de datos con SQLAlchemy (`database.py`, `models.py`, `crud.py`).
- `static/`: Frontend interactivo en JavaScript vanilla + Chart.js.
- `main.py`: API REST FastAPI.
- `api/index.py`: Entrypoint serverless para despliegue en Vercel.
- `vercel.json`: Manifiesto de despliegue en la nube.
