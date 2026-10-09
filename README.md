# Class Checker

Classroom attendance web application. Monorepo layout:

- `frontend/` — Next.js (App Router, React, TypeScript, Tailwind CSS)
- `backend/` — FastAPI (owns all business logic)
- `docs/` — local documentation (excluded from version control)

## Database (PostgreSQL 16 via Docker Compose)

1. Create your local environment file:

   ```bash
   cp .env.example .env
   ```

   Set `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` in `.env`.

2. Start the database:

   ```bash
   docker compose up -d db
   ```

3. Check status and readiness:

   ```bash
   docker compose ps
   docker compose exec db pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"
   ```

4. Stop the database (data is preserved in the `class_checker_pgdata` volume):

   ```bash
   docker compose down
   ```

   To also remove stored data: `docker compose down -v`.

The backend connects with:

```text
postgresql+psycopg://<POSTGRES_USER>:<POSTGRES_PASSWORD>@localhost:<POSTGRES_PORT>/<POSTGRES_DB>
```
