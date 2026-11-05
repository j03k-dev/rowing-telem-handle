"""Stage 0: detect rowing strokes in phone IMU data from an erg."""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.signal import butter, sosfiltfilt

LOW = 0.10
HIGH = 0.80
ORDER = 3
REFRACTORY = 1.3
ARM = -3.0
START = 5.0
END = 137.5

PHASES = {
    "rate 20": (0, 10),
    "rate 26": (10, 20),
    "rate 32": (20, 30),
    "rate 20 again": (30, 40),
    "rushed recovery": (40, 45),
    "dip at catch": (45, 50),
}


def load(folder):
    df = pd.read_csv(Path(folder) / "Accelerometer.csv")
    t = df["seconds_elapsed"].to_numpy()
    acc_x = df["x"].to_numpy()
    fs = 1 / np.mean(np.diff(t))
    return t, acc_x, fs


def bandpass(signal, fs):
    sos = butter(ORDER, [LOW, HIGH], btype="bandpass", fs=fs, output="sos")
    return sosfiltfilt(sos, signal)


def detect(t, acc_bp, fs):
    lookahead = int(0.8 * fs)
    crossings = np.where((acc_bp[:-1] > 0) & (acc_bp[1:] <= 0))[0]
    strokes = []
    last = -np.inf
    for i in crossings:
        if not (START <= t[i] <= END):
            continue
        if acc_bp[i : i + lookahead].min() > ARM:
            continue
        if t[i] - last >= REFRACTORY:
            strokes.append(i)
            last = t[i]
    return np.array(strokes)


def summarise(t, strokes):
    periods = np.diff(t[strokes])
    for name, (a, b) in PHASES.items():
        p = periods[a:b - 1]
        print(f"{name:16} {60 / np.median(p):5.1f} spm  n={len(p)}")


def get_rebound(acc_x, strokes, fs):
    rebound = []
    for i in strokes:
        spike = i + np.argmin(acc_x[i : i + int(0.8 * fs)])
        start = spike + int(0.15 * fs)
        stop = spike + int(0.6 * fs)
        rebound.append(acc_x[start:stop].max())
    return np.array(rebound)


def mean_stroke(acc_x, strokes, fs, name):
    pre, post = int(1 * fs), int(3 * fs)
    a, b = PHASES[name]
    stack = np.array([acc_x[i - pre : i + post] for i in strokes[a:b]])
    return np.arange(-pre, post) / fs, stack.mean(axis=0)


def save_figures(t, acc_x, acc_bp, strokes, rebound, fs):
    Path("plots").mkdir(exist_ok=True)

    plt.figure(figsize=(14, 4))
    plt.plot(t, acc_x, lw=0.4, alpha=0.4, label="raw")
    plt.plot(t, acc_bp, lw=1.2, label="band-passed")
    plt.plot(t[strokes], acc_bp[strokes], "rv", ms=6, label="detected strokes")
    plt.title(f"Stroke detection: {len(strokes)} of 50 strokes")
    plt.xlabel("time (s)")
    plt.ylabel("ACC-x (m/s²)")
    plt.legend()
    plt.savefig("plots/01_rate_ladder_detected.png", dpi=150, bbox_inches="tight")
    plt.close()

    m = (t >= 10) & (t <= 30)
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(14, 6), sharex=True)
    a1.plot(t[m], acc_x[m], lw=0.6)
    a1.set_title("Raw ACC-x")
    a1.set_ylabel("m/s²")
    a2.plot(t[m], acc_bp[m], lw=1.5, color="C1")
    a2.axhline(0, color="k", lw=0.5)
    a2.set_title("Band-passed, 0.10–0.80 Hz")
    a2.set_xlabel("time (s)")
    a2.set_ylabel("m/s²")
    fig.tight_layout()
    fig.savefig("plots/02_bandpass_before_after.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    periods = np.diff(t[strokes])
    plt.figure(figsize=(14, 4))
    plt.plot(np.arange(2, len(strokes) + 1), 60 / periods, "o-", ms=4)
    plt.axvspan(40.5, 45.5, color="C3", alpha=0.15, label="rushed recovery")
    plt.axvspan(45.5, 50.5, color="C2", alpha=0.15, label="dip at catch")
    plt.title("Detected stroke rate, per stroke")
    plt.xlabel("stroke number")
    plt.ylabel("rate (spm)")
    plt.grid(alpha=0.3)
    plt.legend()
    plt.savefig("plots/03_rate_per_phase.png", dpi=150, bbox_inches="tight")
    plt.close()

    lag, clean = mean_stroke(acc_x, strokes, fs, "rate 20 again")
    _, rushed = mean_stroke(acc_x, strokes, fs, "rushed recovery")
    _, dip = mean_stroke(acc_x, strokes, fs, "dip at catch")

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 4.5))
    a1.plot(lag, clean, label="clean, rate 20")
    a1.plot(lag, rushed, color="C3", label="rushed recovery")
    a1.set_title("Mean stroke shape")
    a1.set_xlabel("time from detection (s)")
    a1.set_ylabel("mean ACC-x (m/s²)")
    a1.legend()
    colours = ["C3" if 40 <= n < 45 else "C0" for n in range(len(strokes))]
    a2.bar(np.arange(1, len(strokes) + 1), rebound, color=colours)
    a2.set_title("Post-finish rebound, per stroke")
    a2.set_xlabel("stroke number")
    a2.set_ylabel("rebound (m/s²)")
    fig.tight_layout()
    fig.savefig("plots/04_rushed_recovery.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    plt.figure(figsize=(14, 4.5))
    plt.plot(lag, clean, label="clean, rate 20")
    plt.plot(lag, dip, color="C2", label="dip at catch")
    plt.title("Dip-at-catch control, mean stroke shape (ACC-x)")
    plt.xlabel("time from detection (s)")
    plt.ylabel("mean ACC-x (m/s²)")
    plt.legend()
    plt.savefig("plots/05_dip_at_catch_null.png", dpi=150, bbox_inches="tight")
    plt.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("data_dir")
    args = parser.parse_args()

    t, acc_x, fs = load(args.data_dir)
    acc_bp = bandpass(acc_x, fs)
    strokes = detect(t, acc_bp, fs)
    print(f"strokes detected: {len(strokes)}")

    if len(strokes) != 50:
        raise SystemExit("Expected 50 strokes, so the phase table doesn't apply.")

    summarise(t, strokes)
    rebound = get_rebound(acc_x, strokes, fs)
    save_figures(t, acc_x, acc_bp, strokes, rebound, fs)
    print("saved 5 figures to plots/")


if __name__ == "__main__":
    main()
