"""
This file tests the TC004 error:

    >> Move import out of type-checking block. Import is used for more than type hinting.

"""
import textwrap

import pytest

from flake8_type_checking.constants import TC004
from tests import _get_error

examples = [
    # No error
    ('', set()),
    # Used in file
    (
        textwrap.dedent(
            """
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from datetime import datetime

    x = datetime
    """
        ),
        {'5:0 ' + TC004.format(module='datetime')},
    ),
    # Used in function
    (
        textwrap.dedent(
            """
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from datetime import date

    def example():
        return date()
    """
        ),
        {'5:0 ' + TC004.format(module='date')},
    ),
    # Used, but only used inside the type checking block
    (
        textwrap.dedent(
            """
    if TYPE_CHECKING:
        from typing import Any

        CustomType = Any
    """
        ),
        set(),
    ),
    # Used for typing only
    (
        textwrap.dedent(
            """
    if TYPE_CHECKING:
        from typing import Any

    def example(*args: Any, **kwargs: Any):
        return

    my_type: Type[Any] | Any
    """
        ),
        set(),
    ),
]


@pytest.mark.parametrize('example, expected', examples)
def test_TC004_errors(example, expected):
    assert _get_error(example, error_code_filter='TC004') == expected
