import os
import platform
import psutil

# ==============================================================================
# SOME BASIC SHIT HE CAN DO
# ==============================================================================

def get_system_vitals() -> dict:
    """Checks the Operator's Linux machine CPU usage, RAM usage, and battery status."""
    cpu_pct = psutil.cpu_percent(interval=0.4)
    mem = psutil.virtual_memory()
    battery = psutil.sensors_battery()

    temps = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
    cpu_temp = None
    for name in ("coretemp", "k10temp", "acpitz"):
        if name in temps and temps[name]:
            cpu_temp = f'{temps[name][0].current:.1f}°C'
            break

    return {
        "os": f"{platform.system()} {platform.release()}",
        "cpu_usage_percent": cpu_pct,
        "cpu_temp": cpu_temp or "Sensor unavailable",
        "ram_used_gb": round(mem.used / (1024**3), 2),
        "ram_total_gb": round(mem.total / (1024**3), 2),
        "ram_percent": mem.percent,
        "battery_percent": round(battery.percent, 1) if battery else "AC Power / Desktop",
        "power_plugged": battery.power_plugged if battery else True,
    }

def list_directory_contents(directory_path: str = "~") -> dict:
    """Lists files and folders in a given local Linux directory path."""
    target = os.path.expanduser(directory_path)
    try:
        stuff = os.listdir(target)
        visible_stuff = [i for i in stuff if not i.startswith(".")][:30]
        return {
            "path": target,
            "item_count": len(stuff),
            "sample_items": visible_stuff,
        }
    except Exception as e:
        return {"Error": str(e)}

