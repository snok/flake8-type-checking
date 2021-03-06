"""
File tests TYO202:
    Annotation is wrapped in unnecessary quotes
"""
import os
import textwrap

import pytest

from flake8_typing_only_imports.constants import TYO202
from tests import REPO_ROOT, _get_error, mod

examples = [
    # # No error
    # ('', set()),
    # # Basic ast.AnnAssign with quotes
    # (
    #     "from __future__ import annotations; x: 'int'",
    #     {'2:0 ' + TYO202.format(annotation='int')},
    # ),
    # # Nested ast.AnnAssign with quotes
    # (
    #     "from __future__ import annotations; from typing import Dict; x: Dict['int']",
    #     {'2:0 ' + TYO202.format(annotation='int')},
    # ),
    # # ast.AnnAssign from type checking block import with quotes
    # (
    #     textwrap.dedent(
    #         f'''
    #         from __future__ import annotations
    #
    #         if TYPE_CHECKING:
    #             import something
    #
    #         x: "something"
    #         '''
    #     ),
    #     {'4:0 ' + TYO202.format(annotation='something')},
    # ),
    # # No futures import and no type checking block
    # (
    #     "from typing import Dict; x: 'Dict'",
    #     {'2:0 ' + TYO202.format(annotation='int')},
    # ),
    # # Sanity check: No futures import and with type checking block
    # (
    #     "if TYPE_CHECKING:\n\tfrom typing import Dict; x: 'Dict'",
    #     set(),  # should not error
    # ),
    # (
    #     textwrap.dedent(
    #         f'''
    #     from __future__ import annotations
    #
    #     if TYPE_CHECKING:
    #         import something
    #
    #     def example(x: "something") -> something:
    #         pass
    #     '''
    #     ),
    #     {'6:12 ' + TYO202.format(annotation='something')},
    # ),
    # (
    #     textwrap.dedent(
    #         f'''
    #     from __future__ import annotations
    #
    #     if TYPE_CHECKING:
    #         import something
    #
    #     def example(x: "something") -> "something":
    #         pass
    #     '''
    #     ),
    #     {'6:12 ' + TYO202.format(annotation='something'), '6:15 ' + TYO202.format(annotation='something')},
    # ),
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
        {'6:12 ' + TYO202.format(annotation='something'), '6:15 ' + TYO202.format(annotation='something')},
    ),
]


@pytest.mark.parametrize('example, expected', examples)
def test_tyo202_errors(example, expected):
    assert _get_error(example) == expected
