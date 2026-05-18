from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from app.models import Outbox

def sent_today_count(db) -> int:
    now = datetime.now(timezone.utc)
    start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    return int(db.execute(
        select(func.count()).select_from(Outbox).where(Outbox.sent == True).where(Outbox.created_at >= start).where(Outbox.created_at < end)
    ).scalar() or 0)
