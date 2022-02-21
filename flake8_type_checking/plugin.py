from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from flake8_type_checking.checker import TypingOnlyImportsChecker

if TYPE_CHECKING:
    from argparse import Namespace
    from ast import Module
    from typing import Optional

    from flake8.options.manager import OptionManager

    from flake8_type_checking.types import Flake8Generator


if sys.version_info >= (3, 8):
    from importlib.metadata import version
else:
    # noinspection PyUnresolvedReferences
    from importlib_metadata import version

logger = logging.getLogger('flake8.type_checking')


class Plugin:
    """Flake8 plugin."""

    name = 'flake8-type-checking'
    version = version('flake8-type-checking')

    __slots__ = ('_tree', 'options')

    def __init__(self, tree: Module, options: Optional[Namespace] = None) -> None:
        self._tree = tree
        self.options = options

    @classmethod
    def add_options(cls, option_manager: OptionManager) -> None:
        """Parse plugin options."""
        option_manager.add_option(
            '--type-checking-exempt-modules',
            comma_separated_list=True,
            parse_from_config=True,
            default=[],
            help='Skip TC001 and TC002 checks for specified modules or libraries.',
        )
        option_manager.add_option(
            '--type-checking-pydantic-enabled',
            action='store_true',
            parse_from_config=True,
            default=False,
            help='Prevent flagging of annotations for class definitions.',
        )
        option_manager.add_option(
            '--type-checking-pydantic-enabled-baseclass-passlist',
            comma_separated_list=True,
            parse_from_config=True,
            default=[],
            help='Names of base classes to not treat as pydantic models. For example `NamedTuple` or `TypedDict`.',
        )
        option_manager.add_option(
            '--type-checking-fastapi-enabled',
            action='store_true',
            parse_from_config=True,
            default=False,
            help='Prevent flagging of annotations for decorated functions.',
        )
        option_manager.add_option(
            '--type-checking-fastapi-dependency-support-enabled',
            action='store_true',
            parse_from_config=True,
            default=False,
            help='Prevent flagging of annotations for any function.',
        )

    def run(self) -> Flake8Generator:
        """Run flake8 plugin and return any relevant errors."""
        visitor = TypingOnlyImportsChecker(self._tree, self.options)
        for e in visitor.errors:
            if self.should_warn(e[2].split(':')[0]):
                yield e

    def should_warn(self, code: str) -> bool:
        """
        Decide whether we should emit a particular warning.

        Flake8 overrides default ignores when the user specifies `ignore = ` in their configuration.
        This is problematic because it means specifying anything in `ignore = ` implicitly enables all optional
        warnings.

        This function is a workaround for this behavior. Stolen from flake8-bugbear because it's good.
        """
        logger.debug('Received code %s', code)

        if code[2] == '0':
            # Any error in the TC0XX range is safe to include by default
            logger.debug('Returning true for code %s, as it is in the 0s range', code)
            return True

        # Our desired behavior is to have the TC100 and TC200 range disabled by default
        # so users can opt-in to just one of them. If they've been selected in the flake8
        # config that overrides the default

        if self.options is None:
            # Don't warn if not opted-in
            logger.info('Options not provided to flake8-type-checking, optional warning %s selected.', code)
            return False

        for i in range(3, len(code) + 1):
            if code[:i] in (
                self.options.select
                + list(self.options.extended_default_select)
                + (self.options.enable_extensions or [])
            ):
                # Warn if opted-in
                return True

        # Don't warn if not opted-in
        logger.info(
            'Optional warning %s not present in selected warnings: %r. Not running it at all.',
            code,
            self.options.select,
        )
        return False
