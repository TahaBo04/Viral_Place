# Copilot Instructions for Viral Place

Viral Place is Viral Talent's Flask marketplace for managed creator campaigns.

## Architecture

- Keep the Flask app factory in `app.py` and extensions in `extensions.py`.
- Put models in `models/`, blueprints in `routes/`, and domain logic in `services/`.
- Roles are `business`, `influencer`, and `admin`.
- Companies receive immediate access and must not be placed in an identity-review queue.
- Creators require social-account ownership approval before discovery or campaign applications.
- Creator activation happens only after customer payment is confirmed.
- All content must pass Viral Place review before customer delivery or creator payout.
- Use PostgreSQL in production and SQLite only for local development.
- Never commit credentials, local databases, `.env` files, or `.vercel` state.
