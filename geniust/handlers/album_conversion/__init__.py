from pathlib import Path
import os
import sys

_root = Path(os.path.realpath(__file__)).parent.parent.parent
sys.path.insert(0, str(_root))
