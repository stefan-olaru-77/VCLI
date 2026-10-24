# Repository Guidelines

## Project Structure & Module Organization

This repository is a Python 3.10+ terminal editor built with `prompt_toolkit`
and Pygments. Application code lives in `src/vcli/`; UI components are under
`src/vcli/ui/`. Keep reusable text transformations and file handling in their
focused modules (`actions.py`, `search.py`, `fileio.py`) rather than coupling
them to the terminal UI. Tests are in `tests/`, with shared fixtures in
`tests/conftest.py`. `run.py` supports running directly from a checkout;
`pyproject.toml` defines the package and `vcli` console entry point.

## Build, Test, and Development Commands

Create an editable development environment and run the suite:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest
```

Run the application locally with `vcli` after installation, or use
`python run.py -w /path/to/workspace` without installing the package. Run a
focused test file while iterating, for example:
`python -m pytest tests/test_search_fuzzy.py`.

## Coding Style & Naming Conventions

Use four-space indentation, standard PEP 8 Python style, and type annotations
for new public functions and meaningful internal interfaces. Use `snake_case`
for modules, functions, and variables; `PascalCase` for classes; and `UPPER_CASE`
for constants. Preserve the existing `from __future__ import annotations`
pattern where appropriate. Keep UI behavior in UI modules and pure logic free
of `prompt_toolkit` dependencies when practical. No formatter or linter is
configured currently, so keep changes readable and consistent with nearby code.

## Testing Guidelines

Tests use pytest and are discovered from `tests/`. Name test files
`test_<area>.py` and test functions `test_<behavior>`. Cover pure operations,
file I/O edge cases, workspace behavior, configuration, and key-binding flows
when changing those areas. Run the complete suite before submitting changes;
there is no declared coverage threshold.

## Commit & Pull Request Guidelines

No repository commit history is available to establish a project-specific
message convention. Use short, imperative subjects such as `Fix regex replace`
or `Add workspace refresh tests`. Keep commits focused. Pull requests should
explain the user-visible or maintenance change, mention relevant tests and
commands run, and include terminal screenshots or reproduction details when
changing interactive UI behavior. Call out configuration, dependency, or
platform assumptions explicitly.

## Security & Configuration Tips

Do not commit personal configuration, terminal state, credentials, or generated
artifacts. Runtime settings belong in the user config path described in
`README.md`; tests should use temporary directories and fixtures rather than
real user workspaces.
