"""
File tests TCHB002:
    Annotation is wrapped in unnecessary quotes
"""
import textwrap

import pytest

from flake8_type_checking.constants import TCHB002
from tests import _get_error

examples = [
    ('', set()),
    ("x: 'int'", {'1:3 ' + TCHB002.format(annotation='int')}),
    ("x: 'Dict[int]'", {'1:3 ' + TCHB002.format(annotation='Dict[int]')}),
    ("from __future__ import annotations\nx: 'int'", {'2:3 ' + TCHB002.format(annotation='int')}),
    ("if TYPE_CHECKING:\n\tfrom typing import Dict\nx: 'Dict'", set()),
    ("if TYPE_CHECKING:\n\tfrom typing import Dict\nx: 'Dict[int]'", set()),
    (
        "from __future__ import annotations\nfrom typing import Dict\nx: Dict['int']",
        {'3:8 ' + TCHB002.format(annotation='int')},
    ),
    (
        "from __future__ import annotations\nif TYPE_CHECKING:\n\tfrom typing import Dict\nx: Dict['int']",
        {'4:8 ' + TCHB002.format(annotation='int')},
    ),
    (
        textwrap.dedent(
            f'''
            from __future__ import annotations

            if TYPE_CHECKING:
                import something

            x: "something"
            '''
        ),
        set(),
    ),
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
        set(),
    ),
]


@pytest.mark.parametrize('example, expected', examples)
def test_TCHB002_errors(example, expected):
    assert _get_error(example, error_code_filter='TCHB002') == expected
