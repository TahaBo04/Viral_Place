# Viral Place Technical Report

Viral Place is a Flask/Jinja application with SQLAlchemy persistence, Flask-Login authentication, Stripe payment integration, and a Vercel Python entrypoint.

## Domain model

| Model | Responsibility |
| --- | --- |
| `User` | Business, influencer, and admin accounts |
| `CreatorProfile` | Creator audience, rates, portfolio, and social ownership review |
| `Campaign` | Managed or marketplace advertising brief |
| `Application` | Influencer application or direct business invitation |
| `Order` | Customer funds, creator assignment, workflow, refund, and payout state |
| `Submission` | Versioned creator content sent to Viral Place review |
| `OrderEvent` | Customer-visible and operations timeline |
| `Notification` | In-app workflow alerts |
| `DealReview` | Private post-deal feedback from each order participant |
| `AuthThrottle` | Database-backed email and IP login throttling |

## State flow

1. A business creates a managed brief or public marketplace campaign.
2. Viral Place assigns a creator, or the business selects an approved applicant.
3. Stripe or operations confirms customer payment.
4. The creator is notified and submits a secure delivery URL.
5. Operations approves and delivers, requests revision, or refunds the customer.
6. Approved work moves the influencer payout to `ready`; operations records payout completion.
7. After completion or refund, each participant may send one private rating and comment to operations.

Businesses do not require identity verification. Creators prove control of a social account by placing their generated Viral Place code in the linked profile until an admin approves it.

Both account types must provide an international phone number before campaign selection. Numbers are private to operations and self-confirmed by the user. Admin authentication is isolated to its own portal and requires a password plus a separately configured operations access code. All browser forms use CSRF tokens, login failures are throttled in the shared database, sensitive HTML responses are not cached, and operations state changes are written to the audit log.

## Deployment

`api/index.py` exposes the WSGI app for Vercel. Production requires persistent PostgreSQL; SQLite is intended only for local development. Database tables and the configured admin are bootstrapped idempotently at application startup.
