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
| 8 | Java MQTT Client | Spring Boot Paho connect | ✅ Connection test completed |

---

## ☕ Java/Spring Boot MQTT Client Test (Colleague Verified)

> ✅ Tested on `2026-04-10` — **MQTT server connection test completed**
> Spring Boot app ကနေ Mosquitto Broker သို့ ချိတ်ဆက်ခြင်း အောင်မြင်ပါသည်။

### Setup
| Item | Detail |
|------|--------|
| **Language** | Java 17 |
| **Framework** | Spring Boot 3.5.13 |
| **MQTT Client** | Eclipse Paho `mqttv3` v1.2.5 |
| **Build Tool** | Maven |
| **Package** | `com.drone.station.stationcontrol` |

### Maven Dependencies (pom.xml)
```xml
<!-- MQTT Client -->
<dependency>
    <groupId>org.eclipse.paho</groupId>
    <artifactId>org.eclipse.paho.client.mqttv3</artifactId>
    <version>1.2.5</version>
</dependency>

<!-- Spring AMQP -->
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-amqp</artifactId>
</dependency>
```

### Connection Config (application.yml)
```yaml
mqtt:
  broker: tcp://15.165.59.154:1883
  clientId: spring-station-client
  topics:
    - station/docks/#
    - station/drones/#
```

### Architecture (Java Client ↔ MQTT Server)
```
┌──────────────────────────┐
│  Spring Boot App (Java)  │
│  Paho MQTT Client v1.2.5 │
│  com.drone.station       │
└──────────┬───────────────┘
           │
    tcp://15.165.59.154:1883
           │
           ▼
┌──────────────────────────┐
│  Our MQTT Server (EC2)   │
│  Mosquitto :1883         │
│  drone-mqtt container    │
└──────────────────────────┘
```


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

---

---

# 🆕 Update — WebRTC + RTMP + DJI MQTT OSD (April 2026)

> **Changes Made:** WebRTC low-latency browser streaming enabled, RTMP input added, DJI Cloud API MQTT topics fixed.
> **Files changed:** `mediamtx/mediamtx.yml` · `docker-compose.yml` · `station-api/mqtt_handler.py`

---

## 🎥 Change 1 — WebRTC & RTMP Enabled (mediamtx.yml)

### What Changed

| Feature | Before | After |
|---------|--------|-------|
| WebRTC | ❌ Disabled | ✅ **Enabled** `:8889` (~0.5s latency) |
| RTMP input | ❌ Disabled | ✅ **Enabled** `:1935` (OBS/FFmpeg push) |
| HLS | ✅ `:8888` | ✅ `:8888` (unchanged — fallback) |
| RTSP ingest | ✅ `:8554` | ✅ `:8554` (unchanged) |

### RTMP → WebRTC Workflow

```
OBS / FFmpeg
     │
     │  rtmp://SERVER_IP:1935/live/mystream
     ▼
MediaMTX (Port 1935)
     │  Auto transmux (no re-encode)
     │  RTMP/FLV → WebRTC/UDP
     ▼
Browser viewer
     http://SERVER_IP:8889/live/mystream
     (~0.5 second latency)
```

### Full mediamtx.yml (Copy-Ready)

```yaml
###############################################
# MediaMTX — Drone Station (RTSP + WebRTC + RTMP)
###############################################
logLevel: info
logDestinations: [stdout]

authMethod: internal
authInternalUsers:
- user: any
  pass:
  ips: []
  permissions:
  - action: publish
    path:
  - action: read
    path:
  - action: playback
    path:
  - action: api
  - action: metrics
  - action: pprof

api: yes
apiAddress: :9997
apiAllowOrigin: '*'

# Drone RTSP ingest
rtsp: yes
rtspAddress: :8554

# OBS / FFmpeg RTMP push input  ← NEW
rtmp: yes
rtmpAddress: :1935

# HLS browser fallback (3-6s delay)
hls: yes
hlsAddress: :8888
hlsVariant: lowLatency
hlsAllowOrigin: '*'

srt: no

# WebRTC low-latency (~0.5s)  ← NEW
webrtc: yes
webrtcAddress: :8889
webrtcEncryption: no
# ⚠️ CHANGE THIS to your EC2 public IP:
webrtcICEUDPMuxAddress: YOUR_EC2_PUBLIC_IP:8890

pathDefaults:
  source: publisher
  record: yes
  recordPath: /recordings/%path/%Y-%m-%d_%H-%M-%S-%f
  recordFormat: fmp4
  recordSegmentDuration: 1h
  recordDeleteAfter: 7d

paths:
  all_others:
```

> ⚠️ **One thing to change:** Replace `YOUR_EC2_PUBLIC_IP` with your actual EC2 elastic/public IP (e.g. `15.164.50.229`)

---

## 🐳 Change 2 — Docker Compose Ports Updated (docker-compose.yml)

Three new ports added to the `rtsp` (MediaMTX) service:

```yaml
# mediamtx service — ports section (updated)
ports:
  - "8554:8554"        # RTSP ingest (drone streams)
  - "1935:1935"        # RTMP ingest (OBS / FFmpeg)   ← NEW
  - "8888:8888"        # HLS playback (browser fallback)
  - "8889:8889"        # WebRTC signaling HTTP         ← NEW
  - "8890:8890/udp"    # WebRTC ICE UDP media          ← NEW
  - "9997:9997"        # MediaMTX Control API
```

### Full Port Reference (Updated)

| Port | Protocol | Service | Purpose |
|------|----------|---------|---------|
| 22 | TCP | EC2 | SSH |
| 1883 | TCP | Mosquitto | MQTT (Dock/Drone) |
| 9001 | TCP | Mosquitto | MQTT WebSocket |
| 8554 | TCP | MediaMTX | RTSP drone ingest |
| **1935** | **TCP** | **MediaMTX** | **RTMP (OBS/FFmpeg)** ← NEW |
| 8888 | TCP | MediaMTX | HLS browser fallback |
| **8889** | **TCP** | **MediaMTX** | **WebRTC signaling** ← NEW |
| **8890** | **UDP** | **MediaMTX** | **WebRTC ICE media** ← NEW |
| 9997 | TCP | MediaMTX | MediaMTX API |
| 8000 | TCP | Station API | REST endpoints |

---

## 📡 Change 3 — DJI Cloud API MQTT Topics Fixed (mqtt_handler.py)

### Problem
The original `mqtt_handler.py` only listened to **custom topics** (`station/docks/+/status`).
DJI dock sends telemetry on **DJI Cloud API topics** (`thing/product/{sn}/osd`) — these were never parsed, causing the "OSD broken" display.

### Fix — New subscriptions added

```python
# Now subscribes to ALL 4 DJI Cloud API topic patterns:
client.subscribe("thing/product/+/osd")             # Dock telemetry
client.subscribe("thing/product/+/events")           # cover_open, etc.
client.subscribe("thing/product/+/services")         # Commands sent
client.subscribe("thing/product/+/services_reply")   # Command results
```

### DJI OSD Fields Explained

```json
{
  "cover_state": 1,          // 0=CLOSED, 1=OPEN
  "putter_state": 2,         // 0=RETRACTED, 1=MOVING, 2=EXTENDED
  "temperature": 27.4,       // Inside dock °C
  "humidity": 38.9,          // Humidity %
  "wind_speed": 0.0,         // Wind m/s
  "rainfall": 0,             // 0=none
  "emergency_stop_state": 0, // 0=normal
  "drone_charge_state": {
    "state": 0,              // 0=not charging
    "capacity_percent": 0    // Drone battery %
  }
}
```

### New Clean Log Output (Before vs After)

**Before (broken/truncated):**
```
2026-04-17T17:02:25Z | thing/product/5P7tbXBdP5AQJB9nRwsz/osd |
{"air_conditioner":{"air_conditioner_state":0,"max_temperature":35...  ← cut off!
```

**After (clean, human-readable):**
```
[OSD]  🏠 Dock 5P7tbXB.. | Cover:OPEN Putter:EXTENDED | Temp:27.4°C Hum:38.9% Wind:0.0m/s | Battery:0%
[EVENT] 🔔 5P7tbXB.. | method=cover_open result=0 status=ok
[SVC]  ⚙️  5P7tbXB.. | cover_open → in_progress
```

### New API Methods Available

```python
# Get latest DJI dock telemetry
station.get_dji_osd("5P7tbXBdP5AQJB9nRwsz")

# Get last 20 DJI events
station.get_dji_events(limit=20)

# Send DJI service command (e.g. open dock cover)
station.send_dji_service("5P7tbXBdP5AQJB9nRwsz", "cover_open")
```

---

## 🚀 Step-by-Step Redeploy Guide

### Step 1 — Open AWS Security Group (New Ports)

Go to **AWS Console → EC2 → Security Groups → Inbound Rules → Edit**:

Add these 3 new rules:

| Port | Protocol | Source | Purpose |
|------|----------|--------|---------|
| 1935 | TCP | 0.0.0.0/0 | RTMP (OBS/FFmpeg input) |
| 8889 | TCP | 0.0.0.0/0 | WebRTC signaling |
| 8890 | UDP | 0.0.0.0/0 | WebRTC ICE media (UDP!) |

### Step 2 — Update mediamtx.yml on EC2

```bash
ssh ubuntu@YOUR_EC2_IP
cd ~/drone-station-server

# Edit the one required line — set your EC2 public IP:
nano mediamtx/mediamtx.yml
# Change: webrtcICEUDPMuxAddress: YOUR_EC2_PUBLIC_IP:8890
# Example: webrtcICEUDPMuxAddress: 15.164.50.229:8890
```

### Step 3 — Pull Latest Code (if using git)

```bash
cd ~/drone-station-server
git pull origin main
```

### Step 4 — Restart All Containers

```bash
cd ~/drone-station-server
docker compose down
docker compose up -d
```

### Step 5 — Verify All Containers Running

```bash
docker compose ps
```

Expected output:
```
NAME                IMAGE                              STATUS    PORTS
drone-mqtt          eclipse-mosquitto:2                Up        :1883, :9001
drone-rtsp          bluenviron/mediamtx:latest         Up        :8554, :1935, :8888, :8889, :8890/udp, :9997
drone-station-api   drone-station-server-station-api   Up        :8000
```

### Step 6 — Test WebRTC (Browser)

**Push stream from OBS:**
```
Settings → Stream → Service: Custom
Server:     rtmp://YOUR_EC2_IP/live/mystream
Stream Key: mystream
```

**View in browser:**
```
http://YOUR_EC2_IP:8889/live/mystream
```

### Step 7 — Test WebRTC with FFmpeg (no OBS needed)

```bash
# Push a test stream via RTMP from EC2 itself
ffmpeg -re -f lavfi -i testsrc=size=1280x720:rate=30 \
  -c:v libx264 -preset ultrafast -b:v 1M \
  -f flv rtmp://localhost/live/teststream

# Then open browser: http://YOUR_EC2_IP:8889/live/teststream
```

### Step 8 — Test DJI MQTT OSD

```bash
# Watch DJI dock OSD topic
mosquitto_sub -h localhost -t 'thing/product/#' -v

# Simulate DJI dock OSD message
mosquitto_pub -h localhost -t 'thing/product/5P7tbXBdP5AQJB9nRwsz/osd' \
  -m '{"tid":"abc","bid":"def","timestamp":946761224605,"gateway":"5P7tbXBdP5AQJB9nRwsz","data":{"cover_state":1,"putter_state":2,"temperature":27.4,"humidity":38.9,"wind_speed":0.0,"rainfall":0,"emergency_stop_state":0,"drone_charge_state":{"state":0,"capacity_percent":85}}}'
```

Expected station-api log:
```
[OSD]  🏠 Dock 5P7tbXB.. | Cover:OPEN Putter:EXTENDED | Temp:27.4°C Hum:38.9% Wind:0.0m/s | Battery:85%
```

### Step 9 — Full Verification Checklist

| # | Test | Command | Expected |
|---|------|---------|----------|
| 1 | Containers up | `docker compose ps` | 3 containers Up, all ports shown |
| 2 | RTSP API | `curl localhost:9997/v3/paths/list` | `{"items":[]}` (no error) |
| 3 | Station API | `curl localhost:8000/status` | `{"mqtt":"connected"...}` |
| 4 | RTMP ingest | FFmpeg push to `:1935` | Stream appears at `:9997` |
| 5 | WebRTC view | Browser `http://IP:8889/live/teststream` | Live video, ~0.5s latency |
| 6 | DJI OSD | `mosquitto_pub` to `thing/product/+/osd` | Clean log line in station-api |
| 7 | DJI events | `mosquitto_pub` to `thing/product/+/events` | `[EVENT]` line in logs |

---

*Updated: April 2026 — WebRTC + RTMP + DJI Cloud API MQTT*

---

## 🚀 Git Push & EC2 Redeploy (Full Workflow)

> Run this after **any config change** on your local machine to push and redeploy on EC2.

### Step 1 — Push Changes from Local Machine (WSL) to GitHub

```bash
# On your LOCAL machine (WSL):
cd ~/drone-station-server

git add mediamtx/mediamtx.yml \
        docker-compose.yml \
        station-api/mqtt_handler.py \
        .env.example \
        README.md

git commit -m "feat: enable WebRTC+RTMP, fix DJI MQTT OSD topics"
git push origin main
```

---

### Step 2 — SSH into EC2

```bash
ssh ubuntu@15.165.59.154
```

---

### Step 3 — Pull Latest Code on EC2

```bash
cd ~/drone-station-server
git pull origin main
```

---

### Step 4 — Set Your EC2 Public IP in mediamtx.yml

> ⚠️ **Do this once only** — only if you haven't set it yet

```bash
nano mediamtx/mediamtx.yml
```

Find this line and replace with your real public IP:
```yaml
# Change this:
webrtcICEUDPMuxAddress: YOUR_EC2_PUBLIC_IP:8890

# To your actual EC2 public IP, e.g:
webrtcICEUDPMuxAddress: 15.165.59.154:8890
```

Save: `Ctrl+X` → `Y` → `Enter`

---

### Step 5 — Open 3 New Ports in AWS Security Group

> AWS Console → EC2 → Security Groups → your group → Inbound Rules → Edit → Add rule

| Port | Protocol | Source | Purpose |
|------|----------|--------|---------|
| `1935` | TCP | 0.0.0.0/0 | RTMP (OBS/FFmpeg input) |
| `8889` | TCP | 0.0.0.0/0 | WebRTC signaling |
| `8890` | **UDP** | 0.0.0.0/0 | WebRTC ICE media ⚠️ UDP |

---

### Step 6 — Restart All Containers

```bash
cd ~/drone-station-server
docker compose down
docker compose up -d
```

---

### Step 7 — Verify Containers & Ports

```bash
docker compose ps
```

Expected:
```
NAME                IMAGE                              STATUS    PORTS
drone-mqtt          eclipse-mosquitto:2                Up        0.0.0.0:1883->1883, 0.0.0.0:9001->9001
drone-rtsp          bluenviron/mediamtx:latest         Up        0.0.0.0:1935->1935, 0.0.0.0:8554->8554
                                                                 0.0.0.0:8888->8888, 0.0.0.0:8889->8889
                                                                 0.0.0.0:8890->8890/udp, 0.0.0.0:9997->9997
drone-station-api   drone-station-server-station-api   Up        0.0.0.0:8000->8000
```

---

### Step 8 — Test WebRTC in Browser

**Option A — OBS Studio:**
```
Settings → Stream → Service: Custom
Server:      rtmp://15.165.59.154/live/mystream
Stream Key:  mystream
```
Then open browser: `http://15.165.59.154:8889/live/mystream`

**Option B — FFmpeg (no OBS needed):**
```bash
# Run on EC2 itself
ffmpeg -re -f lavfi -i testsrc=size=1280x720:rate=30 \
  -c:v libx264 -preset ultrafast -b:v 1M \
  -f flv rtmp://localhost/live/test
```
Then open browser: `http://15.165.59.154:8889/live/test`

---

### Step 9 — Test DJI MQTT OSD

```bash
# Subscribe to watch DJI dock topics
mosquitto_sub -h localhost -t 'thing/product/#' -v

# Simulate DJI dock OSD (in another terminal)
mosquitto_pub -h localhost \
  -t 'thing/product/5P7tbXBdP5AQJB9nRwsz/osd' \
  -m '{"tid":"abc","bid":"def","timestamp":946761224605,
       "gateway":"5P7tbXBdP5AQJB9nRwsz",
       "data":{"cover_state":1,"putter_state":2,
               "temperature":27.4,"humidity":38.9,
               "wind_speed":0.0,"rainfall":0,
               "drone_charge_state":{"state":0,"capacity_percent":85}}}'
```

Expected station-api log:
```
[OSD]  🏠 Dock 5P7tbXB.. | Cover:OPEN Putter:EXTENDED | Temp:27.4°C Hum:38.9% Wind:0.0m/s | Battery:85%
```

---

### ✅ Final Checklist

| # | Check | Command | Expected |
|---|-------|---------|----------|
| 1 | Git pushed | `git log --oneline -1` | latest commit visible |
| 2 | EC2 pulled | `git status` | `up to date` |
| 3 | Containers up | `docker compose ps` | 3 × Up, all ports |
| 4 | Station API | `curl localhost:8000/status` | `mqtt: connected` |
| 5 | RTSP ingest | `curl localhost:9997/v3/paths/list` | no error |
| 6 | WebRTC test | Browser `http://IP:8889/live/test` | live video ✅ |
| 7 | DJI MQTT OSD | `mosquitto_pub` simulate | clean `[OSD]` log ✅ |

---
*Deployed on: EC2 `ip-10-10-2-210` (Ubuntu 24.04) | Public IP: `15.165.59.154`*


PowerShell:
Perfect. Use this exact command in your PowerShell:

powershell
ffmpeg -re -i "file.mp4.mp4" `
  -c:v libx264 -preset ultrafast -tune zerolatency -pix_fmt yuv420p `
  -c:a aac -b:a 128k `
  -f flv rtmp://15.165.59.154:1935/live/test

ffmpeg -f dshow -i video="Integrated Camera":audio="Microphone Array (Intel® Smart Sound Technology for Digital Microphones)" `
  -c:v libx264 -preset ultrafast -tune zerolatency -pix_fmt yuv420p -g 60 `
  -c:a aac -b:a 128k `
  -f flv rtmp://15.165.59.154:1935/live/test

Once you start this, you will see frame= numbers starting to count up. When they reach about 30, open your browser to:

🔗 Watch here: http://15.165.59.154:8889/live/test

How to install ffmped at my power shell 
The easiest way to install FFmpeg on Windows using PowerShell is using Winget (the built-in Windows Package Manager).

Run these commands in your PowerShell:

1. Install FFmpeg
powershell
winget install "FFmpeg (Shared)"
(If it asks to agree to terms, type Y and press Enter)

2. Refresh Environment Variables
After installing, you need to tell PowerShell that a new program is available. You can just close and reopen PowerShell, or run this command:

powershell
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
3. Verify it works
Type this to confirm:

powershell
ffmpeg -version
Alternative (if Winget doesn't work)
If for some reason Winget fails, you can use Chocolatey:

powershell
# Run this only if you have Chocolatey installed
choco install ffmpeg
Once installed, find your camera name:
Run this to see your webcam name for the stream:

powershell
ffmpeg -list_devices true -f dshow -i dummy

🎉 IT WORKED! Full WebRTC Pipeline Proven!
Looking at the Docker logs carefully — everything worked perfectly:

log
[RTMP] [conn 172.18.0.1:50346] closed: EOF          ← FFmpeg pushed stream ✅
[path live/test] [recorder] recording stopped        ← Stream was recorded ✅
[WebRTC] [session 06fcadfb] created by 16.171.14.114 ← Browser connected via WebRTC ✅
[WebRTC] [session 06fcadfb] closed: terminated       ← Session ended when stream stopped ✅
[HLS] [muxer live/test] created                      ← HLS also worked ✅
And FFmpeg stats confirm the stream ran healthy for 1 minute 15 seconds:

frame=2253  fps=30  time=00:01:15  bitrate=1004kbits/s  speed=1.01x
📋 Evidence Report for Your Engineer
Send this to your engineer:

✅ MEDIAMTX WEBRTC TEST — PASSED
1. RTMP Ingest:
   FFmpeg → rtmp://localhost:1935/live/test
   2253 frames @ 30fps, 1000kbps, 75 seconds ✅
2. WebRTC Viewer Session:
   [WebRTC] session 06fcadfb created by 16.171.14.114 ✅
3. HLS Fallback:
   [HLS] muxer live/test created ✅
4. Recording:
   [recorder] recording stopped (stored to /recordings) ✅
Server: 15.165.59.154
Ports open: 1935/TCP, 8554/TCP, 8888/TCP, 8889/TCP, 8890/UDP
MediaMTX: v1.17.1 running in Docker ✅
Now run a live stream to keep it active:
bash
# Run as nohup so it stays running even if SSH disconnects
nohup ffmpeg -re -f lavfi -i testsrc=size=1280x720:rate=30 \
  -c:v libx264 -preset ultrafast -b:v 1M \
  -f flv rtmp://localhost:1935/live/test \
  > /tmp/ffmpeg.log 2>&1 &
echo "Streaming PID: $!"
# Browser:
# http://15.165.59.154:8889/live/test  ← WebRTC
# http://15.165.59.154:8888/live/test  ← HLS