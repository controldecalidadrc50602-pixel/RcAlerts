from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Float, Text, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.database import Base

class Client(Base):
    __tablename__ = "clients"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    website = Column(String(255), default="https://sin-web.com")
    industry = Column(String(100), default="General")
    focus = Column(Text, default="Atención multicanal")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relación con sus métricas históricas semanales
    metrics = relationship("WeeklyMetric", back_populates="client", cascade="all, delete-orphan", order_by="desc(WeeklyMetric.report_date)")

class WeeklyMetric(Base):
    __tablename__ = "weekly_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(String(50), ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    report_date = Column(Date, default=date.today, index=True)

    sessions = Column(Integer, default=0)
    prev_sessions = Column(Integer, default=0)
    user_msgs = Column(Integer, default=0)
    bot_msgs = Column(Integer, default=0)
    agent_msgs = Column(Integer, default=0)
    templates_sent = Column(Integer, default=0)
    templates_delivered = Column(Integer, default=0)
    templates_replies = Column(Integer, default=0)

    # Métricas calculadas
    auto_ratio = Column(Float, default=0.0)
    delivery_rate = Column(Float, default=0.0)
    reply_rate = Column(Float, default=0.0)
    session_delta = Column(Float, default=0.0)
    churn_score = Column(Float, default=100.0)
    status = Column(String(20), default="green") # 'red', 'yellow', 'green'
    issues = Column(Text, default="[]") # JSON en texto con las alertas
    weekly_data = Column(Text, default="[]") # JSON con desglose semana a semana (WoW)

    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client", back_populates="metrics")
