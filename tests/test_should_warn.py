"""
The behavior of all TC000 errors should be opt-out.

The behavior of TC100 and TC200 errors should be opt-in.
"""
import os
import re
import sys
import textwrap

if sys.version_info >= (3, 8):
    from importlib.metadata import version
else:
    from importlib_metadata import version


def test_version(flake8dir):
    """Stolen from flake8-comprehensions to check flake8 is picking up our plugin."""
    result = flake8dir.run_flake8(['--version'])
    version_regex = r'flake8-type-checking:( )*' + version('flake8-type-checking')
    unwrapped = ''.join(result.out_lines)
    assert re.search(version_regex, unwrapped)


def test_tc_is_enabled_with_config(flake8dir):
    flake8dir.make_setup_cfg('[flake8]\nselect = TC')
    flake8dir.make_example_py(
        '''
        from typing import Union

        x: Union[str, int] = 1
    '''
    )
    result = flake8dir.run_flake8()
    assert result.out_lines == [
        f".{os.sep}example.py:1:1: TC002 Move third-party import 'typing.Union' into a type-checking block"
    ]


def test_tc1_and_tc2_are_disabled_by_default(flake8dir):
    flake8dir.make_setup_cfg('')
    flake8dir.make_example_py(
        '''
        from typing import TYPE_CHECKING

        if TYPE_CHECKING:
            from typing import Union

        x: Union[str, int]
    '''
    )
    result = flake8dir.run_flake8()
    assert result.out_lines == []


def test_tc1_and_tc2_are_disabled_by_default_when_tc_is_enabled(flake8dir):
    flake8dir.make_setup_cfg('[flake8]\nselect = TC')
    flake8dir.make_example_py(
        '''
        from typing import TYPE_CHECKING

        if TYPE_CHECKING:
            from typing import Union

        x: Union[str, int]
    '''
    )
    result = flake8dir.run_flake8()
    assert result.out_lines == []


def test_tc1_works_when_opted_in(flake8dir):
    flake8dir.make_setup_cfg('[flake8]\nselect = TC1')
    flake8dir.make_example_py(
        '''
        from typing import TYPE_CHECKING

        if TYPE_CHECKING:
            from typing import Union

        x: Union[str, int]
    '''
    )
    result = flake8dir.run_flake8()
    assert result.out_lines == [f".{os.sep}example.py:1:1: TC100 Add 'from __future__ import annotations' import"]


def test_tc2_works_when_opted_in(flake8dir):
    flake8dir.make_setup_cfg(
        textwrap.dedent(
            """\
            [flake8]
            select = TC2
            """
        )
    )
    flake8dir.make_example_py(
        '''
        from typing import TYPE_CHECKING

        if TYPE_CHECKING:
            from typing import Union

        x: Union[str, int]
    '''
    )
    result = flake8dir.run_flake8()
    assert result.out_lines == [
        f".{os.sep}example.py:6:4: TC200 Annotation 'Union' needs to be made into a string literal"
    ]
