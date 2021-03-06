from typing import TYPE_CHECKING

from flake8_typing_only_imports.checker import TypingOnlyImportsChecker
from flake8_typing_only_imports.constants import disabled_by_default, enabled_by_default

if TYPE_CHECKING:
    from ast import Module
    from typing import Generator

    from flake8.options.manager import OptionManager

import sys

if sys.version_info <= (3, 8):
    import importlib_metadata
else:
    import importlib.metadata as importlib_metadata


class Plugin:
    """Flake8 plugin."""

    name = __name__
    version = importlib_metadata.version(__name__)

    __slots__ = ('_tree',)

    def __init__(self, tree: 'Module') -> None:
        self._tree = tree

    def run(self) -> 'Generator':
        """Run flake8 plugin and return any relevant errors."""
        visitor = TypingOnlyImportsChecker(self._tree)
        yield from visitor.errors

    @staticmethod
    def add_options(mgr: 'OptionManager') -> None:
        """Informs flake8 to ignore TYO101 and TYO201 by default."""
        mgr.extend_default_ignore(disabled_by_default)
        mgr.extend_default_select(enabled_by_default)
