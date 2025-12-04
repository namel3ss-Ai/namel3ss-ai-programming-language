from namel3ss.security.context import SecurityContext
from namel3ss.security.quotas import InMemoryQuotaTracker, QuotaConfig, QuotaExceededError


def test_quota_allows_then_blocks():
    tracker = InMemoryQuotaTracker(QuotaConfig(max_requests_per_minute=2))
    ctx = SecurityContext(subject_id="s", app_id=None, tenant_id=None, roles=[], scopes=[], auth_scheme="api_key")
    tracker.check_and_consume(ctx)
    tracker.check_and_consume(ctx)
    try:
        tracker.check_and_consume(ctx)
        assert False, "Expected quota exceeded"
    except QuotaExceededError:
        pass


def test_quota_separated_per_subject():
    tracker = InMemoryQuotaTracker(QuotaConfig(max_requests_per_minute=1))
    ctx_a = SecurityContext(subject_id="a", app_id=None, tenant_id=None, roles=[], scopes=[], auth_scheme="api_key")
    ctx_b = SecurityContext(subject_id="b", app_id=None, tenant_id=None, roles=[], scopes=[], auth_scheme="api_key")
    tracker.check_and_consume(ctx_a)
    # second call for same subject exceeds
    try:
        tracker.check_and_consume(ctx_a)
        assert False, "Expected quota exceeded for ctx_a"
    except QuotaExceededError:
        pass
    # ctx_b should still be allowed
    tracker.check_and_consume(ctx_b)
