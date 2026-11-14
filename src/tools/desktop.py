import os
import platform
import shutil
import subprocess
import psutil


def get_system_vitals() -> dict:
    """
    Checks the Operator's Linux machine CPU usage, CPU/GPU temperatures, RAM usage, and battery status.
    """
    cpu_pct = psutil.cpu_percent(interval=0.3)
    mem = psutil.virtual_memory()
    battery = psutil.sensors_battery()

    # CPU Temps
    temps = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
    cpu_temp = "Sensor unavailable"
    for name in ("coretemp", "k10temp", "acpitz"):
        if name in temps and temps[name]:
            cpu_temp = f"{temps[name][0].current:.1f}°C ({name})"
            break

    # NVIDIA GPU stats via nvidia-smi
    gpu_info = "No NVIDIA GPU detected"
    if shutil.which("nvidia-smi"):
        try:
            res = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if res.returncode == 0 and res.stdout.strip():
                name, temp, util, mem_used, mem_total = [
                    i.strip() for i in res.stdout.strip().split(",")
                ]
                gpu_info = f"{name}: {temp}°C, {util}% load, VRAM {mem_used}/{mem_total} MB"
        except Exception:
            pass

    return {
        "os": f"{platform.system()} {platform.release()}",
        "cpu_usage_percent": cpu_pct,
        "cpu_temp": cpu_temp,
        "gpu_status": gpu_info,
        "ram_used_gb": round(mem.used / (1024**3), 2),
        "ram_total_gb": round(mem.total / (1024**3), 2),
        "ram_percent": mem.percent,
        "battery_percent": round(battery.percent, 1) if battery else "AC Power / Desktop",
        "power_plugged": battery.power_plugged if battery else True,
    }


def list_directory_contents(directory_path: str = ".") -> dict:
    """
    Lists files and folders in a given local Linux directory path (defaults to current project directory).
    """
    target = os.path.abspath(os.path.expanduser(directory_path))
    try:
        stuff = os.listdir(target)
        visible_stuff = sorted([i for i in stuff if not i.startswith(".")])[:40]
        return {
            "path": target,
            "item_count": len(stuff),
            "sample_items": visible_stuff,
        }
    except Exception as e:
        return {"Error": str(e)}


def read_text_file(file_path: str) -> str:
    """
    Reads the contents of a local code or text file (such as Ordis's own source files) so Ordis can inspect or review it.
    """
    target = os.path.abspath(os.path.expanduser(file_path))
    if os.path.basename(target) == ".env":
        return "Refused: .env contains private API keys."
    if not os.path.isfile(target):
        return f"File not found: {target}"
    try:
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(8000)  # Cap at 8KB so huge files don't blow up context
        return content
    except Exception as e:
        return f"Error reading file: {e}"


def control_media(action: str) -> str:
    """
    Controls system media playback (Spotify, YouTube in browser, VLC, etc.).
    Args:
        action: Must be one of 'play', 'pause', 'play-pause', 'next', 'previous', or 'status'.
    """
    valid_actions = {"play", "pause", "play-pause", "next", "previous", "status"}
    action = action.lower().strip()
    if action not in valid_actions:
        return f"Invalid action {action}. Use one of: {', '.join(valid_actions)}"

    if not shutil.which("playerctl"):
        return "Error: needs 'playerctl' installed on system to work"

    try:
        if action == "status":
            meta = subprocess.run(
                ["playerctl", "metadata", "--format", "{{status}}: {{artist}} - {{title}}"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            return meta.stdout.strip() or "No active media player found."

        subprocess.run(["playerctl", action], check=True, timeout=3)
        return f"Media action '{action}' executed successfully."
    except subprocess.CalledProcessError:
        return "No active media player responded to command."
    except Exception as e:
        return f"Media control error: {e}"


def set_system_volume(level_percent: int, mute: bool = False) -> str:
    """
    Adjusts the Ubuntu speaker output volume (0 to 100) or mutes/unmutes audio.
    """
    try:
        if mute:
            subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1"], check=True)
            return "Audio Muted"

        clamped = max(0, min(100, int(level_percent)))
        subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"], check=True)
        subprocess.run(
            ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{clamped}%"],
            check=True,
        )
        return f"Speaker volume set to {clamped}%"
    except Exception as e:
        return f"Failed to adjust volume: {e}"


def launch_application(app_name: str, url_or_arg: str = "") -> str:
    """
    Launches a desktop application on Ubuntu (e.g., 'code', 'firefox', 'discord', 'spotify', 'konsole', 'dolphin').
    Args:
        app_name: Name of the application to open.
        url_or_arg: Optional file path, folder path, or website URL to open inside the app.
    """
    aliases = {
        "vscode": "code",
        "vs code": "code",
        "visual studio code": "code",
        "browser": "xdg-open",
        "terminal": "konsole",
        "files": "dolphin",
        "file manager": "dolphin",
    }
    target = aliases.get(app_name.lower().strip(), app_name.lower().strip())

    # open url with browser
    if url_or_arg.startswith(("http://", "https://")) and not shutil.which(target):
        target = "xdg-open"

    if not shutil.which(target):
        return f"Can't find executable '{target}' in PATH"

    cmd = [target]
    if url_or_arg.strip():
        cmd.append(url_or_arg.strip())

    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return f"Launched '{' '.join(cmd)}' in the background"
    except Exception as e:
        return f"Failed to launch '{target}': {e}"


def manage_process(action: str, process_name: str = "") -> str:
    """
    Lists the top 5 RAM-heavy processes or terminates a running process by name.
    Args:
        action: Either 'top' (to list top memory processes) or 'kill' (to terminate a process).
        process_name: Name of the process to terminate when action is 'kill'.
    """
    action = action.lower().strip()

    if action == "top":
        procs = []
        for p in psutil.process_iter(["pid", "name", "memory_percent"]):
            try:
                procs.append(p.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        top_mem = sorted(procs, key=lambda x: x.get("memory_percent") or 0.0, reverse=True)[:5]
        lines = [
            f"{p['name']} (PID {p['pid']}): {p['memory_percent']:.1f}% RAM"
            for p in top_mem
        ]
        return "Top memory processes: " + " | ".join(lines)

    if action == "kill":
        if not process_name.strip():
            return "Error: provide a process_name to terminate it"
        target = process_name.lower().strip()
        # so ordis does not accidentally kill himself
        protected = {"python", "python3", "xorg", "wayland", "kwin", "plasmashell", "systemd", "pipewire"}
        if target in protected:
            return f"Refused to terminate {target}: {target} is critical to Ordis's functionality"

        killed = []
        for p in psutil.process_iter(["pid", "name"]):
            try:
                if target in (p.info["name"] or "").lower():
                    p.terminate()
                    killed.append(f"{p.info['name']} ({p.info['pid']})")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if not killed:
            return f"No running processes found matching '{process_name}'"
        return f"Terminated: {', '.join(killed)}"

    return "Invalid action. Must be either 'top' or 'kill'."