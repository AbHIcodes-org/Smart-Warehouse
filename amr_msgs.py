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
            # Optimization: Faster string size estimation rather than heavy JSON serialization
            return len(str(self.payload)) + 64
        except Exception:
            return 128

