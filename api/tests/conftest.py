import os
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="bomerang_test_")
os.environ["BOMERANG_DATA_DIR"] = _tmp
os.environ.pop("ANTHROPIC_API_KEY", None)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
