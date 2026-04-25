# Contributing

Thanks for considering a contribution.

## Development Setup

1. Fork the repository and clone your fork.
2. Create a feature branch from `main`.
3. Copy `.env.example` to `.env` and set local values.
4. Start via Docker:

```bash
docker compose up -d --build
```

## Pull Request Guidelines

- Keep PRs focused and small.
- Update `README.md` if behavior or config changed.
- Update `CHANGELOG.md` under `Unreleased`.
- Avoid committing secrets (`.env`, credentials, API keys).

## Commit Message Suggestions

- `feat: add ...` for new functionality
- `fix: correct ...` for bug fixes
- `docs: update ...` for documentation updates
- `refactor: improve ...` for internal code improvements

## Testing Checklist

- App starts successfully.
- Login works.
- `/healthz` returns 200.
- Metrics API endpoints return valid JSON.
- Docker image builds locally.
