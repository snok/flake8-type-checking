import textwrap

from flake8_type_checking.constants import TC002
from tests.conftest import _get_error


def test_strict_mode():
    """
    Assert that imports are flagged for TC00[1-3] on a per-module basis by default,
    but individually when --type-checking-strict is set to true.
    """
    example = textwrap.dedent('''
        from x import Y, Z

        a = Y
        b: Z
        ''')
    assert _get_error(example, error_code_filter='TC002', type_checking_strict=False) == set()
    assert _get_error(example, error_code_filter='TC002', type_checking_strict=True) == {
        '2:0 ' + TC002.format(module='x.Z')
    }
