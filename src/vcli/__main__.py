"""Allow ``python -m vcli`` to start the editor."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
