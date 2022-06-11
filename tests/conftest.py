import os

import pytest

from . import REPO_ROOT


@pytest.fixture(autouse=True)
def change_test_dir():
    os.chdir(REPO_ROOT / 'flake8_type_checking')
    yield
    os.chdir(REPO_ROOT)
