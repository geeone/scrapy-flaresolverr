# Contributing

Contributions are welcome.

## Development setup

Create and activate a virtual environment:

```bash
python -m venv .venv
```

On Linux or macOS:

```bash
source .venv/bin/activate
```

On Windows:

```powershell
.venv\Scripts\Activate.ps1
```

Install the development dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

## Checks

Run the test suite:

```bash
pytest --cov=scrapy_flaresolverr --cov-report=term-missing tests/
```

Run the configured pre-commit checks:

```bash
pre-commit run --all-files
```

Additional checks can be run directly:

```bash
ruff check .
ruff format --check .
mypy scrapy_flaresolverr
python -m build
```

## Pull requests

- Keep changes focused.
- Add or update tests for behavioral changes.
- Update documentation when configuration or public behavior changes.
- Keep backward compatibility in mind for supported Python and Scrapy versions.
- Do not include credentials, private target details, or client-specific code.
