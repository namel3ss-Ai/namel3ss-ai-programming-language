# Scaling and concurrency

Configure intra-instance parallelism via `N3_MAX_PARALLEL_TASKS` (default: 4). The flow engine creates an asyncio semaphore with this value; increase it to allow more concurrent flow branches per instance, or lower it to protect downstream providers/tools.

Provider resilience (timeouts/retries/circuits) still applies per call. Combine `N3_MAX_PARALLEL_TASKS` with provider-level limits and cache settings to balance throughput.

Horizontal scaling pattern:
- Keep each instance stateless; externalize DB/vector stores/tools and secrets.
- Run multiple containers behind a load balancer.
- Tune `N3_MAX_PARALLEL_TASKS` per instance alongside provider quotas to avoid saturation.
- Optional provider cache (`N3_PROVIDER_CACHE_ENABLED=true`, `N3_PROVIDER_CACHE_TTL_SECONDS=300`) can reduce repeated calls within a pod; it is in-memory and not shared across instances.
