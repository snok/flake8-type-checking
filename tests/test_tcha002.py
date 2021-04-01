"""
File tests TCHA002:
    Annotation is wrapped in unnecessary quotes
"""
import textwrap

import pytest

from flake8_typing_only_imports.constants import TCHA002
from tests import _get_error

examples = [
    # No error
    ('', set()),
    ("x: 'int'", {'1:3 ' + TCHA002.format(annotation='int')}),
    ("from __future__ import annotations\nx: 'int'", {'2:3 ' + TCHA002.format(annotation='int')}),
    ("if TYPE_CHECKING:\n\timport y\nx: 'y'", set()),
    ("x: 'Dict[int]'", {'1:3 ' + TCHA002.format(annotation='Dict[int]')}),
    ("if TYPE_CHECKING:\n\tfrom typing import Dict\nx: 'Dict[int]'", set()),
    # Basic AnnAssign with type-checking block and exact match
    (
        "from __future__ import annotations\nif TYPE_CHECKING:\n\tfrom typing import Dict\nx: 'Dict'",
        {'4:3 ' + TCHA002.format(annotation='Dict')},
    ),
    # Nested ast.AnnAssign with quotes
    (
        "from __future__ import annotations\nfrom typing import Dict\nx: Dict['int']",
        {'3:8 ' + TCHA002.format(annotation='int')},
    ),
    (
        'from __future__ import annotations\nfrom typing import Dict\nx: Dict | int',
        set(),
    ),
    # ast.AnnAssign from type checking block import with quotes
    (
        textwrap.dedent(
            f'''
            from __future__ import annotations

            if TYPE_CHECKING:
                import something

            x: "something"
            '''
        ),
        {'7:3 ' + TCHA002.format(annotation='something')},
    ),
    # No futures import and no type checking block
    ("from typing import Dict\nx: 'Dict'", {'2:3 ' + TCHA002.format(annotation='Dict')}),
    (
        textwrap.dedent(
            f'''
        from __future__ import annotations

        if TYPE_CHECKING:
            import something

        def example(x: "something") -> something:
            pass
        '''
        ),
        {'7:15 ' + TCHA002.format(annotation='something')},
    ),
    (
        textwrap.dedent(
            f'''
        from __future__ import annotations

        if TYPE_CHECKING:
            import something

        def example(x: "something") -> "something":
            pass
        '''
        ),
        {'7:15 ' + TCHA002.format(annotation='something'), '7:31 ' + TCHA002.format(annotation='something')},
    ),
    (
        textwrap.dedent(
            f'''
        from __future__ import annotations

        def example(x: "something") -> "something":
            pass
        '''
        ),
        {'4:15 ' + TCHA002.format(annotation='something'), '4:31 ' + TCHA002.format(annotation='something')},
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
        class X:
            def foo(self) -> 'X':
                pass
        '''
        ),
        set(),
    ),
    (
        textwrap.dedent(
            f'''
        from __future__ import annotations
        class X:
            def foo(self) -> 'X':
                pass
        '''
        ),
        {'4:21 ' + TCHA002.format(annotation='X')},
    ),
]


@pytest.mark.parametrize('example, expected', examples)
def test_TCHA002_errors(example, expected):
    assert _get_error(example, error_code_filter='TCHA002') == expected
