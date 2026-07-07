# Viral Place

Viral Place is Viral Talent's managed creator marketplace. Companies publish public, private, or managed briefs and send independently priced offers to creators. A creator must accept the exact offer before an order can be created or paid; Viral Place then secures the funds, reviews delivery, and releases the creator payout after approval.

## Product workflow

- Instant business signup with no company identity approval queue.
- Creator social-account ownership review before marketplace visibility.
- Public marketplace, private invite-only, and private managed campaigns.
- Structured creator social accounts with safe HTTPS links and per-platform audience counts.
- Accepted-offer checkout: creators see the gross price and estimated 70% payout before responding.
- Multiple independently priced creator orders under one campaign.
- Deterministic creator-to-campaign match scores.
- Stripe Checkout with manual-payment support for operations, both blocked until offer acceptance.
- In-app selection, payment, revision, approval, refund, and payout notifications.
- Creator video-link submission, Viral Place quality control, and approved customer delivery.
- Operations dashboard for creator verification, assignment, payment, content review, refunds, and payouts.
- Private, self-confirmed international phone contacts for brands and influencers.
- One private post-deal review per party after completion or refund.
- CSRF-protected forms, throttled login attempts, hardened response headers, and a separate operations access code.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
VIRAL_PLACE_DEMO=1 python app.py
```

Open `http://127.0.0.1:5000`.

Demo users use the password `viralplace123`:

- Business: `brand@viralplace.local`
- Creator: `lina@viralplace.local`
- Creator: `samir@viralplace.local`

## Production configuration

The Vercel deployment uses PostgreSQL through `DATABASE_URL` or `POSTGRES_URL`. Configure `SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, and a distinct `ADMIN_ACCESS_CODE`. Admin accounts can sign in only at `/auth/login/admin` with both the password and access code. Stripe checkout additionally requires `STRIPE_SECRET_KEY`; signed webhooks use `STRIPE_WEBHOOK_SECRET`.

Phone numbers are selected from a worldwide calling-code catalog, validated by region, normalized to E.164, and shown only to Viral Place operations. The confirmation checkbox is a user attestation, not carrier-level SMS verification. Add an SMS provider before treating numbers as technically verified.

Creator profile-picture and social-profile URLs must use safe public HTTPS hosts. Influencers must retain at least one supported social account with an audience count. Campaign offers are whole-dollar USD values from the creator's published minimum through `MAX_OFFER_USD` (default `$1,000,000`).

Do not enable `VIRAL_PLACE_DEMO` in production.

## Main routes

- `/auth/register`, `/auth/register/business`, `/auth/register/influencer`
- `/auth/login`, `/auth/login/business`, `/auth/login/influencer`
- `/creators/`, `/campaigns/`, `/campaigns/new`
- `/campaigns/<id>/close`, `/offers/<id>/accept`, `/offers/<id>/decline`
- `/business/dashboard`, `/influencer/dashboard`
- `/orders/<id>`, `/orders/<id>/review`, `/notifications/`
- `/admin/`, `/admin/contacts`, `/auth/login/admin`
- `/payments/stripe/webhook`
