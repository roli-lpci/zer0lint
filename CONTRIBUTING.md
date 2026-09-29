# Contributing

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Checks

```bash
ruff check zer0lint tests --ignore E501
pytest -q
python -m py_compile zer0lint/*.py
```

## Contribution rules

- keep the tool focused on fact-survival checks and Mem0 extraction-prompt comparison
- add tests for new CLI flags or diagnostic behavior
- avoid examples that depend on private configs, prompts, or memory data
