const canvas = document.getElementById('warehouseCanvas');
const ctx = canvas.getContext('2d');
const logContainer = document.getElementById('log-container');
const packetDetails = document.getElementById('packet-details');
const amrDetails = document.getElementById('amr-details-content');
const amrSelect = document.getElementById('amr-select');

let amrs = {};
let deadZone = {x0: 15, y0: 15, x1: 45, y1: 45};
let activeLinks = [];
let selectedAmr = null;

let metrics = {
    sent: 0,
    delivered: 0,
    dups: 0,
    ttl: 0
};

// Canvas mapping: 60x60 units -> 600x600 pixels (scale 10)
const SCALE = 10;

function drawWarehouse() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw Dead Zone
    ctx.fillStyle = 'rgba(255, 0, 0, 0.1)';
    ctx.strokeStyle = 'red';
    ctx.lineWidth = 1;
    ctx.fillRect(deadZone.x0 * SCALE, deadZone.y0 * SCALE, (deadZone.x1 - deadZone.x0) * SCALE, (deadZone.y1 - deadZone.y0) * SCALE);
    ctx.strokeRect(deadZone.x0 * SCALE, deadZone.y0 * SCALE, (deadZone.x1 - deadZone.x0) * SCALE, (deadZone.y1 - deadZone.y0) * SCALE);
    
    // Draw links
    const now = Date.now();
    activeLinks = activeLinks.filter(link => now - link.timestamp < 300); // fade out after 300ms
    
    activeLinks.forEach(link => {
        const src = amrs[link.src];
        const dst = amrs[link.dst];
        if (src && dst) {
            ctx.beginPath();
            ctx.moveTo(src.x * SCALE, src.y * SCALE);
            ctx.lineTo(dst.x * SCALE, dst.y * SCALE);
            if (link.type === 'WIFI') ctx.strokeStyle = 'rgba(74, 222, 128, 0.6)'; // green
            else if (link.type === 'WISUN') ctx.strokeStyle = 'rgba(96, 165, 250, 0.6)'; // blue
            else if (link.type === 'DROP') ctx.strokeStyle = 'rgba(248, 113, 113, 0.8)'; // red
            else ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
            ctx.lineWidth = 2;
            ctx.stroke();
        }
    });
    
    // Draw AMRs
    for (const [id, amr] of Object.entries(amrs)) {
        ctx.beginPath();
        ctx.arc(amr.x * SCALE, amr.y * SCALE, 6, 0, 2 * Math.PI);
        if (selectedAmr == id) {
            ctx.fillStyle = '#facc15'; // yellow
        } else if (amr.in_dz) {
            ctx.fillStyle = '#f87171'; // red
        } else {
            ctx.fillStyle = '#4ade80'; // green
        }
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 1;
        ctx.stroke();
        
        ctx.fillStyle = '#fff';
        ctx.font = '10px sans-serif';
        ctx.fillText(`AMR-${id}`, amr.x * SCALE - 15, amr.y * SCALE - 10);
    }
}

function updateMetrics() {
    document.getElementById('m-sent').innerText = metrics.sent;
    document.getElementById('m-delivered').innerText = metrics.delivered;
    document.getElementById('m-dups').innerText = metrics.dups;
    document.getElementById('m-ttl').innerText = metrics.ttl;
}

function logEvent(type, msg, packet = null, cssClass = "log-INFO") {
    const el = document.createElement('div');
    el.className = `log-entry ${cssClass}`;
    const time = new Date().toLocaleTimeString();
    el.innerText = `[${time}] ${msg}`;
    
    if (packet) {
        el.onclick = () => {
            packetDetails.innerText = JSON.stringify(packet, null, 2);
        };
    }
    
    logContainer.prepend(el);
    if (logContainer.children.length > 100) {
        logContainer.removeChild(logContainer.lastChild);
    }
}

function updateAmrDetails() {
    if (!selectedAmr || !amrs[selectedAmr]) return;
    const amr = amrs[selectedAmr];
    amrDetails.innerHTML = `
        <strong>ID:</strong> AMR-${selectedAmr}<br>
        <strong>Position:</strong> (${amr.x.toFixed(1)}, ${amr.y.toFixed(1)})<br>
        <strong>Wi-Fi:</strong> ${amr.in_dz ? '<span style="color:red">DISCONNECTED</span>' : '<span style="color:lime">CONNECTED</span>'}<br>
        <strong>Wi-SUN:</strong> ${amr.in_dz ? '<span style="color:lime">ACTIVE</span>' : 'STANDBY'}<br>
        <strong>Queue Load:</strong> ${amr.queue_len || 0}
    `;
}

// Interactivity
canvas.addEventListener('click', (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / SCALE;
    const y = (e.clientY - rect.top) / SCALE;
    
    selectedAmr = null;
    for (const [id, amr] of Object.entries(amrs)) {
        if (Math.hypot(amr.x - x, amr.y - y) < 2) {
            selectedAmr = id;
            amrSelect.value = id;
            break;
        }
    }
    updateAmrDetails();
});

// WebSocket
const ws = new WebSocket(`ws://${location.host}/ws`);

ws.onopen = () => {
    logEvent("SYS", "WebSocket Connected", null, "log-INFO");
};

ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    const type = msg.type;
    const data = msg.data;
    const pkt = msg.packet;
    
    if (type === "AMR_MOVED") {
        const id = data.amr_id;
        if (!amrs[id]) {
            amrs[id] = { id, in_dz: false, queue_len: 0 };
            const opt = document.createElement('option');
            opt.value = id;
            opt.innerText = `AMR-${id}`;
            amrSelect.appendChild(opt);
        }
        amrs[id].x = data.x;
        amrs[id].y = data.y;
    }
    else if (type === "WIFI_LOST") {
        amrs[data.amr_id].in_dz = true;
        logEvent(type, `AMR-${data.amr_id} entered dead zone. Wi-Fi lost.`, null, "log-WARN");
    }
    else if (type === "WIFI_RECOVERED") {
        amrs[data.amr_id].in_dz = false;
        logEvent(type, `AMR-${data.amr_id} exited dead zone. Wi-Fi recovered.`, null, "log-INFO");
    }
    else if (type === "PACKET_CREATED") {
        metrics.sent++;
    }
    else if (type === "PACKET_QUEUED") {
        amrs[data.amr_id].queue_len = data.queue_length;
    }
    else if (type === "PACKET_TRANSMITTING") {
        if (pkt.destination_id != -1) {
            activeLinks.push({
                src: pkt.forwarder_id,
                dst: pkt.destination_id,
                type: pkt.medium,
                timestamp: Date.now()
            });
        }
    }
    else if (type === "PACKET_DELIVERED") {
        metrics.delivered++;
        if (pkt.message_type !== "TELEMETRY") {
            logEvent(type, `Delivered: ${pkt.message_id} to AMR-${data.receiver_id} via ${pkt.medium}`, pkt, "log-WIFI");
        }
    }
    else if (type === "DUPLICATE_DROPPED") {
        metrics.dups++;
        if (pkt.message_type !== "TELEMETRY") {
            logEvent(type, `Duplicate Dropped: ${pkt.message_id} at AMR-${data.amr_id}`, pkt, "log-DROP");
        }
    }
    else if (type === "TTL_EXPIRED") {
        metrics.ttl++;
        logEvent(type, `TTL Expired: ${pkt.message_id} at AMR-${data.amr_id}`, pkt, "log-DROP");
    }
    else if (type === "PACKET_DROPPED") {
        if (data.reason === "DEADZONE_SENDER" || data.reason === "DEADZONE_RECEIVER") {
            // Visualize drop
            if (pkt.destination_id != -1) {
                activeLinks.push({
                    src: pkt.forwarder_id,
                    dst: pkt.destination_id,
                    type: 'DROP',
                    timestamp: Date.now()
                });
            }
        }
    }
    else if (type === "CONGESTION_DETECTED") {
        logEvent(type, `Congestion at AMR-${data.amr_id} (${(data.score*100).toFixed(0)}%)`, null, "log-WARN");
    }
    else if (type === "BRIDGE_SELECTED") {
        logEvent(type, `Bridge Selected: AMR-${data.amr_id} forwarding ${pkt.message_id}`, pkt, "log-WISUN");
    }
    
    updateMetrics();
    updateAmrDetails();
};

function loop() {
    drawWarehouse();
    requestAnimationFrame(loop);
}
requestAnimationFrame(loop);

document.getElementById('btn-force-dz').onclick = () => {
    const id = parseInt(amrSelect.value);
    if(id) ws.send(JSON.stringify({action: "FORCE_DEADZONE", amr_id: id, in_deadzone: true}));
};
document.getElementById('btn-restore-wifi').onclick = () => {
    const id = parseInt(amrSelect.value);
    if(id) ws.send(JSON.stringify({action: "FORCE_DEADZONE", amr_id: id, in_deadzone: false}));
};
document.getElementById('btn-send-task').onclick = () => {
    const src = parseInt(document.getElementById('task-src').value);
    const dst = parseInt(document.getElementById('task-dst').value);
    ws.send(JSON.stringify({action: "SEND_TASK", src, dst, task: {type: "GOTO_BAY"}}));
};
