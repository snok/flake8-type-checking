"""
This file tests the TYO101 error: unused remote imports.

Some things to note: local/remote is a pretty arbitrary divide, and remote here really just means
not from the module our current working directory is in, or in the current working dir, but inside a venv.
"""
import os
import textwrap

import pytest

from flake8_typing_only_imports.constants import TYO100, TYO200
from tests import REPO_ROOT, _get_error, mod

examples = [
    # No error
    ('', set()),
    # ast.AnnAssign missing quotes
    (
        f'if TYPE_CHECKING:\n\timport something\n\nx: something\ny: int',
        {
            '4:0 ' + TYO200.format(annotation='something'),
        },
    ),
    (
        f'if TYPE_CHECKING:\n\timport something\n\ndef example(x: something, y:int) -> something:\n\tpass',
        {
            '4:0 ' + TYO200.format(annotation='something'),
            '4:12 ' + TYO200.format(annotation='something'),
        },
    ),
]


@pytest.mark.parametrize('example, expected', examples)
def test_tyo200_errors(example, expected):
    assert (
        _get_error(example) == expected
    ), f"No match for example: '{example}'. Found '{_get_error(example)}' instead of '{expected}'"
