# Mini Ticket Tracker

A small full-stack ticket tracker with a Django REST API, PostgreSQL database, and separate React interface. It supports authenticated sign-in, creating and filtering tickets, changing status and priority, and seeing counts by status.

**Links:** [GitHub repository](https://github.com/sartim/mini-ticket-tracker) · [Live UI preview](https://mini-ticket-tracker-two.vercel.app/)

## Run with Docker Compose

Install Docker Desktop, start it, then run from this directory:

```sh
cp .env.example .env
docker compose up --build
```

Open [http://localhost:5173](http://localhost:5173). The API is available at [http://localhost:8000](http://localhost:8000). Compose starts PostgreSQL, applies Django migrations, and serves the React development UI. The root `.env` configures Compose and Django; `web/.env` is only needed when running Vite directly. Stop the services with `Ctrl+C`; use `docker compose down -v` only when you also want to delete the local database volume.

### Live demo login

The public demo uses a shared Agent account. Anyone can sign in and change the shared demo tickets, so do not enter private information.

- Username: `demo`
- Password: `ticketdesk-demo-2026`

The demo account can create and update tickets, but it is not an administrator. The production deployment workflow seeds this account and example tickets after applying database migrations.

For a private local Docker setup, create your own administrator account after the containers are up:

```sh
docker compose exec api python manage.py createsuperuser
```

Enter the username and password you choose in the login form at `http://localhost:5173`. The superuser has Admin access. Seed sample tickets locally with `docker compose exec api python manage.py seed_demo_data`.

For a non-admin Agent or Viewer account, create a regular Django user, then assign its role:

```sh
docker compose exec api python manage.py shell
```

At the Django shell prompt, create the account with a password you choose:

```python
from getpass import getpass
from django.contrib.auth import get_user_model
get_user_model().objects.create_user(username="support-agent", password=getpass("Password: "))
```

Exit the shell, then assign its role (replace the username or role as needed):

```sh
docker compose exec api python manage.py assign_role support-agent --role Agent
```

Seed the database with example tickets across all statuses and priorities:

```sh
docker compose exec api python manage.py seed_demo_data
```

The command is safe to run more than once; existing demo tickets are left unchanged. For a local API, run `python manage.py seed_demo_data` from the `api` directory.

## Run without Docker

You need Python 3.10+, Node.js 20+, and PostgreSQL 16+.

1. Create a PostgreSQL database and user. Copy the starter environment file and adjust the connection string as needed:

   ```sh
   cp .env.example .env
   ```

   Django loads variables from the root `.env` file. Set `DATABASE_URL` to match your local PostgreSQL setup. Do not commit `.env`; it is ignored by Git. `.env.example` lists backend, database, and JWT settings.
2. In one terminal, install and start the API:

   ```sh
   cd api
   python3 -m venv .venv
   . .venv/bin/activate
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py runserver
   ```

3. In another terminal, install and start the UI:

   ```sh
   cd web
   cp .env.example .env
   npm install
   npm run dev
   ```

4. Open [http://localhost:5173](http://localhost:5173).

Create a login account from the API directory with `python manage.py createsuperuser`.

## Authentication

The React login form authenticates with Django REST Framework Simple JWT. There is no public registration endpoint; create accounts with Django's `createsuperuser` command or another administrator-managed user workflow. The board includes status navigation, a sliding sidebar, board/list views, and a global search across ticket titles, descriptions, and displayed ticket codes such as `TKT-0007`.

- `POST /api/v1/auth/token` accepts `username` and `password`, returns a short-lived access token and user profile, and sets the refresh token in an HttpOnly cookie.
- `POST /api/v1/auth/token/refresh` reads the refresh cookie and returns a new access token and user profile.
- `GET /api/v1/auth/me` returns the signed-in account.
- `POST /api/v1/auth/logout` blacklists the refresh token and clears its cookie.

Ticket and statistics endpoints require `Authorization: Bearer <access-token>`. Access tokens last 10 minutes; refresh cookies last one day. For production, configure `DJANGO_DEBUG=false`, a unique `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, and database credentials in the deployment environment. Never deploy the example secret or commit a real `.env` file. The refresh cookie is marked Secure when debug mode is off and expects the frontend and API to share an origin or use a same-origin `/api` proxy. JWT lifetimes and the refresh cookie name can also be configured with the variables listed in `.env.example`.

## Roles and permissions

Ticket access uses Django Groups and model permissions. Migration `0002_seed_ticket_roles` creates three groups and assigns their permissions:

| Role | View tickets | Create tickets | Update status/priority | Delete permission |
| --- | --- | --- | --- | --- |
| Admin | Yes | Yes | Yes | Yes |
| Agent | Yes | Yes | Yes | No |
| Viewer | Yes | No | No | No |

The API checks permissions on every request, so hiding controls in the UI is not the security boundary. Users without a role have no ticket access; Django superusers receive Admin access. `/api/v1/auth/me` returns the user's role and effective ticket permissions, and the UI hides ticket creation and editing controls for Viewers.

Assign a role after creating the account (and running migrations):

```sh
cd api
python manage.py assign_role <username> --role Agent
```

Use `Admin`, `Agent`, or `Viewer` for `--role`. Assigning a role replaces the user's existing group memberships.

## API

- `POST /api/v1/tickets` creates a ticket. `title` is required; `description` and `priority` are optional. New tickets start as `open`.
- `GET /api/v1/tickets?page=1&limit=20&status=open&search=printer` lists tickets in newest-first order. The status and search filters are optional; search matches ticket titles, descriptions, and displayed ticket codes. The response uses `count`, `next`, `previous`, and `results`.
- `GET /api/v1/tickets/:id` retrieves one active ticket.
- `PATCH /api/v1/tickets/:id` updates `status`, `priority`, or both. Ticket responses include `created_at`, `updated_at`, and `deleted_at` timestamps; `updated_at` changes on every edit.
- `DELETE /api/v1/tickets/:id` soft-deletes a ticket for Admin users and returns the ticket with its `deleted_at` timestamp. Deleted tickets are hidden from normal list, detail, search, and stats queries. They remain available through the model's `all_objects` manager for audit or recovery.
- `GET /api/v1/tickets/stats` returns counts for `open`, `in_progress`, and `closed`.
- `GET /api/v1/health` checks that the API can reach the database.

Successful login and refresh responses include the authenticated user and structured role/permission objects:

```json
{
  "access": "<access-token>",
  "user": {
    "id": 12,
    "username": "support-agent",
    "role": "Agent",
    "roles": [{ "name": "Agent" }],
    "permissions": [
      { "code": "tickets.view_ticket", "name": "Can view ticket" },
      { "code": "tickets.add_ticket", "name": "Can add ticket" }
    ]
  }
}
```

List responses use standard page-number pagination. `next` and `previous` are absolute URLs or `null` when there is no adjacent page:

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 42,
      "title": "Printer queue is delayed",
      "description": "The front office printer is not responding.",
      "status": "open",
      "priority": "medium",
      "created_at": "2026-10-12T08:00:00Z",
      "updated_at": "2026-10-12T08:00:00Z",
      "deleted_at": null
    }
  ]
}
```

API errors use one top-level `error` field. Validation errors place field messages inside it:

```json
{ "error": { "title": ["This field may not be blank."] } }
```

The API is versioned under `/api/v1/`. Its Python package metadata in `api/pyproject.toml` is the version source of truth. The `v1.0.0` tag marks the baseline release. After tests and the production deployment pass on `main`, Python Semantic Release reads Conventional Commit messages, updates the Python version, commits the change, creates a `vMAJOR.MINOR.PATCH` tag, and publishes a GitHub Release. Use `fix:` for a patch, `feat:` for a minor release, and `feat!:` or `BREAKING CHANGE:` for a major release. Commits without a release type do not create a release. Releases are GitHub repository releases; this app is not published to PyPI.

Statuses are `open`, `in_progress`, and `closed`. Priorities are `low`, `medium`, and `high`.

## Checks

Run the API unit tests locally without PostgreSQL with `cd api && python manage.py test --settings=config.test_settings`. The test settings use SQLite; CI separately runs the backend suite against PostgreSQL. Run the frontend interaction tests with `cd web && npm test`, and check the React production build with `cd web && npm run build`.

## GitHub Actions and Vercel deployment

The workflow in `.github/workflows/ci-cd.yml` runs Django checks and API tests against PostgreSQL, then runs the frontend tests and production build. Pull requests run these checks without deployment credentials. Pushes to `main` deploy the API and frontend to production and then publish a semantic release when the commit messages call for one.

Deployment details:

1. The Vercel project at [mini-ticket-tracker-two.vercel.app](https://mini-ticket-tracker-two.vercel.app) deploys both services from this repository. The root `vercel.json` routes `/api/*` to Django in `api/` and other paths to React in `web/`, on the same origin.
2. The Vercel project builds from the repository root. Its Neon Postgres `mini-ticket-tracker-prod` resource uses the free plan, with deployment branches for Production and Preview. The existing `mini-ticket-tracker-dev` database remains available for development.
3. Vercel stores the runtime `DATABASE_URL`, a generated `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`, and `DJANGO_ALLOWED_HOSTS=.vercel.app`. GitHub Actions uses separately encrypted copies of the database URL and Django key only for running production migrations and seeds; no secrets belong in the repository.
4. GitHub Actions uses the repository variables `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, and `ENABLE_VERCEL_DEPLOY=true`, plus the team-scoped `VERCEL_TOKEN` secret. The protected `Production` GitHub Actions environment also needs `PRODUCTION_DATABASE_URL` (the Neon unpooled connection string) and `PRODUCTION_DJANGO_SECRET_KEY` so its migration and seed commands can connect without downloading Vercel's protected Secret values. Rotate the Vercel token before its 90-day expiry.
5. Pull requests run CI checks. Pushes to `main` run CI, migrate Production, seed the demo tickets and shared Agent account, then deploy both services.

The demo login listed above is seeded on Production by the deployment workflow. The seed command resets that shared account to the documented demo password on every production deployment; never use this account for private data. The runtime keeps its connection string and Django secret in Vercel; GitHub Actions keeps separate encrypted copies only for running Production migrations and seeds.

## Decisions & Tradeoffs

The API and UI live in one repository and deploy as separate Vercel Services under one project and domain. PostgreSQL stores tickets, and Django migrations track schema changes. The API validates ticket input and returns pagination metadata so the UI can show queue pages and totals. Offset pagination is a simple fit for a small support queue, though cursor pagination would scale better for a much larger one. A fully automated end-to-end browser suite and structured logging would be useful next steps.
