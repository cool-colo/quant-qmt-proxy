# Repository Guidelines

## Project Structure & Module Organization

This is a Python 3.10+ FastAPI, WebSocket, and gRPC proxy for xtquant/QMT.
Application code lives in `app/`: `routers/` exposes REST and WebSocket endpoints,
`grpc_services/` implements gRPC handlers, `services/` contains domain logic, and
`models/` contains Pydantic request/response models. Protobuf definitions are in
`proto/`; generated `*_pb2.py`, `*_pb2_grpc.py`, and `*.pyi` files are committed in
`generated/`. Tests are maintained in `tests/unit`, with shared fixtures in
`tests/conftest.py`. Runtime configuration examples are `config.local.example.yml`,
`config.test.local.example.yml`, and `env.example`.

## Build, Test, and Development Commands

- `pip install -r requirements.txt`: install runtime dependencies.
- `pip install pytest pytest-asyncio`: install test dependencies when not using Poetry.
- `python start.py --mode mock --servers all`: start REST/WebSocket and gRPC locally
  without QMT.
- `python run.py`: start using environment/config values such as `APP_MODE` and
  `APP_SERVERS`.
- `python -m pytest tests/unit -q --xt-mode=mock`: run the default local-safe tests.
- `python scripts/generate_proto.py --mode generate`: regenerate code after editing
  `proto/*.proto`.
- `ruff check .` and `ruff format .`: lint and format according to `pyproject.toml`.

## Coding Style & Naming Conventions

Use four-space indentation, double quotes, and a 100-character line target. Follow
existing type-hinted Python style and keep service, router, and model responsibilities
separate. Name tests `test_*.py` and test functions `test_*`. Do not hand-edit generated
protobuf files; update `proto/` definitions and rerun the generator.

## Testing Guidelines

Pytest is configured by `pytest.ini` to collect `tests/unit` only. Mock mode is the
default and should pass without local QMT. Real xtquant validation is opt-in: copy
`config.test.local.example.yml` to `config.test.local.yml`, register accounts, then use
options such as `--xt-mode=dev --xt-account-profile=sim-dev --xt-enable-live-streams`.
Production tests are read-only and require the explicit unlock settings documented in
`tests/README.md`.

## Commit & Pull Request Guidelines

Recent history uses concise Chinese descriptions and conventional prefixes such as
`feat:` and `fix:`. Keep commits focused, for example `feat: add market data stream`
or `fix: handle grpc auth failure`. Pull requests should describe behavior changes,
list tests run, note any config/protobuf changes, and include screenshots only for
documentation or UI-visible updates.

## Security & Configuration Tips

Keep machine-specific QMT paths, account IDs, tokens, and prod unlock values out of
tracked files. Use local override files (`config.local.yml`, `config.test.local.yml`)
and environment variables instead. In `prod`, real order placement must remain gated by
`xtquant.trading.enable_prod_orders`.
