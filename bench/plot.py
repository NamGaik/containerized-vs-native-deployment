"""Builds graphs + the filled evaluation matrix from results/*.csv (actual data only)."""
import csv, statistics as st
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

R = Path(__file__).resolve().parent / "results"
load = lambda n: list(csv.DictReader(open(R / f"{n}.csv")))
runs, lrows, setup = load("runs"), load("load"), load("setup")
LBL = {"docker": "Approach A: Containerized (Docker)", "native": "Approach B: Non-containerized (venv)"}
modes = [m for m in ["docker", "native"] if any(r["approach"] == m for r in runs)]
col = lambda rows, m, k: [float(r[k]) for r in rows if r["approach"] == m]
ms = lambda v: (st.mean(v), st.stdev(v) if len(v) > 1 else 0.0)

# Graph 1: startup time per repeated run
plt.figure(figsize=(7, 4))
for m in modes:
    v = col(runs, m, "startup_ms"); plt.plot(range(1, len(v) + 1), v, marker="o", label=LBL[m])
plt.xlabel("Run number"); plt.ylabel("Startup time to first 200 OK (ms)")
plt.title("Graph 1: Cold startup time across repeated runs"); plt.legend(); plt.grid(alpha=.3)
plt.tight_layout(); plt.savefig(R / "graph1_startup.png", dpi=150)

# Graph 2: mean response time vs workload
W = sorted({int(r["requests"]) for r in lrows})
plt.figure(figsize=(7, 4))
for m in modes:
    means = [st.mean([float(r["mean_ms"]) for r in lrows if r["approach"] == m and int(r["requests"]) == w]) for w in W]
    plt.plot(W, means, marker="o", label=LBL[m])
plt.xscale("log"); plt.xticks(W, [str(w) for w in W])
plt.xlabel("Workload (total requests, concurrency 10)"); plt.ylabel("Mean response time (ms)")
plt.title("Graph 2: Mean response time vs workload"); plt.legend(); plt.grid(alpha=.3)
plt.tight_layout(); plt.savefig(R / "graph2_response.png", dpi=150)

# Graph 3: memory idle vs after load
import numpy as np
x = np.arange(2); w = 0.35
plt.figure(figsize=(7, 4))
for i, m in enumerate(modes):
    vals = [ms(col(runs, m, "idle_mem_mb")), ms(col(runs, m, "mem_after_load_mb"))]
    plt.bar(x + (i - .5) * w, [v[0] for v in vals], w, yerr=[v[1] for v in vals], capsize=4, label=LBL[m])
plt.xticks(x, ["Idle (2 s after start)", "After 6,100 requests"]); plt.ylabel("Memory (MB)")
plt.title("Graph 3: Memory usage (mean ± std over runs)"); plt.legend(); plt.tight_layout()
plt.savefig(R / "graph3_memory.png", dpi=150)

# Filled matrix
def cell(m, f):
    try: return f(m)
    except Exception: return "-"
fmt = lambda t: f"{t[0]:.1f} ± {t[1]:.1f}"
lat = lambda m, w, k: ms([float(r[k]) for r in lrows if r["approach"] == m and int(r["requests"]) == w])
S = {r["approach"]: r for r in setup}
rows = [("Cold startup", "Startup time (ms)", lambda m: fmt(ms(col(runs, m, "startup_ms")))),
        ("Idle service", "Memory (MB)", lambda m: fmt(ms(col(runs, m, "idle_mem_mb")))),
        ("After all load tests", "Memory (MB)", lambda m: fmt(ms(col(runs, m, "mem_after_load_mb"))))]
for wl in W:
    rows.append((f"Load {wl} req", "Mean response time (ms)", lambda m, wl=wl: fmt(lat(m, wl, "mean_ms"))))
    rows.append((f"Load {wl} req", "p95 response time (ms)", lambda m, wl=wl: fmt(lat(m, wl, "p95_ms"))))
    rows.append((f"Load {wl} req", "Throughput (req/s)", lambda m, wl=wl: fmt(lat(m, wl, "throughput_rps"))))
rows += [("First-time setup", "Setup time (s)", lambda m: f"{float(S[m]['setup_s']):.1f}"),
         ("First-time setup", "Disk footprint (MB)", lambda m: f"{float(S[m]['footprint_mb']):.1f}")]
out = ["| Sr. No. | Test Case / Workload | Evaluation Metric | Approach A (Docker) | Approach B (Native) |", "|---|---|---|---|---|"]
for i, (tc, met, f) in enumerate(rows, 1):
    out.append(f"| {i} | {tc} | {met} | {cell('docker', f)} | {cell('native', f)} |")
if "docker" in S: out.append(f"\nBase image pull time (not in setup time): {float(S['docker']['base_pull_s']):.1f} s")
(R / "matrix.md").write_text("\n".join(out)); print("\n".join(out))
