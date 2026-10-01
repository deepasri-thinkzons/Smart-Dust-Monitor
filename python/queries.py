from datetime import datetime, timedelta
from sqlalchemy import select, func
from models import SessionLocal, RawSample, MinuteStat, HourlyStat, DailyStat, AIInsight

def latest_raw(limit=60):
    with SessionLocal() as s:
        return list(reversed(s.scalars(select(RawSample).order_by(RawSample.ts.desc()).limit(limit)).all()))

def range_rows(model, start, end):
    with SessionLocal() as s:
        return list(s.scalars(select(model).where(model.period_start >= start, model.period_start < end).order_by(model.period_start)).all())

def latest_stats(model, limit=60):
    with SessionLocal() as s:
        return list(reversed(s.scalars(select(model).order_by(model.period_start.desc()).limit(limit)).all()))

def latest_ai(limit=10):
    with SessionLocal() as s:
        return list(s.scalars(select(AIInsight).order_by(AIInsight.created_at.desc()).limit(limit)).all())

def current_minute_samples():
    now = datetime.now().replace(second=0, microsecond=0)
    return range_rows(RawSample, now, now + timedelta(minutes=1))

def insert_raw(row):
    with SessionLocal() as s:
        obj = RawSample(**row)
        s.add(obj); s.commit(); s.refresh(obj)
        return obj

def upsert_stat(model, period_start, values):
    with SessionLocal() as s:
        obj = s.scalar(select(model).where(model.period_start == period_start))
        if obj is None:
            obj = model(period_start=period_start, **values); s.add(obj)
        else:
            for k,v in values.items(): setattr(obj,k,v)
        s.commit(); s.refresh(obj); return obj

def save_ai(period_type, period_start, data):
    with SessionLocal() as s:
        obj = AIInsight(created_at=datetime.now(), period_type=period_type, period_start=period_start, **data)
        s.add(obj); s.commit(); s.refresh(obj); return obj
