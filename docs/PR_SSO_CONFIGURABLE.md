## Make HUST SSO/CAS authentication configurable

This PR makes the hardcoded HUST unified identity authentication (SSO/CAS) into a configurable option, following the same pattern used by Kook and Discord integrations.

### Problem

The SSO login was entirely hardcoded for HUST:
- `CAS_SERVER_URL` hardcoded to `pass.hust.edu.cn`
- `CAS_REDIRECT_URL` hardcoded to `pwn.cse.hust.edu.cn`
- Email suffix hardcoded to `@hust.edu.cn`
- No enable/disable toggle — the "统一身份认证" button always appeared
- Could not be used by other schools or deployments without editing source code

### Solution

**6 files changed, 32 insertions, 26 deletions** (net +6 lines)

| File | Change |
|------|--------|
| `dojo_plugin/config.py` | Add 5 env vars: `ENABLE_SSO`, `CAS_SERVER_URL`, `CAS_REDIRECT_URL`, `CAS_EMAIL_SUFFIX`, `CAS_VERSION` |
| `dojo_plugin/api/v1/sso_login.py` | Remove 20-line hardcoded `Settings` class, import from config instead |
| `dojo_plugin/pages/sso_login.py` | Add `abort(501)` guard when SSO disabled (Kook/Discord pattern) |
| `dojo_plugin/__init__.py` | Conditional blueprint registration: `if ENABLE_SSO: app.register_blueprint(sso)` |
| `dojo_theme/templates/login.html` | `{% if Configs.sso_enabled %}` wrapper around SSO hint |
| `dojo_theme/templates/components/navbar.html` | `{% if Configs.sso_enabled %}` wrapper around SSO button |

### Configuration

```bash
# Enable SSO (disabled by default)
ENABLE_SSO=True

# Required — CAS callback URL
CAS_REDIRECT_URL=http://pwn.cse.hust.edu.cn/cas-login/

# Optional — defaults match HUST
# CAS_SERVER_URL=https://pass.hust.edu.cn/cas/login
# CAS_EMAIL_SUFFIX=@hust.edu.cn
# CAS_VERSION=2
```

### Behavior

| `ENABLE_SSO` | `/cas-login/` | Navbar button | Login page hint |
|--------------|---------------|---------------|-----------------|
| `True` | 302 → CAS server | Visible | Visible |
| `False` (default) | 404 (route unregistered) | Hidden | Hidden |

### Backward Compatibility

Existing HUST deployment only needs to add 2 lines to `config.env`:
```bash
ENABLE_SSO=True
CAS_REDIRECT_URL=http://pwn.cse.hust.edu.cn/cas-login/
```
All other defaults (`pass.hust.edu.cn`, `@hust.edu.cn`, CAS v2) remain unchanged.

### Design Decisions

- **Default off** — new deployments won't show a broken SSO button
- **Same pattern as Kook/Discord** — `os.getenv()` + `abort(501)` + conditional template rendering
- **Zero new dependencies** — uses existing `os.getenv`, `ast.literal_eval`, Jinja2 `Configs`
- **Core auth logic untouched** — `_verify_cas2()`, `CASBackend.authenticate()`, `register_sso()` unchanged

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
