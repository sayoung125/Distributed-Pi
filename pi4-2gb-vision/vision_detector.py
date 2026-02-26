"""Pi 4 2GB: Vision Detector - Runs YOLOv8-nano on video frames."""

import sys
import os
import time
import base64
import signal
import logging
import threading

import cv2
import numpy as np
from ultralytics import YOLO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.config import get_config, setup_logging
from shared.mqtt_client import MQTTClient
from shared.metrics import start_metrics_publisher

# Configuration
CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.4"))
MODEL_PATH = os.environ.get("YOLO_MODEL", "yolov8n.pt")


class VisionDetector:
    """Processes frames with YOLOv8-nano and publishes detections."""

    def __init__(self, mqtt_client: MQTTClient, logger: logging.Logger):
        self.mqtt = mqtt_client
        self.logger = logger
        self._latest_frame = None
        self._frame_lock = threading.Lock()
        self._processing = False

        # Load model once at startup
        self.logger.info("Loading YOLOv8 model: %s", MODEL_PATH)
        load_start = time.time()
        self.model = YOLO(MODEL_PATH)
        self.logger.info(
            "Model loaded in %.1fs", time.time() - load_start
        )

    def on_frame(self, topic: str, payload: dict):
        """Handle incoming frame - store latest, skip if busy."""
        with self._frame_lock:
            self._latest_frame = payload

    def process_loop(self):
        """Continuously process the latest available frame."""
        while True:
            # Grab latest frame
            with self._frame_lock:
                frame_data = self._latest_frame
                self._latest_frame = None

            if frame_data is None:
                time.sleep(0.05)
                continue

            try:
                self._process_frame(frame_data)
            except Exception as e:
                self.logger.error("Error processing frame %s: %s",
                                  frame_data.get("frame_id"), e)

    def _process_frame(self, payload: dict):
        """Decode frame, run YOLO inference, publish results."""
        frame_id = payload["frame_id"]
        timestamp = payload["timestamp"]

        # Decode base64 JPEG to numpy array
        jpeg_bytes = base64.b64decode(payload["jpeg_b64"])
        nparr = np.frombuffer(jpeg_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            self.logger.warning("Failed to decode frame %d", frame_id)
            return

        # Run inference
        inference_start = time.time()
        results = self.model.predict(
            frame,
            conf=CONFIDENCE_THRESHOLD,
            verbose=False,
        )
        inference_ms = (time.time() - inference_start) * 1000

        # Parse results
        detections = []
        object_counts = {}

        for result in results:
            for box in result.boxes:
                class_id = int(box.cls[0])
                class_name = self.model.names[class_id]
                confidence = float(box.conf[0])
                bbox = box.xyxy[0].tolist()  # [x1, y1, x2, y2]

                detections.append({
                    "class": class_name,
                    "confidence": round(confidence, 3),
                    "bbox": [round(c, 1) for c in bbox],
                })

                object_counts[class_name] = object_counts.get(class_name, 0) + 1

        # Publish analysis
        result_payload = {
            "frame_id": frame_id,
            "timestamp": timestamp,
            "detections": detections,
            "object_counts": object_counts,
            "total_objects": len(detections),
            "inference_ms": round(inference_ms, 1),
            "model": MODEL_PATH,
        }

        self.mqtt.publish_json("analysis/vision", result_payload)

        self.logger.info(
            "Frame %d: %d objects detected in %.0fms (%s)",
            frame_id,
            len(detections),
            inference_ms,
            ", ".join(f"{k}:{v}" for k, v in object_counts.items()) or "none",
        )


def main():
    config = get_config()
    logger = setup_logging("pi4-2gb-vision", config["log_level"])

    running = True

    def signal_handler(sig, frame):
        nonlocal running
        logger.info("Shutdown signal received")
        running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Connect to MQTT
    mqtt = MQTTClient(config["mqtt_broker_host"], config["mqtt_port"], "pi4-2gb")
    mqtt.connect()

    # Start metrics publisher
    start_metrics_publisher(mqtt, "pi4-2gb")

    # Initialize detector
    detector = VisionDetector(mqtt, logger)

    # Subscribe to raw frames
    mqtt.subscribe("frames/raw", detector.on_frame)

    logger.info("Vision detector ready, waiting for frames...")

    # Run processing loop on main thread
    try:
        detector.process_loop()
    except KeyboardInterrupt:
        pass
    finally:
        mqtt.disconnect()
        logger.info("Vision detector shut down")


if __name__ == "__main__":
    main()
