# Add test coverage expansion and merge upstream request logging & tracing module

## Overview

This PR adds comprehensive test coverage and merges the upstream request logging & tracing module from `origin/master`. The two features are complementary: tests verify correctness, structured logging makes every request traceable end-to-end.

**12 files changed, 1858 insertions, 1 deletion**

---

## 1. Test Coverage Expansion (6 new files, 1559 lines)

111 tests (76 unit + 35 integration) across 6 modules:

| File | Lines | Type | Coverage |
|------|-------|------|----------|
| `test/test_dojo_spec.py` | 375 | Unit | Dojo spec / dojo.yml parsing, validation, edge cases |
| `test/test_flag_utils.py` | 289 | Unit | Flag serialization, signing, verification utilities |
| `test/test_config.py` | 255 | Unit | Config loading, environment variables, bootstrap logic |
| `test/test_models.py` | 259 | Unit | Database models: Dojos, DojoChallenges, Belts, Emojis |
| `test/test_api_endpoints.py` | 208 | Integration | REST API endpoints: scoreboard, dojo, belts, score, bootstrap |
| `test/test_awards.py` | 171 | Integration | Belts API, scoreboard badges, dojo pages, profile settings |

Tests run against the live pwn.hust.college instance using existing dojos (`welcome`, `pwntools`) — no test-only dojos needed.

---

## 2. Merge Upstream Request Logging & Tracing (3 new + 3 modified files, 262 lines)

Merged from `origin/master`. Coexists with the existing Prometheus-Grafana monitoring stack — Prometheus handles aggregate metrics, request logging handles per-request traceability.

### New Files

#### `dojo_plugin/utils/request_logging.py` (174 lines)

Structured request logging with trace_id propagation. Key components:

| Component | Purpose |
|-----------|---------|
| `RequestIdFilter` | `logging.Filter` that auto-attaches `trace_id`, `user_id`, `remote_addr`, `reltime` to every log record |
| `setup_trace_id_tracking()` | Flask `before_request` reads `PWN-Trace-ID` header → stores in `flask.g` + `threading.local()` (for werkzeug compatibility) |
| `setup_logging()` | Replaces **all** logger handlers (root, Flask, CTFd, werkzeug, gunicorn) with a single structured formatter |
| `setup_uncaught_error_logging()` | Global `@app.errorhandler(Exception)` — captures method, path, IP, user-agent, referrer, query/form/json data on crash |
| `log_exception()` | Logs 11 request context fields on errors |
| `log_generator_output()` | Times generator yields for streaming responses |

#### `dojo_plugin/utils/query_timer.py` (76 lines)

SQLAlchemy slow query detection:

| Component | Purpose |
|-----------|---------|
| `before_cursor_execute` | SQLAlchemy event — timestamps every query start per thread |
| `after_cursor_execute` | Checks query duration > 0.5s → logs warning with stack trace filtered to dojo_plugin frames |
| `query_timeout()` | Utility to wrap queries with PostgreSQL `statement_timeout` |

#### `nginx-proxy/etc/nginx/conf.d/pwn-trace-id.conf` (1 line)

```nginx
proxy_set_header PWN-Trace-ID $request_id;
```

### Modified Files

| File | Change |
|------|--------|
| `dojo_plugin/__init__.py` | +8 lines — import and wire up `init_query_timer()`, `setup_logging()`, `setup_trace_id_tracking()`, `setup_uncaught_error_logging()` after prometheus_metrics init |
| `nginx-proxy/etc/nginx/vhost.d/default` | +1 line — `proxy_set_header PWN-Trace-ID $request_id;` in `location @forward` |
| `docker-compose.yml` | +1 line — mount `pwn-trace-id.conf` into nginx container |

### trace_id Propagation Chain

```
Browser → nginx (port 80/443)
  nginx generates $request_id → sets PWN-Trace-ID header
    → proxy_pass to ctfd:8000
      → Flask before_request reads header → flask.g + threading.local()
        → every log call passes through RequestIdFilter
          → log line auto-tagged:
            trace_id=<value> user_id=<id> remote_ip=<ip> request_reltime=<sec>
```

### Log Format

```
Before:
INFO [werkzeug] 127.0.0.1 - - [09/Jul/2026 13:22:50] "GET / HTTP/1.1" 200 -

After:
time="2026-07-13 12:21:51,435" trace_id=bd09b9fc6b13338c... request_reltime=0.07 remote_ip=172.17.0.1 user_id=None logger=werkzeug INFO 172.17.0.1 - - [13/Jul/2026 12:21:51] "GET / HTTP/1.1" 200 -
```

### trace_id Values

| Value | Source | Meaning |
|-------|--------|---------|
| `bd09b9fc...` (hex) | nginx `$request_id` | Normal browser request — **correct propagation** |
| `LOCAL` | Flask before_request | Container-internal health check (no nginx) |
| `NONE` | Default fallback | Prometheus scraper bypassing nginx, direct to ctfd:8000 |

---

## Design Decisions

- **Coexistence with Prometheus**: `request_logging.setup_logging()` replaces root logger handler; `prometheus_metrics` uses separate Flask `before_request`/`after_request` hooks — they don't interfere. Verified: `/metrics` still returns HTTP 200.
- **Thread safety**: `setup_trace_id_tracking()` stores trace_id in both `flask.g` (for Flask contexts) and `threading.local()` (for werkzeug logger which runs outside Flask context). Both are thread-safe.
- **No new dependencies**: Uses only stdlib `logging` + `threading`, Flask's `g`/`request`, and CTFd's `get_current_user()`.

---

## Verification (tested on live instance)

- [x] Website HTTP 200
- [x] `/metrics` Prometheus endpoint unaffected
- [x] trace_id propagates from nginx through to application logs (unique per request)
- [x] `request_reltime` timing accurate
- [x] All 13 containers healthy
- [x] Structured log fields present: time, trace_id, request_reltime, remote_ip, user_id, logger, level
- [x] `log_exception()` captures full request context on errors

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
