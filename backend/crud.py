import json
from datetime import date
from sqlalchemy.orm import Session
from backend.models import Client, WeeklyMetric

def compute_health(sessions: int, prev_sessions: int, user_msgs: int, bot_msgs: int, 
                   agent_msgs: int, templates_sent: int, templates_delivered: int, 
                   templates_replies: int):
    total_conv = bot_msgs + agent_msgs
    auto_ratio = (bot_msgs / total_conv * 100.0) if total_conv > 0 else 0.0
    delivery_rate = (templates_delivered / templates_sent * 100.0) if templates_sent > 0 else 0.0
    reply_rate = (templates_replies / templates_delivered * 100.0) if templates_delivered > 0 else 0.0
    session_delta = ((sessions - prev_sessions) / prev_sessions * 100.0) if prev_sessions > 0 else 0.0

    score = 100.0
    status = "green"
    issues = []

    if session_delta <= -20:
        score -= 30.0
        issues.append(f"Caída de sesiones WoW del {abs(session_delta):.1f}%")

    if reply_rate < 3.0 and templates_sent > 100:
        score -= 30.0
        status = "red"
        issues.append(f"Tasa de respuesta en plantillas crítica ({reply_rate:.1f}%). Posible bloqueo o fatiga")
    elif reply_rate < 6.0 and templates_sent > 100:
        score -= 15.0
        issues.append(f"Respuesta de plantillas baja ({reply_rate:.1f}%) vs media del mercado")

    if delivery_rate < 80.0 and templates_sent > 50:
        score -= 20.0
        issues.append(f"Fallas de entrega de plantillas ({delivery_rate:.1f}%). Requerida depuración")

    if auto_ratio > 92.0 and agent_msgs < 50 and user_msgs > 500:
        score -= 25.0
        issues.append(f"Saturación por Bot ({auto_ratio:.0f}%) con abandono de agentes humanos")

    if score < 60.0 or status == "red":
        status = "red"
    elif score < 80.0 or len(issues) > 0:
        status = "yellow"
    else:
        status = "green"

    return {
        "auto_ratio": round(auto_ratio, 2),
        "delivery_rate": round(delivery_rate, 2),
        "reply_rate": round(reply_rate, 2),
        "session_delta": round(session_delta, 2),
        "churn_score": max(0.0, round(score, 2)),
        "status": status,
        "issues": issues if issues else ["Actividad saludable"]
    }

def upsert_client_and_metric(db: Session, data: dict, report_date: date = None):
    if not report_date:
        report_date = date.today()

    client_id = str(data.get("id", "")).strip()
    name = str(data.get("name", "")).strip()

    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        client = db.query(Client).filter(Client.name == name).first()

    if not client:
        client = Client(
            id=client_id,
            name=name,
            website=data.get("website", "https://sin-web.com"),
            industry=data.get("industry", "General"),
            focus=data.get("focus", "Atención multicanal")
        )
        db.add(client)
        db.flush()
    else:
        if data.get("website"): client.website = data["website"]
        if data.get("industry"): client.industry = data["industry"]
        if data.get("focus"): client.focus = data["focus"]

    sessions = int(data.get("sessions", 0))
    prev_sessions = int(data.get("prev_sessions", sessions))
    user_msgs = int(data.get("user_msgs", 0))
    bot_msgs = int(data.get("bot_msgs", 0))
    agent_msgs = int(data.get("agent_msgs", 0))
    templates_sent = int(data.get("templates_sent", 0))
    templates_delivered = int(data.get("templates_delivered", 0))
    templates_replies = int(data.get("templates_replies", 0))

    health = compute_health(
        sessions=sessions, prev_sessions=prev_sessions,
        user_msgs=user_msgs, bot_msgs=bot_msgs, agent_msgs=agent_msgs,
        templates_sent=templates_sent, templates_delivered=templates_delivered,
        templates_replies=templates_replies
    )

    # Buscar si ya existe métrica para este cliente en esta fecha
    metric = db.query(WeeklyMetric).filter(
        WeeklyMetric.client_id == client.id,
        WeeklyMetric.report_date == report_date
    ).first()

    if not metric:
        metric = WeeklyMetric(
            client_id=client.id,
            report_date=report_date
        )
        db.add(metric)

    metric.sessions = sessions
    metric.prev_sessions = prev_sessions
    metric.user_msgs = user_msgs
    metric.bot_msgs = bot_msgs
    metric.agent_msgs = agent_msgs
    metric.templates_sent = templates_sent
    metric.templates_delivered = templates_delivered
    metric.templates_replies = templates_replies

    metric.auto_ratio = health["auto_ratio"]
    metric.delivery_rate = health["delivery_rate"]
    metric.reply_rate = health["reply_rate"]
    metric.session_delta = health["session_delta"]
    metric.churn_score = health["churn_score"]
    metric.status = health["status"]
    metric.issues = json.dumps(health["issues"], ensure_ascii=False)

    db.commit()
    db.refresh(client)
    return client

def delete_client(db: Session, client_id: str):
    client = db.query(Client).filter(Client.id == client_id).first()
    if client:
        db.delete(client)
        db.commit()
        return True
    return False

def clear_all_data(db: Session):
    db.query(WeeklyMetric).delete()
    db.query(Client).delete()
    db.commit()
    return True

def get_clients_with_latest_metric(db: Session):
    clients = db.query(Client).all()
    if not clients:
        return []

    # Totales de cartera para Análisis Vertical
    portfolio_total_sessions = 0
    portfolio_total_msgs = 0

    temp_list = []
    for c in clients:
        latest = c.metrics[0] if c.metrics else None
        sessions = latest.sessions if latest else 0
        user_msgs = latest.user_msgs if latest else 0
        bot_msgs = latest.bot_msgs if latest else 0
        agent_msgs = latest.agent_msgs if latest else 0
        total_msgs = user_msgs + bot_msgs + agent_msgs

        portfolio_total_sessions += sessions
        portfolio_total_msgs += total_msgs

        temp_list.append({
            "client": c,
            "latest": latest,
            "sessions": sessions,
            "user_msgs": user_msgs,
            "bot_msgs": bot_msgs,
            "agent_msgs": agent_msgs,
            "total_msgs": total_msgs
        })

    results = []
    for item in temp_list:
        c = item["client"]
        latest = item["latest"]
        sessions = item["sessions"]
        prev_sessions = latest.prev_sessions if latest else sessions
        user_msgs = item["user_msgs"]
        bot_msgs = item["bot_msgs"]
        agent_msgs = item["agent_msgs"]
        total_msgs = item["total_msgs"]
        templates_sent = latest.templates_sent if latest else 0
        templates_delivered = latest.templates_delivered if latest else 0
        templates_replies = latest.templates_replies if latest else 0

        # Variaciones Horizontales (WoW)
        delta_sessions_abs = sessions - prev_sessions
        delta_sessions_pct = ((sessions - prev_sessions) / prev_sessions * 100.0) if prev_sessions > 0 else 0.0

        # Análisis Vertical Interno (% de cada canal en la cuenta)
        share_bot = (bot_msgs / total_msgs * 100.0) if total_msgs > 0 else 0.0
        share_agent = (agent_msgs / total_msgs * 100.0) if total_msgs > 0 else 0.0
        share_user = (user_msgs / total_msgs * 100.0) if total_msgs > 0 else 0.0

        # Análisis Vertical de Cartera (% de participación del cliente en la cartera global)
        portfolio_share_sessions = (sessions / portfolio_total_sessions * 100.0) if portfolio_total_sessions > 0 else 0.0
        portfolio_share_msgs = (total_msgs / portfolio_total_msgs * 100.0) if portfolio_total_msgs > 0 else 0.0

        issues = json.loads(latest.issues) if latest and latest.issues else ["Sin métricas"]

        results.append({
            "id": c.id,
            "name": c.name,
            "website": c.website,
            "industry": c.industry,
            "focus": c.focus,
            
            # Volumetría
            "sessions": sessions,
            "prev_sessions": prev_sessions,
            "user_msgs": user_msgs,
            "bot_msgs": bot_msgs,
            "agent_msgs": agent_msgs,
            "total_msgs": total_msgs,
            "templates_sent": templates_sent,
            "templates_delivered": templates_delivered,
            "templates_replies": templates_replies,

            # Ratios de Eficiencia
            "auto_ratio": latest.auto_ratio if latest else 0.0,
            "delivery_rate": latest.delivery_rate if latest else 0.0,
            "reply_rate": latest.reply_rate if latest else 0.0,
            "churn_score": latest.churn_score if latest else 100.0,
            "status": latest.status if latest else "green",
            "issues": issues,

            # Análisis Horizontal (Evolución Temporal)
            "delta_sessions_abs": delta_sessions_abs,
            "delta_sessions_pct": round(delta_sessions_pct, 1),
            
            # Análisis Vertical Interno (Estructura de la Cuenta)
            "share_bot": round(share_bot, 1),
            "share_agent": round(share_agent, 1),
            "share_user": round(share_user, 1),

            # Análisis Vertical de Cartera (Peso relativo del cliente)
            "portfolio_share_sessions": round(portfolio_share_sessions, 1),
            "portfolio_share_msgs": round(portfolio_share_msgs, 1),

            "report_date": str(latest.report_date) if latest else str(date.today())
        })

    return results

def seed_demo_data(db: Session):
    demo_clients = [
        {
            "id": "CLI-01", "name": "Clínica Dental Sonrisas",
            "website": "https://clinicasonrisas.com", "industry": "Salud y Citas Médicas",
            "focus": "Agendamiento 24/7 y recordatorios", "sessions": 1420, "prev_sessions": 1400,
            "user_msgs": 4890, "bot_msgs": 4120, "agent_msgs": 980,
            "templates_sent": 1600, "templates_delivered": 1540, "templates_replies": 245
        },
        {
            "id": "CLI-02", "name": "Moda Express E-commerce",
            "website": "https://modaexpress.shop", "industry": "Retail / Ropa Femenina",
            "focus": "Lanzamientos de catálogo e impulso de compras", "sessions": 2890, "prev_sessions": 3900,
            "user_msgs": 11200, "bot_msgs": 4200, "agent_msgs": 7600,
            "templates_sent": 6500, "templates_delivered": 5900, "templates_replies": 110
        },
        {
            "id": "CLI-03", "name": "Inmobiliaria Hábitat Prime",
            "website": "https://habitatprime.com", "industry": "Bienes Raíces / Asesoría",
            "focus": "Captura de leads cualificados de alto ticket", "sessions": 420, "prev_sessions": 400,
            "user_msgs": 1850, "bot_msgs": 650, "agent_msgs": 1400,
            "templates_sent": 300, "templates_delivered": 290, "templates_replies": 48
        },
        {
            "id": "CLI-04", "name": "AutoPartes del Norte",
            "website": "https://autopartesnorte.com", "industry": "Repuestos y B2B",
            "focus": "Cotizaciones técnicas por agentes humanos", "sessions": 980, "prev_sessions": 1300,
            "user_msgs": 3100, "bot_msgs": 2800, "agent_msgs": 40,
            "templates_sent": 800, "templates_delivered": 620, "templates_replies": 15
        },
        {
            "id": "CLI-05", "name": "Academia Idiomas Global",
            "website": "https://idiomasglobal.edu", "industry": "Educación Online",
            "focus": "Atención a postulantes y soporte escolar", "sessions": 2150, "prev_sessions": 1950,
            "user_msgs": 7200, "bot_msgs": 4900, "agent_msgs": 2600,
            "templates_sent": 2200, "templates_delivered": 2100, "templates_replies": 360
        }
    ]
    for d in demo_clients:
        upsert_client_and_metric(db, d)
