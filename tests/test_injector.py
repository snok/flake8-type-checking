"""This file tests injector support."""

import textwrap

import pytest

from flake8_type_checking.constants import TC002
from tests.conftest import _get_error


@pytest.mark.parametrize(
    ('enabled', 'expected'),
    [
        (True, {'2:0 ' + TC002.format(module='services.Service')}),
        (False, {'2:0 ' + TC002.format(module='services.Service')}),
    ],
)
def test_non_pydantic_model(enabled, expected):
    """A class does not use injector, so error should be risen in both scenarios."""
    example = textwrap.dedent('''
        from services import Service

        class X:
            def __init__(self, service: Service) -> None:
                self.service = service
        ''')
    assert _get_error(example, error_code_filter='TC002', type_checking_pydantic_enabled=enabled) == expected


@pytest.mark.parametrize(
    ('enabled', 'expected'),
    [
        (True, set()),
        (False, {'2:0 ' + TC002.format(module='injector.Inject'), '3:0 ' + TC002.format(module='services.Service')}),
    ],
)
def test_injector_option(enabled, expected):
    """When an injector option is enabled, injector should be ignored."""
    example = textwrap.dedent('''
        from injector import Inject
        from services import Service

        class X:
            def __init__(self, service: Inject[Service]) -> None:
                self.service = service
        ''')
    assert _get_error(example, error_code_filter='TC002', type_checking_injector_enabled=enabled) == expected


@pytest.mark.parametrize(('enabled', 'expected'), [(True, set())])
def test_injector_option_only_allows_injected_dependencies(enabled, expected):
    """Whenever an injector option is enabled, only injected dependencies should be ignored."""
    example = textwrap.dedent('''
        from injector import Inject
        from services import Service
        from other_dependency import OtherDependency

        class X:
            def __init__(self, service: Inject[Service], other: OtherDependency) -> None:
                self.service = service
                self.other = other
        ''')
    assert _get_error(example, error_code_filter='TC002', type_checking_injector_enabled=enabled) == expected


@pytest.mark.parametrize(('enabled', 'expected'), [(True, set())])
def test_injector_option_only_allows_injector_slices(enabled, expected):
    """
    Whenever an injector option is enabled, only injected dependencies should be ignored,
    not any dependencies with slices.
    """
    example = textwrap.dedent("""
        from injector import Inject
        from services import Service
        from other_dependency import OtherDependency

        class X:
            def __init__(self, service: Inject[Service], other_deps: list[OtherDependency]) -> None:
                self.service = service
                self.other_deps = other_deps
        """)
    assert _get_error(example, error_code_filter='TC002', type_checking_injector_enabled=enabled) == expected


@pytest.mark.parametrize(('enabled', 'expected'), [(True, set())])
def test_injector_option_require_injections_under_unpack(enabled, expected):
    """Whenever an injector option is enabled, injected dependencies should be ignored, even if unpacked."""
    example = textwrap.dedent("""
        from typing import Unpack

        from injector import Inject
        from services import ServiceKwargs

        class X:
            def __init__(self, service: Inject[Service], **kwargs: Unpack[ServiceKwargs]) -> None:
                self.service = service
                self.args = args
        """)
    assert _get_error(example, error_code_filter='TC002', type_checking_injector_enabled=enabled) == expected


@pytest.mark.parametrize(
    ('enabled', 'expected'),
    [
        (True, set()),
        (False, {'2:0 ' + TC002.format(module='injector'), '3:0 ' + TC002.format(module='services.Service')}),
    ],
)
def test_injector_option_allows_injector_as_module(enabled, expected):
    """Whenever an injector option is enabled, injected dependencies should be ignored, even if import as module."""
    example = textwrap.dedent('''
            import injector
            from services import Service

            class X:
                def __init__(self, service: injector.Inject[Service]) -> None:
                    self.service = service
            ''')
    assert _get_error(example, error_code_filter='TC002', type_checking_injector_enabled=enabled) == expected


@pytest.mark.parametrize(
    ('enabled', 'expected'),
    [
        (True, set()),
        (False, {'2:0 ' + TC002.format(module='injector.Inject'), '3:0 ' + TC002.format(module='services.Service')}),
    ],
)
def test_injector_option_only_mentioned_second_time(enabled, expected):
    """Whenever an injector option is enabled, dependency referenced second time is accepted."""
    example = textwrap.dedent("""
        from injector import Inject
        from services import Service

        class X:
            def __init__(self, service: Inject[Service], other_deps: list[Service]) -> None:
                self.service = service
                self.other_deps = other_deps
        """)
    assert _get_error(example, error_code_filter='TC002', type_checking_injector_enabled=enabled) == expected
