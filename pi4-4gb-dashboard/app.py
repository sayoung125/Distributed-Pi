"""Pi 4 4GB: Dashboard & Orchestrator - Real-time web dashboard for the analytics pipeline.

Co-located on the same Pi as the frame processor (pi4-4gb-dashboard).
"""

import sys
import os
import time
import signal
import logging
import threading
from collections import deque

from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.config import get_config, setup_logging
from shared.mqtt_client import MQTTClient
from shared.metrics import start_metrics_publisher

# Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "distributed-pi-dashboard")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# State
state = {
    "latest_frame": None,
    "latest_vision": None,
    "latest_intelligence": None,
    "metrics": {},  # node_name -> latest metrics
    "history": deque(maxlen=50),
    "pipeline_stats": {
        "frames_received": 0,
        "visions_received": 0,
        "narratives_received": 0,
        "start_time": time.time(),
    },
}


def on_frame(topic: str, payload: dict):
    """Handle raw frame from the local processor container."""
    state["latest_frame"] = payload
    state["pipeline_stats"]["frames_received"] += 1
    socketio.emit("frame_update", {
        "frame_id": payload["frame_id"],
        "timestamp": payload["timestamp"],
        "jpeg_b64": payload["jpeg_b64"],
        "width": payload["width"],
        "height": payload["height"],
        "capture_ms": payload.get("capture_ms", 0),
    })


def on_vision(topic: str, payload: dict):
    """Handle vision analysis from Pi 4 2GB."""
    state["latest_vision"] = payload
    state["pipeline_stats"]["visions_received"] += 1
    socketio.emit("vision_update", payload)


def on_intelligence(topic: str, payload: dict):
    """Handle intelligence narrative from Pi 3."""
    state["latest_intelligence"] = payload
    state["pipeline_stats"]["narratives_received"] += 1
    state["history"].appendleft(payload)
    socketio.emit("intelligence_update", payload)


def on_metrics(topic: str, payload: dict):
    """Handle system metrics from any Pi."""
    node = payload.get("node", "unknown")
    state["metrics"][node] = payload
    socketio.emit("metrics_update", payload)


# Routes
@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/state")
def get_state():
    return jsonify({
        "latest_vision": state["latest_vision"],
        "latest_intelligence": state["latest_intelligence"],
        "metrics": state["metrics"],
        "pipeline_stats": {
            **state["pipeline_stats"],
            "uptime_seconds": round(time.time() - state["pipeline_stats"]["start_time"]),
        },
    })


@app.route("/api/history")
def get_history():
    return jsonify(list(state["history"]))


# SocketIO events
@socketio.on("connect")
def handle_connect():
    """Send current state to newly connected client."""
    if state["latest_frame"]:
        socketio.emit("frame_update", {
            "frame_id": state["latest_frame"]["frame_id"],
            "timestamp": state["latest_frame"]["timestamp"],
            "jpeg_b64": state["latest_frame"]["jpeg_b64"],
            "width": state["latest_frame"]["width"],
            "height": state["latest_frame"]["height"],
        })
    if state["latest_vision"]:
        socketio.emit("vision_update", state["latest_vision"])
    if state["latest_intelligence"]:
        socketio.emit("intelligence_update", state["latest_intelligence"])
    for node, metrics in state["metrics"].items():
        socketio.emit("metrics_update", metrics)


def start_mqtt():
    """Start MQTT client in a background thread."""
    config = get_config()
    mqtt = MQTTClient(config["mqtt_broker_host"], config["mqtt_port"], "pi4-4gb-dashboard")
    mqtt.connect()

    # Subscribe to all pipeline topics
    mqtt.subscribe("frames/raw", on_frame)
    mqtt.subscribe("analysis/vision", on_vision)
    mqtt.subscribe("analysis/intelligence", on_intelligence)
    mqtt.subscribe("system/metrics/#", on_metrics)

    # Start metrics publisher for this Pi
    start_metrics_publisher(mqtt, "pi4-4gb")

    return mqtt


def main():
    config = get_config()
    logger = setup_logging("pi4-dashboard", config["log_level"])

    logger.info("Starting dashboard...")

    # Start MQTT
    mqtt = start_mqtt()
    logger.info("MQTT connected, subscribed to pipeline topics")

    # Run Flask with SocketIO
    port = int(os.environ.get("DASHBOARD_PORT", "5000"))
    logger.info("Dashboard available at http://0.0.0.0:%d", port)
    socketio.run(app, host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
