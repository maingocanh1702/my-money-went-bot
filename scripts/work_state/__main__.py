"""Allow `python -m scripts.work_state.engine` invocation."""

from __future__ import annotations

import sys

from scripts.work_state.engine import main

sys.exit(main())
