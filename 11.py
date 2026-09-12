"""
amr_msgs.py - Standard message definition for P2P transport layer.
"""
import json
from dataclasses import dataclass, field

BROADCAST: int = -1

@dataclass
class LinkPacket:
    msg_id: str             # Unique message identifier
    src: int                # Permanent Origin AMR ID
    forwarder: int          # ID of node transmitting this hop
    dst: int                # Target AMR ID or BROADCAST (-1)
    ttl: int                # Time-To-Live (hop count)
    msg_type: str           # 'TELEMETRY', 'TASK_BROADCAST', 'P2P_INTENT'
    priority: int           # Priority flag (1 = High, 5 = Low)
    payload: dict = field(default_factory=dict)

    def size_bytes(self) -> int:
        """Calculate packet size in bytes for network volume logging."""
        try:
            return len(json.dumps({
                "msg_id": self.msg_id,
                "src": self.src,
                "forwarder": self.forwarder,
                "dst": self.dst,
                "ttl": self.ttl,
                "msg_type": self.msg_type,
                "priority": self.priority,
                "payload": self.payload
            }).encode('utf-8'))
        except Exception:
            return 128