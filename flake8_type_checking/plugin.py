from __future__ import annotations

import logging
from dataclasses import dataclass
from importlib.metadata import version as v
from typing import TYPE_CHECKING, ClassVar

from flake8_type_checking.checker import TypingOnlyImportsChecker
from flake8_type_checking.constants import flake_version_gt_v4

if TYPE_CHECKING:
    from argparse import Namespace
    from ast import Module
    from typing import Optional

    from flake8.options.manager import OptionManager

    from flake8_type_checking.types import Flake8Generator

logger = logging.getLogger('flake8.type_checking')


@dataclass(frozen=True)
class Plugin:
    """Flake8 plugin."""

    tree: Module
    filename: str
    options: Optional[Namespace] = None

    name: ClassVar[str] = 'flake8-type-checking'
    version: ClassVar[str] = v('flake8-type-checking')

    @classmethod
    def add_options(cls, option_manager: OptionManager) -> None:  # pragma: no cover
        """Parse plugin options."""
        option_manager.add_option(
            '--type-checking-exempt-modules',
            comma_separated_list=True,
            parse_from_config=True,
            default=[],
            help='Skip TC001, TC002, and TC003 checks for specified modules or libraries.',
        )
        option_manager.add_option(
            '--type-checking-strict',
            action='store_true',
            parse_from_config=True,
            default=False,
            help='Flag individual imports rather than looking at the module.',
        )

        # Third-party library options
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
        option_manager.add_option(
            '--type-checking-cattrs-enabled',
            action='store_true',
            parse_from_config=True,
            default=False,
            help='Prevent flagging of annotations on attrs class definitions.',
        )

    def run(self) -> Flake8Generator:
        """Run flake8 plugin and return any relevant errors."""
        visitor = TypingOnlyImportsChecker(self.tree, self.options)

        for e in visitor.errors:
            code = e[2].split(':')[0]
            if self.filename.endswith('.pyi') and code.startswith('TC100'):
                # Stub files don't need futures imports
                # context: https://github.com/snok/flake8-type-checking/issues/121
                continue
            if self.should_warn(code):
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

        selected_rules = tuple(
            list(self.options.select or [])
            + list(self.options.extended_default_select or [])
            + list(self.options.enable_extensions or []),
        )

        if flake_version_gt_v4:
            selected_rules += tuple(self.options.extend_select or [])

        for i in range(3, len(code) + 1):
            if code[:i] in selected_rules:
                # Warn if opted-in
                return True

        # Don't warn if not opted-in
        logger.info(
            'Optional warning %s not present in selected warnings: %r. Not running it at all.',
            code,
            selected_rules,
        )
        return False
