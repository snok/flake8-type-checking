"""
Contains special test cases that fall outside the scope of remaining test files.
"""
import textwrap

from flake8_typing_only_imports.constants import TYO100, TYO101, TYO200
from tests import _get_error, mod


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
            '2:0 ' + TYO100.format(module=f'{mod}'),
            '3:0 ' + TYO101.format(module=f'pytest'),
            '4:0 ' + TYO101.format(module=f'x.y'),
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
            '1:0 ' + TYO200,
            '2:0 ' + TYO101.format(module='x'),
            '3:0 ' + TYO101.format(module='y.z'),
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
