# Security Review — Python / FastAPI / Django Extension

Replace Go-specific Gate D domains with these checks for Python services. All other gates (A-C, E-F), scenario checklists, severity model, and output contract remain unchanged.

---

## Domain Checklist

| Domain | Check | Tool |
|--------|-------|------|
| Injection | No `eval()` / `exec()` / `pickle.loads()` on untrusted input; ORM (SQLAlchemy/Django ORM) for queries, raw SQL only with bind params | `bandit`, `semgrep` |
| SSTI | Jinja2 `Environment(autoescape=True)` for user content; no `Template(user_string)` | `bandit` |
| Auth | FastAPI `Depends(get_current_user)` on protected routes; Django `@login_required` / `@permission_required`; CSRF middleware enabled for session auth | manual review |
| Dependency | `pip-audit` or `safety check` for installed packages; `requirements.txt` / `poetry.lock` pinned to exact versions | `pip-audit`, `safety` |
| Deserialization | No `yaml.load()` without `Loader=SafeLoader`; no `pickle` with network input | `bandit` |
| Async safety | FastAPI async endpoints: no blocking I/O in `async def` (use `run_in_executor`); shared mutable state requires lock | manual review |
| TLS/Crypto | `ssl.create_default_context()` instead of manual context; `PROTOCOL_TLS_CLIENT` not deprecated `PROTOCOL_TLSv1`; `hashlib.scrypt` / `bcrypt` / `argon2` for passwords, not `hashlib.md5`/`sha1` | manual review |
| Input validation | Pydantic models with constrained types (`conint`, `constr`, `Field(max_length=...)`) for all API inputs; `Body(max_length=...)` or middleware body size limit | manual review |

## Secure Pattern Examples

### SQL Injection

```python
# BAD: string interpolation in SQL
@app.get("/users")
async def get_users(name: str):
    query = f"SELECT * FROM users WHERE name = '{name}'"  # injection
    return await db.fetch_all(query)

# GOOD: parameterized query
@app.get("/users")
async def get_users(name: str):
    query = "SELECT * FROM users WHERE name = :name"
    return await db.fetch_all(query, values={"name": name})
```

### Insecure Deserialization

```python
# BAD: pickle on untrusted input
import pickle
def load_session(data: bytes):
    return pickle.loads(data)  # arbitrary code execution

# GOOD: use JSON or signed serialization
import json
from itsdangerous import URLSafeTimedSerializer
serializer = URLSafeTimedSerializer(SECRET_KEY)

def load_session(token: str):
    return serializer.loads(token, max_age=3600)
```

### SSTI (Server-Side Template Injection)

```python
# BAD: user string rendered as template
from jinja2 import Template
def render(user_input: str):
    return Template(user_input).render()  # SSTI: {{ config }}

# GOOD: sandboxed environment with autoescape
from jinja2 import Environment, select_autoescape
env = Environment(autoescape=select_autoescape(["html"]))
def render(template_name: str, **kwargs):
    return env.get_template(template_name).render(**kwargs)
```

### TLS Configuration

```python
# BAD: disabled certificate verification
import ssl
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# GOOD: default secure context
import ssl
ctx = ssl.create_default_context()
# optionally set minimum version
ctx.minimum_version = ssl.TLSVersion.TLSv1_2
```

### Password Hashing

```python
# BAD: raw hash without salt/stretch
import hashlib
password_hash = hashlib.sha256(password.encode()).hexdigest()

# GOOD: proper password hashing
from passlib.hash import argon2
password_hash = argon2.hash(password)
if argon2.verify(provided_password, stored_hash):
    # authenticated
```

## Automation Commands

```bash
# Dependency audit
pip-audit

# Static analysis
bandit -r . -ll

# Secret sweep
rg -n "(password\s*=\s*[\"'][^\"']+|secret\s*=\s*[\"'][^\"']+|AKIA[0-9A-Z]{16})" .

# Optional: semgrep for Python patterns
semgrep --config=p/python .
```

## Common False Positives

- `pickle.loads` used only for internal cache with trusted data → suppressed with note on trust boundary.
- `yaml.load` with `Loader=SafeLoader` already specified → suppressed.
- `eval()` in migration scripts not reachable at runtime → suppressed with note.
- `hashlib.sha256` used for content fingerprinting (not password storage) → suppressed.
- `ssl.CERT_NONE` in test fixture connecting to self-signed test server → suppressed with note.
