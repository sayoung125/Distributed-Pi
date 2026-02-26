/**
 * Distributed Pi Video Analytics Dashboard
 * Real-time frontend using Socket.IO
 */

const socket = io();

// State
let latestDetections = [];
let frameCount = 0;
let visionCount = 0;
let narrativeCount = 0;
const startTime = Date.now();

// DOM elements
const connectionStatus = document.getElementById('connection-status');
const videoCanvas = document.getElementById('video-canvas');
const videoFrame = document.getElementById('video-frame');
const ctx = videoCanvas.getContext('2d');

// Connection status
socket.on('connect', () => {
    connectionStatus.textContent = 'Connected';
    connectionStatus.className = 'status-connected';
});

socket.on('disconnect', () => {
    connectionStatus.textContent = 'Disconnected';
    connectionStatus.className = 'status-disconnected';
});

// Frame updates - draw image and bounding boxes
socket.on('frame_update', (data) => {
    frameCount++;
    document.getElementById('frame-id').textContent = `Frame: ${data.frame_id}`;
    document.getElementById('frame-timestamp').textContent = formatTime(data.timestamp);
    document.getElementById('stat-frames').textContent = frameCount;

    // Load image
    const img = new Image();
    img.onload = () => {
        videoCanvas.width = data.width || 640;
        videoCanvas.height = data.height || 480;
        ctx.drawImage(img, 0, 0, videoCanvas.width, videoCanvas.height);
        drawBoundingBoxes(ctx, latestDetections, videoCanvas.width, videoCanvas.height);
    };
    img.src = `data:image/jpeg;base64,${data.jpeg_b64}`;
});

// Vision updates
socket.on('vision_update', (data) => {
    visionCount++;
    latestDetections = data.detections || [];
    document.getElementById('vision-inference').textContent = Math.round(data.inference_ms);
    document.getElementById('stat-visions').textContent = visionCount;

    // Update detections list
    const listEl = document.getElementById('detections-list');
    if (latestDetections.length === 0) {
        listEl.innerHTML = '<p class="placeholder">No objects detected</p>';
        return;
    }

    listEl.innerHTML = latestDetections.map(d => `
        <div class="detection-item">
            <span class="class-name">${d.class}</span>
            <span class="confidence">
                ${(d.confidence * 100).toFixed(0)}%
                <span class="confidence-bar">
                    <span class="confidence-bar-fill" style="width: ${d.confidence * 100}%"></span>
                </span>
            </span>
        </div>
    `).join('');
});

// Intelligence updates
socket.on('intelligence_update', (data) => {
    narrativeCount++;
    document.getElementById('narrative').innerHTML = `<p>${escapeHtml(data.narrative)}</p>`;
    document.getElementById('trend').textContent = data.trend || '';
    document.getElementById('intel-inference').textContent = Math.round(data.inference_ms);
    document.getElementById('stat-narratives').textContent = narrativeCount;

    // Add to timeline
    addTimelineEntry(data);
});

// Metrics updates
socket.on('metrics_update', (data) => {
    const node = data.node;
    if (!node) return;

    const cpuBar = document.getElementById(`${node}-cpu`);
    const cpuVal = document.getElementById(`${node}-cpu-val`);
    const memBar = document.getElementById(`${node}-mem`);
    const memVal = document.getElementById(`${node}-mem-val`);
    const tempEl = document.getElementById(`${node}-temp`);
    const card = document.getElementById(`node-${node}`);

    if (cpuBar) {
        cpuBar.style.width = `${data.cpu_percent}%`;
        cpuBar.style.background = getBarColor(data.cpu_percent);
    }
    if (cpuVal) cpuVal.textContent = `${Math.round(data.cpu_percent)}%`;
    if (memBar) {
        memBar.style.width = `${data.memory_percent}%`;
        memBar.style.background = getBarColor(data.memory_percent);
    }
    if (memVal) memVal.textContent = `${Math.round(data.memory_percent)}%`;
    if (tempEl) {
        tempEl.textContent = data.cpu_temperature
            ? `${data.cpu_temperature.toFixed(1)}°C`
            : '--';
    }
    if (card) card.classList.add('online');
});

// Draw bounding boxes on canvas
function drawBoundingBoxes(ctx, detections, canvasW, canvasH) {
    const colors = {
        person: '#3fb950',
        car: '#58a6ff',
        dog: '#d29922',
        cat: '#bc8cff',
    };
    const defaultColor = '#58a6ff';

    detections.forEach(det => {
        const [x1, y1, x2, y2] = det.bbox;
        const color = colors[det.class] || defaultColor;

        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);

        // Label background
        const label = `${det.class} ${(det.confidence * 100).toFixed(0)}%`;
        ctx.font = '12px sans-serif';
        const textWidth = ctx.measureText(label).width;
        ctx.fillStyle = color;
        ctx.fillRect(x1, y1 - 18, textWidth + 8, 18);

        // Label text
        ctx.fillStyle = '#000';
        ctx.fillText(label, x1 + 4, y1 - 5);
    });
}

// Add entry to timeline
function addTimelineEntry(data) {
    const timeline = document.getElementById('timeline');

    // Remove placeholder
    const placeholder = timeline.querySelector('.placeholder');
    if (placeholder) placeholder.remove();

    const entry = document.createElement('div');
    entry.className = 'timeline-entry';

    const counts = data.vision_summary || {};
    const objectStr = Object.entries(counts)
        .map(([k, v]) => `${v} ${k}`)
        .join(', ') || 'none';

    entry.innerHTML = `
        <div class="time">${formatTime(data.timestamp)} | Frame #${data.frame_id}</div>
        <div class="narrative">${escapeHtml(data.narrative)}</div>
        <div class="objects">Objects: ${objectStr}</div>
    `;

    timeline.prepend(entry);

    // Keep only last 20 entries
    while (timeline.children.length > 20) {
        timeline.removeChild(timeline.lastChild);
    }
}

// Utility: format ISO timestamp
function formatTime(isoStr) {
    if (!isoStr) return '--';
    try {
        const d = new Date(isoStr);
        return d.toLocaleTimeString();
    } catch {
        return isoStr;
    }
}

// Utility: get bar color based on percentage
function getBarColor(percent) {
    if (percent > 90) return '#f85149';
    if (percent > 70) return '#d29922';
    return '#58a6ff';
}

// Utility: escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Update uptime counter
setInterval(() => {
    const seconds = Math.floor((Date.now() - startTime) / 1000);
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    document.getElementById('stat-uptime').textContent =
        mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
}, 1000);
