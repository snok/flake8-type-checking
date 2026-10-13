import textwrap

from flake8_type_checking.constants import TC002
from tests.conftest import _get_error


def test_ignore_dunder_lazy_modules():
    """
    Assert that imports are flagged for TC00[1-3] even if they appear
    inside a __lazy_modules__ declaration.
    """
    example = textwrap.dedent('''
        __lazy_modules__ = ['pandas']
        from pandas import DataFrame

        a: DataFrame
        ''')
    assert _get_error(example, error_code_filter='TC002', type_checking_ignore_dunder_lazy_modules=False) == set()
    assert _get_error(example, error_code_filter='TC002', type_checking_ignore_dunder_lazy_modules=True) == {
        '3:0 ' + TC002.format(module='pandas.DataFrame')
    }
