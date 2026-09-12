from __future__ import annotations
import time
import threading

try:
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from nav_msgs.msg import Odometry
    from sensor_msgs.msg import LaserScan
    HAS_ROS2 = True
except ImportError:
    HAS_ROS2 = False
    class Node:
        """Dummy base class when running outside a ROS 2 environment."""
        def __init__(self, name: str):
            self._node_name = name
    Odometry = object
    LaserScan = object

class TelemetryExtractorNode(Node):
    def __init__(self, robot_id: int):
        if HAS_ROS2:
            super().__init__(f'telemetry_extractor_{robot_id}')
        else:
            super().__init__(f'telemetry_extractor_{robot_id}')
        self.robot_id = robot_id
        
        # Concurrency lock to prevent torn reads
        self.lock = threading.Lock()
        
        # Sensor state cache
        self.x = 0.0
        self.y = 0.0
        self.linear_v = 0.0
        self.angular_v = 0.0
        self.current_intent = "IDLE"
        self.min_obstacle_dist = 999.0
        self.is_path_clear = True
        
        # Subscriptions to MiR100 hardware topics (Optimized: Best-Effort QoS)
        if HAS_ROS2:
            self.create_subscription(Odometry, f'/amr_{robot_id}/odom', self._odom_cb, qos_profile_sensor_data)
            self.create_subscription(LaserScan, f'/amr_{robot_id}/scan', self._scan_cb, qos_profile_sensor_data)

    def _odom_cb(self, msg: Odometry):
        with self.lock:
            self.x = round(msg.pose.pose.position.x, 2)
            self.y = round(msg.pose.pose.position.y, 2)
            self.linear_v = round(msg.twist.twist.linear.x, 2)
            self.angular_v = round(msg.twist.twist.angular.z, 2)

    def _scan_cb(self, msg: LaserScan):
        # Optimized: Generator expression avoids creating an intermediate list in memory
        min_dist = min((r for r in msg.ranges if msg.range_min <= r <= msg.range_max), default=999.0)
        with self.lock:
            self.min_obstacle_dist = round(min_dist, 2)
            self.is_path_clear = self.min_obstacle_dist > 1.0

    def set_intent(self, intent_str: str):
        with self.lock:
            self.current_intent = intent_str

    def update_simulated_pose(self, x: float, y: float, linear_v: float = 0.0, angular_v: float = 0.0):
        """Allows direct pose injection in simulation or test benches without ROS 2 topics."""
        with self.lock:
            self.x = round(x, 2)
            self.y = round(y, 2)
            self.linear_v = round(linear_v, 2)
            self.angular_v = round(angular_v, 2)

    def set_simulated_scan(self, min_obstacle_dist: float):
        """Allows direct simulated LiDAR range injection."""
        with self.lock:
            self.min_obstacle_dist = round(min_obstacle_dist, 2)
            self.is_path_clear = self.min_obstacle_dist > 1.0

    def get_json_payload(self) -> dict:
        """Returns JSON payload formatted for backend algorithm consumption."""
        with self.lock:
            return {
                "timestamp": time.time(),
                "amr_id": self.robot_id,
                "position": {"x": self.x, "y": self.y},
                "velocity": {"linear": self.linear_v, "angular": self.angular_v},
                "intent": self.current_intent,
                "lidar_summary": {
                    "min_obstacle_dist": self.min_obstacle_dist,
                    "path_clear": self.is_path_clear
                }
            }

