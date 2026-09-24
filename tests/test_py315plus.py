import textwrap

from flake8_type_checking.constants import LAZY_SUFFIX, TC002
from tests.conftest import _get_error


def test_py315plus():
    """
    Assert that TC00[1-3] errors contain a hint about lazy imports
    as a possible remediation in addition to moving the import into
    a type checking_block
    """
    example = textwrap.dedent('''
        from pandas import DataFrame

        a: DataFrame
        ''')
    assert _get_error(example, error_code_filter='TC002', type_checking_py315plus=False) == {
        '2:0 ' + TC002.format(module='pandas.DataFrame')
    }
    assert _get_error(example, error_code_filter='TC002', type_checking_py315plus=True) == {
        '2:0 ' + TC002.format(module='pandas.DataFrame') + LAZY_SUFFIX
    }
