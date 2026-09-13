# Launch Readiness

Assessment date: 13 September 2026.

## Verdict

Not ready for an unrestricted commercial launch. The application can support a closely supervised, invited beta after credentials and payment procedures are verified; the business's legal setup, policy approval, and live account email remain incomplete. A working website is not legal clearance or a guarantee against security incidents.

## Verified in implementation and testing

- New rates, campaigns, offers, orders, transfer instructions, and payouts use explicitly recorded MAD currency. Historical USD values are preserved, not converted or relabeled.
- The supplied bank details are private server configuration. Only the buyer of an accepted, eligible order can retrieve transfer instructions.
- Transfer reports notify operations without marking payment paid. Fresh admin confirmation unlocks production and sends in-app notifications.
- Regression coverage checks amount/currency tampering, role boundaries, CSRF, rate limits, and backward-compatible currency migration. Browser checks use isolated synthetic orders.
- Deployment targets the existing Render Free service. No paid plan, banking API, or domain purchase is included.
- Account security now supports current-password changes and revocation of existing sessions/remember cookies. Recovery and verification use expiring, one-use, purpose-bound signed links, CSRF, account/IP limits, and a durable email queue. Unknown-address responses do not reveal account existence.
- Email delivery is deliberately disabled pending a verified sender and monitored support address. The site explicitly reports that recovery is unavailable. Enforcement cannot be enabled without email configuration.
- Terms, privacy, and cancellation/refund drafts exist as admin-only previews. The requested no-guaranteed-marketing-results clause distinguishes missed targets from non-delivery and preserves non-waivable liability. Public publication is gated on factual details; versioned acceptance is implemented for new and existing accounts once published.
- An encrypted production-schema backup was restored into an isolated local PostgreSQL 17.11 server, with all 15 original application tables and matching row counts. A second run through the daily systemd service also passed. Neither drill wrote to production.
- A daily local backup-and-restore timer is enabled. It depends on this computer/WSL being available. A daily/manual GitHub health workflow checks public pages, database health, security headers, and protected configuration paths without attack traffic.
- 65 automated tests passed, including recovery, verification, session revocation, policy visibility/acceptance, and existing marketplace/payment regressions. Browser checks exercised reset, new-password login, and email verification using synthetic local accounts; mobile and desktop account views fit without horizontal overflow. External inbox delivery has not been tested.

## Before a public commercial launch

1. Verify the account holder and RIB with the bank and complete a small, authorized real transfer. Match amount, currency, and reference; then verify the full fulfillment, payout, and refund procedures. The app cannot detect bank receipt automatically.
2. Confirm that all previously exposed credentials were rotated. Enable MFA for hosting, source control, and database accounts. The app's separate admin access code is not time-based MFA.
3. Confirm business registration, invoicing/tax arrangements, and use of this bank account with qualified local advisers. The owner has no business address yet. Supply a monitored public support address, finalize cancellation/refund rules, and review the drafts before publication. Complete required privacy/CNDP and international-processing assessments; no registration or exemption has been invented.
4. Configure a verified email sender on a free plan, prove external inbox delivery, then enable `EMAIL_VERIFICATION_REQUIRED=1`. The recovery/verification code and local tests are done; provider setup and live delivery are not.
5. Verify Neon backup/PITR retention, approve backup retention/deletion, and arrange an encrypted off-site copy with a separately protected recovery key. The local restore drill and timer are done, but a computer-dependent backup is not sufficient disaster recovery by itself. Confirm health-check failure notifications and appoint an incident/support owner.
6. Onboard real verified creators and test with invited brands. At the database check, the live marketplace had no creator profiles, campaigns, offers, or orders.

## Hosting limitations

Render Free sleeps when idle, shares free instance hours across the workspace, and is not an always-on service. Free compute does not guarantee zero spending: bandwidth/build overages can incur charges with a card attached. Workspace-wide billing settings were not changed. See [Render's free-service limits](https://render.com/docs/free).

The `.com` domain is not registered by this project. The Render subdomain can be used for the supervised beta.

See [OPERATIONS.md](OPERATIONS.md) for the installed backup paths, commands, email activation, policy review, and incident procedures. No actual bank transfer, payout, or refund was initiated during these checks.
