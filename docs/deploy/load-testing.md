# Load testing flows

Use the lightweight harness to exercise a flow under concurrency:

```bash
python scripts/load_test_flows.py \
  --program path/to/app.n3 \
  --flow my_flow \
  --concurrency 8 \
  --requests 50
```

The script runs `FlowEngine.run_flow_async` concurrently and prints totals, average latency, and p95 latency. Adjust `N3_MAX_PARALLEL_TASKS` to see how per-instance concurrency impacts latency and errors. For horizontal scaling, run multiple containers behind a balancer and distribute load while keeping external stores shared.
