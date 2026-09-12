import time
from amr_msgs import LinkPacket, BROADCAST
from comms import CommsMediator

class ServerDashboard:
    def __init__(self, server_id: int, wifi_net: CommsMediator):
        self.server_id = server_id
        self.wifi_net = wifi_net
        self.fleet_positions = {}
        self.last_seen = {}  # Optimization: Track staleness of AMRs
        self.delivery_route = {}  # 'DIRECT_WIFI' or 'WISUN_RELAY'
        self.relayed_via = {}     # Forwarder robot ID if relayed
        self.packet_counts = {}
        self.seen_msg_ids = set()
        self.duplicates_suppressed = 0
        self.last_task_broadcast = 0.0

    def broadcast_task(self, task_data: dict, now: float = None) -> LinkPacket:
        """Broadcasts task commands at 0.5 Hz (every 2 seconds)."""
        if now is None:
            now = time.time()
        if now - self.last_task_broadcast < 2.0:
            return None
        
        self.last_task_broadcast = now
        msg_id = f"TASK_{now:.2f}"
        pkt = LinkPacket(
            msg_id=msg_id,
            src=self.server_id,
            forwarder=self.server_id,
            dst=BROADCAST,
            ttl=4,
            msg_type="TASK_ASSIGNMENT",
            priority=1,
            payload=task_data
        )
        self.wifi_net.send(pkt, now)
        return pkt

    def receive_telemetry(self, now: float = None) -> dict:
        """Collects telemetry delivered via direct Wi-Fi or gateway relays with deduplication."""
        if now is None:
            now = time.time()
            
        pkts = self.wifi_net.receive(self.server_id)
        for pkt in pkts:
            if pkt.msg_type in ["TELEMETRY", "TELEMETRY_RELAY"]:
                # Suppress multi-gateway duplicate relays
                if pkt.msg_id in self.seen_msg_ids:
                    self.duplicates_suppressed += 1
                    continue
                self.seen_msg_ids.add(pkt.msg_id)

                amr_id = pkt.payload.get("amr_id")
                pos = pkt.payload.get("position")
                if amr_id is not None and pos is not None:
                    self.fleet_positions[amr_id] = pos
                    self.last_seen[amr_id] = now
                    self.packet_counts[amr_id] = self.packet_counts.get(amr_id, 0) + 1
                    if pkt.msg_type == "TELEMETRY_RELAY":
                        self.delivery_route[amr_id] = "WISUN_RELAY"
                        self.relayed_via[amr_id] = pkt.forwarder
                    else:
                        self.delivery_route[amr_id] = "DIRECT_WIFI"
                        self.relayed_via[amr_id] = None
                    
        # Optimization: Evict stale AMRs that haven't reported in > 5.0 seconds
        stale_amrs = [r_id for r_id, last_t in self.last_seen.items() if now - last_t > 5.0]
        for r_id in stale_amrs:
            self.fleet_positions.pop(r_id, None)
            self.last_seen.pop(r_id, None)
            self.delivery_route.pop(r_id, None)
            self.relayed_via.pop(r_id, None)
            
        return self.fleet_positions

