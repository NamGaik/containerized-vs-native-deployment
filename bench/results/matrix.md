| Sr. No. | Test Case / Workload | Evaluation Metric | Approach A (Docker) | Approach B (Native) |
|---|---|---|---|---|
| 1 | Cold startup | Startup time (ms) | 1751.9 ± 151.1 | 1148.2 ± 564.1 |
| 2 | Idle service | Memory (MB) | 25.7 ± 0.8 | 47.4 ± 0.1 |
| 3 | After all load tests | Memory (MB) | 55.4 ± 0.6 | 104.8 ± 6.6 |
| 4 | Load 100 req | Mean response time (ms) | 75.5 ± 14.2 | 17.3 ± 5.8 |
| 5 | Load 100 req | p95 response time (ms) | 114.0 ± 17.8 | 30.6 ± 16.2 |
| 6 | Load 100 req | Throughput (req/s) | 131.7 ± 21.4 | 578.1 ± 157.8 |
| 7 | Load 1000 req | Mean response time (ms) | 100.5 ± 22.3 | 20.5 ± 3.3 |
| 8 | Load 1000 req | p95 response time (ms) | 161.4 ± 46.6 | 31.2 ± 8.1 |
| 9 | Load 1000 req | Throughput (req/s) | 103.3 ± 23.6 | 491.8 ± 69.9 |
| 10 | Load 5000 req | Mean response time (ms) | 119.5 ± 5.1 | 20.3 ± 1.9 |
| 11 | Load 5000 req | p95 response time (ms) | 202.7 ± 12.9 | 29.8 ± 3.0 |
| 12 | Load 5000 req | Throughput (req/s) | 83.8 ± 3.6 | 495.1 ± 48.3 |
| 13 | First-time setup | Setup time (s) | 8.0 | 15.1 |
| 14 | First-time setup | Disk footprint (MB) | 176.6 | 16.7 |

Base image pull time (not in setup time): 7.6 s