# Contributing / Local Checks

## One-time setup
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # if present
pip install pre-commit
pre-commit install
```

## Running checks
```bash
# Run all pre-commit hooks against the whole repo
pre-commit run --all-files

# Or run individually
flake8 .
mypy . --install-types --non-interactive
```

## CI policy
- Flake8 max line length: **120**
- E203/W503 ignored for compatibility with modern formatters
- mypy is configured to be lenient (`ignore_missing_imports = True`) while the codebase iterates
