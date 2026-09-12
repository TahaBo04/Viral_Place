# Launch Readiness

Assessment date: 12 September 2026.

## Verdict

Ready for a supervised beta after deployment verification, not an unrestricted commercial launch. A working website does not establish that the business is legally or operationally ready. This checklist is not legal clearance or a guarantee against security incidents.

## Verified in implementation and testing

- New rates, campaigns, offers, orders, transfer instructions, and payouts use explicitly recorded MAD currency. Historical USD values are preserved, not converted or relabeled.
- The supplied bank details are private server configuration. Only the buyer of an accepted, eligible order can retrieve transfer instructions.
- Transfer reports notify operations without marking payment paid. Fresh admin confirmation unlocks production and sends in-app notifications.
- Regression coverage checks amount/currency tampering, role boundaries, CSRF, rate limits, and backward-compatible currency migration. Browser checks use isolated synthetic orders.
- Deployment targets the existing Render Free service. No paid plan, banking API, or domain purchase is included.

## Before a public commercial launch

1. Verify the account holder and RIB with the bank and complete a small, authorized real transfer. Match amount, currency, and reference; then verify the full fulfillment, payout, and refund procedures. The app cannot detect bank receipt automatically.
2. Confirm that all previously exposed credentials were rotated. Enable MFA for hosting, source control, and database accounts. The app's separate admin access code is not time-based MFA.
3. Confirm business registration, invoicing/tax arrangements, and use of this bank account with qualified local advisers. Publish accurate business/contact information and reviewed privacy, terms, cancellation, and refund policies. These pages are not currently implemented.
4. Provide a secure account-recovery process and email verification before open registration at scale. Self-service password recovery and email verification are not currently implemented.
5. Verify database backup retention and perform a restore drill; establish monitoring and an incident/support owner. These operational checks have not been completed.
6. Onboard real verified creators and test with invited brands. At the database check, the live marketplace had no creator profiles, campaigns, offers, or orders.

## Hosting limitations

Render Free sleeps when idle, shares free instance hours across the workspace, and is not an always-on service. Free compute does not guarantee zero spending: bandwidth/build overages can incur charges with a card attached. Workspace-wide billing settings were not changed. See [Render's free-service limits](https://render.com/docs/free).

The `.com` domain is not registered by this project. The Render subdomain can be used for the supervised beta.
