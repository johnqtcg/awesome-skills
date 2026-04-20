# Vegeta Load Test Patterns

## Table of Contents
1. [Core Concepts](#1-core-concepts)
2. [Attack Patterns](#2-attack-patterns)
3. [Target Files](#3-target-files)
4. [Result Analysis](#4-result-analysis)
5. [Pipeline Composition](#5-pipeline-composition)
6. [Go Integration](#6-go-integration)

---

## 1 Core Concepts

Vegeta is a constant-rate HTTP load testing tool. Unlike k6's virtual-user
model, vegeta sends requests at a fixed rate regardless of response time.
This means slow responses don't reduce throughput — they queue up, which
is exactly how you find saturation points.

**Key difference from k6**: k6 models user behavior (VUs with think time);
vegeta models traffic arrival (fixed RPS). Choose vegeta when you need
precise rate control; choose k6 when you need realistic user simulation.

---

## 2 Attack Patterns

### Constant rate attack
```bash
# 500 RPS for 60 seconds
echo "GET http://api.example.com/endpoint" | \
  vegeta attack -rate=500/s -duration=60s | \
  vegeta report -type=text
```

### Ramp-up via pipeline
```bash
# Ramp from 100 to 1000 RPS in 5 steps
for rate in 100 250 500 750 1000; do
  echo "GET http://api.example.com/endpoint" | \
    vegeta attack -rate=${rate}/s -duration=30s
done | vegeta report -type=text
```

### With headers and body
```bash
# POST with auth and JSON body
vegeta attack -rate=200/s -duration=2m \
  -header "Authorization: Bearer ${TOKEN}" \
  -header "Content-Type: application/json" \
  -body payload.json \
  -targets targets.txt | \
  vegeta report -type=text
```

### With warmup separation
```bash
# Warmup phase (discard results)
echo "GET http://api/endpoint" | \
  vegeta attack -rate=50/s -duration=15s > /dev/null

# Measurement phase (capture results)
echo "GET http://api/endpoint" | \
  vegeta attack -rate=500/s -duration=60s | \
  tee results.bin | \
  vegeta report -type=text
```

---

## 3 Target Files

### Basic targets file
```
# targets.txt
GET http://api.example.com/users/1
GET http://api.example.com/users/2
GET http://api.example.com/orders?limit=10

POST http://api.example.com/orders
Content-Type: application/json
@payload.json
```

### Multiple endpoints with weights (round-robin)
```
# mixed-targets.txt — vegeta round-robins through these
GET http://api/users/1
GET http://api/users/2
GET http://api/users/3
GET http://api/products/search?q=test
POST http://api/orders
Content-Type: application/json
@order-payload.json
```

### Generate targets programmatically
```bash
# Generate 1000 unique user targets
for i in $(seq 1 1000); do
  echo "GET http://api/users/$i"
done > targets.txt

vegeta attack -rate=200/s -duration=60s -targets=targets.txt | \
  vegeta report
```

---

## 4 Result Analysis

### Text report
```bash
vegeta attack -rate=500/s -duration=60s ... | vegeta report -type=text
```

Output:
```
Requests      [total, rate, throughput]  30000, 500.02, 498.71
Duration      [total, attack, wait]     60.155s, 59.998s, 156.834ms
Latencies     [min, mean, 50, 90, 95, 99, max]  2.1ms, 15.3ms, 8.2ms, 32.1ms, 55.7ms, 182.4ms, 1.2s
Bytes In      [total, mean]             7350000, 245.00
Bytes Out     [total, mean]             0, 0.00
Success       [ratio]                   99.87%
Status Codes  [code:count]              200:29961  503:28  0:11
Error Set:
503 Service Unavailable
```

### JSON report (machine-readable)
```bash
vegeta attack ... | vegeta report -type=json > report.json
```

### HDR histogram
```bash
vegeta attack ... | vegeta report -type=hdrplot > hdr.txt
# Import into HdrHistogram Plotter for visualization
```

### Plot latency over time
```bash
vegeta attack ... | vegeta plot > plot.html
# Opens interactive latency-over-time chart in browser
```

### Encode/decode for storage
```bash
# Save binary results
vegeta attack ... > results.bin

# Analyze later
vegeta report -type=text < results.bin
vegeta plot < results.bin > plot.html

# Combine multiple runs
cat run1.bin run2.bin | vegeta report
```

---

## 5 Pipeline Composition

Vegeta's power is Unix-pipe composability:

### Breakpoint test (find ceiling)
```bash
#!/bin/bash
# breakpoint.sh — increase rate until p99 > SLO
SLO_P99_MS=200

for rate in 100 200 500 1000 2000 5000; do
  echo "Testing at ${rate} RPS..."
  p99=$(echo "GET http://api/endpoint" | \
    vegeta attack -rate=${rate}/s -duration=30s | \
    vegeta report -type=json | \
    jq '.latencies."99th"' | \
    awk '{printf "%.0f", $1/1000000}')  # ns to ms

  echo "  p99 = ${p99}ms (SLO: ${SLO_P99_MS}ms)"

  if [ "$p99" -gt "$SLO_P99_MS" ]; then
    echo "BREAKPOINT: p99 exceeded SLO at ${rate} RPS"
    break
  fi
done
```

### Soak test with periodic reporting
```bash
#!/bin/bash
# soak.sh — 30-minute soak with 5-minute checkpoints
DURATION=1800  # 30 minutes
INTERVAL=300   # 5-minute checkpoints

for i in $(seq 0 $INTERVAL $((DURATION - INTERVAL))); do
  echo "Checkpoint at ${i}s..."
  echo "GET http://api/endpoint" | \
    vegeta attack -rate=200/s -duration=${INTERVAL}s | \
    vegeta report -type=text | tee "checkpoint_${i}.txt"
done
```

---

## 6 Go Integration

Vegeta is a Go library — embed it for programmatic tests:

```go
package loadtest

import (
    "fmt"
    "net/http"
    "testing"
    "time"

    vegeta "github.com/tsenart/vegeta/v12/lib"
)

func TestAPICapacity(t *testing.T) {
    rate := vegeta.Rate{Freq: 500, Per: time.Second}
    duration := 60 * time.Second

    targeter := vegeta.NewStaticTargeter(vegeta.Target{
        Method: "GET",
        URL:    "http://localhost:8080/api/users/1",
        Header: http.Header{
            "Authorization": []string{"Bearer " + testToken},
        },
    })

    attacker := vegeta.NewAttacker()
    var metrics vegeta.Metrics

    for res := range attacker.Attack(targeter, rate, duration, "load-test") {
        metrics.Add(res)
    }
    metrics.Close()

    // Assert SLOs
    if p99 := metrics.Latencies.P99; p99 > 200*time.Millisecond {
        t.Errorf("p99 latency %v exceeds SLO (200ms)", p99)
    }
    if metrics.Success < 0.999 {
        t.Errorf("success rate %.4f below SLO (99.9%%)", metrics.Success)
    }

    fmt.Printf("Requests: %d, Rate: %.2f/s\n", metrics.Requests, metrics.Rate)
    fmt.Printf("Latencies: p50=%v p99=%v max=%v\n",
        metrics.Latencies.P50, metrics.Latencies.P99, metrics.Latencies.Max)
}
```