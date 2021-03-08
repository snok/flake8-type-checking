"""
File tests TYO301:
    Annotation is wrapped in unnecessary quotes
"""
import textwrap

import pytest

from flake8_typing_only_imports.constants import TYO301
from tests import _get_error

examples = [
    ('', set()),
    ("x: 'int'", {'1:3 ' + TYO301.format(annotation='int')}),
    ("x: 'Dict[int]'", {'1:3 ' + TYO301.format(annotation='Dict[int]')}),
    ("from __future__ import annotations\nx: 'int'", {'2:3 ' + TYO301.format(annotation='int')}),
    ("if TYPE_CHECKING:\n\tfrom typing import Dict\nx: 'Dict'", set()),
    ("if TYPE_CHECKING:\n\tfrom typing import Dict\nx: 'Dict[int]'", set()),
    (
        "from __future__ import annotations\nfrom typing import Dict\nx: Dict['int']",
        {'3:8 ' + TYO301.format(annotation='int')},
    ),
    ("from __future__ import annotations\nif TYPE_CHECKING:\n\tfrom typing import Dict\nx: Dict['int']", set()),
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
]


@pytest.mark.parametrize('example, expected', examples)
def test_tyo301_errors(example, expected):
    assert _get_error(example, error_code_filter='TYO301') == expected
