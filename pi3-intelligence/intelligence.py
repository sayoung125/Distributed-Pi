"""Pi 3: Intelligence Layer - Generates AI narratives from vision detections."""

import sys
import os
import time
import signal
import logging
import threading
import json
from collections import deque

import ollama

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.config import get_config, setup_logging
from shared.mqtt_client import MQTTClient
from shared.metrics import start_metrics_publisher

# Configuration
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "tinyllama")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
HISTORY_SIZE = 10

SYSTEM_PROMPT = """You are a concise scene narrator for a real-time video analytics system.
Given object detections from a camera feed, describe what's happening in 1-2 sentences.
If trend information is provided, note any changes.
Be specific about counts and types of objects. Keep responses under 50 words."""


class IntelligenceLayer:
    """Transforms vision detections into natural language narratives."""

    def __init__(self, mqtt_client: MQTTClient, logger: logging.Logger):
        self.mqtt = mqtt_client
        self.logger = logger
        self._latest_vision = None
        self._vision_lock = threading.Lock()
        self.recent_observations = deque(maxlen=HISTORY_SIZE)
        self.ollama_client = ollama.Client(host=OLLAMA_HOST)

        # Verify Ollama connectivity and model availability
        self._check_model()

    def _check_model(self):
        """Verify the Ollama model is available."""
        self.logger.info("Checking Ollama model: %s at %s", OLLAMA_MODEL, OLLAMA_HOST)
        try:
            models = self.ollama_client.list()
            model_names = [m.model for m in models.models]
            if not any(OLLAMA_MODEL in name for name in model_names):
                self.logger.warning(
                    "Model '%s' not found. Available: %s. Attempting pull...",
                    OLLAMA_MODEL,
                    model_names,
                )
                self.ollama_client.pull(OLLAMA_MODEL)
            self.logger.info("Model '%s' is ready", OLLAMA_MODEL)
        except Exception as e:
            self.logger.error("Ollama check failed: %s (will retry on first inference)", e)

    def _summarize_trends(self) -> str:
        """Build a summary of recent observations for context."""
        if len(self.recent_observations) < 2:
            return "No previous observations yet."

        recent = list(self.recent_observations)[-5:]
        summaries = []
        for obs in recent:
            counts = obs.get("object_counts", {})
            total = obs.get("total_objects", 0)
            summaries.append(f"{total} objects ({', '.join(f'{v} {k}' for k, v in counts.items())})")

        return "Recent observations (oldest first): " + " → ".join(summaries)

    def on_vision_result(self, topic: str, payload: dict):
        """Handle incoming vision analysis - store latest."""
        with self._vision_lock:
            self._latest_vision = payload

    def process_loop(self):
        """Continuously process the latest vision result."""
        while True:
            with self._vision_lock:
                vision_data = self._latest_vision
                self._latest_vision = None

            if vision_data is None:
                time.sleep(0.1)
                continue

            try:
                self._process_vision(vision_data)
            except Exception as e:
                self.logger.error("Error processing vision data: %s", e)

    def _process_vision(self, payload: dict):
        """Generate narrative from vision detections."""
        frame_id = payload["frame_id"]
        timestamp = payload["timestamp"]
        detections = payload.get("detections", [])
        object_counts = payload.get("object_counts", {})
        total_objects = payload.get("total_objects", 0)

        # Store in history
        self.recent_observations.append(payload)

        # Build prompt
        if total_objects == 0:
            detection_text = "No objects detected in the current frame."
        else:
            detection_list = ", ".join(
                f"{v} {k}{'s' if v > 1 else ''}" for k, v in object_counts.items()
            )
            detection_text = f"Detected: {detection_list} ({total_objects} total objects)."

        trends = self._summarize_trends()

        prompt = f"""Current frame analysis:
{detection_text}

{trends}

Describe what's happening in 1-2 concise sentences."""

        # Call Ollama
        inference_start = time.time()
        try:
            response = self.ollama_client.generate(
                model=OLLAMA_MODEL,
                prompt=prompt,
                system=SYSTEM_PROMPT,
                options={"temperature": 0.7, "num_predict": 100},
            )
            narrative = response["response"].strip()
            inference_ms = (time.time() - inference_start) * 1000
        except Exception as e:
            self.logger.error("Ollama inference failed: %s", e)
            narrative = f"[Inference unavailable] Detected: {', '.join(f'{v} {k}' for k, v in object_counts.items())}"
            inference_ms = 0

        # Build trend description
        trend = ""
        if len(self.recent_observations) >= 3:
            recent_counts = [obs.get("total_objects", 0) for obs in list(self.recent_observations)[-3:]]
            if recent_counts[-1] > recent_counts[0] + 1:
                trend = "Activity is increasing."
            elif recent_counts[-1] < recent_counts[0] - 1:
                trend = "Activity is decreasing."
            else:
                trend = "Activity is stable."

        # Publish result
        result = {
            "frame_id": frame_id,
            "timestamp": timestamp,
            "vision_summary": object_counts,
            "narrative": narrative,
            "trend": trend,
            "inference_ms": round(inference_ms, 1),
            "model": OLLAMA_MODEL,
        }

        self.mqtt.publish_json("analysis/intelligence", result)

        self.logger.info(
            "Frame %d narrative (%.0fms): %s",
            frame_id,
            inference_ms,
            narrative[:100],
        )


def main():
    config = get_config()
    logger = setup_logging("pi3-intelligence", config["log_level"])

    running = True

    def signal_handler(sig, frame):
        nonlocal running
        logger.info("Shutdown signal received")
        running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Connect to MQTT
    mqtt = MQTTClient(config["mqtt_broker_host"], config["mqtt_port"], "pi3")
    mqtt.connect()

    # Start metrics publisher
    start_metrics_publisher(mqtt, "pi3")

    # Initialize intelligence layer
    intel = IntelligenceLayer(mqtt, logger)

    # Subscribe to vision results
    mqtt.subscribe("analysis/vision", intel.on_vision_result)

    logger.info("Intelligence layer ready, waiting for vision data...")

    try:
        intel.process_loop()
    except KeyboardInterrupt:
        pass
    finally:
        mqtt.disconnect()
        logger.info("Intelligence layer shut down")


if __name__ == "__main__":
    main()
