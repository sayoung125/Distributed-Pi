"""Pi 4 4GB: Edge Processor - Captures video frames and publishes to MQTT.

Co-located on the same Pi as the dashboard (pi4-4gb-dashboard).
Runs as a separate container alongside the dashboard container.
"""

import sys
import os
import time
import base64
import signal
import logging

import cv2

# Add parent directory to path for shared module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.config import get_config, setup_logging
from shared.mqtt_client import MQTTClient
from shared.metrics import start_metrics_publisher

# Configuration
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
JPEG_QUALITY = 70
TARGET_FPS = 2  # Publish rate - matches Pi 2 inference speed
CAMERA_INDEX = int(os.environ.get("CAMERA_INDEX", "0"))


def encode_frame(frame) -> str:
    """Encode a frame as base64 JPEG."""
    encode_params = [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
    success, buffer = cv2.imencode(".jpg", frame, encode_params)
    if not success:
        raise RuntimeError("Failed to encode frame as JPEG")
    return base64.b64encode(buffer).decode("utf-8")


def open_camera(camera_index: int, logger: logging.Logger):
    """Open camera with retries."""
    for attempt in range(5):
        logger.info("Opening camera %d (attempt %d)...", camera_index, attempt + 1)
        cap = cv2.VideoCapture(camera_index)
        if cap.isOpened():
            # Set resolution
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
            actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            logger.info("Camera opened: %dx%d", actual_w, actual_h)
            return cap
        cap.release()
        time.sleep(2)
    raise RuntimeError(f"Failed to open camera {camera_index}")


def main():
    config = get_config()
    logger = setup_logging("pi4-4gb-processor", config["log_level"])

    # Graceful shutdown
    running = True

    def signal_handler(sig, frame):
        nonlocal running
        logger.info("Shutdown signal received")
        running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Connect to MQTT
    mqtt = MQTTClient(config["mqtt_broker_host"], config["mqtt_port"], "pi4-4gb-processor")
    mqtt.connect()

    # Metrics are published by the dashboard container for this node
    # No need to duplicate here

    # Open camera
    camera = open_camera(CAMERA_INDEX, logger)

    frame_id = 0
    publish_interval = 1.0 / TARGET_FPS
    last_publish_time = 0

    logger.info("Starting frame capture at %d FPS publish rate...", TARGET_FPS)

    try:
        while running:
            ret, frame = camera.read()
            if not ret:
                logger.warning("Failed to read frame, retrying...")
                time.sleep(0.5)
                continue

            now = time.time()
            if now - last_publish_time < publish_interval:
                continue  # Skip frame to maintain target FPS

            # Resize if camera doesn't support requested resolution
            h, w = frame.shape[:2]
            if w != FRAME_WIDTH or h != FRAME_HEIGHT:
                frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))

            # Encode and publish
            capture_start = time.time()
            jpeg_b64 = encode_frame(frame)
            capture_ms = (time.time() - capture_start) * 1000

            payload = {
                "frame_id": frame_id,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
                "width": FRAME_WIDTH,
                "height": FRAME_HEIGHT,
                "jpeg_b64": jpeg_b64,
                "capture_ms": round(capture_ms, 1),
            }

            mqtt.publish_json("frames/raw", payload)
            frame_id += 1
            last_publish_time = now

            if frame_id % 10 == 0:
                logger.info(
                    "Published frame %d (encode: %.1fms, size: %.1fKB)",
                    frame_id,
                    capture_ms,
                    len(jpeg_b64) / 1024,
                )

    finally:
        camera.release()
        mqtt.disconnect()
        logger.info("Processor shut down cleanly after %d frames", frame_id)


if __name__ == "__main__":
    main()
