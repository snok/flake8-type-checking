"""
File tests TYO201:
    Annotation should be wrapped in quotes
"""
import textwrap

import pytest

from flake8_typing_only_imports.constants import TYO201
from tests import _get_error

examples = [
    # No error
    ('', set()),
    # Basic ast.AnnAssign without quotes and futures import
    (
        'x: int',
        set(),
    ),
    (
        "if TYPE_CHECKING:\n\tfrom typing import Dict; x: 'Dict'",
        set(),  # should not error
    ),
    # Nested ast.AnnAssign without quotes and futures import
    (
        'from __future__ import annotations; from typing import Dict; x: Dict[int]',
        set(),
    ),
    # ast.AnnAssign from type checking block import without quotes and futures import
    (
        textwrap.dedent(
            f'''
            from __future__ import annotations

            if TYPE_CHECKING:
                import something

            x: something
            '''
        ),
        set(),
    ),
    # ast.AnnAssign from type checking block import without quotes
    (
        textwrap.dedent(
            f'''
            if TYPE_CHECKING:
                import something

            x: something
            '''
        ),
        {'4:0 ' + TYO201.format(annotation='something')},
    ),
    (
        textwrap.dedent(
            f'''
        if TYPE_CHECKING:
            import something

        def example(x: "something") -> something:
            pass
        '''
        ),
        {'6:12 ' + TYO201.format(annotation='something')},
    ),
    (
        textwrap.dedent(
            f'''
        if TYPE_CHECKING:
            import something

        def example(x: "something") -> "something":
            pass
        '''
        ),
        {'6:12 ' + TYO201.format(annotation='something'), '6:15 ' + TYO201.format(annotation='something')},
    ),
    (
        textwrap.dedent(
            f'''
        if TYPE_CHECKING:
            import something

        def example(x: "something") -> "something":
            pass
        '''
        ),
        set(),
    ),
    (
        textwrap.dedent(
            f'''
    import something

    def example(x: "something") -> "something":
        pass
    '''
        ),
        {'6:12 ' + TYO201.format(annotation='something'), '6:15 ' + TYO201.format(annotation='something')},
    ),
]


@pytest.mark.parametrize('example, expected', examples)
def test_tyo201_errors(example, expected):
    assert (
        _get_error(example) == expected
    ), f"No match for example: '{example}'. Found '{_get_error(example)}' instead of '{expected}'"
