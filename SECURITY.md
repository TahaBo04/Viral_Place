# Security

## Application controls

- Passwords are hashed with Werkzeug scrypt. New passwords require 12-128 characters. Unknown accounts still perform a password-hash comparison to reduce timing differences.
- Login failures are blocked at five per account or 30 per IP within 15 minutes. Atomic request counters additionally cap 10 login requests per account and 40 per IP in 15 minutes, preventing concurrent requests from bypassing failure counters. Registration permits 10 requests per IP per hour; other writes permit 120 per minute. Limits survive worker restarts in PostgreSQL and return HTTP 429 with `Retry-After`.
- CSRF applies to browser forms, including payment confirmation and logout. No exempt payment blueprint remains. HTML responses use `Cache-Control: no-store`.
- Production cookies use Secure, HttpOnly, SameSite=Lax and `__Host-` names. Signed sessions expire after eight hours. Admins cannot use remember-me; operations mutations require a fresh login and role checks. A distinct admin access code is required in addition to the password.
- Production startup requires persistent PostgreSQL, a session secret of at least 32 characters, and disabled demo seeding. Configure strong randomly generated secrets, not repeated or guessable values.
- CSP restricts scripts to local files, blocks plugins and framing, restricts form submissions, and disallows inline script. HSTS is set in production. Responses include nosniff, frame denial, referrer, permissions, and opener policies.
- Request bodies are limited to 64 KiB, multipart fields to 80, and values to field-specific lengths. Duplicate scalar fields, control characters, uploads, unsupported content types, non-finite metrics, and out-of-range amounts are rejected.
- SQLAlchemy binds user values. Jinja escapes text. Public HTTPS URL validation rejects credentials, private/local names, numeric IPs, alternate ports, backslashes, and control characters. The server does not fetch submitted URLs. This is not DNS-rebinding protection for a future URL-fetching feature.
- Private campaigns, orders, phone contacts, and reviews enforce ownership/role checks. Exact accepted offer amounts come from the database, never checkout form fields.
- Company banking details are configured only through server environment variables, appear only for the buying account after offer acceptance, and remain unavailable until configuration is complete. RIB formatting validation cannot verify bank-account ownership. Only operations can confirm a received transfer; refunds require a transaction reference after the refund has actually been sent.

## Operations

Render includes automatic edge DDoS mitigation on free web services. Application throttling covers targeted authentication and write abuse that can pass through the edge. No custom Vercel firewall rule is applied because this deployment targets Render instead. See [Render's DDoS documentation](https://render.com/articles/how-render-handles-ddos-attacks).

Keep the origin behind its trusted hosting edge. Verify real client IP handling after deploying; never trust arbitrary forwarded headers on a directly exposed origin. Configure only owned domains in `TRUSTED_HOSTS`.

Enable MFA on GitHub, the hosting account, and the database account. Rotate credentials inherited from former owners, remove their access, review database users, and verify backups and restore procedures. These account-level changes are not performed automatically by application code. The app's static operations access code is not time-based MFA.

Monitor failed logins and HTTP 429/5xx rates. Review logs without exposing credentials. Schedule retention of expired `auth_throttles` records and operational logs according to business needs; identifiers in throttle records are HMACs, but login/audit logs contain IPs and user-agent data.

Never deploy a demo database containing published demo credentials. The current startup guard prevents new production seeding; it cannot identify every historical test account. Verify the chosen database before launch. Keep PostgreSQL credentials only in hosting secrets, use TLS, and ensure the database plan/backup retention meets business needs.

## Verification scope

Automated regression tests exercise authentication, request parsing, access boundaries, transfer-only payment behavior, XSS escaping, unsafe links, and production guards. Bandit scans runtime source and pip-audit checks known dependency advisories. These checks are not a guarantee against all vulnerabilities or future attacks. Live hosting, edge behavior, TLS, database permissions, and recovery require verification on the actual deployed service.
