from __future__ import annotations

import ast
import fnmatch
import os
import sys
from ast import Index, literal_eval
from contextlib import suppress
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING, Literal, NamedTuple, cast

from classify_imports import Classified, classify_base

from flake8_type_checking.constants import (
    ANNOTATION_PROPERTY,
    ATTRIBUTE_PROPERTY,
    ATTRS_DECORATORS,
    ATTRS_IMPORTS,
    GLOBAL_PROPERTY,
    NAME_RE,
    TC001,
    TC002,
    TC003,
    TC004,
    TC005,
    TC006,
    TC007,
    TC008,
    TC100,
    TC101,
    TC200,
    TC201,
    py38,
)

try:
    ast_unparse = ast.unparse  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover
    # Python < 3.9

    import astor

    def ast_unparse(node: ast.AST) -> str:
        """AST unparsing helper for Python < 3.9."""
        return cast('str', astor.to_source(node)).strip()


if TYPE_CHECKING:
    from _ast import AsyncFunctionDef, FunctionDef
    from argparse import Namespace
    from typing import Any, Optional, Union

    from flake8_type_checking.types import (
        Flake8Generator,
        FunctionRangesDict,
        FunctionScopeNamesDict,
        Import,
        ImportTypeValue,
        Name,
    )


class AttrsMixin:
    """
    Contains necessary logic for cattrs + attrs support.

    When the cattrs_enabled option is specified as True,
    we treat type hints on attrs classes as needed at runtime.
    """

    if TYPE_CHECKING:
        third_party_imports: dict[str, Import]

    def get_all_attrs_imports(self) -> dict[Optional[str], str]:
        """Return a map of all attrs/attr imports."""
        attrs_imports: dict[Optional[str], str] = {}  # map of alias to full import name

        for node in self.third_party_imports.values():
            module = getattr(node, 'module', '')
            names: list[Name] = getattr(node, 'names', [])

            for name in names:
                if module in ATTRS_IMPORTS:
                    alias = name.name if name.asname is None else name.asname
                    attrs_imports[alias] = f'{module}.{name.name}'
                elif name.name.split('.')[0] in ATTRS_IMPORTS:
                    attrs_imports[name.asname] = name.name

        return attrs_imports

    def is_attrs_class(self, class_node: ast.ClassDef) -> bool:
        """Check whether an ast.ClassDef is an attrs class or not."""
        attrs_imports = self.get_all_attrs_imports()
        return any(self.is_attrs_decorator(decorator, attrs_imports) for decorator in class_node.decorator_list)

    def is_attrs_decorator(self, decorator: Any, attrs_imports: dict[Optional[str], str]) -> bool:
        """Check whether a class decorator is an attrs decorator or not."""
        if isinstance(decorator, ast.Call):
            return self.is_attrs_decorator(decorator.func, attrs_imports)
        elif isinstance(decorator, ast.Attribute):
            return self.is_attrs_attribute(decorator)
        elif isinstance(decorator, ast.Name):
            return self.is_attrs_str(decorator.id, attrs_imports)
        return False

    @staticmethod
    def is_attrs_attribute(attribute: ast.Attribute) -> bool:
        """Check whether an ast.Attribute is an attrs attribute or not."""
        s1 = f"attr.{getattr(attribute, 'attr', '')}"
        s2 = f"attrs.{getattr(attribute, 'attrs', '')}"
        actual = [s1, s2]
        return any(e for e in actual if e in ATTRS_DECORATORS)

    @staticmethod
    def is_attrs_str(attribute: Union[str, ast.expr], attrs_imports: dict[Optional[str], str]) -> bool:
        """Check whether an ast.expr or string is an attrs string or not."""
        actual = attrs_imports.get(str(attribute), '')
        return actual in ATTRS_DECORATORS


class DunderAllMixin:
    """
    Contains the necessary logic for preventing __all__ false positives.

    Python modules will typically export internals using syntax like this:

    ```python
    # app/__init__.py

    from app.x import y

    __all__ ('y',)
    ```

    Since there are no uses of the `do_something_important` we would typically raise
    a TC001 error saying that this import can be moved into a type checking block, but
    this is an exception to the general rule.
    """

    if TYPE_CHECKING:
        uses: dict[str, ast.AST]

        def generic_visit(self, node: ast.AST) -> None:  # noqa: D102
            ...

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.__all___assignments: list[tuple[int, int]] = []

    def in___all___declaration(self, node: ast.Constant) -> bool:
        """
        Indicate whether a node is a sub-node of an __all__ assignment node.

        We want to avoid raising TC001 errors when imports are defined
        as strings, like this:

        This is a little tricky though. We can't just add string definitions
        to our 'uses' map, since that will generate false positives elsewhere.
        Instead we need this helper to tell us when *not* to ignore constants.
        """
        if not self.__all___assignments:
            return False
        if not isinstance(getattr(node, 'value', ''), str):
            return False
        return any(
            (assignment[0] is not None and node.lineno is not None and assignment[1] is not None)
            and (assignment[0] <= node.lineno <= assignment[1])
            for assignment in self.__all___assignments
        )

    def visit_Assign(self, node: ast.Assign) -> ast.Assign:
        """
        Make sure we keep track of all __all__ assignments.

        We would do this in visit_Name, except the name attribute for the assignment's
        target's end_lineno only spans the assignment line, not the whole assignment:

            ^^^^^^^^ this is all the ast.target for __all__ spans
            __all__ = [  <
                'one',   <
                'two',   <
                'three'  < \
            ]            <-- This is the node.value

        So we need to look at the assign element, and inspect both the target(s) and value.
        """
        if len(node.targets) == 1 and getattr(node.targets[0], 'id', '') == '__all__':
            self.__all___assignments.append((node.targets[0].lineno, node.value.end_lineno or node.targets[0].lineno))

        self.generic_visit(node)
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.Constant:
        """Map constant as use, if we're inside an __all__ declaration."""
        if self.in___all___declaration(node):
            self.uses[node.value] = node
        return node


class PydanticMixin:
    """
    Contains the necessary logic for Pydantic support.

    At least the code that could be separated from the main visitor class.
    Some pydantic stuff is still contained in the main class.
    """

    if TYPE_CHECKING:
        pydantic_enabled: bool
        pydantic_validate_arguments_import_name: Optional[str]

        def visit(self, node: ast.AST) -> ast.AST:  # noqa: D102
            ...

    def _function_is_wrapped_by_validate_arguments(self, node: Union[FunctionDef, AsyncFunctionDef]) -> bool:
        if self.pydantic_enabled and node.decorator_list:
            for decorator_node in node.decorator_list:
                if getattr(decorator_node, 'id', '') == self.pydantic_validate_arguments_import_name:
                    return True
        return False

    def visit_FunctionDef(self, node: FunctionDef) -> None:
        """Remove and map function arguments and returns."""
        if self._function_is_wrapped_by_validate_arguments(node):
            for path in [node.args.args, node.args.kwonlyargs, node.args.posonlyargs]:
                for argument in path:
                    if hasattr(argument, 'annotation') and argument.annotation:
                        self.visit(argument.annotation)

    def visit_AsyncFunctionDef(self, node: AsyncFunctionDef) -> None:
        """Remove and map function arguments and returns."""
        if self._function_is_wrapped_by_validate_arguments(node):
            for path in [node.args.args, node.args.kwonlyargs, node.args.posonlyargs]:
                for argument in path:
                    if hasattr(argument, 'annotation') and argument.annotation:
                        self.visit(argument.annotation)


class FastAPIMixin:
    """
    Contains the necessary logic for FastAPI support.

    For FastAPI app/route-decorated views, and for dependencies, we want
    to treat annotations as needed at runtime.
    """

    if TYPE_CHECKING:
        fastapi_enabled: bool
        fastapi_dependency_support_enabled: bool

        def visit(self, node: ast.AST) -> ast.AST:  # noqa: D102
            ...

    def visit_FunctionDef(self, node: FunctionDef) -> None:
        """Remove and map function arguments and returns."""
        super().visit_FunctionDef(node)  # type: ignore[misc]
        if (self.fastapi_enabled and node.decorator_list) or self.fastapi_dependency_support_enabled:
            self.handle_fastapi_decorator(node)

    def visit_AsyncFunctionDef(self, node: AsyncFunctionDef) -> None:
        """Remove and map function arguments and returns."""
        super().visit_AsyncFunctionDef(node)  # type: ignore[misc]
        if (self.fastapi_enabled and node.decorator_list) or self.fastapi_dependency_support_enabled:
            self.handle_fastapi_decorator(node)

    def handle_fastapi_decorator(self, node: Union[AsyncFunctionDef, FunctionDef]) -> None:
        """
        Adjust for FastAPI decorator setting.

        When the FastAPI decorator setting is enabled, treat all annotations from within
        a function definition (except for return annotations) as needed at runtime.

        To achieve this, we just visit the annotations to register them as "uses".
        """
        for path in [node.args.args, node.args.kwonlyargs]:
            for argument in path:
                if hasattr(argument, 'annotation') and argument.annotation:
                    self.visit(argument.annotation)
        if (
            hasattr(node.args, 'kwarg')
            and node.args.kwarg
            and hasattr(node.args.kwarg, 'annotation')
            and node.args.kwarg.annotation
        ):
            self.visit(node.args.kwarg.annotation)
        if (
            hasattr(node.args, 'vararg')
            and node.args.vararg
            and hasattr(node.args.vararg, 'annotation')
            and node.args.vararg.annotation
        ):
            self.visit(node.args.vararg.annotation)


@dataclass
class ImportName:
    """DTO for representing an import in different string-formats."""

    _module: str
    _name: str
    _alias: Optional[str]

    @property
    def module(self) -> str:
        """
        Return the import module.

        The self._module value contains a trailing ".".
        """
        return self._module.rstrip('.')

    @property
    def name(self) -> str:
        """
        Return the name of the import.

        The name is

            import pandas
                     ^-- this

            from pandas import DataFrame
                                  ^--this

            from pandas import DataFrame as df
                                            ^-- or this

        depending on the type of import.
        """
        return self._alias or self._name

    @property
    def full_name(self) -> str:
        """
        Return the full name of the import.

        The full name is

            import pandas --> 'pandas'

            from pandas import DataFrame --> 'pandas.DataFrame'

            from pandas import DataFrame as df --> 'pandas.DataFrame'
        """
        return f'{self._module}{self._name}'

    @property
    def import_name(self) -> str:
        """
        Return the import name.

        The import name is a hybrid of the two above, and is what will match the entries in the self.uses dict.
        """
        return self._alias or self.full_name

    @property
    def import_type(self) -> ImportTypeValue:
        """Return the import type of the import."""
        return cast('ImportTypeValue', classify_base(self.full_name.partition('.')[0]))


class UnwrappedAnnotation(NamedTuple):
    """Represents a single `ast.Name` in an unwrapped annotation."""

    lineno: int
    col_offset: int
    annotation: str
    type: Literal['annotation', 'alias', 'new-alias']


class WrappedAnnotation(NamedTuple):
    """Represents a wrapped annotation i.e. a string constant."""

    lineno: int
    col_offset: int
    annotation: str
    names: set[str]
    type: Literal['annotation', 'alias', 'new-alias']


class ImportVisitor(DunderAllMixin, AttrsMixin, FastAPIMixin, PydanticMixin, ast.NodeVisitor):
    """Map all imports outside of type-checking blocks."""

    def __init__(
        self,
        cwd: Path,
        pydantic_enabled: bool,
        fastapi_enabled: bool,
        fastapi_dependency_support_enabled: bool,
        cattrs_enabled: bool,
        pydantic_enabled_baseclass_passlist: list[str],
        exempt_modules: Optional[list[str]] = None,
    ) -> None:
        super().__init__()

        #: Plugin settings
        self.pydantic_enabled = pydantic_enabled
        self.fastapi_enabled = fastapi_enabled
        self.fastapi_dependency_support_enabled = fastapi_dependency_support_enabled
        self.cattrs_enabled = cattrs_enabled
        self.pydantic_enabled_baseclass_passlist = pydantic_enabled_baseclass_passlist
        self.pydantic_validate_arguments_import_name = None
        self.cwd = cwd  # we need to know the current directory to guess at which imports are remote and which are not

        #: Import patterns we want to avoid mapping
        self.exempt_imports: list[str] = ['*', 'TYPE_CHECKING']
        self.exempt_modules: list[str] = exempt_modules or []

        #: All imports, in each category
        self.application_imports: dict[str, Import] = {}
        self.third_party_imports: dict[str, Import] = {}
        self.built_in_imports: dict[str, Import] = {}

        #: Map of import name to verbose import name and import type
        # We compare the key of the dict to the uses of a file to figure out
        # which imports are unused (after ignoring all annotation uses),
        # then use the import type to yield the error with the appropriate type
        self.imports: dict[str, ImportName] = {}

        #: List of all names and ids, except type declarations
        self.uses: dict[str, ast.AST] = {}

        #: Tuple of (node, import name) for all import defined within a type-checking block
        # This lets us identify imports that *are* needed at runtime, for TC004 errors.
        self.type_checking_block_imports: set[tuple[Import, str]] = set()

        #: Set of variable names for all declarations defined within a type-checking block
        # This lets us avoid false positives for annotations referring to e.g. a TypeAlias
        # defined within a type checking block
        self.type_checking_block_declarations: set[str] = set()

        #: Set of all the class names defined within the file
        # This lets us avoid false positives for classes referring to themselves
        self.class_names: set[str] = set()

        #: All type annotations in the file, without quotes around them
        self.unwrapped_annotations: list[UnwrappedAnnotation] = []

        #: All type annotations in the file, with quotes around them
        self.wrapped_annotations: list[WrappedAnnotation] = []

        #: Whether there is a `from __futures__ import annotations` is present in the file
        self.futures_annotation: Optional[bool] = None

        #: Where the type checking block exists (line_start, line_end, col_offset)
        # Empty type checking blocks are used for TC005 errors, while the type
        # checking blocks list is used for several things. Among other things,
        # to build the type_checking_block_imports list.
        self.empty_type_checking_blocks: list[tuple[int, int, int]] = []
        self.type_checking_blocks: list[tuple[int, int, int]] = []

        #: Function imports and ranges
        # Function scopes can tell us if imports that appear in type-checking blocks
        # are repeated inside a function. This prevents false TC004 positives.
        self.function_scope_names: dict[int, FunctionScopeNamesDict] = {}
        self.function_ranges: dict[int, FunctionRangesDict] = {}

        #: Set to the alias of TYPE_CHECKING if one is found
        self.type_checking_alias: Optional[str] = None

        #: Set to the alias of typing if one is found
        self.typing_alias: Optional[str] = None

        #: Where typing.cast() is called with an unquoted type.
        # Used for TC006 errors. Also tracks imported aliases of typing.cast().
        self.typing_cast_aliases: set[str] = set()
        self.unquoted_types_in_casts: list[tuple[int, int, str]] = []

    @property
    def typing_module_name(self) -> str:
        """
        Return the appropriate module name for the typing import.

        It's possible to do:

            from typing import Set
                    ^--> module name is `typing`

        but you could also do:

            from typing as t import Set
                           ^--> module name is `t`

        This property returns the correct module name, accounting
        for possible aliases.
        """
        return self.typing_alias or 'typing'

    @property
    def names(self) -> set[str]:
        """Return unique names."""
        return set(self.uses.keys())

    # -- Map type checking block ---------------

    def in_type_checking_block(self, lineno: int, col_offset: int) -> bool:
        """Indicate whether an import is defined inside an `if TYPE_CHECKING` block or not."""
        if col_offset == 0:
            return False
        if not self.type_checking_blocks and not self.empty_type_checking_blocks:
            return False

        return any(
            type_checking_block[0] <= lineno <= type_checking_block[1]
            for type_checking_block in self.type_checking_blocks + self.empty_type_checking_blocks
        )

    def is_type_checking(self, node: ast.AST) -> bool:
        """Determine if the node is equivalent to TYPE_CHECKING."""
        return (
            # True for `TYPE_CHECKING`
            hasattr(node, 'id')
            and (node.id == 'TYPE_CHECKING')
            # True for `typing.TYPE_CHECKING` or `T.TYPE_CHECKING`
            or (hasattr(node, 'attr') and node.attr == 'TYPE_CHECKING')
            # True for `from typing import TYPE_CHECKING as TC\nTC`
            or (self.type_checking_alias is not None and hasattr(node, 'id') and (node.id == self.type_checking_alias))
        )

    def is_type_checking_true(self, node: ast.Compare) -> bool:
        """
        Check whether the node matches `if TYPE_CHECKING is True`.

        An ast.Compare node has a `left`, `ops`, and `comparators` attribute.

        Here we want to check whether our node corresponds to

            `if TYPE_CHECKING is True`
                    ^         ^    ^
        left _______|        ops   |____ comparators
        """
        # Left side should be a TYPE_CHECKING block
        is_type_checking_block = hasattr(node, 'left') and self.is_type_checking(node.left)
        if not is_type_checking_block:
            return False

        # Operator should be `is`
        operator_is_is = len(node.ops) == 1 and isinstance(node.ops[0], ast.Is)
        if not operator_is_is:
            return False

        # Right side should be `True`
        right_side_is_true = (
            len(node.comparators) == 1
            and isinstance(node.comparators[0], ast.Constant)
            and node.comparators[0].value is True
        )
        if not right_side_is_true:
            return False

        return True

    def is_true_when_type_checking(self, node: ast.AST) -> bool | Literal['TYPE_CHECKING']:
        """Determine if the node evaluates to True when TYPE_CHECKING is True.

        This handles simple boolean logic where the values can be statically determined.
        If a value is dynamic (e.g. a reference or a function call) we assume it may be False.

        Returns True if the statement is always True,
                False if the statement can ever be False when TYPE_CHECKING is True
                'TYPE_CHECKING' if the statement is always True when TYPE_CHECKING is True

        If the return value is 'TYPE_CHECKING', we can consider the statement to be equivalent
        to the value of the `TYPE_CHECKING` symbol for the purposes of this linter.
        """
        if self.is_type_checking(node):
            return 'TYPE_CHECKING'
        if isinstance(node, ast.BoolOp):
            non_type_checking = [v for v in node.values if not self.is_type_checking(v)]
            has_type_checking = len(non_type_checking) < len(node.values)
            num_true = sum(1 if self.is_true_when_type_checking(v) else 0 for v in non_type_checking)
            all_others_true = num_true == len(non_type_checking)
            any_others_true = num_true > 0
            if isinstance(node.op, ast.Or):
                # At least one of the conditions must be TYPE_CHECKING
                return 'TYPE_CHECKING' if has_type_checking else any_others_true
            elif isinstance(node.op, ast.And) and all_others_true:
                # At least one of the conditions must be TYPE_CHECKING, and all others must be True
                return 'TYPE_CHECKING' if has_type_checking else False
        elif isinstance(node, ast.Constant):
            with suppress(Exception):
                return bool(literal_eval(node))
        elif isinstance(node, ast.Compare) and self.is_type_checking_true(node):
            return 'TYPE_CHECKING'
        return False

    def visit_Module(self, node: ast.Module) -> ast.Module:
        """
        Mark global statments.

        We propagate this marking when visiting control flow nodes, that don't affect
        scope, such as if/else, try/except. Although for simplicity we don't handle
        quite all the possible cases, since we're only interested in type checking blocks
        and it's not realistic to encounter these for example inside a TryStar/With/Match.

        If we're serious about handling all the cases it would probably make more sense
        to override generic_visit to propagate this property for a sequence of node types
        and attributes that contain the statements that should propagate global scope.
        """
        for stmt in node.body:
            setattr(stmt, GLOBAL_PROPERTY, True)

        self.generic_visit(node)
        return node

    def visit_Try(self, node: ast.Try) -> ast.Try:
        """Propagate global statements."""
        if getattr(node, GLOBAL_PROPERTY, False):
            for stmt in chain(node.body, (s for h in node.handlers for s in h.body), node.orelse, node.finalbody):
                setattr(stmt, GLOBAL_PROPERTY, True)

        self.generic_visit(node)
        return node

    def visit_If(self, node: ast.If) -> Any:
        """
        Look for a TYPE_CHECKING block.

        Also recursively propagate global, since if/else does not affect scope.
        """
        if getattr(node, GLOBAL_PROPERTY, False):
            for stmt in chain(node.body, getattr(node, 'orelse', ()) or ()):
                setattr(stmt, GLOBAL_PROPERTY, True)

        type_checking_condition = self.is_true_when_type_checking(node.test) == 'TYPE_CHECKING'

        # If it is, note down the line-number-range where the type-checking block exists
        # Initially we just set the node.lineno and node.end_lineno, but it turns out that else blocks are
        # included in this span. We only want to know the range of the if-block.
        if type_checking_condition:
            start_of_else_block = None
            if hasattr(node, 'orelse') and node.orelse:
                # The start of the else block is the lineno of the
                # first element in the else block - 1
                start_of_else_block = node.orelse[0].lineno - 1

            # Check for TC005 errors.
            if ((node.end_lineno or node.lineno) - node.lineno == 1) and (
                len(node.body) == 1 and isinstance(node.body[0], ast.Pass)
            ):
                self.empty_type_checking_blocks.append(
                    (node.lineno, start_of_else_block or node.end_lineno or node.lineno, node.col_offset)
                )
            else:
                self.type_checking_blocks.append(
                    (node.lineno, start_of_else_block or node.end_lineno or node.lineno, node.col_offset)
                )

        self.generic_visit(node)
        return node

    # -- Map imports -------------------------------

    def is_exempt_module(self, module_name: str) -> bool:
        """Template module name check."""
        return any(fnmatch.fnmatch(module_name, exempt_module) for exempt_module in self.exempt_modules)

    def add_import(self, node: Import) -> None:  # noqa: C901
        """Add relevant ast objects to import lists."""
        if self.in_type_checking_block(node.lineno, node.col_offset):
            # For type checking blocks we want to
            # 1. Record annotations for TC2XX errors
            # 2. Avoid recording imports for TC1XX errors, by returning early
            for name_node in node.names:
                if hasattr(name_node, 'asname') and name_node.asname:
                    name = name_node.asname
                else:
                    name = name_node.name
                self.type_checking_block_imports.add((node, name))
            return None

        # Skip checking the import if the module is passlisted.
        if isinstance(node, ast.ImportFrom) and node.module and self.is_exempt_module(node.module):
            return

        for name_node in node.names:
            # Skip checking the import if the module is passlisted
            if isinstance(node, ast.Import) and self.is_exempt_module(name_node.name):
                return

            # Look for a TYPE_CHECKING import
            if name_node.name == 'TYPE_CHECKING' and name_node.asname is not None:
                self.type_checking_alias = name_node.asname

            # Look for pydantic.validate_arguments import
            if name_node.name == 'validate_arguments':
                if name_node.asname is not None:
                    self.pydantic_validate_arguments_import_name = name_node.asname
                else:
                    self.pydantic_validate_arguments_import_name = name_node.name

            # Look for typing import
            if name_node.name == 'typing' and name_node.asname is not None:
                self.typing_alias = name_node.asname
                return

            # Find aliases of typing.cast()
            elif (
                isinstance(node, ast.ImportFrom)
                and node.level == 0
                and node.module == self.typing_module_name
                and name_node.name == 'cast'
            ):
                self.typing_cast_aliases.add(name_node.asname or name_node.name)

            elif (isinstance(node, ast.ImportFrom) and node.module == self.typing_module_name) or (
                isinstance(node, ast.Import) and name_node.name == self.typing_module_name
            ):
                # Skip all remaining typing imports, since we already assume
                # TYPE_CHECKING will be imported at runtime, and guarding the
                # remaining imports probably won't have any tangible benefit
                continue

            # Classify and map imports
            if name_node.name not in self.exempt_imports:
                imp = ImportName(
                    _module=f'{node.module}.' if isinstance(node, ast.ImportFrom) else '',
                    _alias=name_node.asname,
                    _name=name_node.name,
                )

                if imp.import_type == Classified.APPLICATION:
                    self.application_imports[imp.import_name] = node
                elif imp.import_type == Classified.THIRD_PARTY:
                    self.third_party_imports[imp.import_name] = node
                elif imp.import_type == Classified.BUILTIN:
                    self.built_in_imports[imp.import_name] = node
                else:
                    """
                    Check for `from __futures__ import annotations` import.

                    We need to know if this is present or not, to determine whether
                    or not PEP563 is enabled: https://peps.python.org/pep-0563/
                    """
                    if self.futures_annotation is None and imp.import_type == Classified.FUTURE:
                        if any(name.name == 'annotations' for name in node.names):
                            self.futures_annotation = True
                            return
                        else:
                            # futures imports should always be the first line
                            # in a file, so we should only need to check this once
                            self.futures_annotation = False

                # Add to import names map. This is what we use to match imports to uses
                self.imports[imp.name] = imp

                # Add to function scope names, to help catch false positive TC004 errors.
                self._add_function_scope_names(lineno=node.lineno, name=imp.name)

    def visit_Import(self, node: ast.Import) -> None:
        """Append objects to our import map."""
        self.add_import(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Append objects to our import map."""
        self.add_import(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        """Note down class names."""
        has_base_classes = node.bases
        all_base_classes_ignored = all(
            isinstance(base, ast.Name) and base.id in self.pydantic_enabled_baseclass_passlist for base in node.bases
        )
        affected_by_pydantic_support = self.pydantic_enabled and has_base_classes and not all_base_classes_ignored
        affected_by_cattrs_support = self.cattrs_enabled and self.is_attrs_class(node)

        if affected_by_pydantic_support or affected_by_cattrs_support:
            # When pydantic or cattrs support is enabled, treat any class variable
            # annotation as being required at runtime. We need to do this, or
            # users run the risk of guarding imports to resources that actually are
            # required at runtime. This can be pretty scary, since it will crashes
            # the application at runtime.
            for element in node.body:
                if isinstance(element, ast.AnnAssign):
                    self.visit(element.annotation)

        self.class_names.add(node.name)
        self.generic_visit(node)
        return node

    def visit_Name(self, node: ast.Name) -> ast.Name:
        """Map names."""
        if hasattr(node, ANNOTATION_PROPERTY):
            # Skip handling of annotation objects
            return node

        if self.in_type_checking_block(node.lineno, node.col_offset):
            return node

        if hasattr(node, ATTRIBUTE_PROPERTY):
            self.uses[f'{node.id}.{getattr(node, ATTRIBUTE_PROPERTY)}'] = node

        self.uses[node.id] = node
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.Constant:
        """Map constants."""
        super().visit_Constant(node)
        return node

    def add_annotation(self, node: ast.AST, type: Literal['annotation', 'alias', 'new-alias'] = 'annotation') -> None:
        """Map all annotations on an AST node."""
        if isinstance(node, ast.Ellipsis) or node is None:
            return
        if isinstance(node, ast.BinOp):
            if not isinstance(node.op, ast.BitOr):
                return
            self.add_annotation(node.left, type)
            self.add_annotation(node.right, type)
        elif (py38 and isinstance(node, Index)) or isinstance(node, ast.Attribute):
            self.add_annotation(node.value, type)
        elif isinstance(node, ast.Subscript):
            self.add_annotation(node.value, type)
            if getattr(node.value, 'id', '') != 'Literal':
                self.add_annotation(node.slice, type)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for n in node.elts:
                self.add_annotation(n, type)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            # Register annotation value
            setattr(node, ANNOTATION_PROPERTY, True)
            self.wrapped_annotations.append(
                WrappedAnnotation(node.lineno, node.col_offset, node.value, set(NAME_RE.findall(node.value)), type)
            )
        elif isinstance(node, ast.Name):
            # Register annotation value
            setattr(node, ANNOTATION_PROPERTY, True)
            self.unwrapped_annotations.append(UnwrappedAnnotation(node.lineno, node.col_offset, node.id, type))

    @staticmethod
    def set_child_node_attribute(node: Any, attr: str, val: Any) -> Any:
        """Set the parent attribute on the current node children."""
        for key, value in node.__dict__.items():
            if type(value) not in [int, str, list, bool] and value is not None and not key.startswith('_'):
                setattr(node.__dict__[key], attr, val)
        return node

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        """
        Set a custom attribute on the current node.

        The custom attribute lets us read attribute names for `a.b.c` as `a.b.c`
        when we're handling the `c` node, which is important to match attributes to imports
        """
        node = self.set_child_node_attribute(node, ATTRIBUTE_PROPERTY, node.attr)
        self.generic_visit(node)
        return node

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """
        Remove all annotation assignments.

        But also keep track of any explicit `TypeAlias` assignments, we should treat the RHS like
        an annotation as well, but we have to keep in mind that the RHS will not automatically become
        a ForwardRef with a future import, like a true annotation would.
        """
        self.add_annotation(node.annotation)

        if node.value is None:
            return

        # node is an explicit TypeAlias assignment
        if isinstance(node.target, ast.Name) and (
            (isinstance(node.annotation, ast.Name) and node.annotation.id == 'TypeAlias')
            or (isinstance(node.annotation, ast.Constant) and node.annotation.value == 'TypeAlias')
        ):
            self.add_annotation(node.value, 'alias')

            if getattr(node, GLOBAL_PROPERTY, False) and self.in_type_checking_block(node.lineno, node.col_offset):
                self.type_checking_block_declarations.add(node.target.id)

        # if it wasn't a TypeAlias we need to visit the value expression
        else:
            self.visit(node.value)

    def visit_Assign(self, node: ast.Assign) -> ast.Assign:
        """
        Keep track of any top-level variable declarations inside type-checking blocks.

        For simplicity we only accept single value assignments, i.e. there should only be one
        target and it should be an `ast.Name`.
        """
        if (
            getattr(node, GLOBAL_PROPERTY, False)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and self.in_type_checking_block(node.lineno, node.col_offset)
        ):
            self.type_checking_block_declarations.add(node.targets[0].id)

        super().visit_Assign(node)
        return node

    if sys.version_info >= (3, 12):

        def visit_TypeAlias(self, node: ast.TypeAlias) -> None:
            """
            Remove all type aliases.

            Keep track of any type aliases declared inside a type checking block using the new
            `type Alias = value` syntax. We need to keep in mind that the RHS using this syntax
            will always become a ForwardRef, so none of the names are needed at runtime, so we
            don't visit the RHS and also have to treat the annotation differently from a regular
            annotation when emitting errors.
            """
            self.add_annotation(node.value, 'new-alias')

            if getattr(node, GLOBAL_PROPERTY, False) and self.in_type_checking_block(node.lineno, node.col_offset):
                self.type_checking_block_declarations.add(node.name.id)

    def register_function_ranges(self, node: Union[FunctionDef, AsyncFunctionDef]) -> None:
        """
        Note down the start and end line number of a function.

        We use the start and end line numbers to prevent raising false TC004
        positives in examples like this:

            from typing import TYPE_CHECKING

            if TYPE_CHECKING:
                from pandas import DataFrame

                MyType = DataFrame | str

            x: MyType

            def some_unrelated_function():
                from pandas import DataFrame
                return DataFrame()

        where it could seem like the first pandas import is actually used
        at runtime, but in fact, it's not.
        """
        end_lineno = cast('int', node.end_lineno)
        for i in range(node.lineno, end_lineno + 1):
            self.function_ranges[i] = {'start': node.lineno, 'end': end_lineno + 1}

    def _add_function_scope_names(self, lineno: int, name: str) -> None:
        """
        Add function names to our function scope map.

        Given this code:

            from typing import TYPE_CHECKING

            if TYPE_CHECKING:
                import requests

            ...

        The `import requests` import will not be in scope at runtime and cannot be used.
        To avoid this happening, this plugin ships the TC004 error which warns users if they
        attempt to use it:

            TC004: Move import out of type-checking block. Import is used for more than type hinting

        The problem is that this is pretty prone to false positives. Some of the things that could happen are:

            1. The user could import `requests` *again* within the scope of the function
            2. The user could override the name of the import with a function argument name
                Moreover, there are several classes of function arguments.
                They could do it with:
                    - an arg
                    - a kwarg
                    - a posonly arg
                    - a kwonly args
            3. The user could override the name with a variable assignment
            4. ?

        This function maps some of these sources of false positives to mitigate them.
        """
        if lineno not in self.function_scope_names:
            self.function_scope_names[lineno] = {'names': [name]}
        else:
            self.function_scope_names[lineno]['names'].append(name)

    def register_function_annotations(self, node: Union[FunctionDef, AsyncFunctionDef]) -> None:
        """
        Map all annotations in a function signature.

        Annotations include:
            - Argument annotations
            - Keyword argument annotations
            - Return annotations

        And we also note down the start and end line number for the function.
        """
        for path in [node.args.args, node.args.kwonlyargs, node.args.posonlyargs]:
            for argument in path:
                # Map annotations
                if hasattr(argument, 'annotation') and argument.annotation:
                    self.add_annotation(argument.annotation)

                # Map argument names
                self._add_function_scope_names(lineno=node.lineno, name=argument.arg)

        path_: str
        for path_ in ['kwarg', 'vararg']:
            if arg := getattr(node.args, path_, None):
                # Map annotations
                if getattr(arg, 'annotation', None):
                    self.add_annotation(arg.annotation)

                # Map argument names
                if name := getattr(arg, 'arg', None):
                    self._add_function_scope_names(lineno=node.lineno, name=name)

        if hasattr(node, 'returns') and node.returns:
            self.add_annotation(node.returns)

        self.register_function_ranges(node)

    def visit_FunctionDef(self, node: FunctionDef) -> None:
        """Remove and map function argument- and return annotations."""
        super().visit_FunctionDef(node)
        self.register_function_annotations(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: AsyncFunctionDef) -> None:
        """Remove and map function argument- and return annotations."""
        super().visit_AsyncFunctionDef(node)
        self.register_function_annotations(node)
        self.generic_visit(node)

    def register_unquoted_type_in_typing_cast(self, node: ast.Call) -> None:
        """Find typing.cast() calls with the type argument unquoted."""
        func = node.func

        # Determine whether this is a call to typing.cast() or an alias of it.
        via_name = isinstance(func, ast.Name) and func.id in self.typing_cast_aliases
        via_attr = (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == self.typing_module_name
            and func.attr == 'cast'
        )

        if not via_name and not via_attr or len(node.args) != 2:
            return  # Not typing.cast() (or an alias) or incorrect number of arguments.

        arg = node.args[0]

        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return  # Type argument is already a string literal.

        self.unquoted_types_in_casts.append((arg.lineno, arg.col_offset, ast_unparse(arg)))

    def visit_Call(self, node: ast.Call) -> None:
        """Check arguments of calls, e.g. typing.cast()."""
        with suppress(AttributeError):
            super().visit_Call(node)
        self.register_unquoted_type_in_typing_cast(node)
        self.generic_visit(node)


class TypingOnlyImportsChecker:
    """Checks for imports exclusively used by type annotation elements."""

    __slots__ = [
        'cwd',
        'strict_mode',
        'visitor',
        'generators',
        'future_option_enabled',
    ]

    def __init__(self, node: ast.Module, options: Optional[Namespace]) -> None:
        self.cwd = Path(os.getcwd())
        self.strict_mode = getattr(options, 'type_checking_strict', False)

        exempt_modules = getattr(options, 'type_checking_exempt_modules', [])
        pydantic_enabled = getattr(options, 'type_checking_pydantic_enabled', False)
        pydantic_enabled_baseclass_passlist = getattr(options, 'type_checking_pydantic_enabled_baseclass_passlist', [])
        fastapi_enabled = getattr(options, 'type_checking_fastapi_enabled', False)
        fastapi_dependency_support_enabled = getattr(options, 'type_checking_fastapi_dependency_support_enabled', False)
        cattrs_enabled = getattr(options, 'type_checking_cattrs_enabled', False)

        if fastapi_enabled and not pydantic_enabled:
            # FastAPI support must include Pydantic support.
            pydantic_enabled = True

        if fastapi_dependency_support_enabled and (not pydantic_enabled or not fastapi_enabled):
            # Dependency support is FastAPI support + a little bit extra
            fastapi_enabled = True
            pydantic_enabled = True

        self.visitor = ImportVisitor(
            self.cwd,
            pydantic_enabled=pydantic_enabled,
            fastapi_enabled=fastapi_enabled,
            cattrs_enabled=cattrs_enabled,
            exempt_modules=exempt_modules,
            fastapi_dependency_support_enabled=fastapi_dependency_support_enabled,
            pydantic_enabled_baseclass_passlist=pydantic_enabled_baseclass_passlist,
        )
        self.visitor.visit(node)

        self.generators = [
            # TC001 - TC003
            self.unused_imports,
            # TC004
            self.used_type_checking_imports,
            # TC005
            self.empty_type_checking_blocks,
            # TC006
            self.unquoted_type_in_cast,
            # TC100
            self.missing_futures_import,
            # TC101
            self.futures_excess_quotes,
            # TC200, TC006
            self.missing_quotes,
            # TC201, TC007
            self.excess_quotes,
        ]

    def unused_imports(self) -> Flake8Generator:
        """Yield TC001, TC002, and TC003 errors."""
        import_types = {
            Classified.APPLICATION: (self.visitor.application_imports, TC001),
            Classified.THIRD_PARTY: (self.visitor.third_party_imports, TC002),
            Classified.BUILTIN: (self.visitor.built_in_imports, TC003),
        }

        unused_imports = set(self.visitor.imports) - self.visitor.names
        used_imports = set(self.visitor.imports) - unused_imports
        already_imported_modules = [self.visitor.imports[name].module for name in used_imports]
        annotation_names = [n for i in self.visitor.wrapped_annotations for n in i.names] + [
            i.annotation for i in self.visitor.unwrapped_annotations
        ]

        for name in unused_imports:
            if name not in annotation_names:
                # The import seems to be completely unused.
                # Prevent flagging these, as they're already covered by F401
                continue

            # Get the ImportName object for this import name
            import_name: ImportName = self.visitor.imports[name]
            # If strict mode is enabled, we want to flag each individual import
            # that can be moved into a type-checking block. If not enabled,
            # we only want to flag imports if there aren't other imports already
            # made from the same module.
            if self.strict_mode or import_name.module not in already_imported_modules:
                error_specific_imports, error = import_types[import_name.import_type]
                node = error_specific_imports.pop(import_name.import_name)
                yield node.lineno, node.col_offset, error.format(module=import_name.import_name), None

    def used_type_checking_imports(self) -> Flake8Generator:
        """TC004."""
        for _import, import_name in self.visitor.type_checking_block_imports:
            if import_name in self.visitor.uses:
                # If we get to here, we're pretty sure that the import
                # shouldn't actually live inside a type-checking block

                use = self.visitor.uses[import_name]

                # .. or whether there is another duplicate import inside the function scope
                # (if the use is in a function scope)
                use_in_function = False
                if use.lineno in self.visitor.function_ranges:
                    for i in range(
                        self.visitor.function_ranges[use.lineno]['start'],
                        self.visitor.function_ranges[use.lineno]['end'],
                    ):
                        if (
                            i in self.visitor.function_scope_names
                            and import_name in self.visitor.function_scope_names[i]['names']
                        ):
                            use_in_function = True
                            break

                if not use_in_function:
                    yield _import.lineno, 0, TC004.format(module=import_name), None

    def empty_type_checking_blocks(self) -> Flake8Generator:
        """TC005."""
        for empty_type_checking_block in self.visitor.empty_type_checking_blocks:
            yield empty_type_checking_block[0], 0, TC005, None

    def unquoted_type_in_cast(self) -> Flake8Generator:
        """TC006."""
        for lineno, col_offset, annotation in self.visitor.unquoted_types_in_casts:
            yield lineno, col_offset, TC006.format(annotation=annotation), None

    def missing_futures_import(self) -> Flake8Generator:
        """TC100."""
        if (
            not self.visitor.futures_annotation
            and {name for _, name in self.visitor.type_checking_block_imports} - self.visitor.names
        ):
            yield 1, 0, TC100, None

    def futures_excess_quotes(self) -> Flake8Generator:
        """TC101."""
        # If futures imports are present, any ast.Constant captured in add_annotation should yield an error
        if self.visitor.futures_annotation:
            for item in self.visitor.wrapped_annotations:
                if item.type != 'annotation':  # TypeAlias value will not be affected by a futures import
                    continue

                yield item.lineno, item.col_offset, TC101.format(annotation=item.annotation), None
        else:
            """
            If we have no futures import and we have no imports inside a type-checking block, things get more tricky:

            When you annotate something like this:

                `x: Dict[int]`

            You receive an ast.AnnAssign element with a subscript containing the int as it's own unit. It means you
            have a separation between the `Dict` and the `int`, and the Dict can be matched against a `Dict` import.

            However, when you annotate something inside quotes, like this:

                 `x: 'Dict[int]'`

            The annotation is *not* broken down into its components, but rather returns an ast.Constant with a string
            value representation of the annotation. In other words, you get one element, with the value `'Dict[int]'`.

            We use a RegEx to extract all the variable names in the annotation into a set we can match against, but
            unlike with unwrapped annotations we don't put them all into separate entries, because there would be false
            positives for annotations like the one above, since int does not need to be wrapped, but Dict might, but
            the inverse would be true for something like:

                `x: 'set[Pattern[str]]'`

            Which could be turned into the following and still be fine:

                `x: set['Pattern[str]']

            So we don't try to unwrap the annotations as far as possible, we just check if the entire
            annotation can be unwrapped or not.
            """
            for item in self.visitor.wrapped_annotations:
                if item.type != 'annotation':  # TypeAlias value will not be affected by a futures import
                    continue

                if any(import_name in item.names for _, import_name in self.visitor.type_checking_block_imports):
                    continue

                if any(class_name in item.names for class_name in self.visitor.class_names):
                    continue

                yield item.lineno, item.col_offset, TC101.format(annotation=item.annotation), None

    def missing_quotes(self) -> Flake8Generator:
        """TC200 and TC007."""
        for item in self.visitor.unwrapped_annotations:
            # A new style alias does never need to be wrapped
            if item.type == 'new-alias':
                continue

            # Annotations inside `if TYPE_CHECKING:` blocks do not need to be wrapped
            # unless they're used before definition, which is already covered by other
            # flake8 rules (and also static type checkers)
            if self.visitor.in_type_checking_block(item.lineno, item.col_offset):
                continue

            for _, name in self.visitor.type_checking_block_imports:
                if item.annotation == name:
                    if item.type == 'alias':
                        error = TC007.format(alias=item.annotation)
                    else:
                        error = TC200.format(annotation=item.annotation)
                    yield item.lineno, item.col_offset, error, None

    def excess_quotes(self) -> Flake8Generator:
        """TC201 and TC008."""
        for item in self.visitor.wrapped_annotations:
            # A new style type alias should never be wrapped
            if item.type == 'new-alias':
                yield item.lineno, item.col_offset, TC008.format(alias=item.annotation), None
                continue

            # False positives for TC201 can be harmful, since fixing them, rather than
            # ignoring them will incur a runtime TypeError, so we should be even more
            # careful than with TC101 and favor false negatives even more, as such we
            # give up immediately if the annotation contains square brackets, because
            # we can't know if subscripting the type at runtime is safe without inspecting
            # the type's source code.
            if '[' in item.annotation or '.' in item.annotation:
                continue

            # See comment in futures_excess_quotes
            if any(import_name in item.names for _, import_name in self.visitor.type_checking_block_imports):
                continue

            if any(class_name in item.names for class_name in self.visitor.class_names):
                continue

            if any(variable_name in item.names for variable_name in self.visitor.type_checking_block_declarations):
                continue

            if item.type == 'alias':
                error = TC008.format(alias=item.annotation)
            else:
                error = TC201.format(annotation=item.annotation)

            yield item.lineno, item.col_offset, error, None

    @property
    def errors(self) -> Flake8Generator:
        """
        Return relevant errors in the required flake8-defined format.

        Flake8 plugins must return generators in this format: https://flake8.pycqa.org/en/latest/plugin-development/
        """
        for generator in self.generators:
            yield from generator()
