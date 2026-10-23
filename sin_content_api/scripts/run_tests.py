# Script chay toan bo bo test offline cua SIN Content Intelligence API
import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if __name__ == "__main__":
    print("=== CHAY BO TEST KIEM THU TOAN DIEN PHA P01 ===")
    test_dir = os.path.join(os.path.dirname(__file__), "..", "tests")
    exit_code = pytest.main(["-v", test_dir])
    sys.exit(exit_code)
