# agentic_chatbot

## Database setup (PostgreSQL)

Backend chat history URL is resolved in this order:

1. `APP_DATABASE_URL`
2. `DATABASE_URL`
3. Built from `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`

Example:

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=agentic_chatbot
```

Notes:

- `APP_DATABASE_URL`/`DATABASE_URL` can still be used as explicit override.
- Docker Compose already injects `APP_DATABASE_URL` for the backend service.
- Tables are initialized at app startup in `backend/app/core/database.py` via `init_app_database()`.
