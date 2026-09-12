import time
from collections import deque
from amr_msgs import LinkPacket, BROADCAST
from comms import CommsMediator

class AMRCommNode:
    def __init__(self, robot_id: int, wifi_net: CommsMediator, wisun_net: CommsMediator, all_ids: list[int]):
        self.robot_id = robot_id
        self.wifi_net = wifi_net
        self.wisun_net = wisun_net
        self.all_ids = all_ids
        
        # Per-peer interface tracking ('WIFI' or 'WISUN')
        self.peer_interfaces = {r_id: 'WIFI' for r_id in all_ids if r_id != robot_id}
        self.seen_msg_ids = set()
        self.seen_msg_history = deque(maxlen=500)
        
        # State tracking
        self.in_dead_zone = False
        self.last_broadcast_time = 0.0
        self.telemetry_sent = 0
        self.relayed_count = 0
        self.tasks_bridged = 0

    def update_dead_zone_status(self, is_dead: bool):
        self.in_dead_zone = is_dead

    def _is_duplicate(self, msg_id: str) -> bool:
        if msg_id in self.seen_msg_ids:
            return True
        self.seen_msg_ids.add(msg_id)
        self.seen_msg_history.append(msg_id)
        if len(self.seen_msg_history) == 500:
            oldest = self.seen_msg_history.popleft()
            self.seen_msg_ids.discard(oldest)
        return False

    def broadcast_telemetry(self, telemetry_payload: dict, now: float):
        """Broadcasts telemetry with dynamic rate throttling based on dead zone state."""
        interval = 0.5 if self.in_dead_zone else 0.1  # 2 Hz in Dead Zone, 10 Hz in Wi-Fi
        if now - self.last_broadcast_time < interval:
            return

        self.last_broadcast_time = now
        self.telemetry_sent += 1
        msg_id = f"TEL_{self.robot_id}_{now:.3f}"
        
        pkt = LinkPacket(
            msg_id=msg_id,
            src=self.robot_id,
            forwarder=self.robot_id,
            dst=BROADCAST,
            ttl=3,
            msg_type="TELEMETRY",
            priority=2,
            payload=telemetry_payload
        )
        self._is_duplicate(msg_id)

        if self.in_dead_zone:
            # Send over Wi-SUN (Lifeline fallback)
            self.wisun_net.send(pkt, now)
        else:
            # Send over Wi-Fi (High-bandwidth direct)
            self.wifi_net.send(pkt, now)

    def process_inbox(self, now: float) -> list[dict]:
        """Drains inbox from both mediums, enforces per-peer rules, and relays bridge messages."""
        received_payloads = []

        # 1. DRAIN WI-FI INBOX
        wifi_pkts = self.wifi_net.receive(self.robot_id)
        for pkt in wifi_pkts:
            if self._is_duplicate(pkt.msg_id) or pkt.ttl <= 0:
                continue
            
            self.peer_interfaces[pkt.src] = 'WIFI'
            received_payloads.append(pkt.payload)

        # 2. DRAIN WI-SUN INBOX (Dead Zone Lifeline)
        wisun_pkts = self.wisun_net.receive(self.robot_id)
        for pkt in wisun_pkts:
            if self._is_duplicate(pkt.msg_id) or pkt.ttl <= 0:
                continue

            # Update link status for dead zone AMR
            self.peer_interfaces[pkt.src] = 'WISUN'
            received_payloads.append(pkt.payload)

            # BRIDGE LOGIC
            if not self.in_dead_zone and pkt.msg_type == "TELEMETRY":
                relay_pkt = LinkPacket(
                    msg_id=f"RELAY_{pkt.msg_id}",
                    src=pkt.src,
                    forwarder=self.robot_id,
                    dst=0,  # Server ID
                    ttl=pkt.ttl - 1,
                    msg_type="TELEMETRY_RELAY",
                    priority=1,
                    payload=pkt.payload
                )
                self.wifi_net.send(relay_pkt, now)
                self.relayed_count += 1

        return received_payloads

    def handle_task_broadcast(self, task_pkt: LinkPacket, active_deadzone_robots: list[int], now: float):
        """Designated Forwarder rule: Load-balanced Wi-Fi robot bridges server tasks to Wi-SUN."""
        if self.in_dead_zone or not active_deadzone_robots:
            return

        wifi_active_nodes = [r_id for r_id, iface in self.peer_interfaces.items() if iface == 'WIFI']
        wifi_active_nodes.append(self.robot_id)
        
        # Optimization: Distribute bridging load over time using modulo instead of static min()
        sorted_nodes = sorted(wifi_active_nodes)
        designated_forwarder = sorted_nodes[int(now) % len(sorted_nodes)]

        if self.robot_id == designated_forwarder:
            for dz_robot in active_deadzone_robots:
                bridge_pkt = LinkPacket(
                    msg_id=f"BRIDGE_TASK_{task_pkt.msg_id}_{dz_robot}",
                    src=task_pkt.src,
                    forwarder=self.robot_id,
                    dst=dz_robot,
                    ttl=2,
                    msg_type="TASK_ASSIGNMENT",
                    priority=1,
                    payload=task_pkt.payload
                )
                self.wisun_net.send(bridge_pkt, now)
                self.tasks_bridged += 1

