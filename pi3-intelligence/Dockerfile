FROM arm64v8/python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared utilities
COPY shared/ ./shared/

# Copy intelligence code
COPY pi3-intelligence/intelligence.py .

CMD ["python", "-u", "intelligence.py"]
