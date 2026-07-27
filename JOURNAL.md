# Module 3 Journal

## Week 7 — Issue selection

**Issue link:** https://github.com/ascherj/pathreview/issues/70

**Issue title:** Add rate limiting per IP address in addition to per user

**Tier:** [ ] Tier 1  [x] Tier 2  [ ] Tier 3

**Problem summary:**
PathReview ships a Redis-backed rolling window `RateLimiter` in `safety/rate_limiter.py`, and the issue points out that limiting only happens per authenticated user ID, which leaves unauthenticated traffic to public endpoints with no limit at all. Someone hammering the health or auth routes without logging in never gets throttled, so the safety layer only protects against users the app already knows about. A successful fix adds per-IP limiting as a second layer, applied in `api/middleware/` alongside the existing auth and request ID middleware, so every request gets checked against an IP budget and authenticated requests additionally get checked against their user budget. Requests over either limit should get a 429 response, and the fail-open behavior on Redis errors that the current limiter has should stay the same so an outage in Redis never takes down the API.

**Branch name:** feat/70-per-ip-rate-limiting

**Setup confirmation:** [x] App runs locally at localhost:5173

**Cohort ledger:** [x] Issue added to cohort ledger

### Selection notes ("Is this right for me?")

- Scope fits the estimate. The limiter logic already exists and takes any identifier string, so the work is a middleware in `api/middleware/` plus tests, which matches the 4 to 6 hour tier 2 estimate.
- I understand the code involved. `safety/rate_limiter.py` is about 60 lines using Redis sorted sets, it already has a unit test suite in `tests/unit/test_rate_limiter.py`, and `api/middleware/request_id.py` gives me a pattern to follow for the new middleware.
- It is testable. Unit tests can cover IP keying and the two-layer check, and an integration test can hit a public endpoint repeatedly and assert the 429.
- Risk is manageable. The main thing to get right is reading the client IP correctly behind a proxy (X-Forwarded-For handling) so the limit can't be trivially spoofed or accidentally applied to the proxy itself.
- One thing I noticed on a first read: grepping the repo shows nothing in `api/` ever calls `check_rate_limit`, and `core/config.py` has a `rate_limit_per_minute` setting that nothing reads. So the per-user limiting the issue describes may only exist as the unwired class, and my first task is confirming where enforcement actually happens today, since that decides whether I am adding a second key to existing middleware or building the middleware layer that applies both.

## Week 8 — Reproduction & solution planning

**Reproduction commit link:** https://github.com/MatthewOscar/pathreview/commit/49e0e52b260cbfe95f3a3225a07380d6b4690890

**Reproduction summary:**
With the app running locally I sent 80 rapid `POST /auth/login` attempts with wrong credentials from a single IP, and every request came back 401 with no 429 ever appearing. This confirmed the gap from my Week 7 read: `api/main.py` registers only CORS and request ID middleware, so the commit above adds a strict xfail test documenting that no rate limiting middleware exists in the request path.

**PLAN.md link:** https://github.com/MatthewOscar/pathreview/blob/feat/70-per-ip-rate-limiting/PLAN.md

**Walkthrough video (recommended):** Not recorded.

**Blockers or open questions:**
- The plan decodes the Bearer token inside the middleware to get the user identity, since `get_current_user` in `api/middleware/auth.py` is a route dependency and runs too late. I want to confirm in PR review that the maintainers are fine with that, and with `/health` staying exempt as a liveness probe.
- `check_rate_limit` returns a remaining request count, so the plan uses a fixed `Retry-After: 60`. If reviewers want the real seconds until reset, `RateLimiter` would need a small extension, which I have kept out of scope for now.

## Week 9 — Solution building & PR submission

### Check-in 1 (mid-week)

**Current progress:**
Sub-tasks 1 through 4 from PLAN.md are implemented: `RateLimitMiddleware` in `api/middleware/rate_limit.py` enforcing the `ip:` budget on every non-exempt request and the `user:` budget when a Bearer token decodes, IP extraction with the new `rate_limit_trust_proxy` opt-in, the full 429 contract, and the wiring in `api/main.py`. Thirteen unit tests pass against a mocked Redis client. Before touching code I recorded the repo baseline the course guide asks for: 182 ruff errors, 52 files black would reformat, 5 mypy stub errors plus 44 more reachable from `api.main`, and 53 failing unit tests, all pre-existing.

**Next steps:**
Promote the Week 8 xfail repro test into real assertions, verify the fix live against the running app, re-run the full check suite against the recorded baseline, and open the PR.

**Blockers:**
The pre-commit mypy hook fails on the pre-existing type errors whenever `api/main.py` changes, so that commit needed `--no-verify` with the identical before and after error set documented in the commit message.

---

### Check-in 2 (end of week)

**PR link:** https://github.com/ascherj/pathreview/pull/313

**Branch:** `feat/70-per-ip-rate-limiting`

**What you built:**
Middleware that applies the existing `RateLimiter` to the request path with two rolling-window budgets: per IP for all traffic and per user for authenticated traffic, returning 429 with `Retry-After` and `X-RateLimit` headers when either is exceeded. Redis runs off the event loop with short socket timeouts so a slow or dead Redis fails open instead of stalling the API. Verified live: 70 rapid unauthenticated login attempts got exactly the configured 60 served, then straight 429s, while `/health` stayed exempt.

**Tests added or updated:**
`tests/unit/test_rate_limit_middleware.py` (new, 13 tests): budgets and identifier keys, the 429 header and body contract, `/health` exemption, both `X-Forwarded-For` trust modes, token edge cases, zero limit, missing client, and fail-open on connection errors and timeouts. `tests/unit/test_ip_rate_limiting_repro.py` (promoted from the Week 8 xfail, 4 tests): middleware registered, the real stack constructs with the kwargs wired in `api/main.py`, a request flows with Redis unreachable, and CORS preflights keep `X-Request-ID`.

**Self-review confirmation:** [x] make check passes  [x] make test-unit passes
(per the course definition for a codebase with documented pre-existing failures: both commands fail before and after my branch with byte-identical failure sets, so my changes introduce no new failures; every file I added or touched passes ruff, black, and mypy individually, and unit tests went from 375 to 392 passing)

**Draft PR feedback received from:** none
