# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A proxy service that fronts xtquant / QMT (a Windows-only Chinese brokerage quant SDK) and exposes it over three transports simultaneously: **REST + WebSocket** (FastAPI/uvicorn) and **gRPC**. The same domain services back all transports — transports are thin adapters over `app/services/`.

## Commands

```cmd
:: install (Windows; mock mode needs no QMT)
pip install -r requirements.txt
pip install pytest pytest-asyncio

:: run (env vars OR start.py flags select mode + which servers)
set APP_MODE=mock & set APP_SERVERS=all & python run.py
python start.py --mode mock --servers all

:: tests — default is mock, safe without QMT
python -m pytest tests\unit -q --xt-mode=mock
python -m pytest tests\unit\test_trading_service.py -q --xt-mode=mock   :: single file
python -m pytest tests\unit\test_trading_service.py::test_name -q --xt-mode=mock  :: single test

:: lint / format (config in pyproject.toml, line length 100, double quotes)
ruff check .
ruff format .

:: regenerate protobuf after editing proto/*.proto (do NOT hand-edit generated/)
python scripts\generate_proto.py --mode generate
```

`APP_MODE` = `mock` | `dev` | `prod`. `APP_SERVERS` = `all` | `rest` | `grpc`. Live reload only works with `APP_SERVERS=rest` + `debug`.

## Modes (this is the core concept)

| Mode | xtquant | Accounts | Order placement |
| --- | --- | --- | --- |
| `mock` | not connected, fake impl | none needed | allowed (fake) |
| `dev` | real xtquant | explicitly-registered `simulated` accounts only | allowed |
| `prod` | real xtquant | explicitly-registered `real` accounts only | tests read-only; runtime gated by `enable_prod_orders` |

Account registration is enforced: a session for an unregistered account is rejected. `dev` refuses `real` accounts and vice versa. Even in `prod`, real orders from external callers require `xtquant.trading.enable_prod_orders: true`. See `is_real_trading_allowed()` in `app/dependencies.py`.

## Configuration layering

`load_config()` in `app/config.py` merges, in order: `config.yml` (repo default) → `config.local.yml` (gitignored runtime override) → a mode block under `modes:` → environment variables. Tests load `config.test.local.yml` instead of `config.local.yml`. Machine-specific values (QMT `qmt_userdata_path`, account IDs, API keys, prod unlock tokens) belong ONLY in the gitignored `*.local.yml` files, never in `config.yml`. `qmt_userdata_path` is the QMT *userdata* dir (MiniQMT → `userdata_mini`, broker QMT → `userdata`), not the install root.

## Architecture

Request flow: **transport adapter → domain service → gateway → xtquant SDK**.

- **Transports** (thin, per-transport request/response mapping only):
  - `app/routers/` — REST + WebSocket (FastAPI routers), plus `app/main.py` (app assembly, middleware, exception handlers that wrap everything in `format_response`).
  - `app/grpc_services/` + `app/grpc_server.py` — gRPC servicers and server assembly, including `ApiKeyServerInterceptor` and `RequestLoggingServerInterceptor`.
- **Domain services** (`app/services/`) — transport-agnostic business logic, shared by both transports:
  - `market_data_service.py` / `reference_data_service.py` — data queries (kline, tick, financial, sectors, L2, etc.).
  - `trading_session_manager.py` — session lifecycle, orders, positions, mode/account enforcement.
  - `xtdata_subscription_hub.py` + `ui_subscription_service.py` — streaming quote subscriptions consumed by WebSocket and gRPC streams.
  - `trading_event_hub.py` — fans out trade/order events to gRPC `StreamTradingEvents`.
  - `contracts.py` — internal command/query dataclasses (e.g. `OpenSessionCommand`, `KlineHistoryQuery`) that decouple services from transport models.
- **Gateways** (`xtdata_gateway.py`, `xttrader_gateway.py`) — the only modules that import xtquant. Each guards the import with `try/except ImportError` setting `XTQUANT_*_AVAILABLE`, so the whole app imports and runs in `mock` even where xtquant is absent (e.g. non-Windows dev). All mock/real branching lives here and in the session manager.
- **Wiring**: `app/dependencies.py` holds process-global singletons of every service, lazily built via `get_*` functions used both by FastAPI `Depends` and by `grpc_server.py`. `reset_services()` tears them down — tests call it between cases.
- **Models** (`app/models/`) — Pydantic request/response models for REST; gRPC uses `generated/` protobuf messages.

## Protobuf

`.proto` sources in `proto/` (`common`, `data`, `trading`, `health`); generated `*_pb2.py` / `*_pb2_grpc.py` / `*.pyi` are committed in `generated/` and imported as `from generated import ...`. After any `proto/` edit, rerun the generator — never edit generated files by hand.

## Tests

`pytest.ini` restricts collection to `tests/unit`. `tests/conftest.py` defines the whole test harness: custom pytest options (`--xt-mode`, `--xt-account-profile`, `--xt-enable-live-streams`, `--xt-enable-prod-tests`), builds isolated `Settings` per test via `build_test_settings`, and spins up in-process gRPC servers and FastAPI `TestClient`s. Mock is the default and must pass with no QMT present. `dev`/`prod` runs are opt-in, need `config.test.local.yml` plus real accounts, and `prod` additionally requires a matching `QMT_TEST_PROD_UNLOCK_TOKEN`; prod tests are read-only (query/subscribe/auth/reject-order only, never real orders). See `tests/README.md`.

## Conventions

- Commit messages: concise, often Chinese, conventional prefixes (`feat:`, `fix:`).
- Domain reference for xtquant signatures/lifecycle: official docs (thinktrader.net nativeApi) and the local `xtquant/` SDK source, in that order.
