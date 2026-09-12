"""
demo_visualizer.py - Live Interactive Multi-AMR Fleet & Mesh Comms Visualizer
Presents a live, real-time animated simulation showing AMR navigation, RF dead zone penetration,
Wi-SUN mesh relay links, dynamic rate throttling, and central server dashboard tracking.
"""
import sys
import os
import math
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.patches as patches
from gazebo_world_and_network import create_simulation_environment

def run_animated_fleet_visualizer(save_gif_path=None, max_frames=120):
    env = create_simulation_environment()
    SERVER_ID = env["SERVER_ID"]
    NUM_AMRS = env["NUM_AMRS"]
    robot_ids = env["robot_ids"]
    wifi_net = env["wifi_net"]
    wisun_net = env["wisun_net"]
    dz = env["dz"]
    dashboard = env["dashboard"]
    telemetry_extractors = env["telemetry_extractors"]
    comm_nodes = env["comm_nodes"]
    positions = env["positions"]

    # Trajectory path for AMR 1 (Recorded for path trail)
    path_history = []

    # Initialize Figure with 2 subplots (Map on Left, Mission Control HUD on Right)
    fig = plt.figure(figsize=(15, 7.5), facecolor='#12151c')
    gs = fig.add_gridspec(1, 2, width_ratios=[1.2, 1.0], wspace=0.25)
    
    ax_map = fig.add_subplot(gs[0, 0])
    ax_hud = fig.add_subplot(gs[0, 1])

    # Simulation step state
    sim_state = {
        "step": 0,
        "sim_time": 0.0,
        "dt": 0.05,
        "paused": False
    }

    def on_key(event):
        if event.key == ' ':
            sim_state["paused"] = not sim_state["paused"]
        elif event.key == 'r':
            sim_state["step"] = 0
            sim_state["sim_time"] = 0.0
            path_history.clear()

    fig.canvas.mpl_connect('key_press_event', on_key)

    def update_frame(frame_num):
        if sim_state["paused"]:
            return

        sim_state["step"] += 1
        sim_state["sim_time"] += sim_state["dt"]
        step = sim_state["step"]
        sim_time = sim_state["sim_time"]

        # 1. Update AMR 1 Trajectory across phases
        # Phase 1: Corridor (5 -> 15) [Wi-Fi Zone]
        # Phase 2: Traverses Dead Zone (15 -> 45) [Wi-SUN Mesh Relay Zone]
        # Phase 3: Exits Dead Zone (45 -> 55) [Handover to Wi-Fi Zone]
        if step < 20:
            positions[1][0] += 0.50
        elif step < 80:
            positions[1][0] += 0.50
        else:
            positions[1][0] += 0.25

        px, py = positions[1]
        path_history.append((px, py))

        # 2. Physics & State Synchronization
        active_dz_robots = []
        for r_id in robot_ids:
            rx, ry = positions[r_id]
            wifi_net.update_position(r_id, rx, ry)
            wisun_net.update_position(r_id, rx, ry)
            telemetry_extractors[r_id].update_simulated_pose(rx, ry, linear_v=0.8)

            in_dz = dz.contains(rx, ry)
            comm_nodes[r_id].update_dead_zone_status(in_dz)
            if in_dz:
                active_dz_robots.append(r_id)

        # 3. Server Task Broadcast & AMR Telemetry Transmission
        task_pkt = dashboard.broadcast_task({"task_id": "DISPATCH_BAY_4", "speed_limit": 1.2}, sim_time)

        for r_id in robot_ids:
            payload = telemetry_extractors[r_id].get_json_payload()
            comm_nodes[r_id].broadcast_telemetry(payload, sim_time)

        # 4. Advance Network Physics (Flight Queues & Latency)
        wifi_net.step(sim_time)
        wisun_net.step(sim_time)

        # 5. Process Inboxes & Relays
        for r_id in robot_ids:
            comm_nodes[r_id].process_inbox(sim_time)
            if task_pkt:
                comm_nodes[r_id].handle_task_broadcast(task_pkt, active_dz_robots, sim_time)

        # 6. Server Telemetry Ingestion
        live_fleet = dashboard.receive_telemetry(sim_time)

        # ==================== RENDER WAREHOUSE MAP ====================
        ax_map.clear()
        ax_map.set_facecolor('#1a1e28')
        ax_map.set_xlim(-5, 65)
        ax_map.set_ylim(-5, 65)
        ax_map.set_title("Warehouse Map: 2D Spatial Comms Topography", color='white', fontsize=12, fontweight='bold', pad=12)
        ax_map.set_xlabel("Warehouse X Coordinates (meters)", color='#9ba3b4', fontsize=9)
        ax_map.set_ylabel("Warehouse Y Coordinates (meters)", color='#9ba3b4', fontsize=9)
        ax_map.tick_params(colors='#737d92', labelsize=8)
        ax_map.grid(True, linestyle='--', alpha=0.15, color='white')

        # Draw Dead Zone (X: 15-45, Y: 15-45)
        dz_rect = patches.Rectangle(
            (15, 15), 30, 30, 
            linewidth=1.5, edgecolor='#ff4444', 
            facecolor='#ff2222', alpha=0.18, 
            hatch='///', zorder=1
        )
        ax_map.add_patch(dz_rect)
        ax_map.text(30, 42.0, "WI-FI DEAD ZONE (Dense Metal Racks)", color='#ff8888', 
                    fontsize=8.5, fontweight='bold', ha='center', va='center', zorder=2)

        # Plot AMR 1 Trail
        if len(path_history) > 1:
            xs, ys = zip(*path_history[-25:])
            ax_map.plot(xs, ys, color='#00e5ff', alpha=0.4, linewidth=1.8, linestyle=':', zorder=3)

        # Plot Server at (0, 0)
        ax_map.scatter(0, 0, color='#3b82f6', s=140, marker='s', edgecolors='white', linewidth=1.5, zorder=6)
        ax_map.text(0, -3.5, "Central Server", color='#60a5fa', fontsize=8, fontweight='bold', ha='center', zorder=6)

        # Plot AMRs 2-15
        amr_x = [positions[r][0] for r in range(2, NUM_AMRS + 1)]
        amr_y = [positions[r][1] for r in range(2, NUM_AMRS + 1)]
        ax_map.scatter(amr_x, amr_y, color='#10b981', s=70, marker='o', edgecolors='#047857', linewidth=1.2, zorder=5)

        # Highlight Gateway AMR (AMR 2)
        ax_map.scatter(positions[2][0], positions[2][1], color='#f59e0b', s=110, marker='D', edgecolors='white', linewidth=1.5, zorder=7)
        ax_map.text(positions[2][0], positions[2][1] + 2.5, "AMR 2 (Gateway)", color='#fbbf24', fontsize=7.5, fontweight='bold', ha='center', zorder=7)

        # Plot AMR 1 with Dynamic Color
        amr1_x, amr1_y = positions[1]
        amr1_in_dz = dz.contains(amr1_x, amr1_y)
        amr1_color = '#ef4444' if amr1_in_dz else '#10b981'
        ax_map.scatter(amr1_x, amr1_y, color=amr1_color, s=150, marker='o', edgecolors='white', linewidth=2.0, zorder=8)
        mode_label = "AMR 1 (Wi-SUN Mesh)" if amr1_in_dz else "AMR 1 (Wi-Fi 10Hz)"
        ax_map.text(amr1_x, amr1_y - 3.2, mode_label, color=amr1_color, fontsize=8, fontweight='bold', ha='center', zorder=8)

        # Draw Active Relay Links
        if amr1_in_dz:
            # Wi-SUN Mesh Link: AMR 1 to Gateway AMR 2
            ax_map.plot([amr1_x, positions[2][0]], [amr1_y, positions[2][1]], 
                        color='#38bdf8', linestyle='--', linewidth=2.2, alpha=0.9, zorder=4)
            # Wi-Fi Bridge Link: Gateway AMR 2 to Server (0, 0)
            ax_map.plot([positions[2][0], 0], [positions[2][1], 0], 
                        color='#fbbf24', linestyle='-', linewidth=2.0, alpha=0.85, zorder=4)
            # Blocked Direct Wi-Fi Red Line
            ax_map.plot([amr1_x, 0], [amr1_y, 0], 
                        color='#ef4444', linestyle=':', linewidth=1.2, alpha=0.4, zorder=3)
        else:
            # Direct Wi-Fi Link: AMR 1 to Server
            ax_map.plot([amr1_x, 0], [amr1_y, 0], 
                        color='#10b981', linestyle='-', linewidth=1.8, alpha=0.7, zorder=4)

        # ==================== RENDER MISSION CONTROL HUD ====================
        ax_hud.clear()
        ax_hud.set_facecolor('#1a1e28')
        ax_hud.axis('off')

        amr1_route = dashboard.delivery_route.get(1, "OFFLINE")
        relayed_by = dashboard.relayed_via.get(1)
        route_text = f"Wi-SUN Relay via AMR {relayed_by}" if relayed_by else "Direct Wi-Fi"
        freq_text = "2 Hz (Wi-SUN Throttled)" if amr1_in_dz else "10 Hz (Full Wi-Fi)"
        status_color = "#f87171" if amr1_in_dz else "#34d399"
        status_text = "DEAD ZONE DETECTED (LIFELINE MESH ON)" if amr1_in_dz else "FULL WI-FI COVERAGE"

        hud_title = "CENTRAL FLEET MISSION CONTROL"
        ax_hud.text(0.04, 0.94, hud_title, color='white', fontsize=13, fontweight='bold')
        ax_hud.text(0.04, 0.89, f"Elapsed Sim Time: {sim_time:5.2f}s  |  Fleet Status: {len(live_fleet)}/{NUM_AMRS} Online", 
                    color='#94a3b8', fontsize=9.5)

        # AMR 1 Telemetry Card
        card_y = 0.84
        rect_card = patches.FancyBboxPatch(
            (0.03, card_y - 0.35), 0.94, 0.35,
            boxstyle="round,pad=0.02,rounding_size=0.03",
            facecolor='#222736', edgecolor='#334155', linewidth=1.2
        )
        ax_hud.add_patch(rect_card)

        ax_hud.text(0.06, card_y - 0.05, "AMR 1 (MISSION VEHICLE TELEMETRY)", color='#38bdf8', fontsize=10, fontweight='bold')
        ax_hud.text(0.06, card_y - 0.11, f"Status: {status_text}", color=status_color, fontsize=8.5, fontweight='bold')
        ax_hud.text(0.06, card_y - 0.17, f"Position: X = {amr1_x:5.2f}m,  Y = {amr1_y:5.2f}m", color='#e2e8f0', fontsize=8.5)
        ax_hud.text(0.06, card_y - 0.23, f"Broadcast Rate: {freq_text}", color='#e2e8f0', fontsize=8.5)
        ax_hud.text(0.06, card_y - 0.29, f"Active Route:    {route_text}", color='#fbbf24' if relayed_by else '#34d399', fontsize=8.5, fontweight='bold')

        # Network Analytics Metrics Card
        stats_y = 0.44
        rect_stats = patches.FancyBboxPatch(
            (0.03, stats_y - 0.38), 0.94, 0.38,
            boxstyle="round,pad=0.02,rounding_size=0.03",
            facecolor='#222736', edgecolor='#334155', linewidth=1.2
        )
        ax_hud.add_patch(rect_stats)

        wifi_stats = wifi_net.stats()
        wisun_stats = wisun_net.stats()
        amr1_sent = comm_nodes[1].telemetry_sent
        amr1_recv = dashboard.packet_counts.get(1, 0)
        pdr = (amr1_recv / max(1, amr1_sent)) * 100

        ax_hud.text(0.06, stats_y - 0.05, "DECENTRALIZED PROTOCOL AUDIT", color='#a78bfa', fontsize=10, fontweight='bold')
        ax_hud.text(0.06, stats_y - 0.11, f"[+] Wi-Fi Packets Delivered:      {wifi_stats['packets_delivered']}", color='#e2e8f0', fontsize=8.5)
        ax_hud.text(0.06, stats_y - 0.17, f"[+] Wi-Fi Dead-Zone Drops:       {wifi_stats['dropped_deadzone']} (Blocked by Obstacle)", color='#f87171', fontsize=8.5)
        ax_hud.text(0.06, stats_y - 0.23, f"[+] Wi-SUN Mesh Packets Relayed: {wisun_stats['packets_delivered']}", color='#38bdf8', fontsize=8.5)
        ax_hud.text(0.06, stats_y - 0.29, f"[+] Server Duplicate Relays Suppressed: {dashboard.duplicates_suppressed}", color='#e2e8f0', fontsize=8.5)
        ax_hud.text(0.06, stats_y - 0.35, f"[+] Telemetry Continuity (PDR): {pdr:5.1f}% (ZERO BLACKOUT)", color='#34d399', fontsize=9, fontweight='bold')

    ani = animation.FuncAnimation(fig, update_frame, frames=max_frames, interval=50, repeat=True)

    if save_gif_path:
        if save_gif_path.endswith('.png') or save_gif_path.endswith('.jpg'):
            print(f"[*] Advancing simulation to mid-journey in dead zone...")
            for _ in range(45):
                update_frame(0)
            plt.tight_layout()
            print(f"[*] Saving presentation snapshot to {save_gif_path}...")
            plt.savefig(save_gif_path, dpi=200, bbox_inches='tight', facecolor=fig.get_facecolor())
            print(f"[+] Snapshot saved successfully!")
            plt.close()
        else:
            print(f"[*] Saving animation to {save_gif_path}...")
            ani.save(save_gif_path, writer='pillow', fps=20)
            print(f"[+] Animation saved successfully!")
    else:
        plt.tight_layout()
        print("\n============================================================")
        print("   LIVE MULTI-AMR SIMULATION RUNNING (Press Space to Pause) ")
        print("============================================================")
        plt.show()

if __name__ == "__main__":
    save_path = sys.argv[1] if len(sys.argv) > 1 else None
    run_animated_fleet_visualizer(save_gif_path=save_path)
