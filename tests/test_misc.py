import os
import subprocess
from pathlib import Path

# def test_run_mypy_module():
#    """Runs mypy on all module sources
#
#    from https://gist.github.com/bbarker/4ddf4a1c58ae8465f3d37b6f2234a421
#    """
#    mypy_call: str = "mypy -p geniust --config-file tests/mypy.ini"
#    pypath: str = os.environ.get(
#        "PYTHONPATH",
#        Path(os.path.realpath(__file__)).parent.parent
#    )
#
#    result: int = subprocess.call(mypy_call, cwd=pypath)
#    assert result == 0, 'mypy on geniust failed'
