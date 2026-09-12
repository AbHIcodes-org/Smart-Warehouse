"""
gazebo_world_and_network.py - Main Hackathon Simulation Harness
Instantiates 15 AMRs, sets up dual network mediums, and simulates physics/network steps.
"""
import time
import random
from amr_msgs import BROADCAST
from comms import CommsMediator, DeadZone
from telemetry_extractor_node import TelemetryExtractorNode
from amr_comm_node import AMRCommNode
from server_dashboard import ServerDashboard

def run_hackathon_simulation():
    SERVER_ID = 0
    NUM_AMRS = 15
    robot_ids = list(range(1, NUM_AMRS + 1))
    all_nodes = [SERVER_ID] + robot_ids

    # 1. INITIALIZE DUAL NETWORK MEDIUMS
    rng = random.Random(42)
    
    # High Bandwidth Wi-Fi Medium
    wifi_net = CommsMediator(robot_ids=all_nodes, rng=rng, comm_range=60.0, loss_rate=0.01)
    # Define rectangular Dead Zone (X: 10m to 50m, Y: 10m to 50m) where Wi-Fi fails completely
    dz = DeadZone(x0=10.0, y0=10.0, x1=50.0, y1=50.0, deliver_prob=0.0)
    wifi_net.dead_zones.append(dz)

    # Backup Low Bandwidth Wi-SUN Medium (No Dead Zones, higher latency)
    wisun_net = CommsMediator(robot_ids=all_nodes, rng=rng, comm_range=40.0, loss_rate=0.05, latency_mean=0.08)

    # 2. INSTANTIATE AGENTS
    dashboard = ServerDashboard(SERVER_ID, wifi_net)
    telemetry_extractors = {r_id: TelemetryExtractorNode(r_id) for r_id in robot_ids}
    comm_nodes = {r_id: AMRCommNode(r_id, wifi_net, wisun_net, robot_ids) for r_id in robot_ids}

    # 3. SET INITIAL POSITIONS IN 300x300m WAREHOUSE
    # AMR 1 is placed inside the Dead Zone (X: 20, Y: 20)
    positions = {1: (20.0, 20.0)}
    for r_id in range(2, NUM_AMRS + 1):
        positions[r_id] = (60.0 + (r_id * 5.0), 60.0 + (r_id * 3.0))

    # Server position at origin
    wifi_net.update_position(SERVER_ID, 0.0, 0.0)
    wisun_net.update_position(SERVER_ID, 0.0, 0.0)

    print("==========================================================")
    print("   DECENTRALIZED MULTI-AMR COMMS SIMULATION RUNNING       ")
    print("==========================================================")

    # 4. SIMULATION LOOP (Stepping through time)
    sim_time = 0.0
    dt = 0.05  # 20 Hz simulation tick

    for step in range(100):
        sim_time += dt

        # Update physical positions in both mediators
        active_dz_robots = []
        for r_id in robot_ids:
            px, py = positions[r_id]
            wifi_net.update_position(r_id, px, py)
            wisun_net.update_position(r_id, px, py)

            # Check if AMR is currently inside Wi-Fi dead zone
            in_dz = dz.contains(px, py)
            comm_nodes[r_id].update_dead_zone_status(in_dz)
            if in_dz:
                active_dz_robots.append(r_id)

        # Step 1: Server broadcasts task at 0.5 Hz
        task_pkt = dashboard.broadcast_task({"task_id": "MOVE_BAY_4", "target_x": 100.0}, sim_time)

        # Step 2: AMRs extract telemetry and send messages
        for r_id in robot_ids:
            # Get JSON data from simulated Jetson extractor
            payload = telemetry_extractors[r_id].get_json_payload()
            
            # Broadcast telemetry via dynamic transport node
            comm_nodes[r_id].broadcast_telemetry(payload, sim_time)

        # Step 3: Advance mediator packets in flight
        wifi_net.step(sim_time)
        wisun_net.step(sim_time)

        # Step 4: Process incoming messages & gateway bridging
        for r_id in robot_ids:
            comm_nodes[r_id].process_inbox(sim_time)
            
            if task_pkt:
                comm_nodes[r_id].handle_task_broadcast(task_pkt, active_dz_robots, sim_time)

        # Step 5: Dashboard processes received status
        live_fleet = dashboard.receive_telemetry()

        # Step log output every 1 second
        if step % 20 == 0:
            print(f"\n[Time {sim_time:.1f}s] Active Fleet Positions on Dashboard: {len(live_fleet)}/{NUM_AMRS}")
            print(f" -> AMR 1 in Dead Zone? {dz.contains(*positions[1])}")
            print(f" -> Server received AMR 1 telemetry via Wi-SUN Relay? {1 in live_fleet}")

    print("\n================ FINAL SIMULATION METRICS ================")
    print(f"Wi-Fi Network Stats: {wifi_net.stats()}")
    print(f"Wi-SUN Network Stats: {wisun_net.stats()}")

if __name__ == "__main__":
    run_hackathon_simulation()