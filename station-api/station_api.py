"""
Station API — FastAPI REST interface for Drone Station
Controls docks, drones, and streams via MQTT + MediaMTX.
"""

import os
import requests
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from mqtt_handler import DroneStation


# ── Config from environment ───────────────────────
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
RTSP_API = os.getenv("RTSP_API", "http://localhost:9997")

# ── MQTT Station Instance ─────────────────────────
station = DroneStation(mqtt_host=MQTT_HOST, mqtt_port=MQTT_PORT)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    station.start()
    yield
    # Shutdown
    station.stop()


app = FastAPI(
    title="🚁 Drone Station API",
    description="MQTT + RTSP Drone/Dock Command Center",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ────────────────────────────────────────

class DockCommand(BaseModel):
    command: str  # open, close, charge, reset
    params: Optional[dict] = None

class DroneCommand(BaseModel):
    command: str  # takeoff, land, waypoint, rtl, hover
    params: Optional[dict] = None


# ── Endpoints ─────────────────────────────────────

@app.get("/")
async def root():
    return {
        "service": "Drone Station Server",
        "version": "1.0.0",
        "components": {
            "mqtt": f"{MQTT_HOST}:{MQTT_PORT}",
            "rtsp": RTSP_API,
        },
    }


@app.get("/status")
async def system_status():
    """System health check."""
    # Check MQTT
    mqtt_ok = station.client.is_connected()

    # Check MediaMTX
    rtsp_ok = False
    try:
        r = requests.get(f"{RTSP_API}/v3/paths/list", timeout=3)
        rtsp_ok = r.status_code == 200
    except Exception:
        pass

    return {
        "mqtt": "connected" if mqtt_ok else "disconnected",
        "rtsp": "running" if rtsp_ok else "down",
        "docks_online": len(station.get_all_docks()),
        "drones_online": len(station.get_all_drones()),
    }


# ── Dock Endpoints ────────────────────────────────

@app.get("/docks")
async def list_docks():
    """List all connected docks and their status."""
    return station.get_all_docks()


@app.post("/docks/{dock_id}/command")
async def dock_command(dock_id: str, cmd: DockCommand):
    """Send a command to a dock (open, close, charge, reset)."""
    result = station.send_dock_command(dock_id, cmd.command, cmd.params)
    return {"status": "sent", "dock_id": dock_id, **result}


# ── Drone Endpoints ──────────────────────────────

@app.get("/drones")
async def list_drones():
    """List all connected drones and their telemetry."""
    return station.get_all_drones()


@app.post("/drones/{drone_id}/command")
async def drone_command(drone_id: str, cmd: DroneCommand):
    """Send a command to a drone (takeoff, land, waypoint, rtl, hover)."""
    result = station.send_drone_command(drone_id, cmd.command, cmd.params)
    return {"status": "sent", "drone_id": drone_id, **result}


# ── Stream Endpoints ─────────────────────────────

@app.get("/streams")
async def list_streams():
    """List all active RTSP streams from MediaMTX."""
    try:
        r = requests.get(f"{RTSP_API}/v3/paths/list", timeout=5)
        if r.status_code == 200:
            return r.json()
        return {"error": "MediaMTX API unavailable"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"RTSP API error: {str(e)}")


# ── Run ──────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
