# Mini Ticket Tracker

A small full-stack ticket tracker with a Django REST API, PostgreSQL database, and separate React interface. It supports authenticated sign-in, creating and filtering tickets, changing status and priority, and seeing counts by status.

## Run with Docker Compose

Install Docker Desktop, start it, then run from this directory:

```sh
cp .env.example .env
docker compose up --build
```

Open [http://localhost:5173](http://localhost:5173). The API is available at [http://localhost:8000](http://localhost:8000). Compose starts PostgreSQL, applies Django migrations, and serves the React development UI. The root `.env` configures Compose and Django; `web/.env` is only needed when running Vite directly. Stop the services with `Ctrl+C`; use `docker compose down -v` only when you also want to delete the local database volume.

Create an account before signing in:

```sh
docker compose exec api python manage.py createsuperuser
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

The React login form authenticates with Django REST Framework Simple JWT. There is no public registration endpoint; create accounts with Django's `createsuperuser` command or another administrator-managed user workflow. The board includes status navigation, a sliding sidebar, board/list views, and a global search across ticket titles and descriptions.

- `POST /auth/token` accepts `username` and `password`, returns a short-lived access token, and sets the refresh token in an HttpOnly cookie.
- `POST /auth/token/refresh` reads the refresh cookie and returns a new access token.
- `GET /auth/me` returns the signed-in account.
- `POST /auth/logout` blacklists the refresh token and clears its cookie.

Ticket and statistics endpoints require `Authorization: Bearer <access-token>`. Access tokens last 10 minutes; refresh cookies last one day. For production, configure `DJANGO_DEBUG=false`, a unique `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, and database credentials in the deployment environment. Never deploy the example secret or commit a real `.env` file. The refresh cookie is marked Secure when debug mode is off and expects the frontend and API to share an origin or use a same-origin `/api` proxy. JWT lifetimes and the refresh cookie name can also be configured with the variables listed in `.env.example`.

## Roles and permissions

Ticket access uses Django Groups and model permissions. Migration `0002_seed_ticket_roles` creates three groups and assigns their permissions:

| Role | View tickets | Create tickets | Update status/priority | Delete permission |
| --- | --- | --- | --- | --- |
| Admin | Yes | Yes | Yes | Yes |
| Agent | Yes | Yes | Yes | No |
| Viewer | Yes | No | No | No |

The API checks permissions on every request, so hiding controls in the UI is not the security boundary. Users without a role have no ticket access; Django superusers receive Admin access. `/auth/me` returns the user's role and effective ticket permissions, and the UI hides ticket creation and editing controls for Viewers.

Assign a role after creating the account (and running migrations):

```sh
cd api
python manage.py assign_role <username> --role Agent
```

Use `Admin`, `Agent`, or `Viewer` for `--role`. Assigning a role replaces the user's existing group memberships.

## API

- `POST /tickets` creates a ticket. `title` is required; `description` and `priority` are optional. New tickets start as `open`.
- `GET /tickets?page=1&limit=20&status=open&search=printer` lists tickets in newest-first order. The status and search filters are optional; search matches ticket titles and descriptions. The response includes `tickets`, `page`, `limit`, and `total`.
- `PATCH /tickets/:id` updates `status`, `priority`, or both.
- `GET /tickets/stats` returns counts for `open`, `in_progress`, and `closed`.
- `GET /health` checks that the API can reach the database.

Statuses are `open`, `in_progress`, and `closed`. Priorities are `low`, `medium`, and `high`.

## Checks

Run the API tests with `cd api && python manage.py test`, the frontend interaction tests with `cd web && npm test`, and check the React production build with `cd web && npm run build`.

## GitHub Actions and Vercel deployment

The workflow in `.github/workflows/ci-cd.yml` runs Django checks and API tests against PostgreSQL, then runs the frontend tests and production build. It runs on pull requests and pushes. Same-repository pull requests create frontend previews, and pushes to `main` deploy the frontend to production. Pull requests from forks still run CI, but do not receive deployment credentials.

Before deployments can run:

1. The React frontend Vercel project uses root directory `web` and is already created. Its first deployment is available at [mini-ticket-tracker-two.vercel.app](https://mini-ticket-tracker-two.vercel.app).
2. The Django API remains local for now. The hosted frontend is therefore for UI preview only; its login and ticket operations need the API. Continue using the local Vite + Django setup for functional testing until the API is deployed or otherwise made reachable.
3. A free-tier Neon Postgres database named `mini-ticket-tracker-dev` is provisioned in Frankfurt and connected to the Vercel project's Development environment only. It is limited to 1 GB storage and 100 compute-hours per project; keep it for development data. To use it locally, install and authenticate the Vercel CLI, then from `web/` link the `mini-ticket-tracker` project and run `vercel env run -e development -- python3 ../api/manage.py migrate` followed by `vercel env run -e development -- python3 ../api/manage.py runserver`. This makes Django use the connected `DATABASE_URL` without copying it into the repository.
4. GitHub Actions is configured with the Vercel team and project IDs, a team-scoped `VERCEL_TOKEN` secret, and `ENABLE_VERCEL_DEPLOY=true`. The token expires in 90 days; rotate it in Vercel and update the GitHub secret before then. The project ID belongs to the `web` root project.
5. The Vercel project is also connected to GitHub, so its built-in Git deployments may run alongside GitHub Actions deployments.

The deployment jobs use the Vercel CLI to publish the frontend after CI succeeds; Vercel performs the remote build using the project's `web` root directory. Vercel project metadata is ignored by Git. When the API later moves to a hosted runtime, add its project ID, API environment variables, migration handling, and a frontend `/api/*` rewrite before enabling full-stack deployment.

## Decisions & Tradeoffs

The API and UI live in one repository but run as separate applications, keeping each layer straightforward to work on. PostgreSQL stores tickets, and Django migrations track schema changes. The API validates ticket input and returns pagination metadata so the UI can show queue pages and totals. Offset pagination is a simple fit for a small support queue, though cursor pagination would scale better for a much larger one. Backend hosting and account administration beyond Django's management command remain to be set up. A fully automated end-to-end browser suite and structured logging would be useful next steps.
