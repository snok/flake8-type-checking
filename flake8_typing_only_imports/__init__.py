from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from flake8_typing_only_imports.checker import TypingOnlyImportsChecker
from flake8_typing_only_imports.constants import disabled_by_default

if TYPE_CHECKING:
    from argparse import Namespace
    from ast import Module
    from typing import Generator

    from flake8.options.manager import OptionManager

if sys.version_info >= (3, 8):
    from importlib.metadata import version
else:
    # noinspection PyUnresolvedReferences
    from importlib_metadata import version


class Plugin:
    """Flake8 plugin."""

    name = 'flake8-typing-only-imports'
    version = version('flake8-typing-only-imports')

    __slots__ = ('_tree',)

    def __init__(self, tree: Module) -> None:
        self._tree = tree

    def run(self) -> Generator:
        """Run flake8 plugin and return any relevant errors."""
        visitor = TypingOnlyImportsChecker(self._tree)
        yield from visitor.errors

    @staticmethod
    def parse_options(optmanager: OptionManager, options: Namespace, extra_args: list) -> None:
        """Informs flake8 to ignore all errors except TYO100."""
        optmanager.extend_default_ignore(disabled_by_default)
