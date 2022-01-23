"""
File tests TC200:
    Annotation should be wrapped in quotes
"""
import textwrap

import pytest

from flake8_type_checking.codes import TC200
from tests import _get_error

examples = [
    # No error
    ('', set()),
    ('x: int', set()),
    ('x: "int"', set()),
    ('from typing import Dict\nx: Dict[int]', set()),
    ('if TYPE_CHECKING:\n\tfrom typing import Dict\nx: Dict', {'3:3 ' + TC200.format(annotation='Dict')}),
    ("if TYPE_CHECKING:\n\tfrom typing import Dict\nx: 'Dict'", set()),
    ("if TYPE_CHECKING:\n\tfrom typing import Dict as d\nx: 'd[int]'", set()),
    ('if TYPE_CHECKING:\n\tfrom typing import Dict\nx: Dict[int]', {'3:3 ' + TC200.format(annotation='Dict')}),
    ('if TYPE_CHECKING:\n\timport something\nx: something', {'3:3 ' + TC200.format(annotation='something')}),
    (
        "if TYPE_CHECKING:\n\timport something\ndef example(x: 'something') -> something:\n\tpass",
        {'3:31 ' + TC200.format(annotation='something')},
    ),
    ("if TYPE_CHECKING:\n\timport something\ndef example(x: 'something') -> 'something':\n\tpass", set()),
    (
        'from typing import Dict, TYPE_CHECKING\nif TYPE_CHECKING:\n\timport something\ndef example(x:'
        ' Dict[\'something\']) -> Dict[\'something\']:\n\tpass',
        set(),
    ),
    (
        textwrap.dedent(
            f'''
        from typing import Dict, TYPE_CHECKING

        if TYPE_CHECKING:
            import something

        def example(x: Dict[something]) -> Dict["something"]:
            pass
        '''
        ),
        {'7:20 ' + TC200.format(annotation='something')},
    ),
    (
        textwrap.dedent(
            f'''
        from typing import TYPE_CHECKING

        if TYPE_CHECKING:
            import ast

        def example(x: ast.If):
            pass
        '''
        ),
        {'7:15 ' + TC200.format(annotation='ast')},
    ),
]


@pytest.mark.parametrize('example, expected', examples)
def test_TC200_errors(example, expected):
    assert _get_error(example, error_code_filter='TC200') == expected
