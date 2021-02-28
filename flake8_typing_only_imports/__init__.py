from typing import TYPE_CHECKING

from flake8_typing_only_imports.checker import TypingOnlyImportsChecker
from flake8_typing_only_imports.constants import disabled_by_default

if TYPE_CHECKING:
    from ast import Module
    from typing import Generator

    from flake8.options.manager import OptionManager


class Plugin:
    """Flake8 plugin."""

    name = 'flake8-typing-only-imports'
    version = '0.1.5'

    def __init__(self, tree: 'Module') -> None:
        self.tree = tree

    def run(self) -> 'Generator':
        """Run flake8 plugin and return any relevant errors."""
        visitor = TypingOnlyImportsChecker(self.tree)
        yield from visitor.errors

    @staticmethod
    def add_options(mgr: 'OptionManager') -> None:
        """Informs flake8 to ignore TYO101 by default."""
        mgr.extend_default_ignore(disabled_by_default)
