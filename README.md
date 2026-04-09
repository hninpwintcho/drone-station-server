# 🚁 Drone Station Server (MQTT + RTSP)

> **One-Stop Docker Deployment**: MQTT Broker + RTSP Server + Station Control API
> For Drone Station with Dock — inspired by HEISHA HSC Architecture.
> Deploy with a single `docker compose up -d` command.

---

## 🏗️ Architecture

```
   ┌────────────┐        Modbus / MQTT         ┌──────────────────────────┐
   │   Docks    │ ──────────────────────────►   │                          │
   │  (HEISHA)  │   station/docks/{id}/status   │   drone-station-server   │
   └────────────┘                               │                          │
                                                │  ┌────────────────────┐  │
   ┌────────────┐   MSDK / RTSP                 │  │  MQTT Broker       │  │
   │   Drones   │ ──────────────────────────►   │  │  (Mosquitto)       │  │
   │  (DJI etc) │   station/drones/{id}/telem   │  │  :1883 TCP         │  │
   └────────────┘                               │  │  :9001 WebSocket   │  │
        │                                       │  └────────────────────┘  │
        │  RTSP Video                           │  ┌────────────────────┐  │
        └───────────────────────────────────►   │  │  RTSP Server       │  │
           rtsp://IP:8554/drone_stream          │  │  (MediaMTX)        │  │
                                                │  │  :8554 Ingest      │  │
                                                │  │  :8888 HLS         │  │
                                                │  │  :9997 API         │  │
                                                │  └────────────────────┘  │
                                                │  ┌────────────────────┐  │    ┌───────────────┐
                                                │  │  Station API       │  │    │ Command Center│
                                                │  │  (FastAPI)         │──────►│  Software     │
                                                │  │  :8000 REST        │  │    │ (aioceaneye)  │
                                                │  └────────────────────┘  │    └───────────────┘
                                                └──────────────────────────┘
```

---

## 📁 Project Structure

```
drone-station-server/
  docker-compose.yml      ← One-command deployment (3 containers)
  ec2-bootstrap.sh        ← EC2 User Data script (installs Docker)
  .env.example            ← Environment variables template
  .gitignore
  mosquitto/
    mosquitto.conf        ← MQTT broker config (TCP + WebSocket)
  mediamtx/
    mediamtx.yml          ← RTSP server config (Ingest + HLS + Recording)
  station-api/
    Dockerfile            ← Python 3.11 slim image
    station_api.py        ← FastAPI REST endpoints
    mqtt_handler.py       ← MQTT client (paho-mqtt) for dock/drone state
    requirements.txt      ← Python dependencies
```

---

## 🚀 Deploy (One-Stop)

### Step 1 — Launch EC2 (Ubuntu 22.04, t3.medium+)
Paste `ec2-bootstrap.sh` into **EC2 → Advanced → User Data**.

Open Security Group ports: **1883, 8000, 8554, 8888, 9001, 9997**

### Step 2 — Copy & Start
```bash
scp -r ~/drone-station-server ubuntu@EC2_IP:~/
ssh ubuntu@EC2_IP
cd ~/drone-station-server
cp .env.example .env
docker compose up -d
```

### Step 3 — Verify
```bash
docker compose ps
# Should show 3 containers: drone-mqtt, drone-rtsp, drone-station-api
```

---

## 📡 MQTT Topic Reference

### Dock Topics
| Topic | Direction | Description |
|-------|-----------|-------------|
| `station/docks/{dock_id}/status` | Dock → Server | Dock reports: state, battery, temperature |
| `station/docks/{dock_id}/command` | Server → Dock | Commands: `open`, `close`, `charge`, `reset` |

### Drone Topics
| Topic | Direction | Description |
|-------|-----------|-------------|
| `station/drones/{drone_id}/telemetry` | Drone → Server | GPS (lat/lon/alt), battery, speed, state |
| `station/drones/{drone_id}/command` | Server → Drone | Commands: `takeoff`, `land`, `waypoint`, `rtl`, `hover` |

### Example Payloads
```json
// Dock Status (published by dock)
{
  "state": "open",
  "battery": 85,
  "temperature": 32.5,
  "charging": true
}

// Drone Telemetry (published by drone)
{
  "lat": 16.8661,
  "lon": 96.1951,
  "alt": 120.5,
  "battery": 72,
  "speed": 12.3,
  "state": "flying"
}

// Dock Command (published by server)
{
  "command": "close",
  "params": {},
  "timestamp": "2026-04-08T13:00:00"
}
```

---

## 🧪 Testing Walkthrough (Step-by-Step)

### Test 1 — MQTT Broker
```bash
# Terminal 1: Subscribe to all station topics
mosquitto_sub -h localhost -t 'station/#' -v

# Terminal 2: Simulate dock status
mosquitto_pub -h localhost -t 'station/docks/DOCK01/status' \
  -m '{"state":"open","battery":85,"temperature":32.5}'

# Terminal 3: Simulate drone telemetry
mosquitto_pub -h localhost -t 'station/drones/DJI001/telemetry' \
  -m '{"lat":16.8661,"lon":96.1951,"alt":120,"battery":72,"speed":12,"state":"flying"}'
```

### Test 2 — Station API
```bash
# System status
curl http://localhost:8000/status

# List connected docks
curl http://localhost:8000/docks

# List connected drones
curl http://localhost:8000/drones

# Send dock command
curl -X POST http://localhost:8000/docks/DOCK01/command \
  -H "Content-Type: application/json" \
  -d '{"command": "close"}'

# Send drone command
curl -X POST http://localhost:8000/drones/DJI001/command \
  -H "Content-Type: application/json" \
  -d '{"command": "land"}'

# List active RTSP streams
curl http://localhost:8000/streams
```

### Test 3 — RTSP Video Stream
```bash
# Push test stream (from drone or test source)
gst-launch-1.0 videotestsrc ! x264enc ! \
  rtspclientsink location=rtsp://EC2_IP:8554/drone_stream

# Watch in browser (HLS)
# Open: http://EC2_IP:8888/drone_stream
```

---

## 🔌 Port Reference

| Port | Service | Protocol | Purpose |
|------|---------|----------|---------|
| 1883 | Mosquitto | MQTT/TCP | Dock/Drone command & telemetry |
| 9001 | Mosquitto | WebSocket | Browser MQTT dashboard |
| 8554 | MediaMTX | RTSP | Drone video ingest |
| 8888 | MediaMTX | HTTP/HLS | Browser video playback |
| 9997 | MediaMTX | HTTP/API | Stream status API |
| 8000 | Station API | HTTP/REST | Command center endpoints |

---

## 🎓 Learning Notes (မြန်မာ)

### MQTT ဆိုတာ ဘာလဲ?
MQTT (Message Queuing Telemetry Transport) သည် IoT devices များအတွက် အသုံးများသော lightweight messaging protocol ဖြစ်သည်။
- **Publish/Subscribe** pattern ကို သုံးသည် (HTTP request/response နှင့် မတူ)
- Drone/Dock က message **publish** လုပ်ပြီး Server က **subscribe** လုပ်ပြီး နားထောင်နေသည်
- Internet connection ညံ့သော အခြေအနေတွင်ပင် အလုပ်လုပ်နိုင်သည် (QoS levels)

### ဘာကြောင့် MQTT + RTSP နှစ်ခုလုံး လိုသလဲ?
- **MQTT**: Drone/Dock ရဲ့ **command & control** (GPS, battery, takeoff/land) အတွက်
- **RTSP**: Drone camera ရဲ့ **video stream** အတွက်
- ဒီနှစ်ခုကို ပေါင်းသုံးမှသာ Drone Station တစ်ခုလုံးကို remote ကနေ ထိန်းချုပ်နိုင်ပြီး ဗီဒီယိုလည်း ကြည့်ရှုနိုင်မည်

---

## 🗺️ Phase Roadmap (အဆင့်ဆင့် Plan)

### Phase 1 — Manual Drone + AI Detection ✅ (Done)
```
Drone (လူကိုယ်တိုင်ပျံ) → RTSP → AI (model.py) → aioceaneye.com
```
- **Repo**: `tuna_v2-ai-server`
- **Dock**: မလို
- **MQTT**: မလို

### Phase 2 — Own MQTT Server + RTSP ✅ (Repo Ready)
```
MQTT Server (Mosquitto) + RTSP Server (MediaMTX) + Station API (FastAPI)
```
- **Repo**: `drone-station-server` (ဒီ repo)
- **Dock**: မလိုသေး (testing/準備)
- **MQTT**: ✅ Ready

### Phase 3 — HEISHA Dock + Own MQTT Server 🔜 (Next)
```
HEISHA Dock #1 ── MQTT ──┐
HEISHA Dock #2 ── MQTT ──┤
HEISHA Dock #3 ── MQTT ──┼──► Own MQTT Server ──► Station API ──► aioceaneye.com
       ...                │
HEISHA Dock #N ── MQTT ──┘
```
- HEISHA Dock hardware ဝယ်ပြီး ကိုယ်ပိုင် MQTT Server ဆီ ချိတ်ဆက်
- Multi-Dock management (Dock တစ်ခုမက တစ်ပြိုင်နက် ထိန်းချုပ်)

### Phase 4 — Full Automation Dashboard 🔜 (Future)
```
aioceaneye.com Dashboard:
├── Map ပေါ်မှာ Dock/Drone အားလုံး ပြသ
├── Auto-Mission scheduling (နေ့စဉ် ပျံခိုင်းစနစ်)
├── AI Detection results (ငါးတူနာ ရှာဖွေတွေ့ရှိမှု)
└── Alert system (Battery နည်း / Weather မကောင်း)
```

---

## 🏗️ Multi-Dock Architecture (Main Destination)

```
   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
   │ HEISHA Dock │  │ HEISHA Dock │  │ HEISHA Dock │
   │   #1 ရန်ကုန် │  │  #2 မန္တလေး  │  │  #3 ပုသိမ်   │
   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
          │                │                │
     Modbus/MQTT      Modbus/MQTT      Modbus/MQTT
          │                │                │
          └────────────────┼────────────────┘
                           │
                           ▼
            ┌──────────────────────────┐
            │   Our AWS EC2 Server     │
            │                          │
            │  ┌────────────────────┐  │
            │  │  MQTT (Mosquitto)  │  │  ← Dock အားလုံးကို ထိန်းချုပ်
            │  │  :1883 / :9001     │  │
            │  └────────────────────┘  │
            │  ┌────────────────────┐  │
            │  │  RTSP (MediaMTX)   │  │  ← Drone Video + AI Detection
            │  │  :8554 / :8888     │  │
            │  └────────────────────┘  │
            │  ┌────────────────────┐  │
            │  │  Station API       │  │  ← REST API for Command Center
            │  │  :8000             │  │
            │  └────────────────────┘  │
            └─────────────┬────────────┘
                          │
                          ▼
              ┌─────────────────────┐
              │   aioceaneye.com    │
              │   Command Center    │
              │   (Multi-Dock Map)  │
              └─────────────────────┘
```

---

## ❓ Q&A — ကိုယ်ပိုင် MQTT vs HEISHA HS API

### Q: HEISHA HS API ရှိပြီးသားမှာ ဘာကြောင့် ကိုယ်ပိုင် MQTT Server လိုသလဲ?

**A**: HS API ကတော့ Dock 1-2 ခု အတွက် အဆင်ပြေပါတယ်။ ဒါပေမယ့် -

| | HS API (HEISHA Cloud) | Own MQTT Server |
|--|----------------------|-----------------|
| **Control** | HEISHA Cloud ကနေ ထိန်း | ကိုယ်ပိုင် Cloud ကနေ ထိန်း |
| **Cost** | Subscription fee ပေးရ | Free (Mosquitto open-source) |
| **Reliability** | HEISHA down = ကိုယ်လည်း down | ကိုယ့် server ကိုယ် control |
| **Multi-Dock** | Dock 1-2 ခု သုံးရင် ok | **Dock 10+ ခု** စီမံရင် ပိုကောင်း |
| **Custom Logic** | HEISHA ပေးတာပဲ သုံးရ | **ကိုယ်ပိုင် AI/Alert** ထည့်နိုင် |

### Q: HEISHA Dock ကို ကိုယ်ပိုင် MQTT Server ဆီ ချိတ်လို့ ရလား?

**A**: ရပါတယ်။ HEISHA Dock များတွင် MQTT configuration ပြောင်းနိုင်သည့် setting ရှိပါသည်။ Dock ၏ MQTT broker address ကို ကိုယ်ပိုင် server IP သို့ ပြောင်းလဲပေးရုံဖြင့် ချိတ်ဆက်နိုင်ပါသည်။

### Q: Dock မရှိသေးရင် ဒီ MQTT Server ကို ဘာနဲ့ စမ်းမလဲ?

**A**: `mosquitto_pub` command ဖြင့် Dock အဖြစ် ဟန်ဆောင်ပြီး test message ပို့နိုင်ပါသည် -
```bash
# Dock simulator
mosquitto_pub -h localhost -t 'station/docks/DOCK01/status' \
  -m '{"state":"open","battery":85,"temperature":32.5}'

# Drone simulator
mosquitto_pub -h localhost -t 'station/drones/DJI001/telemetry' \
  -m '{"lat":16.8661,"lon":96.1951,"alt":120,"battery":72,"state":"flying"}'
```
