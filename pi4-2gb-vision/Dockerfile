FROM arm64v8/python:3.11-slim

WORKDIR /app

# Install OpenCV system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared utilities
COPY shared/ ./shared/

# Copy vision detector code
COPY pi4-2gb-vision/vision_detector.py .

# Download YOLOv8n model at build time so it's cached in the image
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

CMD ["python", "-u", "vision_detector.py"]
