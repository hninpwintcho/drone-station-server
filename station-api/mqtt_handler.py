"""
MQTT Handler — Drone/Dock message broker client
Subscribes to telemetry topics and publishes commands.
"""

import json
import time
import threading
from datetime import datetime
import paho.mqtt.client as mqtt


class DroneStation:
    """Manages state for all connected docks and drones via MQTT."""

    def __init__(self, mqtt_host="localhost", mqtt_port=1883):
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port

        # State stores
        self.docks = {}    # {dock_id: {status, battery, temperature, last_seen}}
        self.drones = {}   # {drone_id: {lat, lon, alt, battery, speed, state, last_seen}}
        self.lock = threading.Lock()

        # MQTT client
        self.client = mqtt.Client(client_id="station-api", protocol=mqtt.MQTTv311)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

    def start(self):
        """Connect to MQTT broker and start listening."""
        print(f"[MQTT] Connecting to {self.mqtt_host}:{self.mqtt_port}...")
        self.client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
        self.client.loop_start()

    def stop(self):
        """Disconnect from MQTT broker."""
        self.client.loop_stop()
        self.client.disconnect()
        print("[MQTT] Disconnected.")

    # ── Callbacks ─────────────────────────────────────

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("[MQTT] Connected to broker ✅")
            # Subscribe to all station topics
            client.subscribe("station/docks/+/status")
            client.subscribe("station/drones/+/telemetry")
            print("[MQTT] Subscribed to station/docks/+/status")
            print("[MQTT] Subscribed to station/drones/+/telemetry")
        else:
            print(f"[MQTT] Connection failed: rc={rc}")

    def _on_disconnect(self, client, userdata, rc):
        print(f"[MQTT] Disconnected (rc={rc}), will auto-reconnect...")

    def _on_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode("utf-8"))
            now = datetime.now().isoformat()

            # Parse: station/docks/{dock_id}/status
            if topic.startswith("station/docks/") and topic.endswith("/status"):
                dock_id = topic.split("/")[2]
                with self.lock:
                    self.docks[dock_id] = {
                        **payload,
                        "last_seen": now,
                    }
                print(f"[DOCK] {dock_id}: {payload}")

            # Parse: station/drones/{drone_id}/telemetry
            elif topic.startswith("station/drones/") and topic.endswith("/telemetry"):
                drone_id = topic.split("/")[2]
                with self.lock:
                    self.drones[drone_id] = {
                        **payload,
                        "last_seen": now,
                    }
                print(f"[DRONE] {drone_id}: lat={payload.get('lat')}, lon={payload.get('lon')}, alt={payload.get('alt')}")

        except Exception as e:
            print(f"[MQTT] Message error: {e}")

    # ── Commands ──────────────────────────────────────

    def send_dock_command(self, dock_id: str, command: str, params: dict = None):
        """Send command to a specific dock (open, close, charge, etc.)."""
        payload = {
            "command": command,
            "params": params or {},
            "timestamp": datetime.now().isoformat(),
        }
        topic = f"station/docks/{dock_id}/command"
        self.client.publish(topic, json.dumps(payload), qos=1)
        print(f"[CMD] → {topic}: {command}")
        return payload

    def send_drone_command(self, drone_id: str, command: str, params: dict = None):
        """Send command to a specific drone (takeoff, land, waypoint, rtl, etc.)."""
        payload = {
            "command": command,
            "params": params or {},
            "timestamp": datetime.now().isoformat(),
        }
        topic = f"station/drones/{drone_id}/command"
        self.client.publish(topic, json.dumps(payload), qos=1)
        print(f"[CMD] → {topic}: {command}")
        return payload

    # ── State Queries ─────────────────────────────────

    def get_all_docks(self):
        with self.lock:
            return dict(self.docks)

    def get_all_drones(self):
        with self.lock:
            return dict(self.drones)
