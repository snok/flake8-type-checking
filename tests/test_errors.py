"""
Contains special test cases that fall outside the scope of remaining test files.
"""
import textwrap

from flake8_typing_only_imports.constants import TYO100, TYO101
from tests import _get_error, mod


def test_mixed_errors():
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


def test_type_checking_block_imports_dont_generate_errors():
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
        '2:0 ' + TYO101.format(module='x'),
        '3:0 ' + TYO101.format(module='y.z'),
    }


def test_model_declarations_dont_trigger_error():
    """
    Initially found false positives in Django project, because name
    visitor did not capture the SomeModel usage in the example below.
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
    assert _get_error(example) == set()
