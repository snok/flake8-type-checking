import ast
import textwrap
from typing import Set

import pytest

from flake8_typing_only_imports.checker import ImportVisitor


def _get_names(example: str) -> Set[str]:
    visitor = ImportVisitor('fake cwd')  # type: ignore
    visitor.visit(ast.parse(example))
    return visitor.names


examples = [
    # ast.Import
    ('import x', set()),
    ('import pytest', set()),
    ('import flake8_typing_only_imports', set()),
    # ast.ImportFrom
    ('from x import y', set()),
    ('from _pytest import fixtures', set()),
    ('from flake8_typing_only_imports import constants', set()),
    # Assignments
    ('x = y', {'x', 'y'}),
    ('x, y = z', {'x', 'y', 'z'}),
    ('x, y, z = a, b, c()', {'x', 'y', 'z', 'a', 'b', 'c'}),
    # Calls
    ('x()', {'x'}),
    ('x = y()', {'x', 'y'}),
    ('def example(): x = y(); z()', {'x', 'y', 'z'}),
    # Attribute
    ('x.y', {'x.y', 'x'}),
    (
        textwrap.dedent(
            """
    def example(c):
        a = 2
        b = c * 2
    """
        ),
        {'a', 2, 'b', 'c'},
    ),
    (
        textwrap.dedent(
            """
    class Test:
        x = 13

        def __init__(self, z):
            self.y = z

    a = Test()
    b = a.y
    """
        ),
        {'self.y', 'z', 'Test', 'self', 13, 'a', 'b', 'x', 'a.y'},
    ),
    (
        textwrap.dedent(
            """
    import ast

    ImportType = Union[Import, ImportFrom]
    """
        ),  # ast should not be a part of this
        {'Union', 'Import', 'ImportFrom', 'ImportType'},
    ),
    (
        textwrap.dedent(
            """
        import ast
        def _get_usages(example):
            visitor = UnusedImportVisitor()
            visitor.visit(parse(example))
            return visitor.usage_names
        """
        ),
        {'UnusedImportVisitor', 'example', 'parse', 'visitor', 'visitor.usage_names', 'visitor.visit'},
    ),
]


@pytest.mark.parametrize('example, result', examples)
def test_basic_annotations_are_removed(example, result):
    assert _get_names(example) == result


def test_model_declarations_are_included_in_names():
    """
    Class definition arguments need to be included in our "names".
    """
    example = textwrap.dedent(
        """
    from django.db import models
    from app.models import SomeModel

    class LoanProvider(models.Model):
        fk = models.ForeignKey(
            SomeModel,
            on_delete=models.CASCADE,
        )
    """
    )
    assert _get_names(example) == {'SomeModel', 'fk', 'models', 'models.CASCADE', 'models.ForeignKey', 'models.Model'}
