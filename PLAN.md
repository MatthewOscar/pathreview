## Solution plan
**Issue:** Add rate limiting per IP address in addition to per user  
https://github.com/ascherj/pathreview/issues/70

### Understand

The repository has a `RateLimiter` class in `safety/rate_limiter.py`, but no request path calls `check_rate_limit`. The configured `rate_limit_per_minute` value is also unused. As a result, unauthenticated requests such as repeated `POST /auth/login` calls are never limited, and authenticated requests are not limited in practice either.

The fix will enforce two independent rolling-window limits in middleware. Every request will use an IP identifier. Requests with a valid authenticated Bearer token will also use a user identifier. Redis failures will log a warning and allow the request.

### Map

- `api/middleware/rate_limit.py`: add a fully typed `RateLimitMiddleware` and helpers for client IP and optional Bearer-token user extraction.
- `api/main.py`: create the Redis client from `settings.redis_url`, register the rate-limit middleware, and preserve the existing CORS and request-ID middleware.
- `core/config.py`: add `rate_limit_trust_proxy: bool = False`; reuse `rate_limit_per_minute` for both IP and user budgets.
- `tests/unit/test_ip_rate_limiting_repro.py`: promote the strict xfail to a real middleware-registration assertion.
- `tests/unit/test_rate_limit_middleware.py`: add mocked or fake Redis tests for identifiers, ordering, exemptions, responses, and Redis failures.
- `safety/rate_limiter.py`: reuse `RateLimiter.check_rate_limit` without changing its fail-open behavior unless tests require a narrowly scoped typing adjustment.

### Plan

1. Implement `RateLimitMiddleware` under `api/middleware/rate_limit.py`. Construct it with a Redis client and settings-derived limit. For each non-exempt request, check the IP budget first, then the user budget when a valid Bearer token identifies a user. Use identifiers with distinct prefixes such as `ip:<address>` and `user:<id>` so the budgets cannot collide.

2. Extract the client IP from `request.client.host`. Ignore `X-Forwarded-For` by default, which matches direct uvicorn access and the local Vite proxy. When `rate_limit_trust_proxy` is true, use the first valid address in `X-Forwarded-For`; deployment must enable this only when the proxy overwrites the header.

3. Limit all application routes except `/health`, which remains available for liveness checks. Apply the same `rate_limit_per_minute` value to separate IP and user windows of 60 seconds. A request with both identities must pass both checks. Return immediately after the first exceeded budget.

4. On rejection, return HTTP `429` with JSON `{"detail": "Rate limit exceeded"}`. Set `Retry-After: 60`, because `check_rate_limit` returns a remaining request count rather than seconds until reset. Include `X-RateLimit-Limit` and `X-RateLimit-Remaining` headers on limited responses. Log Redis exceptions with a warning and continue the request.

5. In `api/main.py`, register the rate limiter first, then `RequestIDMiddleware`, then `CORSMiddleware`. Because `add_middleware` prepends entries, this produces the runtime order CORS outermost, request ID next, and rate limiting innermost. This keeps CORS headers on rate-limit responses for the Vite frontend. Promote the existing reproduction xfail and add unit tests using a fake or mocked Redis client, dynamically importing `api.main` where the app object is required. Run unit tests, ruff, black, and mypy on the new modules and tests.

### Inputs & outputs

Inputs:

- `settings.redis_url` supplies the Redis connection URL.
- `settings.rate_limit_per_minute` supplies the per-IP and per-user limit, with a 60-second rolling window.
- `settings.rate_limit_trust_proxy` controls trusted proxy handling and defaults to `False`.
- `request.client.host` supplies the default IP.
- A valid Bearer token supplies the user identifier when authentication data can be decoded.

Outputs:

- Requests under both applicable budgets continue normally.
- Exceeded IP or user budgets return `429`.
- Rejections include `Retry-After: 60`, `X-RateLimit-Limit`, and `X-RateLimit-Remaining`.
- `/health` remains exempt.
- Redis errors produce a warning and allow the request, preserving fail-open behavior.
- Invalid or missing authentication is treated as IP-only traffic.

### Risks & unknowns

- Middleware must decode tokens consistently with `api/middleware/auth.py` without turning malformed tokens into request failures.
- `request.client` can be absent in tests, so the implementation must use a stable fallback identifier and test that case.
- Trusting forwarded headers incorrectly would let clients evade limits or share another client's limit. The default must remain direct peer IP.
- Middleware registration tests may trigger existing import and type issues in `api.main`; use dynamic imports and mocked settings or Redis as needed.
- The existing broken health-check implementation in `api/routes/health.py` is outside this issue. The rate-limit plan only exempts `/health` and does not repair its database or Redis checks.

### Edge cases

- Missing `request.client` uses `ip:unknown`.
- Multiple forwarded addresses use the first entry only when proxy trust is enabled.
- Empty, malformed, expired, or undecodable Bearer tokens receive IP-only protection.
- Authenticated requests consume both the IP and user budgets.
- Two users behind one IP share the IP budget while keeping separate user budgets.
- Requests with a limit of zero are rejected immediately when Redis is available.
- Redis unavailable, timing out, or raising any client exception allows the request and logs a warning.
- `/health` is exempt regardless of authentication or IP.
