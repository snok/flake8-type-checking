# """
# File tests TYO300:
#     Annotation should be wrapped in quotes
# """
# import textwrap
#
# import pytest
#
# from flake8_typing_only_imports.constants import TYO300
# from tests import _get_error
#
# examples = [
#     # No error
#     ('', set()),
#     # Builting AnnAssign without quotes
#     ('x: int', set()),
#     # Builting AnnAssign with quotes
#     ('x: "int"', set()),
#     # Imported AnnAssign without quotes
#     ('if TYPE_CHECKING:\n\tfrom typing import Dict\nx: Dict', {'3:3 ' + TYO300.format(annotation='Dict')}),
#     # Imported AnnAssign with quotes
#     ("if TYPE_CHECKING:\n\tfrom typing import Dict; x: 'Dict'", set()),
#     # Subscripted ast.AnnAssign without quotes
#     ('from typing import Dict\nx: Dict[int]', set()),
#     # Subscripted ast.AnnAssign without quotes
#     ('if TYPE_CHECKING:\n\tfrom typing import Dict\nx: Dict[int]', {'3:3 ' + TYO300.format(annotation='Dict')}),
#     # ast.AnnAssign from type checking block import without quotes
#     (
#         textwrap.dedent(
#             f'''
#             if TYPE_CHECKING:
#                 import something
#
#             x: something
#             '''
#         ),
#         {'5:3 ' + TYO300.format(annotation='something')},
#     ),
#     (
#         textwrap.dedent(
#             f'''
#         if TYPE_CHECKING:
#             import something
#
#         def example(x: "something") -> something:
#             pass
#         '''
#         ),
#         {'5:31 ' + TYO300.format(annotation='something')},
#     ),
#     (
#         textwrap.dedent(
#             f'''
#         if TYPE_CHECKING:
#             import something
#
#         def example(x: "something") -> "something":
#             pass
#         '''
#         ),
#         set(),
#     ),
#     (
#         textwrap.dedent(
#             f'''
#         from typing import Dict, TYPE_CHECKING
#
#         if TYPE_CHECKING:
#             import something
#
#         def example(x: Dict["something"]) -> Dict["something"]:
#             pass
#         '''
#         ),
#         set(),
#     ),
#     (
#         textwrap.dedent(
#             f'''
#         from typing import Dict, TYPE_CHECKING
#
#         if TYPE_CHECKING:
#             import something
#
#         def example(x: Dict[something]) -> Dict["something"]:
#             pass
#         '''
#         ),
#         {'7:20 ' + TYO300.format(annotation='something')},
#     ),
#     (
#         textwrap.dedent(
#             f'''
#         from typing import TYPE_CHECKING
#
#         if TYPE_CHECKING:
#             import ast
#
#         def example(x: ast.If):
#             pass
#         '''
#         ),
#         {'7:15 ' + TYO300.format(annotation='ast')},
#     ),
# ]
#
#
# @pytest.mark.parametrize('example, expected', examples)
# def test_tyo300_errors(example, expected):
#     assert _get_error(example, error_code_filter='TYO300') == expected
