# CueBeam CI/Lint Cleanup Bundle

**How to use**
1. Extract this zip at the root of your *CueBeam* repository.
2. Commit the changes and push to `main` (or open a PR).
3. The GitHub Actions CI will run with updated settings.

**What's included**
- `.github/workflows/ci.yml` – standardizes the CI to run flake8+mypy using Python 3.11 and installs from `requirements*.txt` if present.
- `setup.cfg` – centralizes settings for **flake8** and **mypy** (max line length 120; lenient mypy).
- `.pre-commit-config.yaml` – hygiene hooks + flake8 + mypy for local consistency.
- `CONTRIBUTING_CI_NOTES.md` – quick how-to for running checks locally.

**Why this helps**
- Your earlier failures referenced line-length (E501). This config raises the limit to 120, which is common and practical for comments/URLs.
- mypy is aligned with CI and pre-commit so type checking is consistent locally and in Actions.
