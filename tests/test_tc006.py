"""
This file tests the TC006 error:

    >> Annotation in typing.cast() should be a string literal

Types passed to typing.cast() are only ever used by type checkers, never at
runtime. Despite this, constructing complex types at runtime can have a very
significant overhead in hot paths. This can be avoided by quoting the type so
that it isn't resolved at runtime.
"""

import textwrap

import pytest

from flake8_type_checking.constants import TC006
from tests.conftest import _get_error

examples = [
    # No error
    ('', set()),
    # Simple type unquoted
    (
        textwrap.dedent("""
    from typing import cast

    cast(int, 3.0)
    """),
        {'4:5 ' + TC006.format(annotation='int')},
    ),
    # Complex type unquoted
    (
        textwrap.dedent("""
    from typing import cast

    cast(list[tuple[bool | float | int | str]], 3.0)
    """),
        {'4:5 ' + TC006.format(annotation='list[tuple[bool | float | int | str]]')},
    ),
    # Complex type unquoted using Union
    (
        textwrap.dedent("""
    from typing import Union, cast

    cast(list[tuple[Union[bool, float, int, str]]], 3.0)
    """),
        {'4:5 ' + TC006.format(annotation='list[tuple[Union[bool, float, int, str]]]')},
    ),
    # Simple type quoted
    (
        textwrap.dedent("""
    from typing import cast

    cast("int", 3.0)
    """),
        set(),
    ),
    # Complex type quoted
    (
        textwrap.dedent("""
    from typing import cast

    cast("list[tuple[bool | float | int | str]]", 3.0)
    """),
        set(),
    ),
    # Complex type quoted using Union
    (
        textwrap.dedent("""
    from typing import Union, cast

    cast("list[tuple[Union[bool, float, int, str]]]", 3.0)
    """),
        set(),
    ),
    # Call aliased function
    (
        textwrap.dedent("""
    from typing import cast as typecast

    typecast(int, 3.0)
    """),
        {'4:9 ' + TC006.format(annotation='int')},
    ),
    # Call function from module
    (
        textwrap.dedent("""
    import typing

    typing.cast(int, 3.0)
    """),
        {'4:12 ' + TC006.format(annotation='int')},
    ),
    # Call function from aliased module
    (
        textwrap.dedent("""
    import typing as t

    t.cast(int, 3.0)
    """),
        {'4:7 ' + TC006.format(annotation='int')},
    ),
    # Call function from star-imported module
    (
        textwrap.dedent("""
    from typing import *

    cast(int, 3.0)
    """),
        {'4:5 ' + TC006.format(annotation='int')},
    ),
    # TODO: What about importing typing.cast() from another module, e.g. a compat module?
]


@pytest.mark.parametrize(('example', 'expected'), examples)
def test_TC006_errors(example, expected):
    assert _get_error(example, error_code_filter='TC006') == expected
