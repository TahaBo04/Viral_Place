# Briefvora Operations

## Account email

The recovery and verification implementation is present, but live email is disabled until a sender is configured. Nothing is sent to a test inbox or written to public logs as a substitute.

1. Provide a monitored support address and a domain you control. Verify the sending domain with Resend, including its required DNS records. Use a sending-only API key and the free plan; do not enable a paid upgrade.
2. Put `RESEND_API_KEY`, `MAIL_FROM` (a plain email address), `SUPPORT_EMAIL`, and `PUBLIC_BASE_URL=https://briefvora.onrender.com` in Render environment settings. Keep local credentials in ignored files, not chat or Git. Flask reads `.env`, not `.env.local` automatically.
3. Redeploy, request a reset for an invited test account, and verify actual inbox receipt, expiry, reset, old-session rejection, and successful login. Test spam/bounce handling and a verification email. The browser fixture is not proof of external delivery.
4. After delivery works, set `EMAIL_VERIFICATION_REQUIRED=1` and redeploy. Existing non-admin accounts must verify before marketplace mutations; reading pages and account-security actions remain possible. No accounts are silently marked verified.

The durable `account_emails` table holds purpose-bound, hashed action tokens and delivery state. Links expire after 30 minutes for resets or two hours for verification. The raw signed token is reconstructed using the server secret, delivered in the URL fragment, and removed from browser history before form submission. Reset POSTs require CSRF protection. Password changes revoke session and remember cookies by incrementing the account's session version.

The background worker runs only when email is configured. It wakes on enqueue and every ten minutes while the web process is running; Render Free can suspend it. It retries with a stable provider idempotency key, at most five attempts. Conservative limits allow at most 80 provider attempts per rolling daily window and 2,400 per 31-day window, shared across workers. These controls do not replace provider billing settings. `flask --app wsgi dispatch-mail` dispatches one batch manually; it can send real emails.

Expired queue records are removed after seven days when the worker runs. Investigate unsent, unexpired rows with five attempts privately. Do not export recipients or token hashes into public issues. Email-key rotation should not rotate the app's session secret unnecessarily; rotating `SECRET_KEY` invalidates all sessions and pending signed action links.

## Backups and Restore

Installed on this computer:

- PostgreSQL 17.11 tools: `/home/taha/.local/briefvora-pg/usr/lib/postgresql/17/bin`.
- Encrypted backups and row-count/checksum manifests: `/home/taha/.local/share/briefvora/backups`, mode 700.
- Separate encryption key: `/home/taha/.config/briefvora/backup.key`, mode 600. Losing this key makes the backups unusable. Keep an additional secure offline copy, separate from the backups.
- User timer `briefvora-backup.timer`: daily around 08:15 local time, with a short randomized delay and a missed-run catch-up. **This requires this computer and its WSL/user service manager to be running. It is not an off-site, always-on backup service.**

The script uses native `pg_dump`, a read-only exported snapshot, and GnuPG AES-256 encryption. It includes the application's `public` schema only, not provider roles, other Neon schemas, provider settings, or environment secrets. Before migration, all 15 public application tables were restored successfully and every table's row count matched the snapshot. A successful restore does not verify external bank transactions or provider-level point-in-time recovery.

```bash
systemctl --user start briefvora-backup.service
systemctl --user list-timers briefvora-backup.timer
journalctl --user -u briefvora-backup.service -n 20 --no-pager
```

Manual backup and drill:

```bash
LD_LIBRARY_PATH=/home/taha/.local/briefvora-pg/usr/lib/x86_64-linux-gnu \
  .venv/bin/python scripts/backup_database.py \
  --pg-bin /home/taha/.local/briefvora-pg/usr/lib/postgresql/17/bin --restore-drill
```

To test an older archive, add `--archive /absolute/path/to/briefvora-TIMESTAMP.dump.gpg`; keep its matching `.dump.json` manifest. This mode does not connect to production. Restore drills create a private, disposable PostgreSQL server listening only on a local Unix socket and remove it afterward. There is deliberately no production-restore destination argument. Only restore archives from a trusted source: database dumps can contain executable database definitions.

Backups are currently retained locally until reviewed and removed by the operator. No automatic deletion of existing backups is configured. Approve a retention schedule, monitor disk usage, arrange an encrypted off-site copy, and verify Neon retention/PITR settings before public launch. A production recovery procedure must include change control, pausing writes, a new empty database, restoration testing, and controlled connection-string replacement; never run a drill over the live database.

## Monitoring and Incidents

`Deployment Health` in GitHub Actions runs daily and manually. It checks the public homepage, login CSRF, database health, security headers, and denial of `.env.local`/`.git/config`. It uses five read-only requests, not brute-force testing or frequent keep-alive traffic. Schedule timing is best-effort; GitHub may disable schedules on inactive public repositories. This is a smoke check, not continuous uptime or attack monitoring. Enable Actions failure notifications and appoint a person to respond.

```bash
gh workflow run monitor.yml
python scripts/check_site.py
```

For an incident: suspend new orders and payment confirmations, preserve logs privately, revoke the affected access, rotate exposed credentials at their issuer, update every dependent deployment, and verify sessions and bank instructions. Do not place passwords, tokens, customer records, or full environment files in a GitHub issue. Assess notification obligations with the appropriate adviser. Avoid changing a shared Neon owner password until every dependent service can be updated together.

The Render API credential, database credentials, and old Stripe secrets previously pasted in chat need confirmed rotation/revocation. MFA enrollment for GitHub, Render, and Neon requires the owner's device and protected recovery codes. A separate static admin access code is not time-based MFA. Rotation and provider MFA remain unverified.

## Policy Publication

Admins can preview `/legal/terms`, `/legal/privacy`, and `/legal/cancellations`. Visitors receive 404 until `POLICIES_PUBLISHED=1`. Publication requires nonempty `BUSINESS_LEGAL_NAME`, `BUSINESS_ADDRESS`, `BUSINESS_REGISTRATION`, `PRIVACY_REGISTRATION`, `SUPPORT_EMAIL`, and `POLICY_VERSION`. Filling fields is not legal approval; do not invent details or claim an exemption without advice.

The owner confirmed that no business address is available yet. Do not infer the registered operator from the bank-account holder or claim Briefvora is an incorporated company. A Moroccan adviser should review the legal operator, registration/tax and invoicing requirements, lawful bank use, data formalities and international processing, retention, content rights, and final cancellation/refund deadlines and calculations. Amend the draft templates and version before publication. Registration and existing-account marketplace writes then require explicit agreement, with a stored version and acceptance timestamp.

The requested clause excludes a guarantee of marketing outcomes, including views, sales, leads, and ROI. It does not erase agreed deliverables or non-waivable responsibility. An express performance commitment must be treated separately. This is draft contract language, not a legal opinion or an assurance of immunity.

References: [OWASP recovery guidance](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html), [Resend HTTPS email API](https://resend.com/docs/api-reference/emails/send-email), [PostgreSQL backups](https://www.postgresql.org/docs/17/app-pgdump.html), [Moroccan obligations code, including Article 232](https://www.wipo.int/wipolex/fr/legislation/details/19785), [CNDP website guidance](https://www.cndp.ma/conformite-des-sites-web/).
