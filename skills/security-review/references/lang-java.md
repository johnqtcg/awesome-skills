# Security Review — Java / Spring Extension

Replace Go-specific Gate D domains with these checks for Java/Spring services. All other gates (A-C, E-F), scenario checklists, severity model, and output contract remain unchanged.

---

## Domain Checklist

| Domain | Check | Tool |
|--------|-------|------|
| Deserialization | No `ObjectInputStream.readObject` on untrusted input; Jackson `DefaultTyping` disabled or restricted to allowlist | `spotbugs`, `semgrep` |
| Injection | No string-concatenated SQL/JPQL → use `@Query` with `?1` params or `CriteriaBuilder`; no SpEL with user input in `@Value` / `@PreAuthorize` | `spotbugs`, `find-sec-bugs` |
| Auth | `@PreAuthorize` / `@Secured` on controller methods; `SecurityFilterChain` order correct; CSRF enabled for session-auth endpoints | manual review |
| Dependency | `mvn dependency:tree` for transitive deps; `OWASP dependency-check-maven` or `snyk` for CVEs | `dependency-check`, `snyk` |
| Logging | No PII/secrets in `log.info()`; use structured logging with masking for sensitive fields; no `e.printStackTrace()` in production code | `spotbugs` |
| Config | `application.yml` secrets use `${VAULT_*}` or Spring Cloud Vault; no plaintext passwords in committed profiles | `rg` pattern sweep |
| TLS/Crypto | `server.ssl.protocol=TLSv1.3` or `TLSv1.2` minimum; no `SSLContext.getInstance("SSL")` or `TLSv1`; `BCryptPasswordEncoder` for passwords, not MD5/SHA1; `MessageDigest.isEqual()` for constant-time comparison | manual review |
| Input validation | `@Valid` / `@Validated` on controller params; `@Size`, `@Min`, `@Max`, `@Pattern` constraints; `spring.servlet.multipart.max-file-size` and `max-request-size` configured | manual review |

## Secure Pattern Examples

### Unsafe Deserialization

```java
// BAD: ObjectInputStream on untrusted data
ObjectInputStream ois = new ObjectInputStream(request.getInputStream());
Object obj = ois.readObject(); // RCE via gadget chains

// GOOD: use JSON with type validation
ObjectMapper mapper = new ObjectMapper();
// do NOT enable default typing:
// mapper.enableDefaultTyping(); // DANGEROUS
MyDTO dto = mapper.readValue(request.getInputStream(), MyDTO.class);
```

### SQL Injection

```java
// BAD: string concatenation
String query = "SELECT * FROM users WHERE name = '" + name + "'";
Statement stmt = conn.createStatement();
ResultSet rs = stmt.executeQuery(query);

// GOOD: parameterized query
PreparedStatement ps = conn.prepareStatement(
    "SELECT * FROM users WHERE name = ?");
ps.setString(1, name);
ResultSet rs = ps.executeQuery();
```

### SSRF in Spring

```java
// BAD: user URL fetched directly
@GetMapping("/fetch")
public String fetch(@RequestParam String url) {
    return restTemplate.getForObject(url, String.class); // SSRF
}

// GOOD: validate against allowlist
private static final Set<String> ALLOWED_HOSTS = Set.of("api.example.com");

@GetMapping("/fetch")
public String fetch(@RequestParam String url) {
    URI uri = URI.create(url);
    if (!ALLOWED_HOSTS.contains(uri.getHost()) || !"https".equals(uri.getScheme())) {
        throw new ResponseStatusException(HttpStatus.FORBIDDEN, "blocked host");
    }
    return restTemplate.getForObject(uri, String.class);
}
```

### TLS Configuration

```java
// BAD: deprecated TLS version
SSLContext ctx = SSLContext.getInstance("TLSv1"); // vulnerable

// GOOD: modern TLS
SSLContext ctx = SSLContext.getInstance("TLSv1.3");

// Spring Boot application.yml
// server:
//   ssl:
//     protocol: TLSv1.3
//     enabled-protocols: TLSv1.3,TLSv1.2
```

### Password Hashing

```java
// BAD: MD5 for password storage
MessageDigest md = MessageDigest.getInstance("MD5");
byte[] hash = md.digest(password.getBytes());

// GOOD: BCrypt
BCryptPasswordEncoder encoder = new BCryptPasswordEncoder(12);
String hash = encoder.encode(password);
if (encoder.matches(providedPassword, storedHash)) {
    // authenticated
}
```

## Automation Commands

```bash
# Dependency vulnerability check
mvn org.owasp:dependency-check-maven:check

# Secret sweep
rg -n "(password\s*[:=]\s*[\"'][^\"']+|secret\s*[:=]\s*[\"'][^\"']+|AKIA[0-9A-Z]{16})" .

# Optional: SpotBugs with find-sec-bugs plugin
mvn spotbugs:check -Dspotbugs.plugins=com.h3xstream.findsecbugs:findsecbugs-plugin
```

## Common False Positives

- `ObjectInputStream` used only for internal RPC with signature verification → suppressed with note.
- `@PreAuthorize` missing on public (unauthenticated) endpoints → N/A.
- `e.printStackTrace()` in test code only → suppressed.
- `MessageDigest("SHA-256")` used for file checksums, not password storage → suppressed.
- `SSLContext` with `TLSv1.2` in legacy client connector with documented upgrade plan → note in risk register.
