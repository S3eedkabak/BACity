"""HTTP Retry-After delta/date handling shared by fetch and delivery paths."""
import math
import time
from email.utils import parsedate_to_datetime
from datetime import timezone


def retry_after(value, default=60):
    if isinstance(value,bytes):
        value=value.decode('ascii','ignore')
    try:
        delay=float(value)
    except (ValueError,TypeError):
        try:
            date=parsedate_to_datetime(value)
            if date.tzinfo is None:
                date=date.replace(tzinfo=timezone.utc)
            delay=date.timestamp()-time.time()
        except (ValueError,TypeError,OverflowError):
            delay=default
    return max(0,delay) if math.isfinite(delay) else default
