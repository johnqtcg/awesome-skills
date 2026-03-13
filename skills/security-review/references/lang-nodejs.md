# Security Review — Node.js / TypeScript Extension

Replace Go-specific Gate D domains with these checks for Node.js/TypeScript services. All other gates (A-C, E-F), scenario checklists, severity model, and output contract remain unchanged.

---

## Domain Checklist

| Domain | Check | Tool |
|--------|-------|------|
| Injection | `child_process.exec` with string interpolation → use `execFile` with args array; template literal SQL → use parameterized queries (pg `$1`, Prisma, Knex) | `eslint-plugin-security`, `semgrep` |
| Prototype pollution | `Object.assign({}, userInput)` / `lodash.merge` with untrusted input → freeze prototype or use `Map` | `npm audit`, manual review |
| ReDoS | Regex on user input without complexity bound → use `re2` or limit input length before regex | `eslint-plugin-security` |
| SSRF | `fetch(userURL)` / `axios.get(userURL)` without allowlist → validate URL scheme+host against allowlist | manual review |
| Dependency | `npm audit --production` for reachable vulns; `package-lock.json` committed and up-to-date | `npm audit`, `snyk` |
| Auth middleware | Express middleware order: `helmet` → `cors` → `rateLimit` → `auth` → routes; verify `next()` not called after `res.send()` | manual review |
| Secrets | No secrets in `.env` committed to repo; `dotenv` loaded only in dev; production uses secret manager | `rg` pattern sweep |
| TLS/Crypto | `https.createServer` with `secureProtocol: 'TLSv1_2_method'` minimum; no `rejectUnauthorized: false` in production; `crypto.timingSafeEqual` for comparisons; `bcrypt` / `argon2` for passwords, not `crypto.createHash('md5')` | manual review |
| Input validation | `express-validator` / `zod` / `joi` on all route params and body; `express.json({ limit: '1mb' })` to cap body size | manual review |

## Secure Pattern Examples

### Command Injection

```javascript
// BAD: exec with string interpolation
const { exec } = require('child_process');
app.get('/ping', (req, res) => {
  exec(`ping -c 4 ${req.query.host}`, (err, stdout) => {
    // host=; rm -rf / → command injection
    res.send(stdout);
  });
});

// GOOD: execFile with separate args
const { execFile } = require('child_process');
app.get('/ping', (req, res) => {
  const host = req.query.host;
  if (!/^[a-zA-Z0-9.-]+$/.test(host)) {
    return res.status(400).send('invalid host');
  }
  execFile('ping', ['-c', '4', host], (err, stdout) => {
    res.send(stdout);
  });
});
```

### Prototype Pollution

```javascript
// BAD: deep merge of untrusted input
const lodash = require('lodash');
app.post('/settings', (req, res) => {
  lodash.merge(config, req.body);
  // body: {"__proto__": {"isAdmin": true}} → pollutes all objects
});

// GOOD: use allowlisted fields
app.post('/settings', (req, res) => {
  const { theme, language } = req.body;
  config.theme = theme;
  config.language = language;
});
```

### SSRF

```javascript
// BAD: user URL fetched without validation
app.get('/proxy', async (req, res) => {
  const resp = await fetch(req.query.url); // SSRF
  res.send(await resp.text());
});

// GOOD: allowlist + scheme check
const ALLOWED_HOSTS = new Set(['api.example.com', 'cdn.example.com']);

app.get('/proxy', async (req, res) => {
  const parsed = new URL(req.query.url);
  if (parsed.protocol !== 'https:' || !ALLOWED_HOSTS.has(parsed.hostname)) {
    return res.status(403).send('blocked');
  }
  const resp = await fetch(parsed.toString());
  res.send(await resp.text());
});
```

### TLS & Crypto

```javascript
// BAD: disabled certificate verification
const https = require('https');
const agent = new https.Agent({ rejectUnauthorized: false }); // MitM

// GOOD: default verification with minimum TLS version
const agent = new https.Agent({
  minVersion: 'TLSv1.2',
  // rejectUnauthorized defaults to true
});

// BAD: timing-unsafe comparison
if (providedToken === storedToken) { /* ... */ }

// GOOD: constant-time comparison
const crypto = require('crypto');
if (crypto.timingSafeEqual(Buffer.from(providedToken), Buffer.from(storedToken))) {
  // safe
}

// BAD: MD5 for password
const hash = crypto.createHash('md5').update(password).digest('hex');

// GOOD: bcrypt
const bcrypt = require('bcrypt');
const hash = await bcrypt.hash(password, 12);
const valid = await bcrypt.compare(providedPassword, storedHash);
```

### Input Validation

```javascript
// BAD: no body size limit
app.use(express.json()); // default limit is 100kb but should be explicit

// GOOD: explicit limits
app.use(express.json({ limit: '1mb' }));
app.use(express.urlencoded({ extended: false, limit: '1mb' }));
```

## Automation Commands

```bash
# Dependency audit
npm audit --production

# Secret sweep
rg -n "(AKIA[0-9A-Z]{16}|-----BEGIN .* KEY-----|ghp_[A-Za-z0-9]{36}|xox[baprs]-|password\s*=|secret\s*=|token\s*=)" .

# Optional: semgrep for Node.js patterns
semgrep --config=p/nodejs .
```

## Common False Positives

- `child_process.execFile` with hardcoded binary and no user input in args → suppressed.
- `eval()` in build scripts (webpack config, babel transform) not reachable at runtime → suppressed with note.
- `Object.assign` on server-controlled objects only → suppressed.
- `rejectUnauthorized: false` in test suite connecting to self-signed test server → suppressed with note.
- `crypto.createHash('sha256')` used for content fingerprinting, not password storage → suppressed.
