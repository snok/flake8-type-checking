import textwrap

from flake8_typing_only_imports.constants import TCH001, TCH002, TCH003, TCHA001
from tests import _get_error, mod


def test_duplicate_type_checking_blocks():
    example = textwrap.dedent(
        """
    if TYPE_CHECKING:
        from typing import Any

    if TYPE_CHECKING:
        from flake8_typing_only_imports.types import ImportType, Flake8Generator
    """
    )
    assert _get_error(example, error_code_filter='TCH003') == {'5:0 ' + TCH003}


def test_duplicate_type_checking_blocks_at_different_levels_of_indentation():
    example = textwrap.dedent(
        """
    if TYPE_CHECKING:
        from typing import Any

    class X:
        if TYPE_CHECKING:
            from flake8_typing_only_imports.types import ImportType, Flake8Generator
    """
    )
    assert _get_error(example, error_code_filter='TCH003') == set()
