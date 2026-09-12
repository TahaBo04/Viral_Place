# Briefvora

An independent marketplace for brands and creators. Public, private, and managed briefs lead to individually priced offers. Creator acceptance creates an order; operations confirms the bank transfer before production starts, reviews content, and records payouts.

Briefvora has no affiliation with Viral Talent. `briefvora.com` was reported available by Vercel's registrar on 11 September 2026. Availability is not a reservation or registration. The GitHub repository retains its existing name to preserve its URL and history.

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. Local development uses the existing `viral_place.db` filename for data compatibility. `.env.local` is not automatically loaded into the app. For persistent local sessions, set a random `SECRET_KEY` in `.env`; otherwise a temporary random key is generated on startup.

Optional demo data: `BRIEFVORA_DEMO=1 python app.py`. Existing local demo logins remain `brand@viralplace.local`, `lina@viralplace.local`, and `samir@viralplace.local`, with password `viralplace123`. Demo seeding is forbidden in production. Never point a production deployment at a database containing these demo accounts.

## Bank transfers

Set `COMPANY_RIB` (24 digits), `COMPANY_BANK_NAME`, `COMPANY_ACCOUNT_HOLDER`, and `COMPANY_BANK_CURRENCY` on the server after confirming the actual company details. Until the account details are configured, buyers see that bank details are pending and are asked not to send funds. No sample RIB is shown on the real site. Bank currency is MAD on the live deployment.

New creator rates and campaign budgets use `MARKETPLACE_CURRENCY=mad`. Currency is stored on each rate, campaign, offer, and order; amounts use integer minor units. Accepted orders show the exact MAD amount and their `BRIEFVORA-<order id>` reference. Existing USD records remain USD, with no numerical conversion or relabeling. Cross-currency offers and transfers are blocked for operations review. Only the buyer sees the RIB in the order. There are no card fields, uploads of bank statements, payment SDKs, or payment webhooks. Operations records received transfers and completed refunds with bank transaction references; the application does not initiate transfers or refunds.

Buyers can copy the RIB/reference, download server-generated instructions, and report sending their transfer with one click. Reporting alerts operations once per order and adds an unverified timeline event; it never changes the amount or marks an order paid. Operations verifies the actual bank receipt and records its transaction reference. Confirmation then automatically notifies the buyer and creator and unlocks production. No bank API is connected, so receipt detection, currency settlement, and reconciliation are not automatic.

## Hosting on Render

Live site: https://briefvora.onrender.com. The service was deployed on 12 September 2026 with its compute plan explicitly verified as `free`, using the existing Neon database. No Render database, persistent disk, paid compute instance, or domain was purchased.

The current service uses manual deployments to avoid unexpected builds. Deploy the latest passing GitHub commit from [the service dashboard](https://dashboard.render.com/web/srv-daijrumk1f9s738gksog). The blueprint below is for creating a separate service, not updating the existing one.

[Deploy the configured free service](https://dashboard.render.com/blueprint/new?repo=https://github.com/TahaBo04/Viral_Place)

`render.yaml` creates a free Python web service with a generated session secret, HTTPS through Render, health checks, and GitHub deployments after checks pass. Connect an existing persistent PostgreSQL database via `DATABASE_URL`. Render's free PostgreSQL expires after 30 days, so it is deliberately not provisioned by this blueprint.

Set `ADMIN_EMAIL`, `ADMIN_PASSWORD`, and a different `ADMIN_ACCESS_CODE` in Render's environment settings. Both admin credentials require at least 16 characters. Admins sign in at `/auth/login/admin`. Do not put secrets in GitHub or share them in chat. The separate access code is an additional shared secret, not time-based MFA.

The live deployment preserves the database's existing administrator account. Its additional `ADMIN_ACCESS_CODE` was generated securely and stored in Render's environment settings; retrieve it there privately. The supplied RIB, bank name, and account holder are stored in private environment configuration, not source control. Transfer instructions are enabled for accepted MAD orders. The app cannot independently verify account ownership or receipt of funds.

Render automatically supplies `RENDER_EXTERNAL_HOSTNAME`. Add purchased custom domains through `TRUSTED_HOSTS` (comma-separated exact hostnames) and the Render dashboard. Do not enable proxy trust on a directly exposed server: the current configuration assumes Render/Vercel is the only public entry point.

Free Render web services sleep after 15 minutes of inactivity and can take about a minute to wake. The 750 monthly free instance hours are shared by all free web services in the workspace. This is a starting option with usage limits, not an uptime guarantee. A free compute plan is not a hard zero-cost cap: bandwidth and build overages can be billed when a payment method is attached. Set the build-pipeline spend limit to zero in Render's billing settings and monitor workspace bandwidth; a build limit does not cap bandwidth charges. Workspace billing limits were not changed by this deployment. No paid plan or domain purchase is performed by this repository. Vercel's free Hobby plan is restricted to non-commercial use.

References: [Render free hosting](https://render.com/docs/free), [Render blueprints](https://render.com/docs/blueprint-spec), [Vercel Hobby](https://vercel.com/docs/plans/hobby).

## Verification

```bash
python -m unittest discover -s tests -v
bandit -r app.py config.py wsgi.py routes services models -x services/demo_seed.py
pip-audit -r requirements.txt
```

CI runs the tests, code security scan, and dependency vulnerability audit. Tests cover role and private-campaign access, forged payment attempts, RIB visibility, admin confirmation, unsafe links, HTML escaping, request limits, duplicate inputs, login abuse, and production configuration. See [SECURITY.md](SECURITY.md) for scope and operational requirements.

Visual assets: the original Briefvora mark; menu, copy, and download icons from [Lucide](https://lucide.dev/license); creator photograph from [Unsplash's image CDN](https://images.unsplash.com/photo-1492691527719-9d1e07e534b4). Legacy image files remain unreferenced for repository compatibility.
