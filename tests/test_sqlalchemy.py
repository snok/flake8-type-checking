"""
This file tests SQLAlchemy support.

See https://github.com/snok/flake8-type-checking/issues/178
for discussion on the implementation.
"""

import textwrap

import pytest

from flake8_type_checking.constants import TC002, TC004
from tests.conftest import _get_error


@pytest.mark.parametrize(
    ('enabled', 'expected'),
    [
        (True, set()),
        (False, {'2:0 ' + TC002.format(module='foo.Bar'), '3:0 ' + TC002.format(module='sqlalchemy.orm.Mapped')}),
    ],
)
def test_simple_mapped_use(enabled, expected):
    """
    Mapped itself must be available at runtime and the inner type may or
    may not need to be available at runtime.
    """
    example = textwrap.dedent('''
        from foo import Bar
        from sqlalchemy.orm import Mapped

        class User:
            x: Mapped[Bar]
        ''')
    assert _get_error(example, error_code_filter='TC002', type_checking_sqlalchemy_enabled=enabled) == expected


@pytest.mark.parametrize(
    ('name', 'expected', 'star_import'),
    [
        ('Mapped', set(), False),
        ('Mapped', set(), True),
        ('DynamicMapped', set(), False),
        ('DynamicMapped', set(), True),
        ('WriteOnlyMapped', set(), False),
        ('WriteOnlyMapped', set(), True),
        (
            'NotMapped',
            {'2:0 ' + TC002.format(module='foo.Bar'), '3:0 ' + TC002.format(module='sqlalchemy.orm.NotMapped')},
            False,
        ),
        (
            'NotMapped',
            # as a star-import it won't trigger TC002, but the other import still will
            {'2:0 ' + TC002.format(module='foo.Bar')},
            True,
        ),
    ],
)
def test_default_mapped_names(name, expected, star_import):
    """Check the three default names and a bogus name."""
    example = textwrap.dedent(f'''
        from foo import Bar
        from sqlalchemy.orm import {"*" if star_import else name}

        class User:
            x: {name}[Bar]
        ''')
    assert _get_error(example, error_code_filter='TC002', type_checking_sqlalchemy_enabled=True) == expected


def test_mapped_with_circular_forward_reference():
    """
    Mapped must still be available at runtime even with forward references
    to a different model.
    """
    example = textwrap.dedent('''
        from sqlalchemy.orm import Mapped
        if TYPE_CHECKING:
            from .address import Address

        class User:
            address: Mapped['Address']
        ''')
    assert _get_error(example, error_code_filter='TC002', type_checking_sqlalchemy_enabled=True) == set()


def test_mapped_use_without_runtime_import():
    """
    Mapped must be available at runtime, so even if it is inside a wrapped annotation
    we should raise a TC004 for Mapped but not for Bar
    """
    example = textwrap.dedent('''
        if TYPE_CHECKING:
            from foo import Bar
            from sqlalchemy.orm import Mapped

        class User:
            created: 'Mapped[Bar]'
        ''')
    assert _get_error(example, error_code_filter='TC004', type_checking_sqlalchemy_enabled=True) == {
        '4:0 ' + TC004.format(module='Mapped')
    }


def test_custom_mapped_dotted_names_unwrapped():
    """
    Check a couple of custom dotted names and a bogus one. This also tests the
    various styles of imports
    """
    example = textwrap.dedent('''
        import a
        import a.b as ab
        from a import b
        from a import MyMapped
        from a.b import MyMapped as B
        from a import Bogus
        from foo import Bar

        class User:
            t: MyMapped[Bar]
            u: B[Bar]
            v: Bogus[Bar]
            w: a.MyMapped[Bar]
            x: b.MyMapped[Bar]
            y: a.b.MyMapped[Bar]
            z: ab.MyMapped[Bar]
        ''')
    assert _get_error(
        example,
        error_code_filter='TC002',
        type_checking_strict=True,  # ignore overlapping imports for this test
        type_checking_sqlalchemy_enabled=True,
        type_checking_sqlalchemy_mapped_dotted_names=['a.MyMapped', 'a.b.MyMapped'],
    ) == {'7:0 ' + TC002.format(module='a.Bogus')}


def test_custom_mapped_dotted_names_wrapped():
    """
    Same as the unwrapped test but with wrapped annotations. This should generate
    a bunch of TC004 errors for the uses of mapped that should be available at runtime.
    """
    example = textwrap.dedent('''
        if TYPE_CHECKING:
            import a
            import a.b as ab
            from a import b
            from a import MyMapped
            from a.b import MyMapped as B
            from a import Bogus
            from foo import Bar

        class User:
            t: 'MyMapped[Bar]'
            u: 'B[Bar]'
            v: 'Bogus[Bar]'
            w: 'a.MyMapped[Bar]'
            x: 'b.MyMapped[Bar]'
            y: 'a.b.MyMapped[Bar]'
            z: 'ab.MyMapped[Bar]'
        ''')
    assert _get_error(
        example,
        error_code_filter='TC004',
        type_checking_sqlalchemy_enabled=True,
        type_checking_sqlalchemy_mapped_dotted_names=['a.MyMapped', 'a.b.MyMapped'],
    ) == {
        '3:0 ' + TC004.format(module='a'),
        '4:0 ' + TC004.format(module='ab'),
        '5:0 ' + TC004.format(module='b'),
        '6:0 ' + TC004.format(module='MyMapped'),
        '7:0 ' + TC004.format(module='B'),
    }
