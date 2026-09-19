import os
from datetime import date
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import engine, Base, get_db
from backend.models import Client
from backend import crud

# Crear tablas automáticamente al iniciar (SQLite local o Postgres Supabase)
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Non-blocking DB initialization warning: {e}")

app = FastAPI(
    title="OmniPulse Intelligence Hub API",
    version="1.0.0",
    description="API híbrida para métricas multicanal y análisis de churn"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class VercelPathMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            # Si Vercel reescribe hacia /api/index.py o /index.py, recuperar ruta original
            if path in ("/api/index.py", "/index.py", "/api", "/api/"):
                headers = dict(scope.get("headers", []))
                matched = headers.get(b"x-matched-path", b"").decode("utf-8", errors="replace")
                if matched:
                    scope["path"] = matched
                else:
                    forwarded = headers.get(b"x-forwarded-uri", b"").decode("utf-8", errors="replace")
                    if forwarded:
                        scope["path"] = forwarded.split("?")[0]
        await self.app(scope, receive, send)

app.add_middleware(VercelPathMiddleware)


class IngestClientItem(BaseModel):
    id: Optional[str] = None
    name: str
    website: Optional[str] = "https://sin-web.com"
    industry: Optional[str] = "General"
    focus: Optional[str] = "Atención multicanal"
    sessions: int = 0
    prev_sessions: Optional[int] = 0
    user_msgs: int = 0
    bot_msgs: int = 0
    agent_msgs: int = 0
    templates_sent: int = 0
    templates_delivered: int = 0
    templates_replies: int = 0
    report_date: Optional[str] = None

class MergeClientsRequest(BaseModel):
    source_id: str
    target_id: str


def ensure_tables():
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Warning ensuring tables: {e}")

@app.get("/api/health-db")
@app.get("/health-db")
def health_db(db: Session = Depends(get_db)):
    from backend.database import DATABASE_URL
    from sqlalchemy import text
    try:
        ensure_tables()
        res = db.execute(text("SELECT 1;")).fetchone()
        masked = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL
        return {"status": "ok", "db_connected": True, "target": masked, "test_query": res[0]}
    except Exception as e:
        return {"status": "error", "db_connected": False, "error": str(e)}

@app.get("/api/periods")
@app.get("/periods")
def get_periods_endpoint(db: Session = Depends(get_db)):
    try:
        ensure_tables()
        return crud.get_available_periods(db)
    except Exception as e:
        return []

@app.get("/api/alerts")
@app.get("/alerts")
def get_alerts_endpoint(db: Session = Depends(get_db)):
    try:
        ensure_tables()
        return crud.compute_smart_alerts(db)
    except Exception as e:
        return []

# Rutas API (Dual Decorator para compatibilidad local y Vercel rewrites)
@app.get("/api/clients")
@app.get("/clients")
def get_clients(period: Optional[str] = None, seed_demo: bool = False, db: Session = Depends(get_db)):
    try:
        return crud.get_clients_with_latest_metric(db, period=period)
    except Exception as err:
        print(f"Retrying get_clients after ensuring tables: {err}")
        try:
            ensure_tables()
            return crud.get_clients_with_latest_metric(db, period=period)
        except Exception as err2:
            print(f"Database error in get_clients: {err2}")
            return []

@app.get("/api/clients/{client_id}/history")
@app.get("/clients/{client_id}/history")
def get_client_history_endpoint(client_id: str, db: Session = Depends(get_db)):
    try:
        ensure_tables()
        history = crud.get_client_history(db, client_id)
        if not history:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        return history
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/clients/{client_id}")
@app.delete("/clients/{client_id}")
def delete_client(client_id: str, db: Session = Depends(get_db)):
    try:
        deleted = crud.delete_client(db, client_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        return {"status": "deleted", "client_id": client_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/clients/merge")
@app.post("/clients/merge")
def merge_clients_endpoint(req: MergeClientsRequest, db: Session = Depends(get_db)):
    try:
        ensure_tables()
        success = crud.merge_clients(db, req.source_id, req.target_id)
        if not success:
            raise HTTPException(status_code=404, detail="Uno o ambos clientes no existen")
        return {"status": "ok", "message": f"Cliente {req.source_id} fusionado exitosamente en {req.target_id}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/clear-db")
@app.post("/clear-db")
def clear_database(db: Session = Depends(get_db)):
    try:
        ensure_tables()
        crud.clear_all_data(db)
        return {"status": "cleared", "message": "Base de datos vaciada con éxito. Lista para datos reales."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ingest")
@app.post("/ingest")
def ingest_clients(items: List[IngestClientItem], db: Session = Depends(get_db)):
    try:
        ensure_tables()
        processed = []
        for item in items:
            raw_dict = item.model_dump()
            rep_date = date.fromisoformat(item.report_date) if item.report_date else date.today()
            client = crud.upsert_client_and_metric(db, raw_dict, report_date=rep_date)
            processed.append(client.id)
        return {"status": "ok", "ingested_count": len(processed), "client_ids": processed}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en ingesta: {str(e)}")


@app.post("/api/seed-demo")
@app.post("/seed-demo")
def reset_to_demo(db: Session = Depends(get_db)):
    crud.clear_all_data(db)
    crud.seed_demo_data(db)
    return {"status": "demo_loaded", "clients": crud.get_clients_with_latest_metric(db)}

@app.get("/api/export/markdown")
@app.get("/export/markdown")
def export_markdown(db: Session = Depends(get_db)):
    clients = crud.get_clients_with_latest_metric(db)
    today = date.today().isoformat()
    total_sessions = sum(c["sessions"] for c in clients)
    total_msgs = sum(c["user_msgs"] + c["bot_msgs"] + c["agent_msgs"] for c in clients)
    avg_auto = (sum(c["auto_ratio"] for c in clients) / len(clients)) if clients else 0

    md = f"# REPORTE CONSOLIDADO SEMANAL MULTICANAL - {today}\n\n"
    md += "> Base cuantitativa estructurada para ingesta en Gemini NotebookLM.\n\n"
    md += "## RESUMEN DE LA CARTERA\n"
    md += f"- Clientes Monitoreados: {len(clients)}\n"
    md += f"- Sesiones Totales: {total_sessions:,}\n"
    md += f"- Mensajes Totales: {total_msgs:,}\n"
    md += f"- Automatización Media: {avg_auto:.1f}%\n\n---\n\n"

    for c in clients:
        tag = "🔴 ALERTA ROJA (CHURN)" if c["status"] == "red" else ("🟡 ALERTA AMARILLA" if c["status"] == "yellow" else "🟢 SALUDABLE")
        md += f"### {c['name']} ({c['id']}) | {tag}\n"
        md += f"- Web: {c['website']} | Giro: {c['industry']}\n"
        md += f"- Sesiones: {c['sessions']:,} (WoW: {c['session_delta']:.1f}%)\n"
        md += f"- Mensajes: Usuario: {c['user_msgs']:,} | Bot: {c['bot_msgs']:,} | Agente: {c['agent_msgs']:,}\n"
        md += f"- Automatización: {c['auto_ratio']:.1f}%\n"
        md += f"- Plantillas: Env: {c['templates_sent']:,} | Entregadas: {c['templates_delivered']:,} | Respuestas: {c['templates_replies']:,} ({c['reply_rate']:.1f}%)\n"
        md += "#### Hallazgos Clave:\n"
        for issue in c["issues"]:
            md += f"- {issue}\n"
        md += "\n---\n\n"

    return PlainTextResponse(md, media_type="text/markdown")

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return PlainTextResponse("", status_code=204)

# Servir Frontend
BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, "static")
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def serve_index():
    for folder in [STATIC_DIR, PUBLIC_DIR]:
        index_file = os.path.join(folder, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
    return {"message": "OmniPulse Backend Running. Static index.html not found."}

