import random
import asyncio
import math
from network import CommsMediator, DeadZone
from amr_node import TelemetryExtractor, AMRCommNode
from models import LinkPacket

class SimulationController:
    def __init__(self, num_amrs=10, on_event=None):
        self.num_amrs = num_amrs
        self.robot_ids = list(range(1, num_amrs + 1))
        self.all_nodes = [0] + self.robot_ids # 0 is server
        self.on_event = on_event
        self.sim_time = 0.0
        
        rng = random.Random(42)
        self.wifi_net = CommsMediator(self.all_nodes, rng, comm_range=30.0, loss_rate=0.01, latency_mean=0.010, name="WIFI", on_event=self._dispatch_event)
        self.wisun_net = CommsMediator(self.all_nodes, rng, comm_range=40.0, loss_rate=0.05, latency_mean=0.080, name="WISUN", on_event=self._dispatch_event)
        
        self.dz = DeadZone(x0=15.0, y0=15.0, x1=45.0, y1=45.0)
        self.wifi_net.dead_zones.append(self.dz)
        
        self.extractors = {r_id: TelemetryExtractor(r_id) for r_id in self.robot_ids}
        self.comm_nodes = {r_id: AMRCommNode(r_id, self.wifi_net, self.wisun_net, self.all_nodes, on_event=self._dispatch_event) for r_id in self.all_nodes}
        
        self.positions = {}
        self.waypoints = {}
        self.current_wp_idx = {}
        self._init_positions()
        
        self.running = False
        
    def _dispatch_event(self, event_type, packet=None, **kwargs):
        if self.on_event:
            self.on_event(event_type, packet, **kwargs)
            
    def _generate_waypoints(self):
        wps = []
        for _ in range(5):
            wps.append([random.uniform(5, 55), random.uniform(5, 55)])
        return wps

    def _init_positions(self):
        # Server pos
        self.positions[0] = [30.0, 5.0]
        self.wifi_net.update_position(0, 30.0, 5.0)
        self.wisun_net.update_position(0, 30.0, 5.0)

        initial_pos = [
            (5.0, 25.0), (48.0, 25.0), (10.0, 5.0), (25.0, 5.0), (45.0, 8.0),
            (5.0, 15.0), (5.0, 35.0), (8.0, 50.0), (20.0, 50.0), (35.0, 48.0)
        ]
        for i, r_id in enumerate(self.robot_ids):
            self.positions[r_id] = list(initial_pos[i % len(initial_pos)])
            self.waypoints[r_id] = self._generate_waypoints()
            self.current_wp_idx[r_id] = 0
            
            self.wifi_net.update_position(r_id, *self.positions[r_id])
            self.wisun_net.update_position(r_id, *self.positions[r_id])
            
    def set_dead_zone(self, x0, y0, x1, y1):
        self.dz.bounds = (x0, y0, x1, y1)
        
    def force_dead_zone(self, amr_id, in_dz):
        if amr_id in self.comm_nodes:
            self.comm_nodes[amr_id].update_dead_zone_status(in_dz)
            
    def create_task(self, src_id, dst_id, task_data):
        if src_id in self.comm_nodes:
            self.comm_nodes[src_id].create_task_packet(dst_id, task_data, self.sim_time)
            
    async def step(self, dt=0.05):
        self.sim_time += dt
        
        # 1. Update positions (Waypoint movement + collision avoidance)
        for r_id in self.robot_ids:
            px, py = self.positions[r_id]
            target = self.waypoints[r_id][self.current_wp_idx[r_id]]
            tx, ty = target
            
            dist = math.hypot(tx - px, ty - py)
            if dist < 1.0:
                self.current_wp_idx[r_id] = (self.current_wp_idx[r_id] + 1) % len(self.waypoints[r_id])
                target = self.waypoints[r_id][self.current_wp_idx[r_id]]
                tx, ty = target

            dx = tx - px
            dy = ty - py
            mag = math.hypot(dx, dy)
            if mag == 0: mag = 1

            vx = (dx / mag) * 0.5
            vy = (dy / mag) * 0.5

            too_close = False
            for other_id in self.robot_ids:
                if other_id != r_id:
                    ox, oy = self.positions[other_id]
                    if math.hypot(ox - px, oy - py) < 3.0:
                        rx = ox - px
                        ry = oy - py
                        dot = vx * rx + vy * ry
                        if dot > 0:
                            too_close = True
                            break
            
            if not too_close:
                self.positions[r_id][0] += vx
                self.positions[r_id][1] += vy
                
            self.positions[r_id][0] = max(0, min(60, self.positions[r_id][0]))
            self.positions[r_id][1] = max(0, min(60, self.positions[r_id][1]))
            
            px, py = self.positions[r_id]
            self.wifi_net.update_position(r_id, px, py)
            self.wisun_net.update_position(r_id, px, py)
            self.extractors[r_id].update_simulated_pose(px, py, linear_v=0.8)
            
            self._dispatch_event("AMR_MOVED", amr_id=r_id, x=px, y=py)

            in_dz = self.dz.contains(px, py)
            self.comm_nodes[r_id].update_dead_zone_status(in_dz)
            
        # Dispatch topology
        links = []
        for i in self.all_nodes:
            for j in self.all_nodes:
                if i < j:
                    pi = self.positions[i]
                    pj = self.positions[j]
                    dist = math.hypot(pi[0] - pj[0], pi[1] - pj[1])
                    
                    i_dz = self.dz.contains(*pi) if i != 0 else False
                    j_dz = self.dz.contains(*pj) if j != 0 else False

                    if not i_dz and not j_dz and dist <= self.wifi_net.range:
                        links.append({"src": i, "dst": j, "type": "WIFI"})
                    if dist <= self.wisun_net.range and (i_dz or j_dz): 
                        links.append({"src": i, "dst": j, "type": "WISUN"})
        
        self._dispatch_event("NETWORK_TOPOLOGY", links=links)

        # 2. Extract and broadcast telemetry
        for r_id in self.robot_ids:
            payload = self.extractors[r_id].get_json_payload()
            self.comm_nodes[r_id].broadcast_telemetry(payload, self.sim_time)
            
        # 3. Process queues
        for n_id in self.all_nodes:
            self.comm_nodes[n_id].process_queue(self.sim_time)
            
        # 4. Step networks
        self.wifi_net.step(self.sim_time)
        self.wisun_net.step(self.sim_time)
        
        # 5. Receive packets
        for n_id in self.all_nodes:
            self.comm_nodes[n_id].process_inbox(self.sim_time)

    async def run_loop(self):
        self.running = True
        while self.running:
            await self.step(dt=0.05)
            await asyncio.sleep(0.05)
