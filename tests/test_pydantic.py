"""
This file tests pydantic support.

See https://github.com/snok/flake8-type-checking/issues/52
for discussion on the implementation.
"""

import textwrap

import pytest

from flake8_type_checking.constants import TC002
from tests import _get_error


@pytest.mark.parametrize(
    'enabled, expected',
    (
        [True, {'2:0 ' + TC002.format(module='pandas.DataFrame')}],
        [False, {'2:0 ' + TC002.format(module='pandas.DataFrame')}],
    ),
)
def test_non_pydantic_model(enabled, expected):
    """
    A class cannot be a pydantic model if it doesn't have a base class,
    so we should raise the same error here in both cases.
    """
    example = textwrap.dedent(
        '''
        from pandas import DataFrame

        class X:
            x: DataFrame
        '''
    )
    assert _get_error(example, error_code_filter='TC002', type_checking_pydantic_enabled=enabled) == expected


def test_class_with_base_class():
    """
    Whenever a class inherits from anything, we need
    to assume it might be a pydantic model, for which
    we need to register annotations as uses.
    """
    example = textwrap.dedent(
        '''
        from pandas import DataFrame

        class X(Y):
            x: DataFrame
        '''
    )
    assert _get_error(example, error_code_filter='TC002', type_checking_pydantic_enabled=True) == set()


def test_complex_pydantic_model():
    """
    Test actual Pydantic models, with different annotation types.
    """
    example = textwrap.dedent(
        '''
        from __future__ import annotations

        from datetime import datetime
        from pandas import DataFrame
        from typing import TYPE_CHECKING

        from pydantic import BaseModel, condecimal, validator

        if TYPE_CHECKING:
            from datetime import date
            from typing import Union


        def format_datetime(value: Union[str, datetime]) -> datetime:
            if isinstance(value, str):
                value = datetime.strptime(value, '%Y-%m-%dT%H:%M:%S.%f%z')
            assert isinstance(value, datetime)
            return value


        class ModelBase(BaseModel):
            id: int
            created_at: datetime
            updated_at: datetime

            _format_datetime = validator('created_at', 'updated_at', pre=True, allow_reuse=True)(format_datetime)


        class NestedModel(ModelBase):
            z: DataFrame
            x: int
            y: str


        class FinalModel(ModelBase):
            a: str
            b: int
            c: float
            d: bool
            e: date
            f: NestedModel
            g: condecimal(ge=Decimal(0)) = Decimal(0)

        '''
    )
    assert _get_error(example, error_code_filter='TC002', type_checking_pydantic_enabled=True) == set()


@pytest.mark.parametrize('c', ['NamedTuple', 'TypedDict'])
def test_type_checking_pydantic_enabled_baseclass_passlist(c):
    """
    Test that named tuples are not ignored.
    """
    example = textwrap.dedent(
        f'''
        from typing import {c}
        from x import Y, Z

        class ModelBase({c}):
            a: Y[str]
            b: Z[int]
        '''
    )
    assert _get_error(
        example,
        error_code_filter='TC002',
        type_checking_pydantic_enabled=True,
        type_checking_pydantic_enabled_baseclass_passlist=['NamedTuple', 'TypedDict'],
    ) == {
        '3:0 ' + TC002.format(module='x.Y'),
        '3:0 ' + TC002.format(module='x.Z'),
    }
