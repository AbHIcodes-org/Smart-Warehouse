const canvas = document.getElementById('warehouseCanvas');
const ctx = canvas.getContext('2d');
const logContainer = document.getElementById('log-container');
const packetDetails = document.getElementById('packet-details');

let amrs = {};
let deadZone = {x0: 15, y0: 15, x1: 45, y1: 45};
let topologyLinks = [];
let activeLinks = [];
let bridges = new Set();
let packetsInFlight = []; // For animation

const SCALE = 10;
const WIFI_RANGE = 30; // Matches backend
const WISUN_RANGE = 40;

// Interactivity for Dead Zone
let isDraggingDZ = false;
let dragOffsetX = 0;
let dragOffsetY = 0;

canvas.addEventListener('mousedown', (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / SCALE;
    const y = (e.clientY - rect.top) / SCALE;
    
    if (x >= deadZone.x0 && x <= deadZone.x1 && y >= deadZone.y0 && y <= deadZone.y1) {
        isDraggingDZ = true;
        dragOffsetX = x - deadZone.x0;
        dragOffsetY = y - deadZone.y0;
    }
});

canvas.addEventListener('mousemove', (e) => {
    if (isDraggingDZ) {
        const rect = canvas.getBoundingClientRect();
        const x = (e.clientX - rect.left) / SCALE;
        const y = (e.clientY - rect.top) / SCALE;
        
        const w = deadZone.x1 - deadZone.x0;
        const h = deadZone.y1 - deadZone.y0;
        
        deadZone.x0 = Math.max(0, Math.min(60 - w, x - dragOffsetX));
        deadZone.y0 = Math.max(0, Math.min(60 - h, y - dragOffsetY));
        deadZone.x1 = deadZone.x0 + w;
        deadZone.y1 = deadZone.y0 + h;
        
        // Send update to server
        ws.send(JSON.stringify({action: "UPDATE_DZ", x0: deadZone.x0, y0: deadZone.y0, x1: deadZone.x1, y1: deadZone.y1}));
    }
});

canvas.addEventListener('mouseup', () => { isDraggingDZ = false; });
canvas.addEventListener('mouseleave', () => { isDraggingDZ = false; });

document.getElementById('dz-w').addEventListener('input', (e) => {
    const w = parseFloat(e.target.value);
    deadZone.x1 = Math.min(60, deadZone.x0 + w);
    ws.send(JSON.stringify({action: "UPDATE_DZ", x0: deadZone.x0, y0: deadZone.y0, x1: deadZone.x1, y1: deadZone.y1}));
});
document.getElementById('dz-h').addEventListener('input', (e) => {
    const h = parseFloat(e.target.value);
    deadZone.y1 = Math.min(60, deadZone.y0 + h);
    ws.send(JSON.stringify({action: "UPDATE_DZ", x0: deadZone.x0, y0: deadZone.y0, x1: deadZone.x1, y1: deadZone.y1}));
});


function drawWarehouse() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw Dead Zone
    ctx.fillStyle = 'rgba(255, 0, 0, 0.2)';
    ctx.strokeStyle = 'red';
    ctx.lineWidth = 2;
    ctx.fillRect(deadZone.x0 * SCALE, deadZone.y0 * SCALE, (deadZone.x1 - deadZone.x0) * SCALE, (deadZone.y1 - deadZone.y0) * SCALE);
    ctx.strokeRect(deadZone.x0 * SCALE, deadZone.y0 * SCALE, (deadZone.x1 - deadZone.x0) * SCALE, (deadZone.y1 - deadZone.y0) * SCALE);
    
    // Draw Topology Links (AVAILABLE NETWORK LINKS)
    topologyLinks.forEach(link => {
        const src = amrs[link.src];
        const dst = amrs[link.dst];
        if (src && dst) {
            ctx.beginPath();
            ctx.moveTo(src.x * SCALE, src.y * SCALE);
            ctx.lineTo(dst.x * SCALE, dst.y * SCALE);
            if (link.type === 'WIFI') ctx.strokeStyle = 'rgba(74, 222, 128, 0.2)'; // Faint green
            else if (link.type === 'WISUN') ctx.strokeStyle = 'rgba(96, 165, 250, 0.2)'; // Faint blue
            ctx.lineWidth = 1;
            ctx.stroke();
        }
    });

    const now = Date.now();
    activeLinks = activeLinks.filter(link => now - link.timestamp < 300); // 300ms flash
    packetsInFlight = packetsInFlight.filter(p => now - p.timestamp < 500); // 500ms animation
    
    // Draw Active Links
    activeLinks.forEach(link => {
        const src = amrs[link.src];
        const dst = amrs[link.dst];
        if (src && dst) {
            ctx.beginPath();
            ctx.moveTo(src.x * SCALE, src.y * SCALE);
            ctx.lineTo(dst.x * SCALE, dst.y * SCALE);
            if (link.type === 'WIFI') ctx.strokeStyle = '#4ade80'; // Bright green
            else if (link.type === 'WISUN') ctx.strokeStyle = '#60a5fa'; // Bright blue
            ctx.lineWidth = 3;
            ctx.stroke();
        }
    });
    
    // Draw Packets (Animated dots)
    packetsInFlight.forEach(pkt => {
        const src = amrs[pkt.src];
        const dst = amrs[pkt.dst];
        if (src && dst) {
            const progress = (now - pkt.timestamp) / 500;
            const x = src.x + (dst.x - src.x) * progress;
            const y = src.y + (dst.y - src.y) * progress;
            ctx.beginPath();
            ctx.arc(x * SCALE, y * SCALE, 4, 0, 2 * Math.PI);
            ctx.fillStyle = '#ffffff';
            ctx.fill();
        }
    });

    // Draw AMRs
    for (const [id, amr] of Object.entries(amrs)) {
        if (id == 0) {
            // Draw Server
            ctx.fillStyle = '#fff';
            ctx.fillRect(amr.x * SCALE - 15, amr.y * SCALE - 15, 30, 30);
            ctx.fillStyle = '#000';
            ctx.font = '10px sans-serif';
            ctx.fillText(`SERVER`, amr.x * SCALE - 20, amr.y * SCALE - 20);
            
            // Server Wifi range
            ctx.beginPath();
            ctx.arc(amr.x * SCALE, amr.y * SCALE, WIFI_RANGE * SCALE, 0, 2 * Math.PI);
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
            ctx.lineWidth = 1;
            ctx.stroke();
            continue;
        }

        // Draw Comm Range
        ctx.beginPath();
        const range = amr.in_dz ? WISUN_RANGE : WIFI_RANGE;
        ctx.arc(amr.x * SCALE, amr.y * SCALE, range * SCALE, 0, 2 * Math.PI);
        ctx.strokeStyle = amr.in_dz ? 'rgba(96, 165, 250, 0.1)' : 'rgba(74, 222, 128, 0.1)';
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 5]);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.beginPath();
        ctx.arc(amr.x * SCALE, amr.y * SCALE, 8, 0, 2 * Math.PI);
        
        let label = "Wi-Fi";
        let color = '#4ade80';
        
        if (amr.in_dz) {
            color = '#f87171';
            label = "DEAD ZONE / Wi-SUN";
        }
        if (bridges.has(parseInt(id))) {
            color = '#facc15';
            label = "BRIDGE";
        }

        ctx.fillStyle = color;
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2;
        ctx.stroke();
        
        ctx.fillStyle = '#fff';
        ctx.font = '12px sans-serif';
        ctx.fillText(`AMR-${id}`, amr.x * SCALE - 15, amr.y * SCALE - 15);
        ctx.fillStyle = color;
        ctx.font = '10px sans-serif';
        ctx.fillText(label, amr.x * SCALE - 15, amr.y * SCALE + 20);
    }
}

function updateMetrics() {
    let wifi_c = 0;
    let dz_c = 0;
    for(const [id, a] of Object.entries(amrs)){
        if (id == 0) continue;
        if(a.in_dz) dz_c++;
        else wifi_c++;
    }
    document.getElementById('m-wifi-amrs').innerText = wifi_c;
    document.getElementById('m-dz-amrs').innerText = dz_c;
    document.getElementById('m-bridges').innerText = bridges.size;
    
    let wl = 0, wl_s = 0;
    topologyLinks.forEach(l => {
        if(l.type === 'WIFI') wl++;
        if(l.type === 'WISUN') wl_s++;
    });
    document.getElementById('m-wifi-links').innerText = wl;
    document.getElementById('m-wisun-links').innerText = wl_s;
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
    if (logContainer.children.length > 50) {
        logContainer.removeChild(logContainer.lastChild);
    }
}

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
        if (!amrs[id]) amrs[id] = { id, in_dz: false };
        amrs[id].x = data.x;
        amrs[id].y = data.y;
    }
    else if (type === "NETWORK_TOPOLOGY") {
        topologyLinks = data.links;
        updateMetrics();
        
        // Ensure server is always registered
        if (!amrs[0]) {
            amrs[0] = {id: 0, x: 30, y: 5, in_dz: false};
        }
    }
    else if (type === "WIFI_LOST") {
        amrs[data.amr_id].in_dz = true;
        bridges.delete(data.amr_id); // cannot be bridge if in dz
        logEvent(type, `AMR-${data.amr_id} ENTERED DEAD ZONE`, null, "log-WARN");
    }
    else if (type === "WIFI_RECOVERED") {
        amrs[data.amr_id].in_dz = false;
        logEvent(type, `AMR-${data.amr_id} EXITED DEAD ZONE`, null, "log-INFO");
    }
    else if (type === "BRIDGE_SELECTED") {
        bridges.add(data.amr_id);
        logEvent(type, `BRIDGE SELECTED: AMR-${data.amr_id} forwarding ${pkt.message_id}`, pkt, "log-WISUN");
    }
    else if (type === "PACKET_TRANSMITTING") {
        if (pkt.destination_id != -1) {
            activeLinks.push({
                src: pkt.forwarder_id,
                dst: pkt.destination_id,
                type: pkt.medium,
                timestamp: Date.now()
            });
            packetsInFlight.push({
                src: pkt.forwarder_id,
                dst: pkt.destination_id,
                timestamp: Date.now()
            });
            // Show explicit logs for tasks/acks
            if (pkt.message_type === "TASK" || pkt.message_type === "ACK") {
                logEvent(type, `${pkt.message_type}: ${pkt.forwarder_id} -> ${pkt.destination_id} via ${pkt.medium}`, pkt, "log-WIFI");
            }
        } else {
            // Broadcast packet - show radiating from forwarder to all in topology
            topologyLinks.forEach(l => {
                if (l.src === pkt.forwarder_id) {
                    activeLinks.push({src: l.src, dst: l.dst, type: l.type, timestamp: Date.now()});
                    packetsInFlight.push({src: l.src, dst: l.dst, timestamp: Date.now()});
                }
                if (l.dst === pkt.forwarder_id) {
                    activeLinks.push({src: l.dst, dst: l.src, type: l.type, timestamp: Date.now()});
                    packetsInFlight.push({src: l.dst, dst: l.src, timestamp: Date.now()});
                }
            });
            if (pkt.message_type === "TASK") {
                logEvent(type, `SERVER BROADCAST STARTED: ${pkt.message_id}`, pkt, "log-WIFI");
            }
        }
    }
    else if (type === "TASK_RECEIVED") {
        logEvent(type, `AMR-${data.amr_id} RECEIVED TASK`, pkt, "log-WIFI");
    }
};

function loop() {
    drawWarehouse();
    requestAnimationFrame(loop);
}
requestAnimationFrame(loop);

document.getElementById('btn-send-task').onclick = () => {
    ws.send(JSON.stringify({action: "SEND_TASK", src: 0, dst: -1, task: {type: "GOTO_BAY"}})); // Broadcast from server
};
