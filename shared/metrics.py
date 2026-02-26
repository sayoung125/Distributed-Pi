"""System metrics collector that publishes to MQTT."""

import time
import logging
import threading
import psutil

logger = logging.getLogger(__name__)


def get_cpu_temperature() -> float | None:
    """Read CPU temperature (works on Raspberry Pi Linux)."""
    try:
        temps = psutil.sensors_temperatures()
        if "cpu_thermal" in temps:
            return temps["cpu_thermal"][0].current
    except (AttributeError, IndexError, KeyError):
        pass
    # Fallback: read from sysfs directly
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return float(f.read().strip()) / 1000.0
    except (FileNotFoundError, ValueError):
        return None


def collect_metrics(node_name: str) -> dict:
    """Collect current system metrics."""
    cpu_temp = get_cpu_temperature()
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return {
        "node": node_name,
        "timestamp": time.time(),
        "cpu_percent": psutil.cpu_percent(interval=None),
        "memory_percent": mem.percent,
        "memory_used_mb": round(mem.used / (1024 * 1024)),
        "memory_total_mb": round(mem.total / (1024 * 1024)),
        "disk_percent": disk.percent,
        "cpu_temperature": cpu_temp,
    }


def start_metrics_publisher(mqtt_client, node_name: str, interval: float = 5.0):
    """Start a background thread that publishes system metrics periodically."""
    # Prime the CPU percent measurement
    psutil.cpu_percent(interval=None)

    def _publish_loop():
        while True:
            try:
                metrics = collect_metrics(node_name)
                topic = f"system/metrics/{node_name}"
                mqtt_client.publish_json(topic, metrics, qos=0)
            except Exception as e:
                logger.error("Failed to publish metrics: %s", e)
            time.sleep(interval)

    thread = threading.Thread(target=_publish_loop, daemon=True, name="metrics")
    thread.start()
    logger.info("Metrics publisher started (every %.0fs)", interval)
    return thread
