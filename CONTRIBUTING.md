# Contributing

Thanks for contributing to HW Monitor.

## Development Setup

1. Fork the repository and clone your fork.
2. Create a feature branch from `main`.
3. Copy `.env.example` to `.env` and set local values.
4. Start with Docker:

```bash
docker compose up -d --build
```

Useful commands:

```bash
docker compose logs -f
docker compose down
```

## Pull Request Guidelines

- Keep PRs focused and small.
- Update `README.md` if behavior or configuration changes.
- Update `CHANGELOG.md` under `Unreleased`.
- Avoid committing secrets (`.env`, credentials, API keys).
- If adding a new environment variable, update:
  - `.env.example`
  - `unraid/hw-monitor.xml` (if relevant)
  - `README.md`

## Commit Message Suggestions

- `feat: ...` for new functionality
- `fix: ...` for bug fixes
- `docs: ...` for documentation
- `refactor: ...` for internal improvements
- `ci: ...` for workflow and automation changes

## Testing Checklist

- App starts successfully.
- Login works.
- `/healthz` returns 200.
- Metrics API endpoints return valid JSON.
- Docker image builds locally (`docker build .`).
