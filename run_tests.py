import pytest
import sys

if __name__ == "__main__":
    # run pytest and print to stdout
    ret = pytest.main(["tests/test_deployment_logic.py", "-v"])
    sys.exit(ret)
