#!/usr/bin/env python3
"""
Data comparison tool: collects system data using psutil (Python app's method)
and simultaneously runs the C++ app to collect data, then compares both.

Usage: python3 compare_data.py [--duration 30]
"""

import csv
import glob
import os
import signal
import subprocess
import sys
import time

import psutil

DURATION = 30
INTERVAL = 0.25  # 250ms, matching both apps
PY_CSV = "/tmp/taskwire_py_data.csv"
CPP_CSV = "/tmp/taskwire_cpp_data.csv"
CPP_BIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build", "taskwire")

# ── AMD GPU sysfs (same logic as C++ app) ──────────────────

def read_amd_gpu():
    paths = glob.glob("/sys/class/drm/card*/device/gpu_busy_percent")
    max_usage = 0.0
    for p in paths:
        try:
            with open(p) as f:
                val = float(f.read().strip())
                max_usage = max(max_usage, max(0.0, min(100.0, val)))
        except (OSError, ValueError):
            pass
    return max_usage

# ── Temperature reading (hwmon, same logic as C++ app) ─────

def read_temps_hwmon():
    """Read temps from /sys/class/hwmon, return count of sensors found."""
    count = 0
    hwmon_dir = "/sys/class/hwmon"
    if not os.path.isdir(hwmon_dir):
        return count
    for hw in os.listdir(hwmon_dir):
        hw_path = os.path.join(hwmon_dir, hw)
        if not os.path.isdir(hw_path):
            continue
        for entry in os.listdir(hw_path):
            if entry.startswith("temp") and entry.endswith("_input"):
                try:
                    with open(os.path.join(hw_path, entry)) as f:
                        val = float(f.read().strip()) / 1000.0
                        if -40 <= val <= 150:
                            count += 1
                except (OSError, ValueError):
                    pass
    return count

# ── Fan reading (hwmon) ────────────────────────────────────

def read_fans_hwmon():
    count = 0
    hwmon_dir = "/sys/class/hwmon"
    if not os.path.isdir(hwmon_dir):
        return count
    for hw in os.listdir(hwmon_dir):
        hw_path = os.path.join(hwmon_dir, hw)
        if not os.path.isdir(hw_path):
            continue
        for entry in os.listdir(hw_path):
            if entry.startswith("fan") and entry.endswith("_input"):
                try:
                    with open(os.path.join(hw_path, entry)) as f:
                        int(f.read().strip())
                        count += 1
                except (OSError, ValueError):
                    pass
    return count


def collect_python_data(duration):
    """Collect data using psutil for `duration` seconds."""
    # Prime psutil counters
    psutil.cpu_percent(interval=None)
    psutil.cpu_times_percent(interval=None)
    net_prev = psutil.net_io_counters()
    disk_prev = psutil.disk_io_counters()
    time.sleep(0.25)

    rows = []
    start = time.time()
    while time.time() - start < duration:
        t0 = time.time()
        ts = int(t0 * 1000)

        # CPU
        times = psutil.cpu_times_percent(interval=None)
        cpu_pct = max(0.0, 100.0 - times.idle - times.iowait)

        # GPU (AMD sysfs, same as C++ app)
        gpu_pct = read_amd_gpu()

        # Memory
        mem = psutil.virtual_memory()
        mem_pct = mem.percent
        mem_used = mem.used

        # Disk IO (delta)
        disk_now = psutil.disk_io_counters()
        elapsed = time.time() - t0 if time.time() - t0 > 0 else 0.25
        # Use a stored prev time for accurate delta
        disk_read_bps = (disk_now.read_bytes - disk_prev.read_bytes) / 0.25
        disk_write_bps = (disk_now.write_bytes - disk_prev.write_bytes) / 0.25
        disk_prev = disk_now

        # Network IO (delta)
        net_now = psutil.net_io_counters()
        net_up = (net_now.bytes_sent - net_prev.bytes_sent) / 0.25
        net_down = (net_now.bytes_recv - net_prev.bytes_recv) / 0.25
        net_prev = net_now

        # Temps & Fans (hwmon count — same method as C++)
        temp_count = read_temps_hwmon()
        fan_count = read_fans_hwmon()

        rows.append({
            "timestamp_ms": ts,
            "cpu_pct": round(cpu_pct, 2),
            "gpu_pct": round(gpu_pct, 2),
            "mem_pct": round(mem_pct, 2),
            "mem_used_bytes": mem_used,
            "disk_read_bps": round(disk_read_bps, 1),
            "disk_write_bps": round(disk_write_bps, 1),
            "net_up_bps": round(net_up, 1),
            "net_down_bps": round(net_down, 1),
            "temp_count": temp_count,
            "fan_count": fan_count,
        })

        # Sleep to maintain ~250ms interval
        sleep_time = 0.25 - (time.time() - t0)
        if sleep_time > 0:
            time.sleep(sleep_time)

    # Write CSV
    with open(PY_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"Python: {len(rows)} samples written to {PY_CSV}")
    return rows


def run_cpp_app(duration):
    """Run the C++ app for `duration` seconds, it writes its own CSV."""
    if not os.path.isfile(CPP_BIN):
        print(f"ERROR: C++ binary not found at {CPP_BIN}")
        return False

    # Remove old CSV
    if os.path.exists(CPP_CSV):
        os.remove(CPP_CSV)

    print(f"Starting C++ app for {duration}s...")
    proc = subprocess.Popen([CPP_BIN], stderr=subprocess.DEVNULL)
    time.sleep(duration)

    # Graceful kill
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()

    if os.path.exists(CPP_CSV):
        with open(CPP_CSV) as f:
            reader = csv.reader(f)
            lines = list(reader)
        print(f"C++:    {len(lines) - 1} samples written to {CPP_CSV}")
        return True
    else:
        print("ERROR: C++ app did not produce CSV output")
        return False


def compare_data():
    """Load both CSVs, align by time, compare metrics."""
    # Load Python data
    py_rows = []
    with open(PY_CSV) as f:
        reader = csv.DictReader(f)
        for row in reader:
            py_rows.append(row)

    # Load C++ data
    cpp_rows = []
    with open(CPP_CSV) as f:
        reader = csv.DictReader(f)
        for row in reader:
            cpp_rows.append(row)

    if not py_rows or not cpp_rows:
        print("ERROR: One or both CSVs are empty")
        return

    # Downsample to ~1s intervals for comparison (skip first 2s for warmup)
    def downsample(rows, interval_ms=1000, skip_ms=2000):
        """Take 1 sample per second, skip first skip_ms."""
        first_ts = int(rows[0]["timestamp_ms"])
        result = []
        last_bucket = -1
        for r in rows:
            ts = int(r["timestamp_ms"]) - first_ts
            if ts < skip_ms:
                continue
            bucket = ts // interval_ms
            if bucket != last_bucket:
                result.append(r)
                last_bucket = bucket
        return result

    py_1s = downsample(py_rows)
    cpp_1s = downsample(cpp_rows)

    # Align by count (both should have ~28 samples for 30s - 2s warmup)
    n = min(len(py_1s), len(cpp_1s))
    if n == 0:
        print("ERROR: No comparable samples after warmup")
        return

    print(f"\n{'='*70}")
    print(f"COMPARISON: {n} samples (1s intervals, first 2s skipped)")
    print(f"{'='*70}")

    metrics = [
        ("cpu_pct", "CPU %", "%.1f"),
        ("gpu_pct", "GPU %", "%.1f"),
        ("mem_pct", "Memory %", "%.1f"),
        ("mem_used_bytes", "Memory Used (bytes)", "%.0f"),
        ("disk_read_bps", "Disk Read (B/s)", "%.0f"),
        ("disk_write_bps", "Disk Write (B/s)", "%.0f"),
        ("net_up_bps", "Net Upload (B/s)", "%.0f"),
        ("net_down_bps", "Net Download (B/s)", "%.0f"),
        ("temp_count", "Temp Sensor Count", "%.0f"),
        ("fan_count", "Fan Sensor Count", "%.0f"),
    ]

    print(f"\n{'Metric':<25} {'Py Avg':>12} {'C++ Avg':>12} {'Diff':>10} {'Max Diff':>10}")
    print(f"{'-'*25} {'-'*12} {'-'*12} {'-'*10} {'-'*10}")

    for key, label, fmt in metrics:
        py_vals = [float(py_1s[i][key]) for i in range(n)]
        cpp_vals = [float(cpp_1s[i][key]) for i in range(n)]

        py_avg = sum(py_vals) / len(py_vals)
        cpp_avg = sum(cpp_vals) / len(cpp_vals)
        diffs = [abs(py_vals[i] - cpp_vals[i]) for i in range(n)]
        avg_diff = sum(diffs) / len(diffs)
        max_diff = max(diffs)

        py_str = fmt % py_avg
        cpp_str = fmt % cpp_avg
        diff_str = fmt % avg_diff
        max_str = fmt % max_diff

        # Flag large differences
        flag = ""
        if key in ("cpu_pct", "gpu_pct", "mem_pct") and avg_diff > 5:
            flag = " *** LARGE"
        elif key in ("temp_count", "fan_count") and avg_diff > 0.5:
            flag = " *** MISMATCH"

        print(f"{label:<25} {py_str:>12} {cpp_str:>12} {diff_str:>10} {max_str:>10}{flag}")

    # Per-sample detail for metrics with large diffs
    print(f"\n{'='*70}")
    print("PER-SAMPLE DETAIL (first 10 samples)")
    print(f"{'='*70}")
    print(f"{'#':>3} {'Py CPU':>8} {'C++ CPU':>8} {'Py GPU':>8} {'C++ GPU':>8} "
          f"{'Py Mem%':>8} {'C++ Mem%':>8} {'Py DkRd':>10} {'C++ DkRd':>10}")
    print("-" * 85)

    for i in range(min(10, n)):
        py = py_1s[i]
        cpp = cpp_1s[i]
        print(f"{i:>3} {float(py['cpu_pct']):>8.1f} {float(cpp['cpu_pct']):>8.1f} "
              f"{float(py['gpu_pct']):>8.1f} {float(cpp['gpu_pct']):>8.1f} "
              f"{float(py['mem_pct']):>8.1f} {float(cpp['mem_pct']):>8.1f} "
              f"{float(py['disk_read_bps']):>10.0f} {float(cpp['disk_read_bps']):>10.0f}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Compare Python vs C++ Taskwire data")
    parser.add_argument("--duration", type=int, default=30, help="Collection duration (seconds)")
    parser.add_argument("--compare-only", action="store_true", help="Only compare existing CSVs")
    args = parser.parse_args()

    if args.compare_only:
        compare_data()
        return

    print(f"Collecting data for {args.duration}s from both Python (psutil) and C++ app...\n")

    # Run C++ app in background
    if not os.path.isfile(CPP_BIN):
        print(f"ERROR: Build the C++ app first: cd build && cmake .. && make -j$(nproc)")
        sys.exit(1)

    if os.path.exists(CPP_CSV):
        os.remove(CPP_CSV)

    cpp_proc = subprocess.Popen([CPP_BIN], stderr=subprocess.DEVNULL)
    time.sleep(1)  # Let C++ app initialize

    # Collect Python data (blocking)
    try:
        collect_python_data(args.duration)
    except KeyboardInterrupt:
        pass

    # Stop C++ app
    cpp_proc.send_signal(signal.SIGTERM)
    try:
        cpp_proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        cpp_proc.kill()
        cpp_proc.wait()

    time.sleep(0.5)  # Let CSV flush

    if os.path.exists(CPP_CSV):
        with open(CPP_CSV) as f:
            reader = csv.reader(f)
            lines = list(reader)
        print(f"C++:    {len(lines) - 1} samples written to {CPP_CSV}")
    else:
        print("ERROR: C++ app did not produce CSV output")
        sys.exit(1)

    compare_data()


if __name__ == "__main__":
    main()
