"""StudioBridge CLI module execution entry point (python -m studiobridge.cli)."""

from __future__ import annotations

import sys

from studiobridge.cli import main

if __name__ == "__main__":
    sys.exit(main())
