# OverWatch

ReplAi's fork of Attendee (meeting bots). It records sales and onboarding calls for the ReplAi Admin app.

Production runs on Railway, project `replai-apis`, environment `production`: services "OverWatch" (API), "OverWatch Worker" (`celery -A attendee worker --concurrency 4`, runs the bots) and "OverWatch Scheduler" (`python manage.py run_scheduler`). A push to `main` auto-deploys the services to production (Oct 24 2026: a version bump went live 3 seconds after the push). Work on a branch and open a PR.

## Running tests locally

Start Docker, then:

```bash
docker compose -f dev.docker-compose.yaml up -d postgres redis
```

The test settings log in as `attendee_test_user`, which the dev Postgres does not have. Create it once (local container only):

```bash
docker compose -f dev.docker-compose.yaml exec -T postgres psql -U attendee_development_user -d attendee_development -c "CREATE ROLE attendee_test_user LOGIN SUPERUSER PASSWORD 'attendee_test_user';"
```

Migrations need a Fernet key, so pass a throwaway one:

```bash
docker compose -f dev.docker-compose.yaml run --rm --no-deps -e DJANGO_SETTINGS_MODULE=attendee.settings.test -e CREDENTIALS_ENCRYPTION_KEY=$(python3 -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())") -e DJANGO_SECRET_KEY=localtest attendee-app-local python manage.py test bots --noinput
```

## Invariants

1. A `run_bot` task must always end once its bot is in a post-meeting state, and must have a hard Celery `time_limit` below the broker `visibility_timeout`. Oct 22-24 2026: two runs whose bots had ended never returned, held the worker's slots, and no bot launched for two days.
