# Rowing Telemetry Handle

**A retrofittable, telemetry-enabled rowing oar handle — bringing stroke kinematics to crews who can't afford elite instrumentation.**

Elite rowing programmes measure their athletes in fine detail: catch and finish timing, blade height, feathering, and how well a crew moves as one. That data lives behind expensive, boat-specific instrumentation. Everyone below the top tier rows largely blind. This project asks whether the same insight can be delivered by a handle that slots onto a standard sweep oar — no boat modifications, no elite budget — pairing a sealed sensor handle with a coach-facing dashboard.

The work is deliberately structured as a sequence of cheap experiments, each one earning the right to spend on the next. This repository documents that sequence as it happens. **Stage 0 — offline stroke detection — is complete, and is written up in full below.**

---

## Project status

| Stage | What it proves | Status |
|-------|----------------|--------|
| **0. Offline stroke detection** | A commodity phone IMU can reliably detect strokes and timing faults — before any hardware spend | ✅ **Complete (this document)** |
| 1. On-water validation | The stroke signal survives the move from erg to water; blade-height faults become visible | ⏳ In progress |
| 2. Metrics pipeline | Raw motion → coaching numbers (catch/finish angle, rate, height, crew sync) | Planned |
| 3. Live firmware + BLE | Stream live off a moving oar instead of record-and-analyse | Planned |
| 4. Sealed handle prototype | A custom, waterproof, wirelessly-charged handle that functions like stock | Planned |
| 5. Field pilot | Real crews, a full season — durability, and whether coaches actually reach for it | Planned |
| 6. Coach dashboard | The recurring-revenue software half: history, multi-crew, comparison | Planned |
| 7. Commercialisation | FTO opinion, design-for-manufacture, go-to-market | Planned |

---

# Stage 0 — Offline Stroke Detection

## Summary

Before committing any money to hardware, I set out to answer the cheapest possible version of the core question: **can a commodity smartphone IMU detect individual rowing strokes reliably, and can it surface basic stroke-timing faults?** Using nothing but an iPhone taped to an erg handle and an offline analysis script, the answer is yes. Working from a single continuous recording — a rate ladder from 20 to 32 strokes/min followed by two deliberately injected faults — a band-pass filter and a zero-crossing detector on one acceleration axis segment the piece into strokes, a rushed-recovery fault shows up clearly as a rate spike and an inverted recovery-to-drive ratio, and a blade-height fault correctly produces *nothing* — which, as explained below, is the right result and a deliberate control rather than a miss.

This stage validates the **detection approach**. It does not yet prove the approach survives the move to open water, and it is explicit below about exactly what remains unproven.

## The question this stage answers

Everything downstream of here — custom hardware, waterproofing, a dashboard, a business — is expensive and slow. None of it is worth starting if the fundamental premise fails: that cheap, low-grade motion data carries enough signal to be useful to a coach.

So Stage 0 isolates the single riskiest assumption and tests it for almost nothing:

> Can offline motion data from a phone-grade IMU reliably segment a rowing piece into individual strokes, and distinguish good strokes from specific, named faults?

If that fails, the whole idea fails cheaply and early. If it works, it earns the right to spend on Stage 1.

## Scope — and why it's deliberately narrow

Every constraint here is a choice, not a limitation I failed to overcome:

- **Erg, not water.** An ergometer is a free, repeatable, controllable test rig. It lets me inject faults on demand and record clean baselines without weather, boat access, or risk to equipment.
- **Phone IMU, not custom hardware.** The point is to test the *idea* before paying for the *thing*. A phone already contains an accelerometer and gyroscope good enough to ask the question.
- **Offline, not live.** Record-then-analyse removes every real-time engineering concern (firmware, BLE, latency) so I can focus purely on whether the signal is there.
- **Detection and timing, not force.** Force measurement needs a load sensor and is explicitly deferred to a later phase. Stage 0 is about kinematics only.

The goal of Stage 0 is not to build the product. It is to de-risk it.

## Method

### Setup

- **Device:** iPhone 13
- **Recording app:** Sensor Logger (v1.62), logging at **100 Hz** (10 ms sample interval)
- **Channels captured:** calibrated and uncalibrated accelerometer and gyroscope, plus gravity and device orientation
- **Mounting:** the phone was taped flat to the handle, screen up, with the camera end pointing left and the charging-port end pointing right — fixing the phone's axes relative to the handle for the entire piece. In this orientation the drive direction runs along the phone's **x-axis**, which the analysis confirms as the channel carrying the stroke (**ACC-x**).

### A key point about which axis carries the signal

On an ergometer, the handle travels **back and forth in a straight line**. The stroke therefore lives in **linear acceleration along the drive axis** — referred to throughout as **ACC-x**. The yaw-rate (angular velocity) channel stays essentially flat, because nothing is rotating.

This matters enormously for what comes later. **On the water, the oar does not translate in a line — it pivots about the pin.** There, the stroke signal will live in **yaw rate**, not linear acceleration. Same sensor, different axis. Recognising this now is what makes Stage 1's central test precise: it is not "does detection still work," it is "does the signal move to the axis I predict, and does detection follow it there." Stage 0 establishes the method on the axis the erg exposes; Stage 1 tests whether it transfers.

### The recording

The whole protocol lives in **one continuous recording**, bracketed by three sharp up-and-down taps of the handle at the very start and again at the very end to mark the boundaries of the piece. Everything in between was rowed at **backstops** — the handle drawn to the chest at the finish position, matching how the handle sits when used on the water — across six phases run back to back:

| Phase | Strokes | Rate (spm) | Purpose |
|-------|---------|-----------|---------|
| 1 | 10 | 20 | Rate ladder — baseline detection |
| 2 | 10 | 26 | Rate ladder |
| 3 | 10 | 32 | Rate ladder — top of range |
| 4 | 10 | 20 | Return to baseline |
| 5 | 5 | 20 | **Rushed-recovery fault** |
| 6 | 5 | 20 | **Dip-at-catch fault** |

Phases 1–4 sweep the rate band to test whether detection holds across cadence rather than at one comfortable rate. Phases 5 and 6 inject two named faults — one the detector should catch, one it should (correctly) not, on an erg.

For reproducibility, the faults were rowed as follows:

- **Rushed recovery:** arms rushed away, a slow rock-over, then a rushed slide into the catch.
- **Dip at catch:** some strokes dipped the hands early on the recovery, others dipped right at the catch.

The two tap markers bracket the rowing; the six phase boundaries within are recovered from the stroke detector's own output, with the deliberate rate changes across phases 1–4 confirming the segmentation.

## The detection pipeline

This is the technical core of Stage 0. The pipeline is intentionally simple, and every step is a deliberate choice:

1. **Isolate ACC-x.** The drive-axis acceleration is where the stroke lives on an erg (see above), so the other channels are set aside for this stage.

2. **Band-pass filter, 0.10–0.80 Hz.** Stroke rates of 20–32 spm correspond to roughly 0.33–0.53 Hz. A band-pass with this range brackets that comfortably: the low cut-off removes DC offset and slow drift (gravity component, posture shifts), and the high cut-off removes fast noise (vibration, sensor jitter) that would otherwise trigger false crossings. What survives is a clean, near-sinusoidal oscillation, one cycle per stroke.

3. **Zero-crossing detection.** On the filtered, zero-centred signal, each stroke is one oscillation that crosses zero. Detecting these crossings (in a consistent direction) marks one event per stroke.

4. **Refractory period, 1.3 s.** After each detected stroke, further detections are suppressed for 1.3 s. This is shorter than the shortest real stroke period in the tested range, so it never clips a legitimate stroke — but it is long enough to swallow the residual within-stroke ripple that would otherwise double-count a single stroke.

**Result:** every stroke across the rate ladder is detected, with no misses and no double-counts. *(Figures below.)*

## Results

*The five figures below are produced by the analysis script in `src/` and exported to `plots/`. Each is captioned with what to look for.*

**Rate ladder with detected strokes.**
![Drive-axis acceleration across the full piece with each detected stroke marked](plots/01_rate_ladder_detected.png)
*The whole piece with every detected stroke marked; the four rate-ladder phases are visible as changing cadence.*

**Band-pass, before and after.**
![ACC-x before and after the 0.10-0.80 Hz band-pass](plots/02_bandpass_before_after.png)
*The raw, drifting, noisy trace against the clean one-cycle-per-stroke oscillation the detector actually runs on.*

**Detected rate across the ladder.**
![Detected stroke rate tracking the commanded rate ladder](plots/03_rate_per_phase.png)
*The detector's recovered stroke rate tracking the commanded 20 → 26 → 32 → 20 ladder — the test that detection holds across cadence, not just one rate.*

**Rushed-recovery fault.**
![Rushed-recovery phase showing a rate spike and inverted recovery-to-drive ratio](plots/04_rushed_recovery.png)
*The rushed phase: stroke rate spikes and the recovery-to-drive time ratio inverts relative to a clean stroke. A timing fault the erg can express, and the pipeline catches it.*

**Dip-at-catch fault (negative control).**
![Dip-at-catch phase showing no distinguishing signal, by design](plots/05_dip_at_catch_null.png)
*The dip phase produces no distinguishing kinematic signature on the erg — the expected null result. See below for why that is correct.*

## What this proves — and what it doesn't

Being precise here is the point. A demo that hides its own limits is worth less than one that states them.

**The dip-at-catch null is a negative control, not a failure.** An erg has no blade in water and no vertical dimension for the blade to be too deep in. A blade-height fault therefore *cannot physically manifest* on an ergometer. Its absence from the data confirms two useful things at once: that the erg's limits are exactly where they should be, and that the detector does not hallucinate a fault that isn't there. This was designed in as a control, precisely so that when height faults *do* need detecting, it happens on water where they can actually occur.

**What remains unproven until on-water testing:**

- That the stroke signal moves from linear acceleration (ACC-x) to **yaw rate** once the oar pivots about the pin, as predicted.
- That **blade-height faults become detectable** once there is a real blade and a real vertical dimension.
- That **catch and finish angles** can be recovered by integrating yaw rate.

Stage 0 validates the detection *approach* on the axis the erg exposes. Whether that approach survives the change of axis is the first thing Stage 1 tests — which is exactly why Stage 1 is next.

## What's next — Stage 1

An ESP32-S3 microcontroller with a BNO055 IMU (~£75 in parts), taken on the water and mounted to the oar with no packaging work at all. The goal is narrow and specific: confirm the signal shifts to yaw rate, confirm catch/finish angles fall out of it, and confirm that height faults — invisible here by design — become visible. In-handle packaging, waterproofing, and everything physical is a deliberately separate, later problem.

---

## Repository structure

```
rowing-telem-handle/
├── README.md                 # this document
├── requirements.txt          # Python dependencies
├── src/
│   └── stage0_erg_explore.py # the analysis + detection pipeline
├── firmware/
│   └── i2c_scanner/          # Stage 1 I2C bus check
├── data/
│   └── sample/               # the Sensor Logger recording used above
└── plots/                    # exported figures referenced above
```

The recording is a standard Sensor Logger export: one CSV per channel (`Accelerometer.csv`, `Gyroscope.csv`, `Gravity.csv`, `Orientation.csv`, and their uncalibrated variants), each with `time` (ns epoch), `seconds_elapsed`, and `z, y, x` columns, plus a `Metadata.csv`. Stage 0 uses the calibrated accelerometer, drive axis (x).

## Running it

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the analysis against the sample recording
python src/stage0_erg_explore.py data/sample/
```

The script loads the accelerometer export, runs the detection pipeline, prints a per-phase stroke summary, and writes the five figures above to `plots/`.

---

*Author: **Joseph Kocabas** — GitHub [@j03k-dev](https://github.com/j03k-dev). Part of an ongoing project documented stage by stage.*
