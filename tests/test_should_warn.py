"""
The behavior of all TC000 errors should be opt-out.

The behavior of TC100 and TC200 errors should be opt-in.
"""
import os
import re
from importlib.metadata import version
from textwrap import dedent


def test_version(flake8_path):
    """Stolen from flake8-comprehensions to check flake8 is picking up our plugin."""
    result = flake8_path.run_flake8(['--version'])
    version_regex = r'flake8-type-checking:( )*' + version('flake8-type-checking')
    unwrapped = ''.join(result.out_lines)
    assert re.search(version_regex, unwrapped)


def test_tc_is_enabled_with_config(flake8_path):
    (flake8_path / 'setup.cfg').write_text('[flake8]\nselect = TC')
    (flake8_path / 'example.py').write_text(
        dedent(
            '''
        from x import Y

        x: Y[str, int] = 1
    '''
        )
    )
    result = flake8_path.run_flake8()
    assert result.out_lines == [
        f".{os.sep}example.py:2:1: TC002 Move third-party import 'x.Y' into a type-checking block"
    ]


def test_tc1_and_tc2_are_disabled_by_default(flake8_path):
    (flake8_path / 'setup.cfg').write_text('')
    (flake8_path / 'example.py').write_text(
        dedent(
            '''
        from typing import TYPE_CHECKING

        if TYPE_CHECKING:
            from typing import Union

        x: Union[str, int]
    '''
        )
    )
    result = flake8_path.run_flake8()
    assert result.out_lines == []


def test_tc1_and_tc2_are_disabled_by_default_when_tc_is_enabled(flake8_path):
    (flake8_path / 'setup.cfg').write_text('[flake8]\nselect = TC')
    (flake8_path / 'example.py').write_text(
        dedent(
            '''
        from typing import TYPE_CHECKING

        if TYPE_CHECKING:
            from typing import Union

        x: Union[str, int]
    '''
        )
    )
    result = flake8_path.run_flake8()
    assert result.out_lines == []


def test_tc1_works_when_opted_in(flake8_path):
    (flake8_path / 'setup.cfg').write_text('[flake8]\nselect = TC1')
    (flake8_path / 'example.py').write_text(
        dedent(
            '''
        from typing import TYPE_CHECKING

        if TYPE_CHECKING:
            from typing import Union

        x: Union[str, int]
    '''
        )
    )
    result = flake8_path.run_flake8()
    assert result.out_lines == [f".{os.sep}example.py:1:1: TC100 Add 'from __future__ import annotations' import"]


def test_tc2_works_when_opted_in(flake8_path):
    (flake8_path / 'setup.cfg').write_text(
        dedent(
            """\
            [flake8]
            select = TC2
            """
        )
    )
    (flake8_path / 'example.py').write_text(
        dedent(
            '''
        from typing import TYPE_CHECKING

        if TYPE_CHECKING:
            from typing import Union

        x: Union[str, int]
    '''
        )
    )
    result = flake8_path.run_flake8()
    assert result.out_lines == [
        f".{os.sep}example.py:7:4: TC200 Annotation 'Union' needs to be made into a string literal"
    ]
