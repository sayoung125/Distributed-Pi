# Intelligent Video Analytics Pipeline - Distributed Edge Computing Cluster

## Project Overview

A distributed edge computing system running across 4 Raspberry Pi computers that processes live video in real-time without cloud connectivity. Each Pi specializes in a specific task within an intelligent analytics pipeline.

**Target Event:** PeopleTec Pie Day (March 14, 2026)  
**Target Audience:** Software engineers, cybersecurity experts, DevOps professionals (700+ employee engineering-focused company)

---

## System Architecture

### High-Level Pipeline

```
Camera Feed → Pi 1 → Pi 2 → Pi 3 → Pi 4 (Dashboard)
(Processor)  (Vision)   (Intelligence) (Aggregator)
```

### Hardware Assignment

| Device | Role | Specs | Responsibilities |
|--------|------|-------|------------------|
| **Pi 1** | Edge Processor | 4GB RAM | Video capture, preprocessing, frame distribution |
| **Pi 2** | Vision Model | 2GB RAM | Object/action detection via vision AI |
| **Pi 3** | Intelligence Layer | 2GB RAM | Semantic analysis via language model |
| **Pi Zero** | Optional Sensor | 512MB RAM | Supplementary data or backup |
| **Pi 4** | Dashboard/Coordinator | 4GB RAM | Web UI, aggregation, system orchestration |

---

## Component Specifications

### Pi 1: Edge Processor

**Purpose:** Capture video frames and distribute to the pipeline

**Tasks:**
- Connect to USB camera or Pi Camera Module
- Capture frames at ~15-30 FPS
- Resize frames to manageable size (640x480 or lower)
- Add timestamp to each frame
- Publish frames to MQTT broker on `frames/raw` topic
- Log frame throughput and latency

**Technology Stack:**
- Python 3.9+
- OpenCV (`cv2`)
- MQTT Client (`paho-mqtt`)
- Docker container

**Key Metrics to Track:**
- Frames captured per second
- Average frame size
- MQTT publish latency
- CPU/Memory usage

**Pseudocode:**
```python
import cv2
import paho.mqtt.client as mqtt
import json
import time
from datetime import datetime

camera = cv2.VideoCapture(0)  # USB camera or Pi camera
mqtt_client = mqtt.Client()
mqtt_client.connect("localhost", 1883)

while True:
    ret, frame = camera.read()
    if ret:
        # Resize for efficiency
        frame = cv2.resize(frame, (640, 480))
        
        # Create payload
        payload = {
            "timestamp": datetime.now().isoformat(),
            "frame_id": frame_count,
            "width": 640,
            "height": 480,
            "frame_data": convert_to_base64(frame)  # or save locally
        }
        
        # Publish to MQTT
        mqtt_client.publish("frames/raw", json.dumps(payload))
        frame_count += 1
        time.sleep(0.033)  # ~30 FPS
```

---

### Pi 2: Vision Model (Object/Action Detection)

**Purpose:** Analyze frames using vision AI to detect objects and actions

**Tasks:**
- Subscribe to `frames/raw` MQTT topic
- Load vision model via Ollama (e.g., LLaVA)
- For each frame, generate structured analysis
- Return JSON with detected objects, actions, confidence scores
- Publish to `analysis/vision` topic
- Handle model inference latency gracefully

**Technology Stack:**
- Python 3.9+
- Ollama (open-source LLM framework)
- MQTT Client (`paho-mqtt`)
- OpenCV for frame handling
- Docker container

**Model Details:**
- **Model Name:** `llava` (vision model via Ollama)
- **Model Size:** ~4GB (quantized version for Pi)
- **Inference Speed:** 5-15 seconds per frame (acceptable for demo)
- **Prompt:** "What objects and actions do you see in this image? Return only JSON."

**Output Format:**
```json
{
  "timestamp": "2026-03-14T12:00:00.000Z",
  "frame_id": 42,
  "analysis": {
    "objects": ["person", "monitor", "desk"],
    "object_count": 3,
    "actions": ["standing", "looking at screen", "gesturing"],
    "scene_description": "Multiple people in an office setting",
    "confidence": 0.85
  },
  "inference_time_ms": 8500,
  "model": "llava"
}
```

**Pseudocode:**
```python
import mqtt
import ollama
import json
import base64
from io import BytesIO
from PIL import Image

def on_frame_received(client, userdata, msg):
    payload = json.loads(msg.payload)
    frame_id = payload["frame_id"]
    frame_data = base64.b64decode(payload["frame_data"])
    
    # Convert to image
    image = Image.open(BytesIO(frame_data))
    
    # Run vision model via Ollama
    prompt = "Analyze this image. List all objects you see and what people are doing. Return ONLY valid JSON with 'objects' and 'actions' arrays."
    
    response = ollama.generate(
        model="llava",
        prompt=prompt,
        images=[image],
        stream=False
    )
    
    analysis = parse_json_response(response.output)
    
    # Publish results
    result = {
        "timestamp": payload["timestamp"],
        "frame_id": frame_id,
        "analysis": analysis,
        "inference_time_ms": response.load_duration
    }
    
    mqtt_client.publish("analysis/vision", json.dumps(result))

mqtt_client.on_message = on_frame_received
mqtt_client.subscribe("frames/raw")
mqtt_client.loop_forever()
```

---

### Pi 3: Intelligence Layer (Semantic Analysis)

**Purpose:** Transform raw detections into intelligent insights using language models

**Tasks:**
- Subscribe to `analysis/vision` MQTT topic
- Take structured vision output and generate human-readable narrative
- Track patterns/trends over time (optional)
- Answer higher-level questions about what's happening
- Publish to `analysis/intelligence` topic
- Maintain short-term memory of recent observations

**Technology Stack:**
- Python 3.9+
- Ollama with text model (e.g., Mistral, Neural Chat)
- MQTT Client (`paho-mqtt`)
- Docker container

**Model Details:**
- **Model Name:** `mistral` or `neural-chat` (via Ollama)
- **Model Size:** ~3-4GB (quantized)
- **Inference Speed:** 2-8 seconds per prompt

**Output Format:**
```json
{
  "timestamp": "2026-03-14T12:00:00.000Z",
  "frame_id": 42,
  "vision_analysis": {
    "objects": ["person", "monitor"],
    "actions": ["standing", "looking at screen"]
  },
  "intelligent_narrative": "Two people are standing and focused on a monitor displaying content. This appears to be an active discussion or presentation scenario.",
  "observation_type": "standard",
  "inference_time_ms": 4200,
  "model": "mistral"
}
```

**Optional Enhancements:**
- Track observations over last 5-10 frames: "Activity level is increasing. More people gathering."
- Detect anomalies: "Unusual: person lying on floor" (if detected)
- Generate summaries: "In the last 5 minutes: 7 people visited, average engagement time 2 minutes"

**Pseudocode:**
```python
import mqtt
import ollama
import json
from collections import deque

recent_observations = deque(maxlen=10)  # Remember last 10 analyses

def on_vision_received(client, userdata, msg):
    payload = json.loads(msg.payload)
    vision_analysis = payload["analysis"]
    
    recent_observations.append(vision_analysis)
    
    # Build context from recent observations
    context = f"""
    Current observation:
    - Objects: {', '.join(vision_analysis['objects'])}
    - Actions: {', '.join(vision_analysis['actions'])}
    - Scene: {vision_analysis['scene_description']}
    
    Recent trends: {summarize_trends(recent_observations)}
    
    Generate a natural language narrative of what's happening in 1-2 sentences.
    """
    
    response = ollama.generate(
        model="mistral",
        prompt=context,
        stream=False
    )
    
    result = {
        "timestamp": payload["timestamp"],
        "frame_id": payload["frame_id"],
        "vision_analysis": vision_analysis,
        "intelligent_narrative": response.output.strip(),
        "inference_time_ms": response.load_duration
    }
    
    mqtt_client.publish("analysis/intelligence", json.dumps(result))

mqtt_client.on_message = on_vision_received
mqtt_client.subscribe("analysis/vision")
mqtt_client.loop_forever()
```

---

### Pi 4: Dashboard & Orchestrator

**Purpose:** Aggregate data, display real-time dashboard, coordinate system health

**Tasks:**
- Subscribe to all analysis topics
- Serve web dashboard on local network (e.g., http://raspberry-pi-4:5000)
- Display live video feed with annotations
- Show real-time AI analysis and narration
- Display system metrics (CPU, memory, latency per Pi)
- Track frame processing timeline
- Provide admin interface for system control

**Technology Stack:**
- Python 3.9+
- Flask (web framework)
- WebSockets or Server-Sent Events (real-time updates)
- MQTT Client (`paho-mqtt`)
- HTML5/CSS/JavaScript frontend
- Docker container

**Dashboard Features:**

1. **Video Feed Display**
   - Show live camera feed
   - Overlay bounding boxes for detected objects (if Pi 2 provides coordinates)
   - Timestamp and frame ID

2. **Real-Time Analysis Panel**
   - Display narration from Pi 3
   - Show detected objects and confidence scores
   - Display action classifications

3. **System Health Dashboard**
   - CPU usage per Pi (Pi 1: _%, Pi 2: _%, etc.)
   - Memory usage per Pi
   - Latency: Camera → Pi 1 → Pi 2 → Pi 3 → Dashboard
   - Frames processed per second
   - Model inference times

4. **Timeline/History View**
   - Last 20 observations listed chronologically
   - Allows scrolling through what system observed over time

**Pseudocode (Flask Backend):**
```python
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import mqtt
import json
import psutil
import threading

app = Flask(__name__)
socketio = SocketIO(app)

current_state = {
    "latest_frame": None,
    "latest_vision": None,
    "latest_intelligence": None,
    "system_metrics": {},
    "observations_history": []
}

def on_vision_message(client, userdata, msg):
    payload = json.loads(msg.payload)
    current_state["latest_vision"] = payload
    socketio.emit("vision_update", payload, broadcast=True)

def on_intelligence_message(client, userdata, msg):
    payload = json.loads(msg.payload)
    current_state["latest_intelligence"] = payload
    current_state["observations_history"].append(payload)
    if len(current_state["observations_history"]) > 50:
        current_state["observations_history"].pop(0)
    socketio.emit("intelligence_update", payload, broadcast=True)

def collect_metrics():
    """Periodically collect system metrics from all Pis"""
    while True:
        metrics = {
            "pi1_cpu": psutil.cpu_percent(),
            "pi1_memory": psutil.virtual_memory().percent,
            "timestamp": time.time()
        }
        socketio.emit("metrics_update", metrics, broadcast=True)
        time.sleep(5)

mqtt_client = mqtt.Client()
mqtt_client.on_message = on_vision_message  # Simplified
mqtt_client.connect("localhost", 1883)
mqtt_client.subscribe("analysis/vision")
mqtt_client.subscribe("analysis/intelligence")

@app.route("/")
def dashboard():
    return render_template("dashboard.html")

@socketio.on("request_state")
def send_state():
    emit("full_state", current_state)

if __name__ == "__main__":
    metrics_thread = threading.Thread(target=collect_metrics, daemon=True)
    metrics_thread.start()
    mqtt_client.loop_start()
    socketio.run(app, host="0.0.0.0", port=5000)
```

---

### MQTT Broker (Lightweight Message Bus)

**Purpose:** Enable inter-Pi communication without central dependency

**Tool:** Mosquitto (lightweight MQTT broker)
**Deployment:** Run on Pi 4 or Pi 1
**Configuration:** Basic (no authentication needed for internal network)

**Topics:**
```
frames/raw                    → Raw video frames (Pi 1 publishes)
analysis/vision              → Vision AI analysis (Pi 2 publishes)
analysis/intelligence        → Narrative analysis (Pi 3 publishes)
system/metrics/pi1           → Pi 1 health metrics
system/metrics/pi2           → Pi 2 health metrics
system/metrics/pi3           → Pi 3 health metrics
system/metrics/pi4           → Pi 4 health metrics
system/control               → Commands to Pis (start, stop, etc.)
```

---

## Deployment & Containerization

### Docker Setup

Each Pi runs containerized components using Docker Compose.

**Docker Image Strategy:**
- Base image: `arm32v7/python:3.9-slim` (for ARM-based Pis)
- Keep images <1GB for Pi storage constraints
- Pre-cache Ollama models on storage or download at container startup

**Pi 1 Dockerfile:**
```dockerfile
FROM arm32v7/python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libatlas-base-dev \
    libopenjp2-7 \
    libtiff5 \
    libjasper-dev \
    libharfp-dev \
    libwebp6 \
    libjasper1 \
    libjpeg-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY processor.py .

CMD ["python", "processor.py"]
```

**docker-compose.yml (deployed on each Pi):**
```yaml
version: '3.8'

services:
  mosquitto:
    image: eclipse-mosquitto:2.0
    ports:
      - "1883:1883"
    volumes:
      - ./mosquitto.conf:/mosquitto/config/mosquitto.conf
    networks:
      - edge-cluster

  pi1-processor:
    build:
      context: ./pi1-processor
      dockerfile: Dockerfile
    environment:
      - MQTT_BROKER=mosquitto
      - MQTT_PORT=1883
      - CAMERA_ID=0
    depends_on:
      - mosquitto
    networks:
      - edge-cluster
    restart: unless-stopped

  pi2-vision:
    build:
      context: ./pi2-vision
      dockerfile: Dockerfile
    environment:
      - MQTT_BROKER=mosquitto
      - MQTT_PORT=1883
      - OLLAMA_MODEL=llava
    depends_on:
      - mosquitto
    networks:
      - edge-cluster
    restart: unless-stopped

  pi3-intelligence:
    build:
      context: ./pi3-intelligence
      dockerfile: Dockerfile
    environment:
      - MQTT_BROKER=mosquitto
      - MQTT_PORT=1883
      - OLLAMA_MODEL=mistral
    depends_on:
      - mosquitto
    networks:
      - edge-cluster
    restart: unless-stopped

  pi4-dashboard:
    build:
      context: ./pi4-dashboard
      dockerfile: Dockerfile
    ports:
      - "5000:5000"
    environment:
      - MQTT_BROKER=mosquitto
      - MQTT_PORT=1883
    depends_on:
      - mosquitto
    networks:
      - edge-cluster
    restart: unless-stopped

networks:
  edge-cluster:
    driver: bridge
```

---

## Installation & Setup Guide

### Pre-Requisites

- 4x Raspberry Pi computers (as specified)
- 1x USB camera or Pi Camera Module v3 (connected to Pi 1)
- microSD cards with Raspberry Pi OS Lite installed
- Local network connectivity (all Pis on same network)
- Power supplies for all Pis
- Ethernet or WiFi (WiFi acceptable for demo)

### Step-by-Step Setup

#### Step 1: Prepare Each Pi
```bash
# On each Pi, run:
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get install -y docker.io docker-compose git python3-pip

# Enable Docker to run without sudo
sudo usermod -aG docker pi

# Install Ollama (on Pi 2 and Pi 3)
curl https://ollama.ai/install.sh | sh
```

#### Step 2: Pull Ollama Models
```bash
# On Pi 2:
ollama pull llava

# On Pi 3:
ollama pull mistral
```

#### Step 3: Clone Project Repository
```bash
git clone <your-repo-url> /home/pi/video-analytics
cd /home/pi/video-analytics
```

#### Step 4: Configure Network
- Determine IP addresses of each Pi:
  ```bash
  hostname -I
  ```
- Update docker-compose.yml with correct hostnames/IPs for MQTT broker
- Ensure all Pis can ping each other

#### Step 5: Deploy Containers
```bash
# On Pi 4 (or designated MQTT broker Pi):
docker-compose up -d mosquitto

# Wait 10 seconds, then on each Pi:
docker-compose up -d
```

#### Step 6: Verify System
```bash
# Check containers running:
docker ps

# Check MQTT connectivity:
docker logs <pi-name>-vision  # Should show subscription messages

# Access dashboard:
# Open browser to http://<pi4-ip>:5000
```

---

## Expected Performance Metrics

### Latency Targets
- Frame capture to Pi 1: <50ms
- Pi 1 → MQTT publish: <100ms
- Pi 2 vision inference: 5-15 seconds
- Pi 3 intelligence inference: 2-8 seconds
- MQTT → Dashboard update: <200ms
- **Total end-to-end latency:** ~8-30 seconds (acceptable for demo)

### Throughput
- Frames per second: 15-30 FPS
- Frames analyzed per minute: ~4-8 (limited by Pi 2 inference time)
- Dashboard updates: Real-time for latest analysis

### Resource Usage (Target)
- **Pi 1:** CPU 30-50%, Memory 300-500MB
- **Pi 2:** CPU 80-100% (during inference), Memory 1.5-1.8GB
- **Pi 3:** CPU 30-50%, Memory 1-1.2GB
- **Pi 4:** CPU 20-40%, Memory 400-600MB

---

## Demo Talking Points

### For Software Engineers
- "Each Pi has a specific responsibility - separation of concerns"
- "MQTT enables loose coupling between services"
- "Docker containers make deployment reproducible"
- "Pipeline parallelization reduces latency"

### For Cybersecurity Experts
- "All processing happens locally - no cloud dependency"
- "Useful for classified environments where data can't leave the network"
- "Models run entirely on-device"

### For Non-Technical Attendees
- "These four tiny computers are working together like a team"
- "Each one does one job really well"
- "The AI watches and understands what's happening in real-time"

---

## File Structure

```
intelligent-video-analytics/
├── README.md
├── docker-compose.yml
├── mosquitto.conf
├── requirements-common.txt
│
├── pi1-processor/
│   ├── Dockerfile
│   ├── processor.py
│   ├── requirements.txt
│   └── config.env
│
├── pi2-vision/
│   ├── Dockerfile
│   ├── vision_model.py
│   ├── requirements.txt
│   └── config.env
│
├── pi3-intelligence/
│   ├── Dockerfile
│   ├── intelligence_model.py
│   ├── requirements.txt
│   └── config.env
│
├── pi4-dashboard/
│   ├── Dockerfile
│   ├── app.py
│   ├── requirements.txt
│   ├── config.env
│   ├── templates/
│   │   └── dashboard.html
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css
│   │   └── js/
│   │       └── dashboard.js
│   └── tests/
│       └── test_dashboard.py
│
└── docs/
    ├── ARCHITECTURE.md
    ├── DEPLOYMENT.md
    └── TROUBLESHOOTING.md
```

---

## Troubleshooting & Common Issues

### Issue: Pi 2 inference taking too long
- **Cause:** Model too large for available RAM
- **Solution:** Use quantized version of LLaVA or switch to a smaller model

### Issue: MQTT messages not reaching Pi 3
- **Cause:** Network connectivity or mosquitto not running
- **Solution:** Check `docker logs mosquitto` and verify network connectivity

### Issue: Dashboard not updating
- **Cause:** WebSocket connection failed or backend not running
- **Solution:** Check Pi 4 logs with `docker logs pi4-dashboard` and verify port 5000 is accessible

### Issue: Out of memory on Pi 2 or Pi 3
- **Cause:** Ollama models consuming too much RAM
- **Solution:** Reduce frame resolution, decrease batch size, or use CPU instead of GPU

### Issue: Camera not detected
- **Cause:** Camera not connected or permissions issue
- **Solution:** Run `v4l2-ctl --list-devices` to verify camera is visible

---

## Optional Enhancements

1. **Voice Output:** Use text-to-speech to narrate observations aloud
2. **Anomaly Detection:** Flag unusual activity ("Person lying on ground detected")
3. **Web Frontend Improvements:** Add controls to start/stop analysis, adjust sensitivity
4. **Multi-Camera Support:** Add second camera stream for different angle
5. **Data Persistence:** Save observations to SQLite database for historical analysis
6. **Authentication:** Add password protection to dashboard
7. **Mobile App:** Create React Native app to view dashboard remotely
8. **Metrics Export:** Export Prometheus metrics for monitoring

---

## Success Criteria for Pie Day Demo

✅ System runs continuously for 30+ minutes without crashing  
✅ Dashboard displays live video feed with <5 second latency  
✅ AI narration generates meaningful observations  
✅ System metrics display on dashboard  
✅ All 4 Pis actively participate (visible in system metrics)  
✅ Audience can understand architecture without deep explanation  
✅ Demo generates 2-3 minutes of engaging conversation  
✅ Code is clean and deployable (no hardcoded paths/IPs)  

---

## References & Resources

- **Ollama:** https://ollama.ai
- **MQTT/Mosquitto:** https://mosquitto.org
- **OpenCV Python:** https://opencv.org
- **Docker Raspberry Pi:** https://docs.docker.com/install/linux/docker-ce/debian/
- **Flask-SocketIO:** https://flask-socketio.readthedocs.io/
- **Raspberry Pi Camera Documentation:** https://www.raspberrypi.com/documentation/accessories/camera.html

---

**Document Version:** 1.0  
**Last Updated:** February 25, 2026  
**Author:** Steven (PeopleTec)
