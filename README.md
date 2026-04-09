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

## 🚀 Step-by-Step Install Guide (Tested on EC2)

> ✅ ဤ guide ကို `ip-10-10-2-210` (Public: `15.165.59.154`, Ubuntu 24.04, t3.small) တွင်
> စမ်းသပ်ပြီးသား ဖြစ်ပါသည်။

### Step 1 — EC2 Instance ဖွင့်ခြင်း

1. **AWS Console** → EC2 → Launch Instance
2. **AMI**: Ubuntu 24.04 LTS
3. **Instance Type**: `t3.small` (2 vCPU, 2GB RAM, ~$15/mo)
4. **Storage**: 50GB gp3
5. **User Data** (Advanced Details): `ec2-bootstrap.sh` ထဲက content ကို paste

### Step 2 — Security Group Ports ဖွင့်ခြင်း

AWS Console → EC2 → Security Groups → Inbound Rules → Edit:

| Port | Protocol | Source | Purpose |
|------|----------|--------|---------|
| 22 | TCP | My IP | SSH |
| 1883 | TCP | 0.0.0.0/0 | MQTT (Dock/Drone) |
| 8000 | TCP | 0.0.0.0/0 | Station API |
| 8554 | TCP | 0.0.0.0/0 | RTSP Video Ingest |
| 8888 | TCP | 0.0.0.0/0 | HLS Browser Playback |
| 9001 | TCP | 0.0.0.0/0 | MQTT WebSocket |
| 9997 | TCP | 0.0.0.0/0 | MediaMTX API |

### Step 3 — Files ကို EC2 သို့ တင်ခြင်း

```bash
# Local machine ကနေ
scp -r ~/drone-station-server ubuntu@EC2_PUBLIC_IP:~/

# SSH ဝင်ပါ
ssh ubuntu@EC2_PUBLIC_IP
```

### Step 4 — Docker Install (User Data မသုံးခဲ့ရင်)

```bash
bash ~/drone-station-server/ec2-bootstrap.sh
# ပြီးရင် logout/login ပြန်လုပ်ပါ (docker group အတွက်)
exit
ssh ubuntu@EC2_PUBLIC_IP
```

### Step 5 — Server Start

```bash
cd ~/drone-station-server
cp .env.example .env
docker compose up -d
```

### Step 6 — Container Status စစ်ဆေး

```bash
docker compose ps
```

Expected output:
```
NAME                IMAGE                              STATUS    PORTS
drone-mqtt          eclipse-mosquitto:2                Up        :1883, :9001
drone-rtsp          bluenviron/mediamtx:latest         Up        :8554, :8888, :9997
drone-station-api   drone-station-server-station-api   Up        :8000
```

---

## 🧪 Testing & Verification (Step-by-Step)

> ⚠️ အောက်ပါ commands အားလုံးကို **EC2 ထဲမှာ** ရိုက်ပါ

### Test 1 — Station API စစ်ဆေးခြင်း

```bash
curl http://localhost:8000/status
```
Expected:
```json
{"mqtt":"connected","rtsp":"running","docks_online":0,"drones_online":0}
```

### Test 2 — RTSP API စစ်ဆေးခြင်း

```bash
curl http://localhost:9997/v3/paths/list
```
Expected:
```json
{"itemCount":0,"pageCount":0,"items":[]}
```
(`items` ထဲ ဘာမှမရှိတာ ပုံမှန်ပါ — Stream မပို့ရသေးလို့)

### Test 3 — MQTT Pub/Sub စစ်ဆေးခြင်း

```bash
# MQTT client install
sudo apt install -y mosquitto-clients

# နားထောင်ပါ (Subscribe)
mosquitto_sub -h localhost -t 'station/#' -v &

# Dock status simulate (Publish)
mosquitto_pub -h localhost -t 'station/docks/DOCK01/status' \
  -m '{"state":"open","battery":85,"temperature":32.5}'
```
Expected output:
```
station/docks/DOCK01/status {"state":"open","battery":85,"temperature":32.5}
```

### Test 4 — RTSP Video Stream စစ်ဆေးခြင်း

```bash
# ffmpeg install
sudo apt install -y ffmpeg

# Test video stream ပို့ (10 စက္ကန့်ခန့်)
ffmpeg -re -f lavfi -i testsrc=size=640x480:rate=30 \
  -c:v libx264 -f rtsp rtsp://localhost:8554/test_stream
```

Stream ပြီးရင် "Broken pipe" ပြပါလိမ့်မယ် — **ပုံမှန်** ပါ (test video ရပ်လို့)။
နောက် terminal တစ်ခုဖွင့်ပြီး စစ်ဆေးပါ:
```bash
curl http://localhost:9997/v3/paths/list
```
Expected — `test_stream` ပေါ်လာပါမည်:
```json
{"itemCount":1,"items":[{"name":"test_stream","ready":true,"online":true,"tracks":["H264"]}]}
```

### Test 5 — Station API (Dock/Drone Commands)

```bash
# Dock command ပို့ကြည့်
curl -X POST http://localhost:8000/docks/DOCK01/command \
  -H "Content-Type: application/json" \
  -d '{"command": "close"}'

# Drone command ပို့ကြည့်
curl -X POST http://localhost:8000/drones/DJI001/command \
  -H "Content-Type: application/json" \
  -d '{"command": "land"}'

# Connected docks/drones ကြည့်
curl http://localhost:8000/docks
curl http://localhost:8000/drones

# Active streams ကြည့်
curl http://localhost:8000/streams
```

### Test 6 — Multi-Stream (VT001 - VT100)

Config ထဲ ပြင်စရာ မလို — `all_others` path config ဖြင့် ဘယ် name နဲ့ ပို့ပို့ auto-accept:
```bash
# VT001
ffmpeg -re -f lavfi -i testsrc=size=640x480:rate=30 \
  -c:v libx264 -f rtsp rtsp://localhost:8554/VT001

# VT100 (another terminal)
ffmpeg -re -f lavfi -i testsrc=size=640x480:rate=30 \
  -c:v libx264 -f rtsp rtsp://localhost:8554/VT100

# စစ်ဆေး
curl http://localhost:9997/v3/paths/list
# VT001 ရော VT100 ရော items ထဲတွင် ပေါ်လာပါမည်
```

### Test 7 — Browser စစ်ဆေးခြင်း (ပြင်ပကနေ)

| Test | URL |
|------|-----|
| Station API | `http://EC2_PUBLIC_IP:8000/status` |
| RTSP Streams | `http://EC2_PUBLIC_IP:9997/v3/paths/list` |
| HLS Player | `http://EC2_PUBLIC_IP:8888/test_stream` |

---

## ✅ Verification Checklist

| # | Test | Command | Expected |
|---|------|---------|----------|
| 1 | Containers running | `docker compose ps` | 3 containers Up |
| 2 | Station API | `curl localhost:8000/status` | `mqtt: connected` |
| 3 | RTSP API | `curl localhost:9997/v3/paths/list` | `items: []` (no error) |
| 4 | MQTT pub/sub | `mosquitto_pub` + `mosquitto_sub` | Message received |
| 5 | RTSP ingest | `ffmpeg … rtsp://localhost:8554/test` | Stream in API |
| 6 | Multi-stream | Push VT001, VT100 | Both in API |
| 7 | Browser | `http://PUBLIC_IP:8000/status` | JSON response |


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
