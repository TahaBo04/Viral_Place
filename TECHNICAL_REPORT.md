# Briefvora Technical Report

Briefvora is an independent Flask/Jinja application with SQLAlchemy persistence, Flask-Login authentication, and a read-only company RIB for bank transfers. It has Gunicorn/Render and Vercel Python entrypoints.

## Domain model

| Model | Responsibility |
| --- | --- |
| `User` | Business, influencer, and admin accounts |
| `CreatorProfile` | Creator audience, rates, portfolio, and social ownership review |
| `CreatorSocialAccount` | Canonical platform, safe profile URL, audience count, and primary badge |
| `Campaign` | Public marketplace or private invite-only/managed advertising brief |
| `Application` | Influencer application, direct invitation, or managed recommendation |
| `CollaborationOffer` | Exact gross price, creator-rate snapshot, payout snapshot, and response state |
| `Order` | Accepted-offer customer funds, delivery, refund, and payout state |
| `Submission` | Versioned creator content sent to Briefvora review |
| `OrderEvent` | Customer-visible and operations timeline |
| `Notification` | In-app workflow alerts |
| `DealReview` | Private post-deal feedback from each order participant |
| `AuthThrottle` | Database-backed email and IP login throttling |

## State flow

1. A business creates a public, private invite-only, or private managed campaign.
2. A business sends a whole-dollar offer at or above the creator's published minimum. Operations may first recommend creators for managed campaigns.
3. The creator accepts or declines after seeing the gross price and payout snapshot.
4. Acceptance creates an order; payment routes reject orders without an accepted offer.
5. The creator submits a secure delivery URL after payment confirmation.
6. Operations approves and delivers, requests revision, or refunds the customer.
7. Approved work moves the influencer payout to `ready`; operations records payout completion.
8. After completion or refund, each participant may send one private rating and comment to operations.

Businesses do not require identity verification. Creators prove control of a social account by placing their generated Briefvora code in the linked profile until an admin approves it.

Both account types must provide a regionally valid international phone number before selection. Numbers are normalized to E.164, remain private to operations, and are self-confirmed by the user. Private campaign authorization is centralized: only the owning business, administrators, and invited/recommended/offered creators can view a private brief; unauthorized direct requests return `404`. Admin authentication is isolated to its own portal and requires a password plus a separately configured operations access code. All browser forms use CSRF tokens, login failures are throttled in the shared database, sensitive HTML responses are not cached, and operations state changes are written to the audit log.

## Deployment

`wsgi.py` exposes the WSGI app for Gunicorn. `render.yaml` configures a free Render web service with an existing persistent PostgreSQL database. `api/index.py` remains available for Vercel, but Vercel Hobby excludes commercial use. Production refuses a missing/short secret, SQLite storage, or demo seeding. Database tables and the configured admin are bootstrapped idempotently at application startup.

The old Stripe-named order columns are retained solely for database compatibility; the payment reference column stores manual bank transaction references. There is no Stripe SDK, checkout request, card form, or registered webhook. The former success URL only redirects to the order and cannot change its state. Refunds are recorded only after an admin provides a completed bank-refund reference; this application never moves money.

Atomic database upserts count login requests, failed logins, registration requests, and other writes across workers. Sensitive identifiers are HMAC-hashed in the throttle table. Local requests use the socket IP; trusted hosting deployments use the final appended forwarded address. The host allowlist excludes arbitrary forwarded hosts. Browser forms reject duplicate single-valued fields, uploads, control characters, oversized values, and unsupported content types. Host-validation errors return a minimal response without rendering URLs against an invalid host.

See `SECURITY.md` for the tested protections and operational limits.
