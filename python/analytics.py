from datetime import datetime, timedelta
from statistics import mean, pstdev
from sqlalchemy import select
from models import SessionLocal, RawSample, MinuteStat, HourlyStat, DailyStat
from queries import upsert_stat

def trend(values):
    if len(values) < 2: return "STABLE"
    n=max(1,len(values)//2); a=mean(values[:n]); b=mean(values[-n:])
    if a == 0: return "STABLE"
    if b > a*1.10: return "INCREASING"
    if b < a*0.90: return "DECREASING"
    return "STABLE"

def calculate_minute(dt=None):
    dt=(dt or datetime.now()).replace(second=0,microsecond=0); end=dt+timedelta(minutes=1)
    with SessionLocal() as s: rows=list(s.scalars(select(RawSample).where(RawSample.ts>=dt,RawSample.ts<end).order_by(RawSample.ts)).all())
    if not rows: return None
    ppm=[r.ppm for r in rows]; temp=[r.temperature for r in rows]; hum=[r.humidity for r in rows]
    vals=dict(sample_count=len(rows),ppm_avg=mean(ppm),ppm_min=min(ppm),ppm_max=max(ppm),ppm_std=pstdev(ppm) if len(ppm)>1 else 0,temp_avg=mean(temp),humidity_avg=mean(hum),poor_count=sum(r.status=="POOR" for r in rows),critical_count=sum(r.status=="CRITICAL" for r in rows),trend=trend(ppm))
    return upsert_stat(MinuteStat,dt,vals)

def calculate_hour(dt=None):
    dt=(dt or datetime.now()).replace(minute=0,second=0,microsecond=0); end=dt+timedelta(hours=1)
    with SessionLocal() as s: rows=list(s.scalars(select(MinuteStat).where(MinuteStat.period_start>=dt,MinuteStat.period_start<end).order_by(MinuteStat.period_start)).all())
    if not rows: return None
    # Aggregate minute averages weighted by sample count.
    weights=[max(1,r.sample_count) for r in rows]; ppm=[r.ppm_avg for r in rows]
    total=sum(weights); avg=sum(x*w for x,w in zip(ppm,weights))/total
    vals=dict(minute_count=len(rows),ppm_avg=avg,ppm_min=min(r.ppm_min for r in rows),ppm_max=max(r.ppm_max for r in rows),ppm_std=mean(r.ppm_std for r in rows),temp_avg=sum(r.temp_avg*w for r,w in zip(rows,weights))/total,humidity_avg=sum(r.humidity_avg*w for r,w in zip(rows,weights))/total,poor_minutes=sum(r.poor_count>0 for r in rows),critical_minutes=sum(r.critical_count>0 for r in rows),trend=trend(ppm))
    return upsert_stat(HourlyStat,dt,vals)

def calculate_day(dt=None):
    dt=(dt or datetime.now()).replace(hour=0,minute=0,second=0,microsecond=0); end=dt+timedelta(days=1)
    with SessionLocal() as s: rows=list(s.scalars(select(HourlyStat).where(HourlyStat.period_start>=dt,HourlyStat.period_start<end).order_by(HourlyStat.period_start)).all())
    if not rows: return None
    vals=dict(hour_count=len(rows),ppm_avg=mean(r.ppm_avg for r in rows),ppm_min=min(r.ppm_min for r in rows),ppm_max=max(r.ppm_max for r in rows),ppm_std=mean(r.ppm_std for r in rows),temp_avg=mean(r.temp_avg for r in rows),humidity_avg=mean(r.humidity_avg for r in rows),poor_hours=sum(r.poor_minutes>0 for r in rows),critical_hours=sum(r.critical_minutes>0 for r in rows),trend=trend([r.ppm_avg for r in rows]))
    return upsert_stat(DailyStat,dt,vals)

def rebuild_recent():
    now=datetime.now();
    for i in range(1440,0,-1):
        calculate_minute(now-timedelta(minutes=i))
    for i in range(24,0,-1): calculate_hour(now-timedelta(hours=i))
    calculate_day(now)
