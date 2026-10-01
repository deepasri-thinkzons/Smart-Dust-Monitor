import sys, csv, hashlib
from pathlib import Path
from datetime import datetime, timedelta
from models import SessionLocal, RawSample
from analytics import calculate_minute, calculate_hour, calculate_day
BASE=Path(__file__).resolve().parent.parent
path=Path(sys.argv[1]) if len(sys.argv)>1 else BASE/'data'/'sensorData.csv'
with open(path,newline='',encoding='utf-8-sig') as f: rows=list(csv.DictReader(f))
with SessionLocal() as s:
    existing={r.device_ms for r in s.query(RawSample).filter(RawSample.device_ms.is_not(None)).all()}
    for i,row in enumerate(rows):
        try:
            ms=int(float(row.get('timestamp_ms','0')))
            if ms in existing: continue
            s.add(RawSample(ts=datetime.now()-timedelta(milliseconds=max(0, int(float(rows[-1].get('timestamp_ms','0')))-ms)),device_ms=ms,source='CSV',adc=float(row['adc']),voltage=float(row['voltage']),rs=float(row['rs']),r0=float(row['r0']),ratio=float(row['rs_r0']),ppm=float(row['ppm']),temperature=float(row['temperature']),humidity=float(row['humidity']),status=row.get('status','UNKNOWN')))
        except Exception as e: print('skip',i,e)
    s.commit()
print(f'Imported/checked {len(rows)} rows. Run rebuild if you need historical period buckets.')
