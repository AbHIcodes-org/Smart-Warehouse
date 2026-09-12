import random
import asyncio
from network import CommsMediator, DeadZone
from amr_node import TelemetryExtractor, AMRCommNode
from models import LinkPacket

class SimulationController:
    def __init__(self, num_amrs=15, on_event=None):
        self.num_amrs = num_amrs
        self.robot_ids = list(range(1, num_amrs + 1))
        self.on_event = on_event
        self.sim_time = 0.0
        
        rng = random.Random(42)
        self.wifi_net = CommsMediator(self.robot_ids, rng, comm_range=60.0, loss_rate=0.01, latency_mean=0.010, name="WIFI", on_event=self._dispatch_event)
        self.wisun_net = CommsMediator(self.robot_ids, rng, comm_range=40.0, loss_rate=0.05, latency_mean=0.080, name="WISUN", on_event=self._dispatch_event)
        
        self.dz = DeadZone(x0=15.0, y0=15.0, x1=45.0, y1=45.0)
        self.wifi_net.dead_zones.append(self.dz)
        
        self.extractors = {r_id: TelemetryExtractor(r_id) for r_id in self.robot_ids}
        self.comm_nodes = {r_id: AMRCommNode(r_id, self.wifi_net, self.wisun_net, self.robot_ids, on_event=self._dispatch_event) for r_id in self.robot_ids}
        
        self.positions = {}
        self._init_positions()
        
        self.running = False
        
    def _dispatch_event(self, event_type, packet=None, **kwargs):
        if self.on_event:
            self.on_event(event_type, packet, **kwargs)
            
    def _init_positions(self):
        initial_pos = [
            (5.0, 25.0), (48.0, 25.0), (10.0, 5.0), (25.0, 5.0), (45.0, 8.0),
            (5.0, 15.0), (5.0, 35.0), (8.0, 50.0), (20.0, 50.0), (35.0, 48.0),
            (48.0, 35.0), (48.0, 10.0), (32.0, 2.0), (18.0, 5.0), (2.0, 28.0)
        ]
        for i, r_id in enumerate(self.robot_ids):
            self.positions[r_id] = list(initial_pos[i % len(initial_pos)])
            self.wifi_net.update_position(r_id, *self.positions[r_id])
            self.wisun_net.update_position(r_id, *self.positions[r_id])
            
    def set_dead_zone(self, x0, y0, x1, y1):
        self.dz.bounds = (x0, y0, x1, y1)
        
    def force_dead_zone(self, amr_id, in_dz):
        if amr_id in self.comm_nodes:
            # Overrides physical dead zone logic slightly for manual test
            self.comm_nodes[amr_id].update_dead_zone_status(in_dz)
            
    def create_task(self, src_id, dst_id, task_data):
        if src_id in self.comm_nodes:
            self.comm_nodes[src_id].create_task_packet(dst_id, task_data, self.sim_time)
            
    async def step(self, dt=0.05):
        self.sim_time += dt
        
        # 1. Update positions (simple movement)
        for r_id in self.robot_ids:
            # Simple circular or back-and-forth movement
            self.positions[r_id][0] += (random.random() - 0.5) * 1.0
            self.positions[r_id][1] += (random.random() - 0.5) * 1.0
            
            # Constrain to 0-60
            self.positions[r_id][0] = max(0, min(60, self.positions[r_id][0]))
            self.positions[r_id][1] = max(0, min(60, self.positions[r_id][1]))
            
            px, py = self.positions[r_id]
            self.wifi_net.update_position(r_id, px, py)
            self.wisun_net.update_position(r_id, px, py)
            self.extractors[r_id].update_simulated_pose(px, py, linear_v=0.8)
            
            # Dispatch movement event
            self._dispatch_event("AMR_MOVED", amr_id=r_id, x=px, y=py)

            in_dz = self.dz.contains(px, py)
            self.comm_nodes[r_id].update_dead_zone_status(in_dz)
            
        # 2. Extract and broadcast telemetry
        for r_id in self.robot_ids:
            payload = self.extractors[r_id].get_json_payload()
            self.comm_nodes[r_id].broadcast_telemetry(payload, self.sim_time)
            
        # 3. Process queues
        for r_id in self.robot_ids:
            self.comm_nodes[r_id].process_queue(self.sim_time)
            
        # 4. Step networks
        self.wifi_net.step(self.sim_time)
        self.wisun_net.step(self.sim_time)
        
        # 5. Receive packets
        for r_id in self.robot_ids:
            self.comm_nodes[r_id].process_inbox(self.sim_time)

    async def run_loop(self):
        self.running = True
        while self.running:
            await self.step(dt=0.05)
            await asyncio.sleep(0.05)
