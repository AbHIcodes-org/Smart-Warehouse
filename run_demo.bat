@echo off
title Multi-AMR Hybrid Communications Simulation
cls
echo ============================================================================
echo         DECENTRALIZED MULTI-AMR HYBRID COMMS SIMULATION
echo   Dual Transport: High-Speed Wi-Fi (10 Hz) + Wi-SUN Sub-GHz Mesh (2 Hz)
echo ============================================================================
echo.
echo Select presentation mode:
echo   [1] Launch Live Interactive GUI Visualizer (Warehouse Map + Mission HUD)
echo   [2] Run Terminal Simulation with Network KPI Telemetry Logs
echo   [3] Generate Fresh Presentation Screenshot (PNG)
echo.
set /p choice="Enter option (1, 2, or 3) [default: 1]: "
if "%choice%"=="" set choice=1

if "%choice%"=="1" (
    echo.
    echo [*] Starting Live Animated GUI Visualizer...
    echo [*] Controls: Press [SPACE] to Pause/Resume, [R] to Restart.
    .\.venv\Scripts\python demo_visualizer.py
) else if "%choice%"=="2" (
    echo.
    echo [*] Executing Multi-AMR Simulation Engine...
    .\.venv\Scripts\python gazebo_world_and_network.py
) else if "%choice%"=="3" (
    echo.
    echo [*] Generating high-resolution presentation screenshot...
    .\.venv\Scripts\python demo_visualizer.py presentation_snapshot.png
    echo [+] Saved to presentation_snapshot.png
) else (
    echo Invalid choice. Exiting.
)

echo.
pause
