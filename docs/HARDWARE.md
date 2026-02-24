# Hardware layer
English | [Русский](HARDWARE_ru.md)

## 1. Idea

Assemble a practical hardware set to launch a UWB system in a gym in order to:
- quickly start backend/metrics development,
- test player tracking stability,
- evaluate real-world limits in frequency, latency, and scalability.

The document separates:
- **fast-low-cost entry (R&D bench)** — for experiments and development,
- **advanced deployment option (gym / pilot)** — closer to real-world operation.

> Important: **the ball is considered only in the advanced deployment option**.  
> In the **fast-low-cost option, the ball is not included**.

---

## 2. Hardware (anchors / gateway / tag core)

### 2.1 Anchors (ready-made, to bring the system up faster)

#### Option A: UbiTrack-A1 (Indoor Anchor)
- Publicly sold as an indoor UWB anchor
- The UbiTrack website lists price around **~$500 / unit**

**Best for:** fast gym pilot where software/metrics matter more than RF hardware tuning.

#### Option B: HID Sewio Vista Anchors (Omni / Direct)
- Commercial RTLS-class anchors (Vista line)
- PoE / enterprise-grade integration
- Pricing usually **quote-based / via integrator**

**Best for:** more serious gym pilot where higher reliability and less DIY are required.

---

### 2.2 Gateway / Edge (local server)

The system requires a **Linux edge host**:
- mini PC / fanless PC / industrial mini PC
- 1× Ethernet uplink to switch
- storage for logs / raw packets / aggregates

**Minimum:**
- CPU: **4–8 cores**
- RAM: **16–32 GB**
- SSD: **512 GB+**
- Network: **1 Gbps Ethernet**

**Recommended:**
- separate disk/partition for logs,
- NTP/PTP time stabilization on edge host,
- UPS

---

### 2.3 Tag Core (wearable player tag)

#### Recommended base module: Qorvo DWM3001C
Inside:
- UWB (DW3110-class)
- BLE SoC (nRF52833)
- accelerometer
- modular format (convenient for custom wearable)

Why this is convenient:
- less RF layout complexity,
- faster transition to firmware and protocols,
- ability to build custom tag on top of a ready module.

**Price reference:** Qorvo store lists **~$50 per unit**.

---

### 2.4 Fast-Low-Cost Entry (R&D): ESP32 + DW3000 (Makerfabs)

#### Makerfabs ESP32 UWB DW3000
- Ready dev board for rapid experiments
- Price reference: **~$43.80**

**Important:** good option for laboratory bench and prototypes, but not automatically a stable sports-grade TDoA solution in a real gym.

---

## 3. Key Technical Parameters (Beyond Hz) That Must Not Be Ignored

Update rate matters, but for real system performance the following parameters are equally important:

### 3.1 End-to-End Latency
What to measure:
- time from measurement/packet to coordinate availability in API,
- average latency and P95/P99.

**Why it matters:** even with good Hz, high latency breaks real-time metrics and live scenarios.

---

### 3.2 Jitter (variation in update intervals)
What matters:
- not only average frequency, but interval stability,
- spikes/drops in time between updates.

**Why it matters:** tracking filters and event detectors perform worse on irregular data streams.

---

### 3.3 Packet Loss / Dropout Rate
What matters:
- percentage of lost packets,
- duration of tracking gaps (e.g., >100 ms, >500 ms).

**Why it matters:** dropouts often define practical quality more than nominal frequency.

---

### 3.4 Position Accuracy and Stability
What matters:
- RMS / median error,
- 95th percentile error,
- stability at court edges,
- degradation under body shadowing / movement / dense player clusters.

**Why it matters:** “20 Hz” without acceptable spatial accuracy is of limited value.

---

### 3.5 Scaling by Number of Tags
What matters:
- how Hz drops / latency increases as tag count grows,
- behavior at 1 / 2 / 4 / 8 / 10+ tags.

**Why it matters:** a system that works with 1 tag may degrade significantly with full lineup.

---

### 3.6 Anchor Synchronization (for TDoA)
What matters:
- sync stability,
- time drift,
- repeatability after restart / reconnect.

**Why it matters:** synchronization issues often cause systematic errors and unstable coordinates.

---

### 3.7 Court RF Conditions
What matters:
- anchor height and geometry,
- metal structures / stands / reflective surfaces,
- LoS/NLoS scenarios,
- cabling/PoE and real installation layout.

**Why it matters:** the same hardware may behave differently in different gyms.

---

### 3.8 Tag Power Consumption and Autonomy
What matters:
- active-mode current,
- battery lifetime,
- mode degradation at higher update rates.

**Why it matters:** wearable tag must survive a training session/match with margin.

---

## 4. Update Rate (Hz): What Actually Matters for Basketball

### 4.1 UWB Coordinate Rate vs Internal Sensor Rate
- **IMU inside tag:** often **200–500+ Hz** (internal accelerometer/gyro polling)
- **UWB position (coordinates):** usually **significantly lower** and depends on:
  - number of tags,
  - mode (TDoA / TWR),
  - channel,
  - infrastructure,
  - RF conditions.

### 4.2 Practical References for Sports Systems
In public sources/validations for KINEXON LPS, often cited:
- **players — 20 Hz**
- **ball — 50 Hz**

This is frequently used as a reference for sports scenarios.

### 4.3 Why This Matters
- ball at **20 m/s** travels **0.4 m in 20 ms** (i.e., at **50 Hz**)
- at **10 Hz**, 100 ms step → about **~2 m** between updates

### 4.4 Practical Conclusion for Basketball MVP
- **players:** target **20 Hz UWB** per player (realistic working reference)
- **ball:** **50 Hz UWB** — separate complex task (preferably separate development branch)

> For fast-low-cost option (R&D bench), **ball is not included**.  
> For advanced deployment option — **ball may be included separately** as extension.

---

## 5. Comparison of Options (Cost / Reliability / Real Constraints)

> Below are engineering references for assembly and launch, not vendor guarantees.

| Option | What We Use | Approximate Price (device-only) | Realistic Player Target | Ball | Reliability |
|---|---|---|---|---|---|
| Fast-Low-Cost (R&D) | ESP32+DW3000 (Makerfabs) nodes | ~$43.8/node | Highly dependent on sync/mode; test first with small tag count | **Not included** | Lab / R&D |
| Basic Gym Setup | Commercial anchors + custom tags | anchors from ~$500/unit; tags depend on build | **Players ~20 Hz** realistic target | Separate task | Higher than DIY |
| Commercial Anchors + DWM3001C Tags | anchors + DWM3001C tag core | DWM3001C ~$50/unit + PCB/battery/case | **Players ~20 Hz**, IMU much higher internally | Separate task | Good for pilot |
| Vista-class (Sewio/HID) | Enterprise anchors + custom integration | Quote-based | Depends on configuration/integration | Possible as separate phase | High |

### Important Note on “Marketing Hz”
If you see “200–500+ Hz” in specifications/marketing, this is often **not UWB coordinate rate**, but internal sensor (IMU) frequency.

---

## 6. Minimum Budgets (Device-Only, No Mounting)

### 6.1 Fast-Low-Cost R&D Bench (Start Writing Software)
- 6 × Makerfabs ESP32 UWB DW3000 anchors ≈ **$260–270**
- 2 × same boards as tags ≈ **$75–90**
- 1 × mini PC / laptop (not counted if already available)

**Total (device-only UWB boards):** ≈ **$340–360**

What this enables:
- bring up protocols,
- test update rates and packet flow,
- validate basic math,
- start backend/logging/filtering.

What this does **not** automatically provide:
- stable sports-grade tracking in a gym with 10 players,
- ready-to-use ball tracking.

> In this option, **ball is not included**.

---

### 6.2 Gym Option (Players Only, No Ball)
- 6 × UbiTrack-A1 anchors ≈ **$3,000** (at $500/unit)
- 10 × DWM3001C modules ≈ **$500** (per-unit price, no bulk discount)

**Total (anchors + tag core modules only):** ≈ **$3.5k+**

Additional required (not included here):
- PoE switch
- PCB/case/battery per tag
- edge host (if not available)
- anchor mounting / cabling / installation
- spare tags / batteries / chargers

---

### 6.3 Advanced Deployment Option (Players + Ball as Separate Track)
- Base: option 6.2 or Vista-class anchors
- Separate R&D/engineering branch for ball tracking:
  - separate tag/form factor,
  - dedicated frequency and stability tests,
  - separate trajectory validation.

**Why separate:** ball requirements are significantly stricter in frequency, latency, dynamics, and track robustness.

---

### 6.4 Sewio/HID Vista-Class Option
- anchors — **quote-based** (typically via integrator)
- higher budget than DIY/retail-like options

What this provides:
- less time spent on RF/anchor-level debugging,
- faster transition to backend/metrics,
- more predictable pilot deployment in gym.
