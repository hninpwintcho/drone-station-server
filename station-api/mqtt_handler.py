"""
MQTT Handler — Drone/Dock message broker client
Subscribes to telemetry topics and publishes commands.

Supports TWO topic schemas:
  1. Custom station topics:   station/docks/+/status, station/drones/+/telemetry
  2. DJI Cloud API topics:    thing/product/{sn}/osd
                              thing/product/{sn}/events
                              thing/product/{sn}/services
                              thing/product/{sn}/services_reply
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
        self.docks = {}     # {dock_id: {status, battery, temperature, last_seen}}
        self.drones = {}    # {drone_id: {lat, lon, alt, battery, speed, state, last_seen}}

        # DJI Cloud API state store
        # Key = product SN (e.g. "5P7tbXBdP5AQJB9nRwsz")
        self.dji_osd = {}   # {sn: {cover_state, temperature, humidity, ...}}
        self.dji_events = []  # list of recent events (cover_open, etc.)

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

            # ── Custom station topics ──────────────
            client.subscribe("station/docks/+/status")
            client.subscribe("station/drones/+/telemetry")
            print("[MQTT] Subscribed: station/docks/+/status")
            print("[MQTT] Subscribed: station/drones/+/telemetry")

            # ── DJI Cloud API topics (wildcard all products) ──
            client.subscribe("thing/product/+/osd")
            client.subscribe("thing/product/+/events")
            client.subscribe("thing/product/+/services")
            client.subscribe("thing/product/+/services_reply")
            print("[MQTT] Subscribed: thing/product/+/osd  (DJI dock telemetry)")
            print("[MQTT] Subscribed: thing/product/+/events")
            print("[MQTT] Subscribed: thing/product/+/services_reply")
        else:
            print(f"[MQTT] Connection failed: rc={rc}")

    def _on_disconnect(self, client, userdata, rc):
        print(f"[MQTT] Disconnected (rc={rc}), will auto-reconnect...")

    def _on_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            raw = msg.payload.decode("utf-8")
            now = datetime.now().isoformat()

            # ── Parse full JSON safely ─────────────────────────────────────
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                print(f"[MQTT] ⚠️  Invalid JSON on {topic}: {raw[:120]}...")
                return

            # ── 1. Custom: station/docks/{dock_id}/status ──────────────────
            if topic.startswith("station/docks/") and topic.endswith("/status"):
                dock_id = topic.split("/")[2]
                with self.lock:
                    self.docks[dock_id] = {**payload, "last_seen": now}
                print(f"[DOCK] {dock_id}: {payload}")

            # ── 2. Custom: station/drones/{drone_id}/telemetry ─────────────
            elif topic.startswith("station/drones/") and topic.endswith("/telemetry"):
                drone_id = topic.split("/")[2]
                with self.lock:
                    self.drones[drone_id] = {**payload, "last_seen": now}
                print(f"[DRONE] {drone_id}: lat={payload.get('lat')}, "
                      f"lon={payload.get('lon')}, alt={payload.get('alt')}")

            # ── 3. DJI Cloud API: thing/product/{sn}/osd ───────────────────
            #    OSD = On-Screen Display telemetry from DJI Dock
            #    Fields: cover_state, putter_state, temperature, humidity,
            #            wind_speed, rainfall, drone_charge_state, etc.
            elif "/osd" in topic:
                sn = topic.split("/")[2]
                data = payload.get("data", payload)  # DJI wraps in "data" key
                with self.lock:
                    self.dji_osd[sn] = {**data, "last_seen": now}

                # Pretty-print key fields only (not the whole dict)
                cover  = data.get("cover_state", "?")        # 0=closed 1=open
                putter = data.get("putter_state", "?")       # 0=retract 2=extend
                temp   = data.get("temperature", "?")
                humid  = data.get("humidity", "?")
                wind   = data.get("wind_speed", "?")
                charge = data.get("drone_charge_state", {})
                bat    = charge.get("capacity_percent", "?") if charge else "?"

                cover_label  = {0: "CLOSED", 1: "OPEN"}.get(cover, cover)
                putter_label = {0: "RETRACTED", 1: "MOVING", 2: "EXTENDED"}.get(putter, putter)

                print(f"[OSD]  🏠 Dock {sn[:8]}.. | "
                      f"Cover:{cover_label} Putter:{putter_label} | "
                      f"Temp:{temp}°C Hum:{humid}% Wind:{wind}m/s | "
                      f"Battery:{bat}%")

            # ── 4. DJI Cloud API: thing/product/{sn}/events ────────────────
            #    Events: cover_open, cover_close, drone_takeoff, etc.
            elif "/events" in topic:
                sn     = topic.split("/")[2]
                method = payload.get("method", "unknown")
                data   = payload.get("data", {})
                result = data.get("result", "?")
                output = data.get("output", {})
                status = output.get("status", "?")
                print(f"[EVENT] 🔔 {sn[:8]}.. | method={method} "
                      f"result={result} status={status}")
                with self.lock:
                    self.dji_events.append({
                        "sn": sn,
                        "method": method,
                        "result": result,
                        "status": status,
                        "timestamp": now,
                    })
                    # Keep only last 100 events
                    self.dji_events = self.dji_events[-100:]

            # ── 5. DJI Cloud API: services / services_reply ────────────────
            elif "/services" in topic:
                sn     = topic.split("/")[2]
                method = payload.get("method", "unknown")
                status = payload.get("data", {}).get("output", {}).get("status", "?")
                print(f"[SVC]  ⚙️  {sn[:8]}.. | {method} → {status}")

        except Exception as e:
            print(f"[MQTT] ❌ Message error on {msg.topic}: {e}")

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

    def send_dji_service(self, sn: str, method: str, params: dict = None):
        """
        Send a DJI Cloud API service command to a dock.
        Example: send_dji_service("5P7tbXBdP5AQJB9nRwsz", "cover_open")
        """
        import uuid
        payload = {
            "tid": str(uuid.uuid4()),
            "bid": str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000),
            "method": method,
            "data": params or {},
        }
        topic = f"thing/product/{sn}/services"
        self.client.publish(topic, json.dumps(payload), qos=1)
        print(f"[DJI_CMD] → {topic}: {method}")
        return payload

    # ── State Queries ─────────────────────────────────

    def get_all_docks(self):
        with self.lock:
            return dict(self.docks)

    def get_all_drones(self):
        with self.lock:
            return dict(self.drones)

    def get_dji_osd(self, sn: str = None):
        """Get latest DJI dock OSD telemetry. Pass sn for specific dock."""
        with self.lock:
            if sn:
                return self.dji_osd.get(sn, {})
            return dict(self.dji_osd)

    def get_dji_events(self, limit: int = 20):
        """Get recent DJI dock events (cover_open, etc.)."""
        with self.lock:
            return self.dji_events[-limit:]
