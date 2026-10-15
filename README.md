# Containerized vs Non-Containerized Deployment - Experiment Kit

Test subject: `app/app.py`, a layered Library Book REST API (Flask + SQLite, served by Waitress).
Approach A = Docker container (`app/Dockerfile`). Approach B = native Python virtual environment.

## Prerequisites (same machine for both approaches)
- Python 3.12 on the host, Docker Engine / Docker Desktop running
- `pip install -r bench/requirements-bench.txt`

## Run
    cd bench
    python benchmark.py --mode both --runs 5     # ~5-10 min, internet needed once for pip / image pull
    python plot.py                               # graphs + matrix.md from the CSVs

Outputs in `bench/results/`: setup.csv, runs.csv, load.csv, environment.json,
graph1_startup.png, graph2_response.png, graph3_memory.png, matrix.md.

## Fair-test rules
- Close other heavy apps; plug in the laptop; run both approaches in the same session.
- Do not edit the CSVs. Paste matrix.md and the PNGs into the report as produced.
- Optional: run it twice (once cold after reboot) and report both if they differ.

## Manual run (for screenshots)
Approach B:  python -m venv .venv && .venv\Scripts\activate (Windows) or source .venv/bin/activate
             pip install -r requirements.txt && python app.py
Approach A:  docker build -t smallapp . && docker run -p 5000:5000 smallapp
Test:        curl http://localhost:5000/api/v1/books?page=1
