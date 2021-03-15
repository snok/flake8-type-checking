import textwrap

from flake8_typing_only_imports.constants import TYO100, TYO101, TYO102, TYO200
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
    assert _get_error(example, error_code_filter='TYO102') == {'5:0 ' + TYO102}


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
    assert _get_error(example, error_code_filter='TYO102') == set()
