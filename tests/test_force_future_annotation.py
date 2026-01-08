import textwrap

from flake8_type_checking.constants import TC100
from tests.conftest import _get_error


def test_force_future_annotation():
    """TC100 should be emitted even if there are no forward references to typing-only symbols."""
    example = textwrap.dedent('''
        from x import Y

        a: Y
        ''')
    assert _get_error(example, error_code_filter='TC100', type_checking_force_future_annotation=False) == set()
    assert _get_error(example, error_code_filter='TC100', type_checking_force_future_annotation=True) == {
        '1:0 ' + TC100
    }
