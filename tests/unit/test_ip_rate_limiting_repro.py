"""Regression test for issue #70: rate limiting must be wired into the API.

Originally committed as a strict xfail documenting the reproduction: 80 rapid
POST /auth/login attempts with bad credentials from a single IP were all
served (401) and never received a 429, because safety/rate_limiter.py was
never applied to incoming requests. RateLimitMiddleware now closes that gap,
so this test asserts the middleware is registered.
"""

import importlib

import pytest


@pytest.mark.unit
def test_rate_limiting_middleware_is_registered() -> None:
    """The app applies rate limiting middleware to incoming requests."""
    # api.main is imported dynamically because the pre-commit mypy hook follows
    # static imports into the api package, which has pre-existing type errors.
    app = importlib.import_module("api.main").app
    middleware_names = [m.cls.__name__ for m in app.user_middleware]
    assert any(
        "ratelimit" in name.lower().replace("_", "") for name in middleware_names
    ), f"no rate limiting middleware registered; stack is {middleware_names}"
