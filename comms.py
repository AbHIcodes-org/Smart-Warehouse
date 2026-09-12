import math
import heapq
from collections import deque

class DeadZone:
    def __init__(self, x0, y0, x1, y1, deliver_prob=0.0):
        self.bounds = (x0, y0, x1, y1)
        self.prob = deliver_prob
        
    def contains(self, x, y):
        x0, y0, x1, y1 = self.bounds
        return x0 <= x <= x1 and y0 <= y <= y1

class CommsMediator:
    """Mock Network Physics Engine for Multi-AMR Fleet Simulation"""
    def __init__(self, robot_ids, rng, comm_range, loss_rate=0.0, latency_mean=0.0, name="NET"):
        self.name = name
        self.positions = {}
        self.inboxes = {r: [] for r in robot_ids}
        self.dead_zones = []
        self.range = comm_range
        self.loss_rate = loss_rate
        self.latency_mean = latency_mean
        self.rng = rng
        self.packets_sent = 0
        self.packets_delivered = 0
        self.packets_dropped_deadzone = 0
        self.packets_dropped_range = 0
        self.packets_dropped_loss = 0
        self.flight_queue = []  # Min-heap of (delivery_time, seq, r_id, packet)
        self.seq = 0
        self.recent_links = deque(maxlen=30)  # Stores (src_id, dst_id, success_bool, timestamp)
        
    def update_position(self, r_id, x, y):
        self.positions[r_id] = (x, y)
        
    def is_in_dead_zone(self, x, y):
        return any(dz.contains(x, y) for dz in self.dead_zones)
        
    def send(self, pkt, now):
        self.packets_sent += 1
        src_pos = self.positions.get(pkt.forwarder)
        if not src_pos:
            return
        
        # Wi-Fi blocking: If sender is inside a dead zone and this medium has dead zones
        if self.dead_zones and self.is_in_dead_zone(*src_pos):
            self.packets_dropped_deadzone += 1
            return
        
        for r_id, pos in self.positions.items():
            if r_id == pkt.forwarder:
                continue
            
            # If unicast/directed packet (not BROADCAST), skip non-destination nodes
            if pkt.dst != -1 and pkt.dst != r_id:
                continue
            
            # Dead zone blocking: If receiver is inside dead zone on this medium
            if self.dead_zones and self.is_in_dead_zone(*pos):
                self.packets_dropped_deadzone += 1
                self.recent_links.append((pkt.forwarder, r_id, False, now, "DEADZONE_DROP"))
                continue
            
            # Check Euclidean range
            dist = math.hypot(pos[0] - src_pos[0], pos[1] - src_pos[1])
            if dist > self.range:
                self.packets_dropped_range += 1
                continue
            
            # Check probabilistic channel packet loss
            if self.rng.random() <= self.loss_rate:
                self.packets_dropped_loss += 1
                self.recent_links.append((pkt.forwarder, r_id, False, now, "RF_LOSS"))
                continue
            
            # Calculate delivery time based on latency model
            if self.latency_mean > 0.0:
                jitter = self.rng.gauss(0, self.latency_mean * 0.15)
                delay = max(0.001, self.latency_mean + jitter)
                delivery_time = now + delay
                self.seq += 1
                heapq.heappush(self.flight_queue, (delivery_time, self.seq, r_id, pkt))
            else:
                self.inboxes[r_id].append(pkt)
                self.packets_delivered += 1

            self.recent_links.append((pkt.forwarder, r_id, True, now, "DELIVERED"))

    def receive(self, r_id):
        pkts = self.inboxes.get(r_id, [])
        self.inboxes[r_id] = []
        return pkts
        
    def step(self, now):
        """Advances network physics and delivers in-flight packets whose latency elapsed."""
        while self.flight_queue and self.flight_queue[0][0] <= now:
            _, _, r_id, pkt = heapq.heappop(self.flight_queue)
            if r_id in self.inboxes:
                self.inboxes[r_id].append(pkt)
                self.packets_delivered += 1
        
    def stats(self):
        return {
            "name": self.name,
            "loss_rate": self.loss_rate,
            "packets_sent": self.packets_sent,
            "packets_delivered": self.packets_delivered,
            "dropped_deadzone": self.packets_dropped_deadzone,
            "dropped_range": self.packets_dropped_range,
            "dropped_loss": self.packets_dropped_loss
        }

