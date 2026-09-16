# Skill: AI Provider Failover & Speed

- All calls via AIProviderRouter / LatencyAwareAIProviderRouter.
- HTTP 404/model-not-found → 1h model cooldown + immediate next candidate.
- Prefer free healthy models, then lowest latency.
- ModelSpeedMonitor keeps EWMA fresh without blocking the bot loop.
