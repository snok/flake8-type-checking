"""
This file tests the TYO101 error: unused remote imports.

Some things to note: local/remote is a pretty arbitrary divide, and remote here really just means
not from the module our current working directory is in, or in the current working dir, but inside a venv.
"""
import os
import textwrap

import pytest

from flake8_typing_only_imports.constants import TYO100
from tests import REPO_ROOT, _get_error, mod

examples = [
    # No error
    ('', set()),
    # Unused local ast.Import
    (f'import {mod}', {'1:0 ' + TYO100.format(module=f'{mod}')}),
    (f'\nimport {mod}', {'2:0 ' + TYO100.format(module=f'{mod}')}),
    # Unused local ast.ImportFrom
    (f'from {mod} import Plugin', {'1:0 ' + TYO100.format(module=f'{mod}.Plugin')}),
    (f'\n\nfrom {mod} import constants', {'3:0 ' + TYO100.format(module=f'{mod}.constants')}),
]


@pytest.mark.parametrize('example, expected', examples)
def test_errors(example, expected):
    assert (
        _get_error(example) == expected
    ), f"No match for example: '{example}'. Found '{_get_error(example)}' instead of '{expected}'"


def test_no_error_raised_when_unused_imports_declared_in_type_checking_block():
    example = textwrap.dedent(
        f"""
    import {mod}
    from {mod} import Plugin

    if TYPE_CHECKING:
        import a

        # arbitrary whitespace

        from b import c

    def test():
        pass
    """
    )
    assert _get_error(example) == {
        '2:0 ' + TYO100.format(module=f'{mod}'),
        '3:0 ' + TYO100.format(module=f'{mod}.Plugin'),
    }
