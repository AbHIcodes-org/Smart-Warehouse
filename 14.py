"""
server_dashboard.py - Passive Central Server & Task Broadcaster
Broadcasting tasks at 0.5 Hz over Wi-Fi and tracking fleet positions.
"""
import time
from amr_msgs import LinkPacket, BROADCAST
from comms import CommsMediator

class ServerDashboard:
    def __init__(self, server_id: int, wifi_net: CommsMediator):
        self.server_id = server_id
        self.wifi_net = wifi_net
        self.fleet_positions = {}
        self.last_task_broadcast = 0.0

    def broadcast_task(self, task_data: dict, now: float) -> LinkPacket:
        """Broadcasts task commands at 0.5 Hz (every 2 seconds)."""
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

    def receive_telemetry((self) -> dict:
        """Collects telemetry delivered via direct Wi-Fi or gateway relays."""
        pkts = self.wifi_net.receive(self.server_id)
        for pkt in pkts:
            if pkt.msg_type in ["TELEMETRY", "TELEMETRY_RELAY"]:
                amr_id = pkt.payload.get("amr_id")
                pos = pkt.payload.get("position")
                if amr_id is not None and pos is not None:
                    self.fleet_positions[amr_id] = pos
        return self.fleet_positions