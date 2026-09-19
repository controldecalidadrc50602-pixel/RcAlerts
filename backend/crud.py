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

    # 5 Niveles Oficiales de Calidad Corporativa
    if score < 60.0 or status == "red":
        status = "critico"       # 0 - 59: Crítico (Rojo)
    elif score < 70.0:
        status = "desarrollo"    # 60 - 69: En Desarrollo (Naranja)
    elif score < 80.0 or len(issues) > 0:
        status = "aceptable"     # 70 - 79: Aceptable (Amarillo)
    elif score < 90.0:
        status = "optimo"        # 80 - 89: Óptimo (Verde)
    else:
        status = "sobresaliente" # 90 - 100: Sobresaliente (Verde Oscuro)

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

    # Buscar métrica existente para este cliente en esta fecha o la última registrada
    metric = db.query(WeeklyMetric).filter(
        WeeklyMetric.client_id == client.id,
        WeeklyMetric.report_date == report_date
    ).first()

    existing_metric = metric or db.query(WeeklyMetric).filter(WeeklyMetric.client_id == client.id).order_by(WeeklyMetric.report_date.desc()).first()

    # Consolidación no-destructiva: si vienen sesiones en 0 pero ya había sesiones registradas, conservarlas
    if sessions == 0 and existing_metric and existing_metric.sessions > 0:
        sessions = existing_metric.sessions
        prev_sessions = existing_metric.prev_sessions
        user_msgs = existing_metric.user_msgs
        bot_msgs = existing_metric.bot_msgs
        agent_msgs = existing_metric.agent_msgs

    # Si vienen plantillas en 0 pero ya había plantillas registradas, conservarlas
    if templates_sent == 0 and existing_metric and existing_metric.templates_sent > 0:
        templates_sent = existing_metric.templates_sent
        templates_delivered = existing_metric.templates_delivered
        templates_replies = existing_metric.templates_replies

    health = compute_health(
        sessions=sessions, prev_sessions=prev_sessions,
        user_msgs=user_msgs, bot_msgs=bot_msgs, agent_msgs=agent_msgs,
        templates_sent=templates_sent, templates_delivered=templates_delivered,
        templates_replies=templates_replies
    )

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

def merge_clients(db: Session, source_id: str, target_id: str):
    target = db.query(Client).filter(Client.id == target_id).first()
    source = db.query(Client).filter(Client.id == source_id).first()
    if not target or not source:
        return False

    # Obtener las métricas más recientes de ambos
    target_metric = db.query(WeeklyMetric).filter(WeeklyMetric.client_id == target_id).order_by(WeeklyMetric.report_date.desc()).first()
    source_metric = db.query(WeeklyMetric).filter(WeeklyMetric.client_id == source_id).order_by(WeeklyMetric.report_date.desc()).first()

    if source_metric:
        if not target_metric:
            source_metric.client_id = target_id
        else:
            # Fusionar plantillas si source las tiene y target no
            if source_metric.templates_sent > 0 and target_metric.templates_sent == 0:
                target_metric.templates_sent = source_metric.templates_sent
                target_metric.templates_delivered = source_metric.templates_delivered
                target_metric.templates_replies = source_metric.templates_replies
            # Fusionar sesiones si source las tiene y target no
            if source_metric.sessions > 0 and target_metric.sessions == 0:
                target_metric.sessions = source_metric.sessions
                target_metric.prev_sessions = source_metric.prev_sessions
                target_metric.user_msgs = source_metric.user_msgs
                target_metric.bot_msgs = source_metric.bot_msgs
                target_metric.agent_msgs = source_metric.agent_msgs

            health = compute_health(
                sessions=target_metric.sessions, prev_sessions=target_metric.prev_sessions,
                user_msgs=target_metric.user_msgs, bot_msgs=target_metric.bot_msgs, agent_msgs=target_metric.agent_msgs,
                templates_sent=target_metric.templates_sent, templates_delivered=target_metric.templates_delivered,
                templates_replies=target_metric.templates_replies
            )
            target_metric.auto_ratio = health["auto_ratio"]
            target_metric.delivery_rate = health["delivery_rate"]
            target_metric.reply_rate = health["reply_rate"]
            target_metric.churn_score = health["churn_score"]
            target_metric.status = health["status"]
            target_metric.issues = json.dumps(health["issues"], ensure_ascii=False)

    # Eliminar métricas restantes de source y eliminar source client
    db.query(WeeklyMetric).filter(WeeklyMetric.client_id == source_id).delete()
    db.delete(source)
    db.commit()
    return True

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

def get_available_periods(db: Session):
    dates = db.query(WeeklyMetric.report_date).distinct().order_by(WeeklyMetric.report_date.desc()).all()
    return [str(d[0]) for d in dates if d[0]]

def get_clients_with_latest_metric(db: Session, period: str = None):
    clients = db.query(Client).all()
    if not clients:
        return []

    # Totales de cartera para Análisis Vertical
    portfolio_total_sessions = 0
    portfolio_total_msgs = 0

    temp_list = []
    if period == "all":
        # Desglose histórico multimes: incluir todas las métricas de todos los clientes
        for c in clients:
            m_sorted = sorted(c.metrics, key=lambda x: x.report_date)
            for idx, m in enumerate(m_sorted):
                sessions = m.sessions or 0
                prev_m = m_sorted[idx - 1] if idx > 0 else None
                prev_sessions = prev_m.sessions if prev_m else (m.prev_sessions or sessions)
                user_msgs = m.user_msgs or 0
                bot_msgs = m.bot_msgs or 0
                agent_msgs = m.agent_msgs or 0
                total_msgs = user_msgs + bot_msgs + agent_msgs

                portfolio_total_sessions += sessions
                portfolio_total_msgs += total_msgs

                temp_list.append({
                    "client": c,
                    "metric": m,
                    "sessions": sessions,
                    "prev_sessions": prev_sessions,
                    "user_msgs": user_msgs,
                    "bot_msgs": bot_msgs,
                    "agent_msgs": agent_msgs,
                    "total_msgs": total_msgs
                })
    else:
        for c in clients:
            target_metric = None
            if period:
                for m in c.metrics:
                    if str(m.report_date) == period or str(m.report_date).startswith(period):
                        target_metric = m
                        break
            if not target_metric:
                target_metric = c.metrics[0] if c.metrics else None

            sessions = target_metric.sessions if target_metric else 0
            user_msgs = target_metric.user_msgs if target_metric else 0
            bot_msgs = target_metric.bot_msgs if target_metric else 0
            agent_msgs = target_metric.agent_msgs if target_metric else 0
            total_msgs = user_msgs + bot_msgs + agent_msgs

            portfolio_total_sessions += sessions
            portfolio_total_msgs += total_msgs

            temp_list.append({
                "client": c,
                "metric": target_metric,
                "sessions": sessions,
                "prev_sessions": target_metric.prev_sessions if target_metric else sessions,
                "user_msgs": user_msgs,
                "bot_msgs": bot_msgs,
                "agent_msgs": agent_msgs,
                "total_msgs": total_msgs
            })

    results = []
    for item in temp_list:
        c = item["client"]
        m = item["metric"]
        sessions = item["sessions"]
        prev_sessions = m.prev_sessions if m else sessions
        user_msgs = item["user_msgs"]
        bot_msgs = item["bot_msgs"]
        agent_msgs = item["agent_msgs"]
        total_msgs = item["total_msgs"]
        templates_sent = m.templates_sent if m else 0
        templates_delivered = m.templates_delivered if m else 0
        templates_replies = m.templates_replies if m else 0

        # Variaciones Horizontales (WoW / MoM)
        delta_sessions_abs = sessions - prev_sessions
        delta_sessions_pct = ((sessions - prev_sessions) / prev_sessions * 100.0) if prev_sessions > 0 else 0.0

        # Análisis Vertical Interno
        share_bot = (bot_msgs / total_msgs * 100.0) if total_msgs > 0 else 0.0
        share_agent = (agent_msgs / total_msgs * 100.0) if total_msgs > 0 else 0.0
        share_user = (user_msgs / total_msgs * 100.0) if total_msgs > 0 else 0.0

        # Análisis Vertical de Cartera
        portfolio_share_sessions = (sessions / portfolio_total_sessions * 100.0) if portfolio_total_sessions > 0 else 0.0
        portfolio_share_msgs = (total_msgs / portfolio_total_msgs * 100.0) if portfolio_total_msgs > 0 else 0.0

        issues = json.loads(m.issues) if m and m.issues else ["Sin métricas"]

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
            "auto_ratio": m.auto_ratio if m else 0.0,
            "delivery_rate": m.delivery_rate if m else 0.0,
            "reply_rate": m.reply_rate if m else 0.0,
            "churn_score": m.churn_score if m else 100.0,
            "status": m.status if m else "green",
            "issues": issues,

            # Deltas Calculadas
            "delta_sessions_abs": delta_sessions_abs,
            "delta_sessions_pct": round(delta_sessions_pct, 1),

            # Mix Canales
            "share_bot": round(share_bot, 1),
            "share_agent": round(share_agent, 1),
            "share_user": round(share_user, 1),

            # Análisis Vertical de Cartera
            "portfolio_share_sessions": round(portfolio_share_sessions, 1),
            "portfolio_share_msgs": round(portfolio_share_msgs, 1),

            "report_date": str(m.report_date) if m else str(date.today()),
            "available_dates": [str(x.report_date) for x in c.metrics]
        })

    return results

def get_portfolio_history(db: Session):
    """
    Retorna la serie cronológica consolidada de toda la cartera agrupada por report_date
    """
    from collections import defaultdict
    metrics = db.query(WeeklyMetric).order_by(WeeklyMetric.report_date.asc()).all()
    if not metrics:
        return []
        
    by_date = defaultdict(lambda: {
        "report_date": "",
        "sessions": 0,
        "user_msgs": 0,
        "bot_msgs": 0,
        "agent_msgs": 0,
        "total_msgs": 0,
        "templates_sent": 0,
        "templates_delivered": 0,
        "templates_replies": 0,
        "clients_count": 0
    })
    
    for m in metrics:
        d_str = str(m.report_date)
        entry = by_date[d_str]
        entry["report_date"] = d_str
        entry["sessions"] += m.sessions or 0
        entry["user_msgs"] += m.user_msgs or 0
        entry["bot_msgs"] += m.bot_msgs or 0
        entry["agent_msgs"] += m.agent_msgs or 0
        entry["total_msgs"] += (m.user_msgs or 0) + (m.bot_msgs or 0) + (m.agent_msgs or 0)
        entry["templates_sent"] += m.templates_sent or 0
        entry["templates_delivered"] += m.templates_delivered or 0
        entry["templates_replies"] += m.templates_replies or 0
        entry["clients_count"] += 1

    history = sorted(by_date.values(), key=lambda x: x["report_date"])
    for idx, item in enumerate(history):
        prev = history[idx - 1] if idx > 0 else None
        item["mom_sessions_abs"] = (item["sessions"] - prev["sessions"]) if prev else 0
        item["mom_sessions_pct"] = round(((item["mom_sessions_abs"] / prev["sessions"]) * 100.0), 1) if prev and prev["sessions"] > 0 else 0.0
        tot_repl = item["templates_replies"]
        tot_deliv = item["templates_delivered"]
        item["reply_rate"] = round((tot_repl / tot_deliv * 100.0), 1) if tot_deliv > 0 else 0.0
        tot_conv = item["bot_msgs"] + item["agent_msgs"]
        item["auto_ratio"] = round((item["bot_msgs"] / tot_conv * 100.0), 1) if tot_conv > 0 else 0.0

    return history

def get_client_history(db: Session, client_id: str):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        return None

    # Métricas ordenadas cronológicamente de más antigua a más reciente
    metrics_sorted = sorted(client.metrics, key=lambda m: m.report_date)
    history = []
    for idx, m in enumerate(metrics_sorted):
        total_msgs = m.user_msgs + m.bot_msgs + m.agent_msgs
        prev_m = metrics_sorted[idx - 1] if idx > 0 else None
        
        # Variación MoM de sesiones
        mom_sessions_abs = (m.sessions - prev_m.sessions) if prev_m else (m.sessions - m.prev_sessions)
        mom_sessions_pct = ((mom_sessions_abs / prev_m.sessions) * 100.0) if prev_m and prev_m.sessions > 0 else 0.0

        # Variación MoM de respuesta de plantillas
        mom_reply_pct = (m.reply_rate - prev_m.reply_rate) if prev_m else 0.0

        history.append({
            "report_date": str(m.report_date),
            "sessions": m.sessions,
            "prev_sessions": m.prev_sessions,
            "mom_sessions_abs": mom_sessions_abs,
            "mom_sessions_pct": round(mom_sessions_pct, 1),
            "user_msgs": m.user_msgs,
            "bot_msgs": m.bot_msgs,
            "agent_msgs": m.agent_msgs,
            "total_msgs": total_msgs,
            "auto_ratio": m.auto_ratio,
            "templates_sent": m.templates_sent,
            "templates_delivered": m.templates_delivered,
            "templates_replies": m.templates_replies,
            "delivery_rate": m.delivery_rate,
            "reply_rate": m.reply_rate,
            "mom_reply_pct": round(mom_reply_pct, 1),
            "status": m.status,
            "churn_score": m.churn_score,
            "issues": json.loads(m.issues) if m.issues else []
        })

    return {
        "client": {
            "id": client.id,
            "name": client.name,
            "website": client.website,
            "industry": client.industry,
            "focus": client.focus
        },
        "history": history
    }

def compute_smart_alerts(db: Session):
    clients = db.query(Client).all()
    alerts = []

    for c in clients:
        metrics = sorted(c.metrics, key=lambda m: m.report_date, reverse=True)
        if not metrics:
            continue

        latest = metrics[0]
        prev = metrics[1] if len(metrics) > 1 else None

        # Alerta 1: Desplome crítico en conversión de plantillas MoM
        if prev and prev.reply_rate > 10.0 and latest.reply_rate < 6.0:
            drop_relative = ((latest.reply_rate - prev.reply_rate) / prev.reply_rate) * 100.0
            alerts.append({
                "id": f"alert-hsm-drop-{c.id}-{latest.report_date}",
                "level": "critical",
                "client_id": c.id,
                "client_name": c.name,
                "period": str(latest.report_date),
                "title": f"Desplome Crítico en Respuestas de Plantillas WhatsApp ({drop_relative:.1f}%)",
                "detail": f"La tasa de respuesta cayó de {prev.reply_rate:.1f}% ({prev.templates_replies} respuestas) a {latest.reply_rate:.1f}% ({latest.templates_replies} respuestas) este mes.",
                "action": "Auditar copy de plantilla reciente, verificar si cambió el público objetivo o segmentar base para evitar fatiga de números."
            })
        elif latest.reply_rate < 5.0 and latest.templates_sent > 100:
            alerts.append({
                "id": f"alert-hsm-low-{c.id}-{latest.report_date}",
                "level": "warning",
                "client_id": c.id,
                "client_name": c.name,
                "period": str(latest.report_date),
                "title": f"Efectividad de Plantillas por debajo de Benchmark ({latest.reply_rate:.1f}%)",
                "detail": f"Solo {latest.templates_replies} respuestas de {latest.templates_delivered} entregadas (esperado >10%).",
                "action": "Incorporar llamadas a la acción (CTA) con botones interactivos de respuesta rápida."
            })

        # Alerta 2: Caída de sesiones MoM
        if prev and latest.sessions < prev.sessions:
            sess_drop = ((latest.sessions - prev.sessions) / prev.sessions) * 100.0
            if sess_drop <= -15.0:
                alerts.append({
                    "id": f"alert-sess-drop-{c.id}-{latest.report_date}",
                    "level": "critical",
                    "client_id": c.id,
                    "client_name": c.name,
                    "period": str(latest.report_date),
                    "title": f"Caída Alarmante de Tráfico Inbound ({sess_drop:.1f}%)",
                    "detail": f"Las sesiones cayeron de {prev.sessions:,} a {latest.sessions:,} ({sess_drop:.1f}%). Riesgo de churn contractual.",
                    "action": "Contactar al cliente para revisar si se apagaron campañas de marketing o hubo cambios en el sitio web."
                })

        # Alerta 3: Sobrecarga en agentes humanos
        if latest.share_agent if hasattr(latest, 'share_agent') else False:
            pass
        total_conv = latest.bot_msgs + latest.agent_msgs
        if total_conv > 100:
            human_share = (latest.agent_msgs / total_conv) * 100.0
            if human_share > 65.0:
                alerts.append({
                    "id": f"alert-human-overload-{c.id}-{latest.report_date}",
                    "level": "warning",
                    "client_id": c.id,
                    "client_name": c.name,
                    "period": str(latest.report_date),
                    "title": f"Sobrecarga de Agentes Humanos ({human_share:.0f}%)",
                    "detail": f"Los agentes humanos están absorbiendo el {human_share:.0f}% del diálogo. El bot solo resuelve el {latest.auto_ratio:.0f}%.",
                    "action": "Revisar motivos de derivación y entrenar intenciones frecuentes en Botmaker para aumentar contención."
                })

    return alerts

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
