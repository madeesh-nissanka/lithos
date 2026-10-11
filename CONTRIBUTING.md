# Contributing to LITHOS

Thanks for your interest in improving LITHOS. This project follows a small,
explicit set of conventions.

## Ground rules

- **Core is dependency-light.** The package under `src/lithos/` must run on the
  Python standard library alone (Python 3.10+). Optional behaviour (XLSX without
  `openpyxl`, matplotlib plots, DOCX reports, YAML config) is detected at runtime
  and degrades gracefully. Any new third-party import must be optional.
- **No network in tests.** Unit tests must never call live APIs. Patch
  `lithos.http.HTTPClient` with synthetic payloads (see `tests/testhelpers.py`).
- **Synthetic fixtures only.** Do not commit real bibliographic dumps or private
  data. Use textbook-level topics and reserved fake DOIs (`10.9999/...`).
- **Keep the license and attribution headers.** Every source file starts with the
  MIT copyright line; do not remove it.

## Development setup

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[all]"   # optional extras; core needs nothing
```

## Running the tests

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Style

- Type hints on public functions and classes.
- Standard library logging via `logging.getLogger(__name__)`.
- Keep CLI flags backward compatible within a major series.

## Pull requests

1. Add or update tests for any behaviour change.
2. Run the full test suite and paste the real output in the PR description.
3. Keep commits focused; describe *why* in the message.

## Reporting issues

Include your Python version, the exact command, and the observed versus expected
output. Never paste API keys or personal data.
