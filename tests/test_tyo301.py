# """
# File tests TYO201:
#     Annotation is wrapped in unnecessary quotes
# """
# import textwrap
# from unittest.mock import patch
#
# import pytest
#
# from flake8_typing_only_imports.constants import TYO201, TYO301
# from tests import _get_error
#
# examples = [
#     # No error
#     ('', set()),
#     # Basic AnnAssign with futures import
#     ("from __future__ import annotations\nx: 'int'", set()),
#     # Basic AnnAssign with quotes and no type checking block
#     ("x: 'Dict[int]'", set()),
#     # Basic AnnAssign with type-checking block and exact match
#     ("if TYPE_CHECKING:\n\tfrom typing import Dict\nx: 'Dict'", set()),
#     ("from typing import Dict\nx: 'Dict'", {'2:3 ' + TYO301.format(annotation='Dict')}),
#     # Nested ast.AnnAssign with quotes
#     # (
#     #     "from __future__ import annotations\nfrom typing import Dict\nx: Dict['int']",
#     #     {'3:8 ' + TYO201.format(annotation='int')},
#     # ),
#     # # ast.AnnAssign from type checking block import with quotes
#     # (
#     #     textwrap.dedent(
#     #         f'''
#     #         from __future__ import annotations
#     #
#     #         if TYPE_CHECKING:
#     #             import something
#     #
#     #         x: "something"
#     #         '''
#     #     ),
#     #     {'7:3 ' + TYO201.format(annotation='something')},
#     # ),
#     # # No futures import and no type checking block
#     # ("from typing import Dict\nx: 'Dict'", {'2:3 ' + TYO201.format(annotation='Dict')}),
#     # # Note: This would be a set if used with TYO201 over TYO200
#     # (
#     #     "if TYPE_CHECKING:\n\tfrom typing import Dict\nx: 'Dict'",
#     #     {'3:3 ' + TYO201.format(annotation='Dict')},
#     # ),
#     # (
#     #     textwrap.dedent(
#     #         f'''
#     #     from __future__ import annotations
#     #
#     #     if TYPE_CHECKING:
#     #         import something
#     #
#     #     def example(x: "something") -> something:
#     #         pass
#     #     '''
#     #     ),
#     #     {'7:15 ' + TYO201.format(annotation='something')},
#     # ),
#     # (
#     #     textwrap.dedent(
#     #         f'''
#     #     from __future__ import annotations
#     #
#     #     if TYPE_CHECKING:
#     #         import something
#     #
#     #     def example(x: "something") -> "something":
#     #         pass
#     #     '''
#     #     ),
#     #     {'7:15 ' + TYO201.format(annotation='something'), '7:31 ' + TYO201.format(annotation='something')},
#     # ),
#     # (
#     #     textwrap.dedent(
#     #         f'''
#     #     if TYPE_CHECKING:
#     #         import something
#     #
#     #     def example(x: "something") -> "something":
#     #         pass
#     #     '''
#     #     ),
#     #     {'5:15 ' + TYO201.format(annotation='something'), '5:31 ' + TYO201.format(annotation='something')},
#     # ),
#     # (
#     #     textwrap.dedent(
#     #         f'''
#     # import something
#     #
#     # def example(x: "something") -> "something":
#     #     pass
#     # '''
#     #     ),
#     #     {'4:15 ' + TYO201.format(annotation='something'), '4:31 ' + TYO201.format(annotation='something')},
#     # ),
# ]
#
#
# @pytest.mark.parametrize('example, expected', examples)
# def test_tyo301_errors(example, expected):
#     patch()
#     assert _get_error(example, error_code_filter='TYO301') == expected
