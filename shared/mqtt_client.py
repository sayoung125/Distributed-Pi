"""MQTT client wrapper with auto-reconnect and JSON helpers."""

import json
import time
import logging
import threading
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class MQTTClient:
    """Wrapper around paho-mqtt with auto-reconnect and JSON helpers."""

    def __init__(self, broker_host: str, broker_port: int, node_name: str):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.node_name = node_name
        self._subscriptions: dict[str, callable] = {}
        self._connected = False
        self._lock = threading.Lock()

        self.client = mqtt.Client(
            client_id=f"{node_name}-{int(time.time())}",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        # Set max inflight and queued messages
        self.client.max_inflight_messages_set(20)
        self.client.max_queued_messages_set(100)

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self._connected = True
            logger.info(
                "Connected to MQTT broker at %s:%s",
                self.broker_host,
                self.broker_port,
            )
            # Re-subscribe on reconnect
            for topic in self._subscriptions:
                self.client.subscribe(topic)
                logger.info("Re-subscribed to %s", topic)
        else:
            logger.error("MQTT connection failed with code %s", rc)

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        self._connected = False
        if rc != 0:
            logger.warning("Unexpected MQTT disconnect (rc=%s), will auto-reconnect", rc)

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        # Find matching subscription (supports wildcards via paho)
        callback = None
        for sub_topic, cb in self._subscriptions.items():
            if mqtt.topic_matches_sub(sub_topic, topic):
                callback = cb
                break

        if callback:
            try:
                payload = json.loads(msg.payload.decode("utf-8"))
                callback(topic, payload)
            except json.JSONDecodeError:
                logger.error("Failed to decode JSON from topic %s", topic)
            except Exception as e:
                logger.error("Error in callback for topic %s: %s", topic, e)

    def connect(self, retry_interval: float = 5.0, max_retries: int = 0):
        """Connect to the broker with retry logic. max_retries=0 means infinite."""
        attempt = 0
        while True:
            try:
                logger.info(
                    "Connecting to MQTT broker at %s:%s (attempt %d)...",
                    self.broker_host,
                    self.broker_port,
                    attempt + 1,
                )
                self.client.connect(self.broker_host, self.broker_port, keepalive=60)
                self.client.loop_start()
                # Wait briefly for connection callback
                deadline = time.time() + 5.0
                while not self._connected and time.time() < deadline:
                    time.sleep(0.1)
                if self._connected:
                    return
            except Exception as e:
                logger.warning("Connection attempt failed: %s", e)

            attempt += 1
            if max_retries and attempt >= max_retries:
                raise ConnectionError(
                    f"Failed to connect after {max_retries} attempts"
                )
            backoff = min(retry_interval * (2 ** min(attempt, 5)), 60)
            logger.info("Retrying in %.1f seconds...", backoff)
            time.sleep(backoff)

    def subscribe(self, topic: str, callback: callable):
        """Subscribe to a topic with a callback that receives (topic, payload_dict)."""
        self._subscriptions[topic] = callback
        if self._connected:
            self.client.subscribe(topic)
            logger.info("Subscribed to %s", topic)

    def publish_json(self, topic: str, payload: dict, qos: int = 1):
        """Publish a JSON payload to a topic."""
        if not self._connected:
            logger.warning("Not connected, dropping message to %s", topic)
            return False
        try:
            data = json.dumps(payload)
            result = self.client.publish(topic, data, qos=qos)
            return result.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as e:
            logger.error("Failed to publish to %s: %s", topic, e)
            return False

    def is_connected(self) -> bool:
        return self._connected

    def disconnect(self):
        """Gracefully disconnect."""
        self.client.loop_stop()
        self.client.disconnect()
        self._connected = False
        logger.info("Disconnected from MQTT broker")
