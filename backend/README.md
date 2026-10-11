# Backend

FastAPI service for Document Assistant. Python 3.12+ and [uv](https://docs.astral.sh/uv/) required.

## Setup

```bash
cd backend
cp .env.example .env   # fill in real values
uv sync
```

Env vars are loaded by `app/config.py`. Do not call `os.getenv` or `load_dotenv` in app code.

## Run

```bash
uv run uvicorn app.main:app --reload
```

Or: `uv run python app/main.py`

- API: http://127.0.0.1:8000
- Health: http://127.0.0.1:8000/health
- Docs: http://127.0.0.1:8000/docs

## Dependencies

```bash
uv add <package>           # runtime
uv add --dev <package>     # test / lint
uv sync                    # install from lockfile
```

More setup and migration notes: [docs/guides/backend-setup.md](../docs/guides/backend-setup.md).
