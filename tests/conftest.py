import sys
from pathlib import Path

# Keep the repo runnable without installation during hackathon iteration.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
