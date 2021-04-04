import textwrap

from flake8_type_checking.codes import TC001, TC002, TC003, TC100
from tests import _get_error, mod


def test_duplicate_type_checking_blocks():
    example = textwrap.dedent(
        """
    if TYPE_CHECKING:
        from typing import Any

    if TYPE_CHECKING:
        from flake8_type_checking.types import ImportType, Flake8Generator
    """
    )
    assert _get_error(example, error_code_filter='TC003') == {'5:0 ' + TC003}


def test_duplicate_type_checking_blocks_at_different_levels_of_indentation():
    example = textwrap.dedent(
        """
    if TYPE_CHECKING:
        from typing import Any

    class X:
        if TYPE_CHECKING:
            from flake8_type_checking.types import ImportType, Flake8Generator
    """
    )
    assert _get_error(example, error_code_filter='TC003') == set()
