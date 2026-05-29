"""Allow `python -m work_state` invocation from tools/dashboard-engine/."""

from __future__ import annotations

import sys

from work_state.engine import main

sys.exit(main())
