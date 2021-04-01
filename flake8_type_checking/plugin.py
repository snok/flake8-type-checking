from __future__ import annotations

from typing import TYPE_CHECKING

from flake8_type_checking.checker import TypingOnlyImportsChecker

if TYPE_CHECKING:
    from ast import Module
    from typing import Generator

import sys

if sys.version_info >= (3, 8):
    from importlib.metadata import version
else:
    # noinspection PyUnresolvedReferences
    from importlib_metadata import version


class Plugin:
    """Flake8 plugin."""

    name = 'flake8-type-checking'
    version = version('flake8-type-checking')

    __slots__ = ('_tree',)

    def __init__(self, tree: Module) -> None:
        self._tree = tree

    def run(self) -> Generator:
        """Run flake8 plugin and return any relevant errors."""
        visitor = TypingOnlyImportsChecker(self._tree)
        yield from visitor.errors
