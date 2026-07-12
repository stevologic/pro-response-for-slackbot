"""Enable ``python -m proresponse`` to invoke the CLI."""

from __future__ import annotations

from proresponse.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
