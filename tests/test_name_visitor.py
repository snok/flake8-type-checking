from __future__ import annotations

import ast
import sys
import textwrap

import pytest

from flake8_type_checking.checker import ImportVisitor


def _get_names_and_soft_uses(example: str) -> tuple[set[str], set[str]]:
    visitor = ImportVisitor(
        cwd='fake cwd',  # type: ignore[arg-type]
        py314plus=False,
        pydantic_enabled=False,
        fastapi_enabled=False,
        fastapi_dependency_support_enabled=False,
        cattrs_enabled=False,
        sqlalchemy_enabled=False,
        sqlalchemy_mapped_dotted_names=[],
        injector_enabled=False,
        pydantic_enabled_baseclass_passlist=[],
    )
    visitor.visit(ast.parse(example))
    return visitor.names, visitor.soft_uses


examples = [
    # ast.Import
    ('import x', set(), set()),
    ('import pytest', set(), set()),
    ('import flake8_type_checking', set(), set()),
    # ast.ImportFrom
    ('from x import y', set(), set()),
    ('from _pytest import fixtures', set(), set()),
    ('from flake8_type_checking import constants', set(), set()),
    # Assignments
    ('x = y', {'x', 'y'}, set()),
    ('x, y = z', {'x', 'y', 'z'}, set()),
    ('x, y, z = a, b, c()', {'x', 'y', 'z', 'a', 'b', 'c'}, set()),
    # Calls
    ('x()', {'x'}, set()),
    ('x = y()', {'x', 'y'}, set()),
    ('def example(): x = y(); z()', {'x', 'y', 'z'}, set()),
    # Attribute
    ('x.y', {'x.y', 'x'}, set()),
    (
        textwrap.dedent(
            """
        def example(c):
            a = 2
            b = c * 2
        """
        ),
        {'a', 'b', 'c'},
        set(),
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
        {'self.y', 'z', 'Test', 'self', 'a', 'b', 'x', 'a.y'},
        set(),
    ),
    (
        textwrap.dedent(
            """
        import ast

        ImportType = Union[Import, ImportFrom]
        """
        ),  # ast should not be a part of this
        {'Union', 'Import', 'ImportFrom', 'ImportType'},
        set(),
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
        set(),
    ),
    (
        textwrap.dedent(
            """
        from typing import Annotated

        from foo import Gt

        x: Annotated[int, Gt(5)]
        """
        ),
        {'Gt'},
        {'int'},
    ),
    (
        textwrap.dedent(
            """
        from __future__ import annotations

        from typing import Annotated

        from foo import Gt

        x: Annotated[int, Gt(5)]
        """
        ),
        set(),
        {'Gt', 'int'},
    ),
]

if sys.version_info >= (3, 12):
    examples.extend(
        [
            (
                textwrap.dedent(
                    """
            from typing import Annotated

            from foo import Gt

            type x = Annotated[int, Gt(5)]
            """
                ),
                set(),
                {'Gt', 'int'},
            ),
        ]
    )


@pytest.mark.parametrize(('example', 'result', 'soft_uses'), examples)
def test_basic_annotations_are_removed(example, result, soft_uses):
    assert _get_names_and_soft_uses(example) == (result, soft_uses)


def test_model_declarations_are_included_in_names():
    """Class definition arguments need to be included in our "names"."""
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
    assert _get_names_and_soft_uses(example) == (
        {'SomeModel', 'fk', 'models', 'models.CASCADE', 'models.ForeignKey', 'models.Model'},
        set(),
    )
