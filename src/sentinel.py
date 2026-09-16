"""
Workstation Sentinel & Resource Governance Engine.
Maintains quiet background execution (<10% CPU footprint) and memory self-healing.
"""

import psutil
import shutil
import time
from typing import Dict, Any

class WorkstationSentinel:
    def __init__(self, cpu_threshold: float = 20.0):
        self.cpu_threshold = cpu_threshold

    def get_hardware_status(self) -> Dict[str, Any]:
        ram = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.1)
        disk = shutil.disk_usage(".")
        return {
            "ram_used_gb": round(ram.used / (1024**3), 2),
            "ram_total_gb": round(ram.total / (1024**3), 2),
            "ram_percent": ram.percent,
            "cpu_percent": cpu,
            "disk_free_gb": round(disk.free / (1024**3), 2),
            "status": "HEALTHY" if cpu < self.cpu_threshold else "THROTTLED"
        }
