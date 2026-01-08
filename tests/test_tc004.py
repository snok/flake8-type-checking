"""
This file tests the TC004 error:

    >> Move import out of type-checking block. Import is used for more than type hinting.

"""

import textwrap

import pytest

from flake8_type_checking.constants import TC004
from tests.conftest import _get_error

examples = [
    # No error
    ('', set()),
    # Used in file
    (
        textwrap.dedent("""
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from datetime import datetime

    x = datetime
    """),
        {'5:0 ' + TC004.format(module='datetime')},
    ),
    # Used in function
    (
        textwrap.dedent("""
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from datetime import date

    def example():
        return date()
    """),
        {'5:0 ' + TC004.format(module='date')},
    ),
    # Used, but only used inside the type checking block
    (
        textwrap.dedent("""
    if TYPE_CHECKING:
        from typing import Any

        CustomType = Any
    """),
        set(),
    ),
    # Used for typing only
    (
        textwrap.dedent("""
    if TYPE_CHECKING:
        from typing import Any

    def example(*args: Any, **kwargs: Any):
        return

    my_type: Type[Any] | Any
    """),
        set(),
    ),
    (
        textwrap.dedent("""
    if TYPE_CHECKING:
        from typing import List, Sequence, Set

    def example(a: List[int], /, b: Sequence[int], *, c: Set[int]):
        return
    """),
        set(),
    ),
    # Used different places, but where each function scope has it's own import
    (
        textwrap.dedent("""
    if TYPE_CHECKING:
        from pandas import DataFrame

    def example():
        from pandas import DataFrame
        x = DataFrame
    """),
        set(),
    ),
    (
        textwrap.dedent("""
    from __future__ import annotations

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from typing import AsyncIterator, List


    class Example:

        async def example(self) -> AsyncIterator[List[str]]:
            yield 0
    """),
        set(),
    ),
    (
        textwrap.dedent("""
    from typing import TYPE_CHECKING
    from weakref import WeakKeyDictionary

    if TYPE_CHECKING:
        from typing import Any


    d = WeakKeyDictionary["Any", "Any"]()
    """),
        set(),
    ),
    (
        textwrap.dedent("""
    if TYPE_CHECKING:
        import a
        import b
        import c
        import d

    def test_function(a, /, b, *, c, **d):
        print(a, b, c, d)
    """),
        set(),
    ),
    # Regression test for #131
    # handle scopes correctly
    (
        textwrap.dedent("""
        if TYPE_CHECKING:
            from a import Foo

        def foo():
            if TYPE_CHECKING:
                from b import Foo
            else:
                Foo = object

            bar: Foo = Foo()
            return bar

        class X:
            if TYPE_CHECKING:
                from b import Foo
            else:
                Foo = object

            bar: Foo = Foo()

        """),
        set(),
    ),
    # Inverse Regression test for #131
    # handle scopes correctly, so we should get an error for the imports
    # in the inner scopes, but not one for the outer scope.
    (
        textwrap.dedent("""
        if TYPE_CHECKING:
            from a import Foo

        def foo():
            if TYPE_CHECKING:
                from b import Foo

            bar: Foo = Foo()
            return bar

        class X:
            if TYPE_CHECKING:
                from b import Foo

            bar: Foo = Foo()

        """),
        {
            '7:0 ' + TC004.format(module='Foo'),
            '14:0 ' + TC004.format(module='Foo'),
        },
    ),
    # Some more complex scope cases where we shouldn't report a
    # runtime use of a typing only symbol, because it is shadowed
    # by an inline definition. We use five different symbols
    # since comprehension scopes will probably leak their iterator
    # variables in the future, just like regular loops, due to
    # comprehension inlining. So we currently treat definitions inside
    # a comprehension as if it occured outside. We may change our minds
    # about this in the future, but comprehension scopes have a bunch of
    # special rules (such as being able to access enclosing class scopes)
    # so it's either to not treat them as separate scopes for now.
    (
        textwrap.dedent("""
        if TYPE_CHECKING:
            from foo import v, w, x, y, z

        (v for v in foo)
        [w for bar in foo if (w := bar)]
        {{x for bar in foo for x in bar}}
        {{y: baz for y, bar in foo for baz in y}}
        foo = z if (z := bar) else None

        """),
        set(),
    ),
    # Inverse test for complex cases
    (
        textwrap.dedent("""
        if TYPE_CHECKING:
            from foo import v, w, x, y, z

        (v(a) for a in foo)
        [w(a) for a in foo]
        {{x(a) for a in foo}}
        {{a: y for a in foo}}
        x = foo if (foo := z) else None

        """),
        {
            '3:0 ' + TC004.format(module='v'),
            '3:0 ' + TC004.format(module='w'),
            '3:0 ' + TC004.format(module='x'),
            '3:0 ' + TC004.format(module='y'),
            '3:0 ' + TC004.format(module='z'),
        },
    ),
    # functools.singledispatch
    (
        textwrap.dedent("""
            import functools

            if TYPE_CHECKING:
                from foo import FooType

            @functools.singledispatch
            def foo(arg: FooType) -> int:
                return 1
            """),
        {'5:0 ' + TC004.format(module='FooType')},
    ),
    (
        textwrap.dedent("""
            from functools import singledispatch

            if TYPE_CHECKING:
                from foo import FooType

            @functools.singledispatch
            def foo(arg: FooType) -> int:
                return 1
            """),
        {'5:0 ' + TC004.format(module='FooType')},
    ),
    (
        textwrap.dedent("""
            from functools import singledispatchmethod

            if TYPE_CHECKING:
                from foo import FooType

            class Foo:
                @functools.singledispatch
                def foo(self, arg: FooType) -> int:
                    return 1
            """),
        {'5:0 ' + TC004.format(module='FooType')},
    ),
]


@pytest.mark.parametrize('py314plus', [False, True])
@pytest.mark.parametrize(('example', 'expected'), examples)
def test_TC004_errors(example, expected, py314plus):
    assert _get_error(example, error_code_filter='TC004', type_checking_py314plus=py314plus) == expected
    if py314plus and 'from __future__ import annotations' in example:
        # removing the future annotation should not change the outcome
        example = example.replace('from __future__ import annotations', '')
        assert _get_error(example, error_code_filter='TC004', type_checking_py314plus=py314plus) == expected
