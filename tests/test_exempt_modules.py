import textwrap

from flake8_type_checking.constants import TC002
from tests import _get_error


def test_exempt_modules_option():
    """
    The plugin provides an option called `--type-checking-exempt-modules`
    which is meant to passlist certain modules from TC001 and TC002 errors.
    """
    # Check that typing is passlisted when exempted
    example = textwrap.dedent(
        '''
        from typing import TYPE_CHECKING, List

        x: List
        '''
    )
    assert _get_error(example, error_code_filter='TC002') == {'2:0 ' + TC002.format(module='typing.List')}
    assert _get_error(example, error_code_filter='TC002', type_checking_exempt_modules=['typing']) == set()

    # Check that other basic errors are still caught
    example2 = textwrap.dedent(
        '''
        from typing import TYPE_CHECKING, List
        from collections.abc import Callable

        x: Callable[[], List]
        '''
    )
    assert _get_error(example2, error_code_filter='TC002') == {
        '2:0 ' + TC002.format(module='typing.List'),
        '3:0 ' + TC002.format(module='collections.abc.Callable'),
    }
    assert _get_error(example2, error_code_filter='TC002', type_checking_exempt_modules=['typing']) == {
        '3:0 ' + TC002.format(module='collections.abc.Callable')
    }

    # Check Import
    example3 = textwrap.dedent(
        '''
        import typing

        x: typing.List
        '''
    )
    assert _get_error(example3, error_code_filter='TC002') == {'2:0 ' + TC002.format(module='typing')}
    assert _get_error(example3, error_code_filter='TC002', type_checking_exempt_modules=['typing']) == set()
