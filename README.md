# Viral Place

Viral Place is Viral Talent's managed creator marketplace. Companies can publish a brief immediately, pay Viral Place, and either request managed creator sourcing or select from creator applications. Creators are activated only after payment is confirmed, submit content for agency review, and receive their payout after approval.

## Product workflow

- Instant business signup with no company identity approval queue.
- Creator social-account ownership review before marketplace visibility.
- Managed campaign briefs and public marketplace campaigns.
- Deterministic creator-to-campaign match scores.
- Stripe Checkout with manual-payment support for operations.
- In-app selection, payment, revision, approval, refund, and payout notifications.
- Creator video-link submission, Viral Place quality control, and approved customer delivery.
- Operations dashboard for creator verification, assignment, payment, content review, refunds, and payouts.

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

The Vercel deployment uses PostgreSQL through `DATABASE_URL` or `POSTGRES_URL`. Configure `SECRET_KEY`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD`. Stripe checkout additionally requires `STRIPE_SECRET_KEY`; signed webhooks use `STRIPE_WEBHOOK_SECRET`.

Do not enable `VIRAL_PLACE_DEMO` in production.

## Main routes

- `/auth/register`, `/auth/register/business`, `/auth/register/influencer`
- `/auth/login`, `/auth/login/business`, `/auth/login/influencer`
- `/creators/`, `/campaigns/`, `/campaigns/new`
- `/business/dashboard`, `/influencer/dashboard`
- `/orders/<id>`, `/notifications/`
- `/admin/`
- `/payments/stripe/webhook`
