## Harden seccomp: remove dangerous syscall allowances and improve DNS resolution

### Summary

This PR tightens the seccomp security profile in `dojo_plugin/config.py` by removing unconditional allowances for four dangerous syscalls, and replacing blocking DNS resolution with a fault-tolerant implementation. The changes match upstream pwncollege master.

**1 file changed, 8 insertions, 11 deletions.**

### Problem

The current `create_seccomp()` unconditionally allows four syscalls commonly used in container escape exploits:

| Syscall | Risk |
|---------|------|
| `clone` | Can create privileged processes with `CLONE_NEWUSER` |
| `unshare` | Can disassociate namespace context |
| `setns` | Can join other namespaces (key container escape primitive) |
| `sethostname` | Can leak kernel information |

Additionally, `USER_FIREWALL_ALLOWED` uses `socket.gethostbyname()` which blocks on DNS failure and can crash the service.

### Changes

#### 1. Remove unconditional syscall allowances (-10 lines)

```python
# REMOVED — these syscalls now fall back to Docker's default conditional policy:
seccomp["syscalls"].append({
    "names": ["clone", "sethostname", "setns", "unshare"],
    "action": "SCMP_ACT_ALLOW",
})
```

Docker's default seccomp profile applies arg-based restrictions on these syscalls (e.g., blocking `CLONE_NEWUSER` on `clone`). The old code bypassed those restrictions entirely.

#### 2. Safe DNS resolution (+7 / -1 lines)

```python
# NEW — fault-tolerant IPv4 resolution:
def first_ipv4_address(hostname):
    try:
        return sorted(set(info[4][0] for info in
            socket.getaddrinfo(hostname, None, family=socket.AF_INET)))[0]
    except Exception as e:
        warnings.warn(f"Could not resolve IPv4 address for {hostname}: {e}")
        return None

# Updated — falls back to "0.0.0.0" on DNS failure:
USER_FIREWALL_ALLOWED = {
    host: first_ipv4_address(host) or "0.0.0.0"
    for host in pathlib.Path("/var/user_firewall.allowed").read_text().split()
}
```

### Verification

Tested on a running pwn.hust.college instance:

| Check | Result |
|-------|--------|
| No unconditional `clone`/`unshare`/`setns`/`sethostname` in seccomp | ✅ |
| `personality` syscall still handled correctly | ✅ |
| `first_ipv4_address()` resolves real hosts | ✅ |
| `first_ipv4_address()` returns `None` for invalid hosts (no crash) | ✅ |
| Main site HTTP 200 | ✅ |
| `/metrics` endpoint | ✅ |
| Dojo listing `/dojos` | ✅ |
| Login page | ✅ |
| SSO `/cas-login/` → CAS redirect | ✅ |
| All 13 containers healthy | ✅ |

### Attack Surface Reduction

| Vector | Impact |
|--------|--------|
| User namespace escape via `clone(CLONE_NEWUSER)` | Blocked by Docker default policy |
| Cross-namespace jump via `setns` | Blocked |
| Namespace manipulation via `unshare` | Blocked |
| Service crash on DNS failure | Eliminated by fallback to `"0.0.0.0"` |

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
