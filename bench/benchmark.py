"""Runs the SAME measurements for Approach A (Docker) and Approach B (native venv).
Usage:  python benchmark.py --mode both --runs 5
Writes raw results to results/*.csv (never edit these by hand)."""
import argparse, csv, http.client, json, os, platform, shutil, statistics, subprocess, sys, threading, time
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import psutil

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
OUT = Path(__file__).resolve().parent / "results"
IMAGE, CNAME = "smallapp:bench", "smallapp_bench"
NATIVE_PORT, DOCKER_PORT = 5001, 5002
WORKLOADS = [100, 1000, 5000]          # total requests per load test
CONCURRENCY = 10
BIN = "Scripts" if os.name == "nt" else "bin"
VENV = APP / ".venv_bench"
VPY = VENV / BIN / ("python.exe" if os.name == "nt" else "python")


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def dir_mb(p: Path):
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 2**20


def wait_ready(port, timeout=60):
    url = f"http://127.0.0.1:{port}/api/v1/health"
    end = time.perf_counter() + timeout
    while time.perf_counter() < end:
        try:
            with urllib.request.urlopen(url, timeout=1) as r:
                if r.status == 200:
                    return
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(0.01)
    raise TimeoutError(f"app on port {port} not ready")


def load_test(port, n):
    """n GET requests, CONCURRENCY threads; 80% list, 20% by-id (deterministic).
    Each thread reuses one keep-alive HTTP connection (avoids Windows port exhaustion)."""
    paths = [f"/api/v1/books/{(i % 100) + 1}" if i % 5 == 0 else f"/api/v1/books?page={(i % 5) + 1}"
             for i in range(n)]
    local = threading.local()

    def one(p):
        c = getattr(local, "c", None)
        if c is None:
            c = local.c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        t = time.perf_counter()
        try:
            c.request("GET", p)
            r = c.getresponse(); r.read(); ok = r.status == 200
        except (http.client.HTTPException, OSError):
            c.close(); local.c = None; ok = False
        return (time.perf_counter() - t) * 1000, ok

    t0 = time.perf_counter()
    with ThreadPoolExecutor(CONCURRENCY) as ex:
        res = list(ex.map(one, paths))
    wall = time.perf_counter() - t0
    lat = sorted(r[0] for r in res)
    return dict(mean_ms=statistics.mean(lat), p95_ms=lat[int(0.95 * (len(lat) - 1))],
                throughput_rps=n / wall, errors=sum(1 for r in res if not r[1]))


# ---------------- Approach B: native ----------------
def native_setup():
    if VENV.exists():
        shutil.rmtree(VENV)
    t = time.perf_counter()
    run([sys.executable, "-m", "venv", str(VENV)])
    run([str(VPY), "-m", "pip", "install", "--no-cache-dir", "-q", "-r", str(APP / "requirements.txt")])
    return dict(approach="native", setup_s=time.perf_counter() - t, footprint_mb=dir_mb(VENV) + (APP / "app.py").stat().st_size / 2**20)


def native_start():
    env = dict(os.environ, PORT=str(NATIVE_PORT), DB_PATH=str(APP / "native.db"))
    t = time.perf_counter()
    p = subprocess.Popen([str(VPY), str(APP / "app.py")], env=env, cwd=APP,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    wait_ready(NATIVE_PORT)
    return p, (time.perf_counter() - t) * 1000


def native_mem(p):
    proc = psutil.Process(p.pid)
    return (proc.memory_info().rss + sum(c.memory_info().rss for c in proc.children(True))) / 2**20


def native_stop(p):
    p.terminate(); p.wait(10)


# ---------------- Approach A: Docker ----------------
def docker_setup():
    t = time.perf_counter()
    run(["docker", "pull", "-q", "python:3.14-slim"])
    pull_s = time.perf_counter() - t
    t = time.perf_counter()
    run(["docker", "build", "--no-cache", "-q", "-t", IMAGE, str(APP)])
    build_s = time.perf_counter() - t
    size = int(run(["docker", "image", "inspect", "-f", "{{.Size}}", IMAGE]).stdout.strip())
    return dict(approach="docker", setup_s=build_s, base_pull_s=pull_s, footprint_mb=size / 2**20)


def docker_start():
    subprocess.run(["docker", "rm", "-f", CNAME], capture_output=True)
    t = time.perf_counter()
    run(["docker", "run", "-d", "--rm", "--name", CNAME, "-p", f"{DOCKER_PORT}:5000", IMAGE])
    wait_ready(DOCKER_PORT)
    return CNAME, (time.perf_counter() - t) * 1000


def docker_mem(_):
    s = run(["docker", "stats", "--no-stream", "--format", "{{json .}}", CNAME]).stdout
    usage = json.loads(s)["MemUsage"].split("/")[0].strip()       # e.g. "31.2MiB"
    num = float("".join(ch for ch in usage if ch.isdigit() or ch == "."))
    unit = usage.lstrip("0123456789.").lower()
    return num * {"kib": 1/1024, "mib": 1, "gib": 1024, "b": 1/2**20}.get(unit, 1)


def docker_stop(_):
    subprocess.run(["docker", "stop", "-t", "2", CNAME], capture_output=True)


APPROACHES = {
    "native": (native_setup, native_start, native_mem, native_stop, NATIVE_PORT),
    "docker": (docker_setup, docker_start, docker_mem, docker_stop, DOCKER_PORT),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["native", "docker", "both"], default="both")
    ap.add_argument("--runs", type=int, default=5)
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    modes = ["docker", "native"] if a.mode == "both" else [a.mode]
    setup_rows, run_rows, load_rows = [], [], []
    for m in modes:
        setup, start, mem, stop, port = APPROACHES[m]
        print(f"[{m}] setup ..."); setup_rows.append(setup())
        for r in range(1, a.runs + 1):
            h, startup_ms = start()
            time.sleep(2)                                   # settle before idle reading
            idle = mem(h)
            for n in WORKLOADS:
                res = load_test(port, n)
                load_rows.append(dict(approach=m, run=r, requests=n, **res))
            after = mem(h)
            stop(h)
            run_rows.append(dict(approach=m, run=r, startup_ms=startup_ms, idle_mem_mb=idle, mem_after_load_mb=after))
            print(f"[{m}] run {r}: start {startup_ms:.0f} ms, idle {idle:.1f} MB, after load {after:.1f} MB")
            time.sleep(2)
    for name, rows in [("setup", setup_rows), ("runs", run_rows), ("load", load_rows)]:
        with open(OUT / f"{name}.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    env = dict(os=platform.platform(), python=platform.python_version(), cpu_count=psutil.cpu_count(),
               ram_gb=round(psutil.virtual_memory().total / 2**30, 1))
    if "docker" in modes:
        env["docker"] = run(["docker", "version", "-f", "{{.Server.Version}}"]).stdout.strip()
    (OUT / "environment.json").write_text(json.dumps(env, indent=2))
    print("done ->", OUT)


if __name__ == "__main__":
    main()