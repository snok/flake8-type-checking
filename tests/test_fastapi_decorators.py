"""
This file tests FastAPI decorator support.

See https://github.com/snok/flake8-type-checking/issues/52
for discussion on the implementation.
"""

import textwrap

import pytest

from flake8_type_checking.constants import TC002
from tests.conftest import _get_error

defaults = {'type_checking_fastapi_enabled': True}


@pytest.mark.parametrize('fdef', ['def', 'async def'])
def test_api_router_decorated_function(fdef):
    """Test sync and async function definition, with an arg and a kwarg."""
    example = textwrap.dedent(
        f'''
        from fastapi import APIRouter

        from app.models import SomeModel
        from app.services import some_function
        from app.types import CustomType

        some_router = APIRouter(prefix='/some-path')

        @some_router.get('/{{resource_id}}')
        {fdef} list_something(resource_id: CustomType, some_model: SomeModel = Depends(some_function)):
            return None
        '''
    )
    assert _get_error(example, error_code_filter='TC001,TC002,TC003', **defaults) == set()


@pytest.mark.parametrize('fdef', ['def', 'async def'])
def test_api_router_decorated_function_return_type(fdef):
    """
    We don't care about return types. To my knowledge,
    these are not evaluated by FastAPI/pydantic.
    """
    example = textwrap.dedent(
        f'''
        from fastapi import APIRouter
        from fastapi import Request

        from app.types import CustomType

        some_router = APIRouter(prefix='/some-path')

        @some_router.get('/{{resource_id}}')
        {fdef} list_something(request: Request) -> CustomType:
            return None
        '''
    )
    assert _get_error(example, error_code_filter='TC001,TC002,TC003', **defaults) == {
        '5:0 ' + TC002.format(module='app.types.CustomType')
    }


@pytest.mark.parametrize('fdef', ['def', 'async def'])
def test_api_router_decorated_nested_function(fdef):
    example = textwrap.dedent(
        f'''
        import logging

        from typing import TYPE_CHECKING

        from fastapi import APIRouter, Request

        if TYPE_CHECKING:
            from starlette.responses import RedirectResponse

        logger = logging.getLogger(__name__)


        def get_auth_router() -> APIRouter:
            router = APIRouter(tags=['Auth'], include_in_schema=False)

            @router.get('/login')
            {fdef} login(request: Request) -> "RedirectResponse":
                ...

        '''
    )
    assert _get_error(example, error_code_filter='TC001,TC002,TC003', **defaults) == set()


@pytest.mark.parametrize('fdef', ['def', 'async def'])
def test_app_decorated_function(fdef):
    example = textwrap.dedent(
        f'''
        from app.main import app
        from app.models import SomeModel
        from app.types import CustomType

        @app.get('/{{resource_id}}')
        {fdef} list_something(resource_id: CustomType, some_model: SomeModel = Depends(lambda: 1)):
            return None
        '''
    )
    assert _get_error(example, error_code_filter='TC001,TC002,TC003', **defaults) == set()
