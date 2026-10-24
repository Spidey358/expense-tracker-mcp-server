# Expense Tracker MCP Server

This FastMCP server stores expenses in PostgreSQL using Psycopg 3.

For Horizon, use `src/expense_tracker_mcp_server/main.py:mcp` as the entrypoint and
configure either a connection URL or these environment variables:

- `DATABASE_URL` (or `DB_URL`) with the PostgreSQL connection URL from your provider; or
- `DB_HOST`, `DB_PORT` (default: `5432`), `DB_NAME`, `DB_USER`, and `DB_PASSWORD`
- `DB_SSLMODE` (defaults to `require`) and, if your provider requires a custom CA,
  `DB_SSLROOTCERT`

For a local PostgreSQL container, `docker compose up -d` starts PostgreSQL on port 5432.
Set `DB_SSLMODE=disable` for that local connection only. Keep credentials in Horizon's
secret/environment settings, not in the repository.