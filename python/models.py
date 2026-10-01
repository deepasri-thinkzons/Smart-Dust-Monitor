from datetime import datetime
from sqlalchemy import create_engine, String, Float, Integer, DateTime, Text, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
DATA.mkdir(exist_ok=True)
DB_URL = f"sqlite:///{(DATA / 'sensor.db').as_posix()}"

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

class Base(DeclarativeBase): pass

class RawSample(Base):
    __tablename__ = "raw_samples"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    source: Mapped[str] = mapped_column(String(32), default="ESP32")
    adc: Mapped[float] = mapped_column(Float, default=0)
    voltage: Mapped[float] = mapped_column(Float, default=0)
    rs: Mapped[float] = mapped_column(Float, default=0)
    r0: Mapped[float] = mapped_column(Float, default=0)
    ratio: Mapped[float] = mapped_column(Float, default=0)
    ppm: Mapped[float] = mapped_column(Float, default=0)
    temperature: Mapped[float] = mapped_column(Float, default=0)
    humidity: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    device_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

class MinuteStat(Base):
    __tablename__ = "minute_stats"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period_start: Mapped[datetime] = mapped_column(DateTime, index=True)
    sample_count: Mapped[int] = mapped_column(Integer)
    ppm_avg: Mapped[float] = mapped_column(Float)
    ppm_min: Mapped[float] = mapped_column(Float)
    ppm_max: Mapped[float] = mapped_column(Float)
    ppm_std: Mapped[float] = mapped_column(Float)
    temp_avg: Mapped[float] = mapped_column(Float)
    humidity_avg: Mapped[float] = mapped_column(Float)
    poor_count: Mapped[int] = mapped_column(Integer)
    critical_count: Mapped[int] = mapped_column(Integer)
    trend: Mapped[str] = mapped_column(String(16))

class HourlyStat(Base):
    __tablename__ = "hourly_stats"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period_start: Mapped[datetime] = mapped_column(DateTime, index=True)
    minute_count: Mapped[int] = mapped_column(Integer)
    ppm_avg: Mapped[float] = mapped_column(Float)
    ppm_min: Mapped[float] = mapped_column(Float)
    ppm_max: Mapped[float] = mapped_column(Float)
    ppm_std: Mapped[float] = mapped_column(Float)
    temp_avg: Mapped[float] = mapped_column(Float)
    humidity_avg: Mapped[float] = mapped_column(Float)
    poor_minutes: Mapped[int] = mapped_column(Integer)
    critical_minutes: Mapped[int] = mapped_column(Integer)
    trend: Mapped[str] = mapped_column(String(16))

class DailyStat(Base):
    __tablename__ = "daily_stats"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period_start: Mapped[datetime] = mapped_column(DateTime, index=True)
    hour_count: Mapped[int] = mapped_column(Integer)
    ppm_avg: Mapped[float] = mapped_column(Float)
    ppm_min: Mapped[float] = mapped_column(Float)
    ppm_max: Mapped[float] = mapped_column(Float)
    ppm_std: Mapped[float] = mapped_column(Float)
    temp_avg: Mapped[float] = mapped_column(Float)
    humidity_avg: Mapped[float] = mapped_column(Float)
    poor_hours: Mapped[int] = mapped_column(Integer)
    critical_hours: Mapped[int] = mapped_column(Integer)
    trend: Mapped[str] = mapped_column(String(16))

class AIInsight(Base):
    __tablename__ = "ai_insights"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    period_type: Mapped[str] = mapped_column(String(16))
    period_start: Mapped[datetime] = mapped_column(DateTime, index=True)
    priority: Mapped[str] = mapped_column(String(16), default="OBSERVE")
    overall_status: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    problem: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[str] = mapped_column(Text, default="")
    causes: Mapped[str] = mapped_column(Text, default="")
    recommendation: Mapped[str] = mapped_column(Text, default="")
    verification: Mapped[str] = mapped_column(Text, default="")
    raw_response: Mapped[str] = mapped_column(Text, default="")

Index("ix_minute_period", MinuteStat.period_start)
Index("ix_hour_period", HourlyStat.period_start)
Index("ix_day_period", DailyStat.period_start)

Base.metadata.create_all(engine)
