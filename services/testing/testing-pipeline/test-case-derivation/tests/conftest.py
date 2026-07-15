"""Put the stage's flat module dir on sys.path so `import direct_planner` etc.
work under pytest (mirrors how services/testing/main.py imports the stage)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
