import os
from datetime import datetime

def check_disk_space():
    stat = os.statvfs("/")
    free = stat.f_bavail * stat.f_frsize / (1024**3)  # GB
    return free

def should_pause_system():
    free = check_disk_space()
    if free < 2:
        return True, f"Low disk space: {free:.2f}GB"
    return False, f"Disk OK: {free:.2f}GB"

def watchdog_status():
    paused, reason = should_pause_system()
    return {
        "paused": paused,
        "reason": reason,
        "checked_at": datetime.utcnow().isoformat()
    }
