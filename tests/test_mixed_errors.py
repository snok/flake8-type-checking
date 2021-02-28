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
