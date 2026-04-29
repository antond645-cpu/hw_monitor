# Contributing

Pull requests welcome. A few pointers:

**Setup:** fork, branch off `main`, copy `.env.example` → `.env`, then `docker compose up -d --build`. Logs with `docker compose logs -f`, tear down with `docker compose down`.

**PRs:** keep them small and scoped. If behaviour or knobs change, update `README.md`, `CHANGELOG.md` under `Unreleased`, and `.env.example`. New env vars should also touch `unraid/hw-monitor.xml` when installers need them.

Don’t commit real secrets—local `.env` stays untracked.

**Commits:** use whatever reads clearly; conventional prefixes (`feat:`, `fix:`, `docs:`) help but aren’t mandatory.

**Before merge:** app boots, login works, `/healthz` is 200, JSON APIs respond, `docker build .` succeeds.
