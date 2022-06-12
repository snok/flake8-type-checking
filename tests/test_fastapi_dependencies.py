"""
This file tests FastAPI decorator support.

See https://github.com/snok/flake8-type-checking/issues/52
for discussion on the implementation.
"""

import textwrap

import pytest

from flake8_type_checking.constants import TC002
from tests import _get_error


@pytest.mark.parametrize('fdef', ['def', 'async def'])
def test_api_router_decorated_function(fdef):
    """
    Test sync and async function definition, with an arg and a kwarg.
    """
    example = textwrap.dedent(
        f'''
        from fastapi import APIRouter

        from app.models import SomeModel
        from app.services import some_function
        from app.types import CustomType

        some_router = APIRouter(prefix='/some-path')

        {fdef} list_something(resource_id: CustomType, some_model: SomeModel = Depends(some_function)):
            return None
        '''
    )
    assert _get_error(example, error_code_filter='TC001,TC002,TC003', type_checking_fastapi_enabled=True) == {
        '4:0 ' + TC002.format(module='app.models.SomeModel'),
        '6:0 ' + TC002.format(module='app.types.CustomType'),
    }
    assert (
        _get_error(
            example, error_code_filter='TC001,TC002,TC003', type_checking_fastapi_dependency_support_enabled=True
        )
        == set()
    )
