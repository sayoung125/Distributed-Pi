FROM arm64v8/python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared utilities
COPY shared/ ./shared/

# Copy dashboard code
COPY pi4-dashboard/app.py .
COPY pi4-dashboard/templates/ ./templates/
COPY pi4-dashboard/static/ ./static/

EXPOSE 5000

CMD ["python", "-u", "app.py"]
