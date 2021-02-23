from typing import TYPE_CHECKING

from flake8_typing_only_imports.ast import Checker

if TYPE_CHECKING:  # pragma: no_cover
    from ast import Module   # pragma: no_cover
    from typing import Generator  # pragma: no_cover


class Plugin:
    """Flake8 plugin."""

    name = 'flake8-typing-only-imports'
    version = '0.1.0'

    def __init__(self, tree: 'Module') -> None:
        self.tree = tree

    def run(self) -> 'Generator':
        """Run flake8 plugin and return any relevant errors."""
        visitor = Checker(self.tree)
        yield from visitor.errors
