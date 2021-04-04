"""
Contains special test cases that fall outside the scope of remaining test files.
"""
import textwrap
from unittest.mock import patch

from flake8_type_checking.checker import ImportVisitor
from flake8_type_checking.codes import TC001, TC002
from tests import REPO_ROOT, _get_error, mod


class TestFoundBugs:
    def test_mixed_errors(self):
        example = textwrap.dedent(
            f"""
        import {mod}
        import pytest
        from x import y
        """
        )
        assert _get_error(example) == {
            '2:0 ' + TC001.format(module=f'{mod}'),
            '3:0 ' + TC002.format(module=f'pytest'),
            '4:0 ' + TC002.format(module=f'x.y'),
        }

    def test_type_checking_block_imports_dont_generate_errors(self):
        example = textwrap.dedent(
            """
        import x
        from y import z

        if TYPE_CHECKING:
            import a

            # arbitrary whitespace

            from b import c

        def test():
            pass
        """
        )
        assert _get_error(example) == {
            '2:0 ' + TC002.format(module='x'),
            '3:0 ' + TC002.format(module='y.z'),
        }

    def test_model_declarations_dont_trigger_error(self):
        """
        Initially found false positives in Django project, because name
        visitor did not capture the SomeModel usage in the example below.
        """
        example = textwrap.dedent(
            """
        from django.db import models
        from app.models import SomeModel

        class LoanProvider(models.Model):
            fk: SomeModel = models.ForeignKey(
                SomeModel,
                on_delete=models.CASCADE,
            )
        """
        )
        assert _get_error(example) == set()

    def test_all_declaration(self):
        """
        __all__ declarations originally generated false positives.
        """
        example = textwrap.dedent(
            """
        from app.models import SomeModel
        from another_app.models import AnotherModel

        __all__ = ['SomeModel', 'AnotherModel']
        """
        )
        assert _get_error(example) == set()

    def test_callable_import(self):
        """
        __all__ declarations originally generated false positives.
        """
        example = textwrap.dedent(
            """
        from x import y

        class X:
            def __init__(self):
                self.all_sellable_models: list[CostModel] = y(
                    country=self.country
                )
        """
        )
        assert _get_error(example) == set()

    def test_ellipsis(self):
        example = textwrap.dedent(
            """
        x: Tuple[str, ...]
        """
        )
        assert _get_error(example) == set()

    def test_literal(self):
        example = textwrap.dedent(
            """
        from __future__ import annotations

        x: Literal['string']
        """
        )
        assert _get_error(example) == set()

    def test_conditional_import(self):
        example = textwrap.dedent(
            """
        version = 2

        if version == 2:
            import x
        else:
            import y as x

        var: x
        """
        )
        assert _get_error(example) == {"7:4 TC002: Move third-party import 'x' into a type-checking block"}


def test_import_is_local():
    """
    Check that if ValueErrors are raised in _import_is_local, we bump it into the TC002 bucket.
    """

    def raise_value_error(*args, **kwargs):
        raise ValueError('test')

    visitor = ImportVisitor(REPO_ROOT)
    assert visitor._import_is_local(mod) is True

    patch('flake8_type_checking.checker.find_spec', raise_value_error).start()
    assert visitor._import_is_local(mod) is False
    patch.stopall()
