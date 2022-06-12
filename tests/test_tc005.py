"""
This file tests the TC005 error:

    >> Empty type-checking block

Sometimes auto-formatting tools for removing redundant imports (i.e. Pycharms)
will leave behind empty type-checking blocks. This just flags them as redundant.
"""
import textwrap

import pytest

from flake8_type_checking.constants import TC005
from tests import _get_error

examples = [
    # No error
    ('', set()),
    # Found in file
    (
        textwrap.dedent(
            """
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        pass
    """
        ),
        {'4:0 ' + TC005},
    ),
    # Found in function
    (
        textwrap.dedent(
            """
    from typing import TYPE_CHECKING

    def example():
        if TYPE_CHECKING:
            pass
        return
    """
        ),
        {'5:0 ' + TC005},
    ),
    # Found in class
    (
        textwrap.dedent(
            """
    from typing import TYPE_CHECKING

    class Test:
        if TYPE_CHECKING:
            pass
        x = 2
    """
        ),
        {'5:0 ' + TC005},
    ),
    (
        textwrap.dedent(
            """
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        if 2:
            pass
    """
        ),
        set(),
    ),
    (
        textwrap.dedent(
            """
    from typing import TYPE_CHECKING
    from typing import List

    if TYPE_CHECKING:
        x: List
    """
        ),
        set(),
    ),
]


@pytest.mark.parametrize('example, expected', examples)
def test_TC005_errors(example, expected):
    assert _get_error(example, error_code_filter='TC005') == expected
