"""Shared configuration loader for all Pi nodes."""

import os
import logging


def get_config():
    """Load configuration from environment variables with sensible defaults."""
    return {
        "mqtt_broker_host": os.environ.get("MQTT_BROKER_HOST", "localhost"),
        "mqtt_port": int(os.environ.get("MQTT_PORT", "1883")),
        "node_name": os.environ.get("NODE_NAME", "unknown"),
        "log_level": os.environ.get("LOG_LEVEL", "INFO"),
    }


def setup_logging(node_name: str, level: str = "INFO"):
    """Configure logging with a consistent format across all nodes."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format=f"%(asctime)s [{node_name}] %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger(node_name)
