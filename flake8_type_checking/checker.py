from __future__ import annotations

import ast
import fnmatch
import os
import sys
from abc import ABC, abstractmethod
from ast import literal_eval
from collections import defaultdict
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, NamedTuple, cast

from classify_imports import Classified, classify_base

from flake8_type_checking.constants import (
    ANNOTATION_PROPERTY,
    ATTRIBUTE_PROPERTY,
    ATTRS_DECORATORS,
    ATTRS_IMPORTS,
    BINOP_OPERAND_PROPERTY,
    MISSING,
    TC001,
    TC002,
    TC003,
    TC004,
    TC005,
    TC006,
    TC007,
    TC008,
    TC009,
    TC010,
    TC100,
    TC101,
    TC200,
    TC201,
    builtin_names,
    sqlalchemy_default_mapped_dotted_names,
)
from flake8_type_checking.util import iter_function_annotation_nodes

if TYPE_CHECKING:
    from _ast import AsyncFunctionDef, FunctionDef
    from argparse import Namespace
    from collections.abc import Iterator

    from flake8_type_checking.types import (
        Comprehension,
        Flake8Generator,
        Function,
        HasPosition,
        Import,
        ImportTypeValue,
        Name,
        SupportsIsTyping,
    )


class AnnotationVisitor(ABC):
    """Simplified node visitor for traversing annotations."""

    @abstractmethod
    def is_typing(self, node: ast.AST, symbol: str) -> bool:
        """Check if the given node matches the given typing symbol."""

    @abstractmethod
    def visit_annotation_name(self, node: ast.Name) -> None:
        """Visit a name inside an annotation."""

    @abstractmethod
    def visit_annotation_string(self, node: ast.Constant) -> None:
        """Visit a string constant inside an annotation."""

    def visit_annotated_type(self, node: ast.expr) -> None:
        """Visit a type expression of `typing.Annotated[type, value]`."""
        self.visit(node)

    def visit_annotated_value(self, node: ast.expr) -> None:
        """Visit a value expression of `typing.Annotated[type, value]`."""
        return

    def visit(self, node: ast.AST) -> None:
        """Visit relevant child nodes on an annotation."""
        if node is None:
            return
        if isinstance(node, ast.BinOp):
            if not isinstance(node.op, ast.BitOr):
                return
            setattr(node.left, BINOP_OPERAND_PROPERTY, True)
            setattr(node.right, BINOP_OPERAND_PROPERTY, True)
            self.visit(node.left)
            self.visit(node.right)
        elif isinstance(node, ast.Attribute):
            self.visit(node.value)
        elif isinstance(node, ast.Subscript):
            self.visit(node.value)
            if self.is_typing(node.value, 'Literal'):
                return
            elif self.is_typing(node.value, 'Annotated') and isinstance(
                node.slice,
                (ast.Tuple, ast.List),
            ):
                if node.slice.elts:
                    elts_iter = iter(node.slice.elts)
                    # only visit the first element like a type expression
                    self.visit_annotated_type(next(elts_iter))
                    for value_node in elts_iter:
                        self.visit_annotated_value(value_node)
            else:
                self.visit(node.slice)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for n in node.elts:
                self.visit(n)
        elif isinstance(node, ast.Starred) and isinstance(node.ctx, ast.Load):
            self.visit(node.value)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            self.visit_annotation_string(node)
        elif isinstance(node, ast.Name):
            self.visit_annotation_name(node)


class AttrsMixin:
    """
    Contains necessary logic for cattrs + attrs support.

    When the cattrs_enabled option is specified as True,
    we treat type hints on attrs classes as needed at runtime.
    """

    if TYPE_CHECKING:
        third_party_imports: dict[str, Import]

    def get_all_attrs_imports(self) -> dict[str | None, str]:
        """Return a map of all attrs/attr imports."""
        attrs_imports: dict[str | None, str] = {}  # map of alias to full import name

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

    def is_attrs_decorator(self, decorator: Any, attrs_imports: dict[str | None, str]) -> bool:
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
    def is_attrs_str(attribute: str | ast.expr, attrs_imports: dict[str | None, str]) -> bool:
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
        uses: dict[str, list[tuple[ast.expr, Scope]]]
        current_scope: Scope

        def generic_visit(self, node: ast.AST) -> None:  # noqa: D102
            ...

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
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
            # for these it doesn't matter where they are declared, the symbol
            # just needs to be available in global scope anywhere, we handle
            # this by special casing `ast.Constant` when we look for used type
            # checking symbols
            self.uses[node.value].append((node, self.current_scope))
        return node


class PydanticMixin:
    """
    Contains the necessary logic for Pydantic support.

    At least the code that could be separated from the main visitor class.
    Some pydantic stuff is still contained in the main class.
    """

    if TYPE_CHECKING:
        pydantic_enabled: bool

        def visit(self, node: ast.AST) -> ast.AST:  # noqa: D102
            ...

        def lookup_full_name(self, node: ast.AST) -> str | None:  # noqa: D102
            ...

    def _function_is_wrapped_by_validate_arguments(self, node: FunctionDef | AsyncFunctionDef) -> bool:
        if self.pydantic_enabled and node.decorator_list:
            for decorator_node in node.decorator_list:
                if self.lookup_full_name(decorator_node) == 'pydantic.validate_arguments':
                    return True
        return False

    def visit_FunctionDef(self, node: FunctionDef) -> None:
        """Remove and map function arguments and returns."""
        if self._function_is_wrapped_by_validate_arguments(node):
            for expr in iter_function_annotation_nodes(node):
                self.visit(expr)

    def visit_AsyncFunctionDef(self, node: AsyncFunctionDef) -> None:
        """Remove and map function arguments and returns."""
        if self._function_is_wrapped_by_validate_arguments(node):
            for expr in iter_function_annotation_nodes(node):
                self.visit(expr)


class SQLAlchemyAnnotationVisitor(AnnotationVisitor):
    """Adds any names in the annotation to mapped names."""

    def __init__(self, sqlalchemy_plugin: SQLAlchemyMixin) -> None:
        self.plugin = sqlalchemy_plugin

    def is_typing(self, node: ast.AST, symbol: str) -> bool:
        """Check if the given node matches the given typing symbol."""
        return self.plugin.is_typing(node, symbol)

    def visit_annotated_value(self, node: ast.expr) -> None:
        """Visit a value expression of `typing.Annotated[type, value]`."""
        previous_context = self.plugin.in_soft_use_context
        self.plugin.in_soft_use_context = True
        self.plugin.visit(node)
        self.plugin.in_soft_use_context = previous_context

    def visit_annotation_name(self, node: ast.Name) -> None:
        """Add name to mapped names."""
        self.plugin.soft_uses.add(node.id)

    def visit_annotation_string(self, node: ast.Constant) -> None:
        """Add all the names in the string to mapped names."""
        visitor = StringAnnotationVisitor(self.plugin)
        visitor.parse_and_visit_string_annotation(node.value)
        self.plugin.soft_uses.update(visitor.names)


class SQLAlchemyMixin:
    """
    Contains the necessary logic for SQLAlchemy (https://www.sqlalchemy.org/) support.

    For mapped attributes we don't know whether or not the enclosed type needs to be
    available at runtime, since it may or may not be a model. So we treat it like a
    runtime use for the purposes of TC001/TC002/TC003 but not anywhere else.

    This supports `sqlalchemy.orm.Mapped`, `sqlalchemy.orm.DynamicMapped` and
    `sqlalchemy.orm.WriteOnlyMapped` by default, but can be extended to cover
    additional user-defined subclassed of `sqlalchemy.orm.Mapped` using the
    setting `type-checking-sqlalchemy-mapped-dotted-names`.
    """

    if TYPE_CHECKING:
        sqlalchemy_enabled: bool
        sqlalchemy_mapped_dotted_names: set[str]
        current_scope: Scope
        uses: dict[str, list[tuple[ast.expr, Scope]]]
        soft_uses: set[str]
        in_soft_use_context: bool

        def in_type_checking_block(self, lineno: int, col_offset: int) -> bool:  # noqa: D102
            ...

        def lookup_full_name(self, node: ast.AST) -> str | None:  # noqa: D102
            ...

        def is_typing(self, node: ast.AST, symbol: str) -> bool:  # noqa: D102
            ...

        def visit(self, node: ast.AST) -> ast.AST:  # noqa: D102
            ...

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        #: Used for visiting annotations
        self.sqlalchemy_annotation_visitor = SQLAlchemyAnnotationVisitor(self)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Remove all annotations assigments."""
        if (
            self.sqlalchemy_enabled
            # We only need to special case runtime use of `Mapped`
            and not self.in_type_checking_block(node.lineno, node.col_offset)
        ):
            self.handle_sqlalchemy_annotation(node.annotation)

    def is_mapped(self, node_or_name: ast.AST | str) -> bool:
        """Check whether the given node or name should be treated as `Mapped`."""
        if isinstance(node_or_name, str):
            try:
                root_node = ast.parse(f'{node_or_name}: _')
                ann_assign_node = root_node.body[0]
                assert isinstance(ann_assign_node, ast.AnnAssign)
                node_or_name = ann_assign_node.target
            except Exception:
                return False

        return self.lookup_full_name(node_or_name) in self.sqlalchemy_mapped_dotted_names

    def handle_sqlalchemy_annotation(self, node: ast.AST) -> None:
        """
        Record all the mapped names inside the annotations.

        If the annotation is an `ast.Constant` that starts with one of our
        `Mapped` names, then we will record a runtime use of that symbol,
        since we know `Mapped` always needs to resolve.
        """
        if isinstance(node, ast.Constant):
            # we only need to handle annotations like `"Mapped[...]"`
            if not isinstance(node.value, str) or '[' not in node.value:
                return

            annotation = node.value.strip()
            if not annotation.endswith(']'):
                return

            mapped_name, inner = annotation.split('[', 1)
            # strip trailing `]` from inner
            inner = inner[:-1]
            if not self.is_mapped(mapped_name):
                return

            # record a use for the first part of the name
            used_name, *_ = mapped_name.split('.', 1)
            self.uses[used_name].append((node, self.current_scope))

            # add all names contained in the inner part of the annotation
            # since this is not as strict as an actual runtime use, we don't
            # care if we record too much here
            visitor = StringAnnotationVisitor(self)
            visitor.parse_and_visit_string_annotation(inner)
            self.soft_uses.update(visitor.names)
            return

        # we only need to handle annotations like `Mapped[...]`
        if not isinstance(node, ast.Subscript):
            return

        # simple case only needs to check mapped_aliases
        if isinstance(node.value, ast.Name):
            if not self.is_mapped(node.value):
                return

            # record a use for the name
            self.uses[node.value.id].append((node.value, self.current_scope))

        # complex case for dotted names
        elif isinstance(node.value, ast.Attribute):
            dotted_name = node.value.attr
            before_dot = node.value.value
            while isinstance(before_dot, ast.Attribute):
                dotted_name = f'{before_dot.attr}.{dotted_name}'
                before_dot = before_dot.value
            # there should be no subscripts between the attributes
            if not isinstance(before_dot, ast.Name):
                return

            # map the module if it's mapped otherwise use it as is
            module = self.lookup_full_name(before_dot) or before_dot.id
            dotted_name = f'{module}.{dotted_name}'
            if dotted_name not in self.sqlalchemy_mapped_dotted_names:
                return

            # record a use for the left-most node in the attribute access chain
            self.uses[before_dot.id].append((before_dot, self.current_scope))

        # any other case is invalid, such as `Foo[...][...]`
        else:
            return

        # visit the wrapped annotations to update the mapped names
        self.sqlalchemy_annotation_visitor.visit(node.slice)


class InjectorMixin:
    """
    Contains the necessary logic for injector (https://github.com/python-injector/injector) support.

    For injected dependencies, we want to treat annotations as needed at runtime.
    """

    if TYPE_CHECKING:
        injector_enabled: bool

        def visit(self, node: ast.AST) -> ast.AST:  # noqa: D102
            ...

        def lookup_full_name(self, node: ast.AST) -> str | None:  # noqa: D102
            ...

    def visit_FunctionDef(self, node: FunctionDef) -> None:
        """Remove and map function arguments and returns."""
        super().visit_FunctionDef(node)  # type: ignore[misc]
        if self.injector_enabled:
            self.handle_injector_declaration(node)

    def visit_AsyncFunctionDef(self, node: AsyncFunctionDef) -> None:
        """Remove and map function arguments and returns."""
        super().visit_AsyncFunctionDef(node)  # type: ignore[misc]
        if self.injector_enabled:
            self.handle_injector_declaration(node)

    def _has_injected_annotation(self, node: AsyncFunctionDef | FunctionDef) -> bool:
        return any(
            isinstance(expr, ast.Subscript) and self.lookup_full_name(expr.value) == 'injector.Inject'
            for expr in iter_function_annotation_nodes(node)
        )

    def handle_injector_declaration(self, node: AsyncFunctionDef | FunctionDef) -> None:
        """
        Adjust for injector declaration setting.

        When the injector setting is enabled, treat all annotations from within
        a function definition (except for return annotations) as needed at runtime.

        To achieve this, we just visit the annotations to register them as "uses".
        """
        if not self._has_injected_annotation(node):
            return

        for expr in iter_function_annotation_nodes(node):
            self.visit(expr)


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

    def handle_fastapi_decorator(self, node: AsyncFunctionDef | FunctionDef) -> None:
        """
        Adjust for FastAPI decorator setting.

        When the FastAPI decorator setting is enabled, treat all annotations from within
        a function definition (except for return annotations) as needed at runtime.

        To achieve this, we just visit the annotations to register them as "uses".
        """
        for expr in iter_function_annotation_nodes(node):
            self.visit(expr)


class FunctoolsSingledispatchMixin:
    """
    Contains the necessary logic for `functools.singledispatch` support.

    `functools.singledispatch` and `functools.singledispatchmethod` require
    runtime access to all annotations.

    ```python
    from functools import singledispatch

    from mylib import Foo

    @singledispatch
    def foo(arg: Foo) -> str:
        return arg.name
    ```

    Since the only use of `Foo` is within an annotation, we would usually emit
    a TC003 for the `mylib` import. But since `singledispatch` requires runtime
    access to `Foo`, that would be a false positive.
    """

    if TYPE_CHECKING:

        def in_type_checking_block(self, lineno: int, col_offset: int) -> bool:  # noqa: D102
            ...

        def lookup_full_name(self, node: ast.AST) -> str | None:  # noqa: D102
            ...

        def visit(self, node: ast.AST) -> ast.AST:  # noqa: D102
            ...

    def visit_FunctionDef(self, node: FunctionDef) -> None:
        """Remove and map function arguments and returns."""
        super().visit_FunctionDef(node)  # type: ignore[misc]
        if self.has_singledispatch_decorator(node):
            for expr in iter_function_annotation_nodes(node):
                self.visit(expr)

    def visit_AsyncFunctionDef(self, node: AsyncFunctionDef) -> None:
        """Remove and map function arguments and returns."""
        super().visit_AsyncFunctionDef(node)  # type: ignore[misc]
        if self.in_type_checking_block(node.lineno, node.col_offset):
            return
        if self.has_singledispatch_decorator(node):
            for expr in iter_function_annotation_nodes(node):
                self.visit(expr)

    def has_singledispatch_decorator(self, node: FunctionDef | AsyncFunctionDef) -> bool:
        """Determine whether this function is decorated with `functools.singledispatch`."""
        return any(
            self.lookup_full_name(decorator_node) in ('functools.singledispatch', 'functools.singledispatchmethod')
            for decorator_node in node.decorator_list
        )


@dataclass
class ImportName:
    """DTO for representing an import in different string-formats."""

    _module: str
    _name: str
    _alias: str | None

    #: Whether or not this import is exempt from TC001-004 checks.
    exempt: bool

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


class WrappedAnnotation(NamedTuple):
    """Represents a wrapped annotation i.e. a string constant."""

    lineno: int
    col_offset: int
    annotation: str
    names: set[str]
    scope: Scope
    type: Literal['annotation', 'alias', 'new-alias']


class UnwrappedAnnotation(NamedTuple):
    """Represents a single `ast.Name` in an unwrapped annotation."""

    lineno: int
    col_offset: int
    annotation: str
    scope: Scope
    type: Literal['annotation', 'alias', 'new-alias']


class Symbol(NamedTuple):
    """Represents an import/definition/declaration of a variable."""

    name: str
    lineno: int
    col_offset: int
    type: Literal['import', 'definition', 'declaration', 'argument']
    in_type_checking_block: bool

    def available_at_runtime(self, use: HasPosition | None = None) -> bool:
        """Return whether or not this symbol is available at runtime."""
        if self.in_type_checking_block or self.type == 'declaration':
            return False

        # we punt in this case, this is to support some use-cases where
        # the location of use does not matter, such as __all__
        if use is None:
            return True

        if use.lineno < self.lineno:
            return False

        if use.lineno == self.lineno and use.col_offset < self.col_offset:
            return False

        return True


class Scope:
    """
    Represents a scope for looking up symbols.

    We currently don't create a new scope for generator expressions, since it
    already has a bunch of special cases for accessing symbols that would not
    be accessible inside a different kind of scope and it may go away entirely
    when comprehension inlining becomes a thing and it no longer generates a
    new stack frame.

    For FunctionDef/AsyncFunctionDef we create a tiny virtual scope for the
    head containing only the function signature to properly handle PEP695
    type parameter scopes.
    """

    def __init__(self, node: ast.Module | ast.ClassDef | Function, parent: Scope | None = None, is_head: bool = False):
        #: The ast.AST node that created this scope
        self.node = node

        #: Map of symbol name to a list of imports/definitions/declarations
        # This also includes the scoping of the symbol so we can look up if
        # it is available at runtime/type checking time.
        self.symbols: dict[str, list[Symbol]] = defaultdict(list)

        #: The outer scope, this will be `None` for the global scope
        # We use this to traverse up to the outer scopes when looking up
        # symbols
        self.parent = parent

        #: For function scopes whether it is just for the head or also the body
        # This is to deal with the fact that defaults and annotations are part
        # of the outer scope, but type params are private to the function without
        # leaking outside, so there is a thin faux-scope around the head which
        # contains just the type params
        self.is_head = is_head

        #: The name of the class if this is a scope created by a class definition
        # classes are not real scopes, i.e. they don't propagate symbols
        # to inner-scopes, so we need to treat them differently in lookup
        # the class name itself is also special, since it's available in methods
        # but not in the class body itself, so we record it, so we can special-case
        # it in symbol lookups
        self.class_name = node.name if isinstance(node, ast.ClassDef) else None

        #: Whether or not annotation assignments never get evaluated in this scope
        self.ann_assign_never_evaluates = not is_head and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))

    def lookup(self, symbol_name: str, use: HasPosition | None = None, runtime_only: bool = True) -> Symbol | None:
        """
        Simulate a symbol lookup.

        If a symbol is redefined multiple times in the same block we don't try
        to return the symbol closest to the use-site, we just return the first
        one we find, since we don't really care what symbol we find currently.
        """
        for symbol in self.symbols.get(symbol_name, ()):
            if runtime_only and not symbol.available_at_runtime(use):
                continue

            # we just return the first symbol we find
            return symbol

        parent = self.parent
        if runtime_only:
            # if the symbol matches our class name we return at this point
            # technically if the class definition is a redefinition of the
            # the same symbol_name it could still exist at runtime, but it's
            # probably an actual mistake at that point and an annotation should
            # be quoted to ensure the correct type is assigned
            if symbol_name == self.class_name:
                return None

            if parent is not None:
                # because of our virtual scope for function definition headers
                # we also need to check the parent scope for a class name
                if self.is_head and symbol_name == parent.class_name:
                    return None

                # if the next scope up is a head scope we don't want to skip it
                if parent.is_head:
                    return parent.lookup(symbol_name, use, runtime_only)

            # skip class scopes when looking up symbols in parent scopes
            # they're only available inside the class scope itself
            while parent is not None and parent.class_name is not None:
                parent = parent.parent

            # we only propagate the use to the outer scope if we're a head-scope or
            # a class scope, this is to deal with the fact that even if a symbol is
            # defined after a function definition, it will still be available inside
            # the function. If the function is called before the symbol actually
            # exists, then an UnboundLocalError is raised, we can't easily detect
            # this case, so there's no point in trying to handle it.
            # Inversely, in case of a type checking lookup if we're not using a
            # futures import the location does matter even in outer scope, since
            # annotations are evaluated immediately, so that's why we're doing
            # this inside the `if runtime_only` block.
            if not self.is_head and not self.class_name:
                use = None

        # we're done looking up and didn't find anything
        if parent is None:
            return None

        return parent.lookup(symbol_name, use, runtime_only)


class StringAnnotationVisitor(AnnotationVisitor):
    """Visit a parsed string annotation and collect all the names."""

    def __init__(self, typing_lookup: SupportsIsTyping) -> None:
        #: All the names referenced inside the annotation
        self.names: set[str] = set()
        self._typing_lookup = typing_lookup

    def is_typing(self, node: ast.AST, symbol: str) -> bool:
        """Check if the given node matches the given typing symbol."""
        return self._typing_lookup.is_typing(node, symbol)

    def parse_and_visit_string_annotation(self, annotation: str) -> None:
        """Parse and visit the given string as an annotation expression."""
        try:
            # in the future this simple approach may fail, because
            # the quoted subexpression is only valid syntax in the context
            # of the parent expression, in which case we would have to
            # do something more clever here
            module_node = ast.parse(f'_: _[{annotation}]')
        except Exception:
            # if we can't parse the annotation we should do nothing
            return

        ann_assign_node = module_node.body[0]
        assert isinstance(ann_assign_node, ast.AnnAssign)
        annotation_node = ann_assign_node.annotation
        assert isinstance(annotation_node, ast.Subscript)
        self.visit(annotation_node.slice)

    def visit_annotation_name(self, node: ast.Name) -> None:
        """Remember all the visited names."""
        self.names.add(node.id)

    def visit_annotation_string(self, node: ast.Constant) -> None:
        """Parse and visit nested string annotations."""
        self.parse_and_visit_string_annotation(node.value)


class ImportAnnotationVisitor(AnnotationVisitor):
    """Map all annotations on an AST node."""

    def __init__(self, import_visitor: ImportVisitor) -> None:
        #: All type annotations in the file, without quotes around them
        self.unwrapped_annotations: list[UnwrappedAnnotation] = []

        #: All type annotations in the file, with quotes around them
        self.wrapped_annotations: list[WrappedAnnotation] = []

        #: All type annotations in the file with unnecessary quotes around them
        self.excess_wrapped_annotations: list[WrappedAnnotation] = []

        #: All the invalid uses of string literals inside ast.BinOp
        self.invalid_binop_literals: list[ast.Constant] = []

        #: Whether or not this annotation ever gets evaluated
        # e.g. AnnAssign.annotation within a function body will never evaluate
        self.never_evaluates = False

        #: Whether or not we're currently in a soft-use context
        # e.g. the type expression of `Annotated[type, value]
        self.in_soft_use_context = False

        self.import_visitor = import_visitor

    def is_typing(self, node: ast.AST, symbol: str) -> bool:
        """Check if the given node matches the given typing symbol."""
        return self.import_visitor.is_typing(node, symbol)

    def visit(
        self,
        node: ast.AST,
        scope: Scope | None = None,
        type: Literal['annotation', 'alias', 'new-alias'] | None = None,
        never_evaluates: bool | None = None,
    ) -> None:
        """Visit the node with the given scope and annotation type."""
        if scope is not None:
            self.scope = scope
        if type is not None:
            self.type = type
        if never_evaluates is not None:
            self.never_evaluates = never_evaluates
        super().visit(node)

    def visit_annotation_name(self, node: ast.Name) -> None:
        """Register unwrapped annotation."""
        setattr(node, ANNOTATION_PROPERTY, True)
        if self.never_evaluates:
            return

        if self.in_soft_use_context:
            self.import_visitor.soft_uses.add(node.id)

        self.unwrapped_annotations.append(
            UnwrappedAnnotation(node.lineno, node.col_offset, node.id, self.scope, self.type)
        )

    def visit_annotation_string(self, node: ast.Constant) -> None:
        """Register wrapped annotation and invalid binop literals."""
        setattr(node, ANNOTATION_PROPERTY, True)
        # we don't want to register them as both so we don't emit redundant errors
        if getattr(node, BINOP_OPERAND_PROPERTY, False):
            self.invalid_binop_literals.append(node)
        else:
            visitor = StringAnnotationVisitor(self.import_visitor)
            visitor.parse_and_visit_string_annotation(node.value)
            if self.in_soft_use_context:
                self.import_visitor.soft_uses.update(visitor.names)
            (self.excess_wrapped_annotations if self.never_evaluates else self.wrapped_annotations).append(
                WrappedAnnotation(node.lineno, node.col_offset, node.value, visitor.names, self.scope, self.type)
            )

    def visit_annotated_type(self, node: ast.expr) -> None:
        """Visit a type expression of `typing.Annotated[type, value]`."""
        if self.never_evaluates:
            return

        previous_context = self.in_soft_use_context
        self.in_soft_use_context = True
        self.visit(node)
        self.in_soft_use_context = previous_context

    def visit_annotated_value(self, node: ast.expr) -> None:
        """Visit a value expression of `typing.Annotated[type, value]`."""
        if self.never_evaluates:
            return

        if self.type == 'alias' or (self.type == 'annotation' and not self.import_visitor.futures_annotation):
            # visit nodes in regular runtime context
            self.import_visitor.visit(node)
            return

        # visit nodes in soft use context
        previous_context = self.import_visitor.in_soft_use_context
        self.import_visitor.in_soft_use_context = True
        self.import_visitor.visit(node)
        self.import_visitor.in_soft_use_context = previous_context


class CastTypeExpressionVisitor(AnnotationVisitor):
    """Visit a cast type expression and collect all the quoted names."""

    def __init__(self, typing_lookup: SupportsIsTyping) -> None:
        #: All the quoted_names referenced inside the type expression
        self.quoted_names: set[str] = set()
        self._typing_lookup = typing_lookup

    def is_typing(self, node: ast.AST, symbol: str) -> bool:
        """Check if the given node matches the given typing symbol."""
        return self._typing_lookup.is_typing(node, symbol)

    def visit_annotation_name(self, node: ast.Name) -> None:
        """Ignore visited names."""
        # We could either record them as quoted names pre-emptively or
        # as uses, but neither seems ideal, let's just skip these names
        # as we have previously.

    def visit_annotation_string(self, node: ast.Constant) -> None:
        """Collect all the names referenced inside the forward reference."""
        visitor = StringAnnotationVisitor(self._typing_lookup)
        visitor.parse_and_visit_string_annotation(node.value)
        self.quoted_names.update(visitor.names)


class ImportVisitor(
    DunderAllMixin,
    FunctoolsSingledispatchMixin,
    AttrsMixin,
    InjectorMixin,
    FastAPIMixin,
    PydanticMixin,
    SQLAlchemyMixin,
    ast.NodeVisitor,
):
    """Map all imports outside of type-checking blocks."""

    #: The currently active scope
    current_scope: Scope

    def __init__(
        self,
        cwd: Path,
        pydantic_enabled: bool,
        fastapi_enabled: bool,
        fastapi_dependency_support_enabled: bool,
        sqlalchemy_enabled: bool,
        sqlalchemy_mapped_dotted_names: list[str],
        injector_enabled: bool,
        cattrs_enabled: bool,
        pydantic_enabled_baseclass_passlist: list[str],
        typing_modules: list[str] | None = None,
        exempt_modules: list[str] | None = None,
        force_future_annotation: bool = False,
    ) -> None:
        super().__init__()

        #: Plugin settings
        self.pydantic_enabled = pydantic_enabled
        self.fastapi_enabled = fastapi_enabled
        self.fastapi_dependency_support_enabled = fastapi_dependency_support_enabled
        self.cattrs_enabled = cattrs_enabled
        self.sqlalchemy_enabled = sqlalchemy_enabled
        self.sqlalchemy_mapped_dotted_names = sqlalchemy_default_mapped_dotted_names | set(
            sqlalchemy_mapped_dotted_names
        )
        self.injector_enabled = injector_enabled
        self.pydantic_enabled_baseclass_passlist = pydantic_enabled_baseclass_passlist
        self.cwd = cwd  # we need to know the current directory to guess at which imports are remote and which are not

        #: A list of modules that re-export symbols from the typing module
        self.typing_modules: list[str] = ['typing', 'typing_extensions', *(typing_modules or ())]

        #: Import patterns we want to avoid mapping
        self.exempt_modules: list[str] = exempt_modules or []

        #: Whether or not TC100 should always be emitted if there are annotations
        self.force_future_annotation = force_future_annotation

        #: All imports, in each category
        self.application_imports: dict[str, Import] = {}
        self.third_party_imports: dict[str, Import] = {}
        self.built_in_imports: dict[str, Import] = {}

        #: Map of import name to verbose import name and import type
        # We compare the key of the dict to the uses of a file to figure out
        # which imports are unused (after ignoring all annotation uses),
        # then use the import type to yield the error with the appropriate type
        self.imports: dict[str, ImportName] = {}

        #: List of scopes including all the symbols within
        self.scopes: list[Scope] = []

        #: List of all names and ids, except type declarations
        self.uses: dict[str, list[tuple[ast.expr, Scope]]] = defaultdict(list)

        #: Contains a set of all names to be treated like soft-uses.
        # i.e. we don't know if it will be used at runtime or not, so
        # we should assume the imports are currently correct
        self.soft_uses: set[str] = set()

        #: Handles logic of visiting annotation nodes
        self.annotation_visitor = ImportAnnotationVisitor(self)

        #: Whether there is a `from __futures__ import annotations` present in the file
        self.futures_annotation: bool | None = None

        #: Where the type checking block exists (line_start, line_end, col_offset)
        # Empty type checking blocks are used for TC005 errors, while the type
        # checking blocks list is used for several things. Among other things,
        # to build the type_checking_block_imports list.
        self.empty_type_checking_blocks: list[tuple[int, int, int]] = []
        self.type_checking_blocks: list[tuple[int, int, int]] = []

        #: Where typing.cast() is called with an unquoted type.
        self.unquoted_types_in_casts: list[tuple[int, int, str]] = []

        #: All forward referenced names used in cast type expressions
        # we need to track this in order to avoid false negatives for TC001-003
        self.quoted_type_names_in_casts: set[str] = set()

        #: For tracking which comprehension/IfExp we're currently inside of
        self.active_context: Comprehension | ast.IfExp | None = None

        #: Whether or not we're in a context where uses count as soft-uses.
        # E.g. the type expression of `typing.Annotated[type, value]`
        self.in_soft_use_context: bool = False

        self._lookup_cache: dict[ast.AST, str | None] = {}

    @contextmanager
    def create_scope(self, node: ast.ClassDef | Function, is_head: bool = True) -> Iterator[Scope]:
        """Create a new scope."""
        parent = self.current_scope
        scope = Scope(node, parent=parent, is_head=is_head)
        self.scopes.append(scope)
        self.current_scope = scope
        yield scope
        self.current_scope = parent

    @contextmanager
    def change_scope(self, scope: Scope) -> Iterator[None]:
        """Change to a different scope."""
        old_scope = self.current_scope
        self.current_scope = scope
        yield
        self.current_scope = old_scope

    @property
    def unwrapped_annotations(self) -> list[UnwrappedAnnotation]:
        """All type annotations in the file, without quotes around them."""
        return self.annotation_visitor.unwrapped_annotations

    @property
    def wrapped_annotations(self) -> list[WrappedAnnotation]:
        """All type annotations in the file, with quotes around them."""
        return self.annotation_visitor.wrapped_annotations

    @property
    def excess_wrapped_annotations(self) -> list[WrappedAnnotation]:
        """All type annotations in the file, with excess quotes around them."""
        return self.annotation_visitor.excess_wrapped_annotations

    @property
    def invalid_binop_literals(self) -> list[ast.Constant]:
        """All invalid uses of binop literals."""
        return self.annotation_visitor.invalid_binop_literals

    @property
    def names(self) -> set[str]:
        """Return unique names."""
        return set(self.uses.keys())

    def type_checking_symbols(self) -> Iterator[Symbol]:
        """Yield all the symbols declared inside a type checking block."""
        for scope in self.scopes:
            for symbols in scope.symbols.values():
                for symbol in symbols:
                    if symbol.in_type_checking_block:
                        yield symbol

    def lookup_full_name(self, node: ast.AST) -> str | None:
        """Lookup the fully qualified name of the given node."""
        if (name := self._lookup_cache.get(node, MISSING)) is not MISSING:
            return name

        if isinstance(node, ast.Name):
            imp = self.imports.get(node.id)
            name = imp.full_name if imp is not None else node.id

        elif not isinstance(node, ast.Attribute):
            name = None

        else:
            current_node: ast.AST = node
            parts: list[str] = []
            while isinstance(current_node, ast.Attribute):
                # left append to the list so the names are in the
                # natural reading order i.e. `a.b.c` becomes `['a', 'b', 'c']`
                parts.insert(0, current_node.attr)
                current_node = current_node.value

            if not isinstance(current_node, ast.Name):
                self._lookup_cache[node] = None
                return None

            parts.insert(0, current_node.id)

            # lookup all variations of `a` `a.b` `a.b.c` in that order
            for num_parts in range(1, len(parts) + 1):
                name = '.'.join(parts[:num_parts])
                imp = self.imports.get(name)
                if imp is not None:
                    prefix = imp.full_name
                    remainder = '.'.join(parts[num_parts:])
                    name = f'{prefix}.{remainder}' if remainder else prefix
                    break
            else:
                # fallback to returning the name as-is
                name = '.'.join(parts)

        self._lookup_cache[node] = name
        return name

    def is_typing(self, node: ast.AST, symbol: str) -> bool:
        """Check if the given node matches the given typing symbol."""
        full_name = self.lookup_full_name(node)
        if full_name is None or '.' not in full_name:
            return False

        module, found_symbol = full_name.rsplit('.', 1)

        return symbol == found_symbol and module in self.typing_modules

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
        if getattr(node, 'id', '') == 'TYPE_CHECKING':
            # NOTE: For backwards-compatibility we still allow unqualified
            #       if TYPE_CHECKING to work, but we may decide to get rid
            #       of this. We'll just have to change our test cases.
            return True
        return self.is_typing(node, 'TYPE_CHECKING')

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
        """Create the global scope."""
        scope = Scope(node)
        self.current_scope = scope
        self.scopes.append(scope)
        self.generic_visit(node)
        return node

    def visit_If(self, node: ast.If) -> Any:
        """Look for a TYPE_CHECKING block."""
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
        # For backwards compatibility we always treat typing as exempt
        # although we may wish to change that to a default setting, so
        # people can override that decision if they choose.
        return module_name == 'typing' or any(
            fnmatch.fnmatch(module_name, exempt_module) for exempt_module in self.exempt_modules
        )

    def add_import(self, node: Import) -> None:  # noqa: C901
        """Add relevant ast objects to import lists."""
        in_type_checking_block = self.in_type_checking_block(node.lineno, node.col_offset)

        # Record the imported names as symbols
        for name_node in node.names:
            if hasattr(name_node, 'asname') and name_node.asname:
                name = name_node.asname
            else:
                name = name_node.name

            self.current_scope.symbols[name].append(
                Symbol(
                    name,
                    node.lineno,
                    node.col_offset,
                    'import',
                    in_type_checking_block=in_type_checking_block,
                )
            )

        all_exempt = in_type_checking_block or (
            isinstance(node, ast.ImportFrom) and node.module and self.is_exempt_module(node.module)
        )

        for name_node in node.names:
            # Skip checking the import if the module is passlisted
            exempt = all_exempt or (isinstance(node, ast.Import) and self.is_exempt_module(name_node.name))

            if name_node.name == '*':
                # don't record * imports
                continue

            # Classify and map imports
            if isinstance(node, ast.ImportFrom):
                module = f'{node.module}.' if node.module else ''
                if node.level != 0:
                    module = '.' * node.level + module
            else:
                module = ''
            imp = ImportName(
                _module=module,
                _alias=name_node.asname,
                _name=name_node.name,
                exempt=exempt,
            )

            # Add to import names map. This is what we use to match imports to uses
            self.imports[imp.name] = imp

            if not exempt:
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

    def visit_Import(self, node: ast.Import) -> None:
        """Append objects to our import map."""
        self.add_import(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Append objects to our import map."""
        self.add_import(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        """Create class scope and Note down class names."""
        for expr in node.decorator_list:
            self.visit(expr)

        in_type_checking_block = self.in_type_checking_block(node.lineno, node.col_offset)
        self.current_scope.symbols[node.name].append(
            Symbol(
                node.name,
                node.lineno,
                node.col_offset,
                'definition',
                in_type_checking_block=in_type_checking_block,
            )
        )

        with self.create_scope(node) as scope:
            # add PEP695 type parameters to class scope
            for type_param in getattr(node, 'type_params', ()):
                scope.symbols[type_param.name].append(
                    Symbol(
                        type_param.name,
                        type_param.lineno,
                        type_param.col_offset,
                        'definition',
                        in_type_checking_block=in_type_checking_block,
                    )
                )
            for head_expr in chain(node.bases, node.keywords):
                self.visit(head_expr)

            has_base_classes = node.bases
            all_base_classes_ignored = all(
                isinstance(base, ast.Name) and base.id in self.pydantic_enabled_baseclass_passlist
                for base in node.bases
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

            for stmt in node.body:
                self.visit(stmt)
            return node

    def visit_Name(self, node: ast.Name) -> ast.Name:
        """Map names."""
        if hasattr(node, ANNOTATION_PROPERTY):
            # Skip handling of annotation objects
            return node

        if self.in_type_checking_block(node.lineno, node.col_offset):
            return node

        names = [node.id]
        if hasattr(node, ATTRIBUTE_PROPERTY):
            names.append(f'{node.id}.{getattr(node, ATTRIBUTE_PROPERTY)}')

        if self.in_soft_use_context:
            self.soft_uses.update(names)
        else:
            for name in names:
                self.uses[name].append((node, self.current_scope))

        return node

    def visit_Constant(self, node: ast.Constant) -> ast.Constant:
        """Map constants."""
        super().visit_Constant(node)
        return node

    def add_annotation(
        self,
        node: ast.AST,
        scope: Scope,
        type: Literal['annotation', 'alias', 'new-alias'] = 'annotation',
        never_evaluates: bool = False,
    ) -> None:
        """Map all annotations on an AST node."""
        self.annotation_visitor.visit(node, scope, type, never_evaluates)

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
        super().visit_AnnAssign(node)

        self.add_annotation(
            node.annotation, self.current_scope, never_evaluates=self.current_scope.ann_assign_never_evaluates
        )

        if node.value is None:
            return

        if isinstance(node.target, ast.Name):
            self.current_scope.symbols[node.target.id].append(
                Symbol(
                    node.target.id,
                    node.target.lineno,
                    node.target.col_offset,
                    (
                        # AnnAssign can omit the RHS, in which case it's just a declaration
                        # and doesn't result in a variable that's available at runtime
                        'definition'
                        if node.value
                        else 'declaration'
                    ),
                    in_type_checking_block=self.in_type_checking_block(node.lineno, node.col_offset),
                )
            )

            # node is an explicit TypeAlias assignment
            if (isinstance(node.annotation, ast.Name) and node.annotation.id == 'TypeAlias') or (
                isinstance(node.annotation, ast.Constant) and node.annotation.value == 'TypeAlias'
            ):
                self.add_annotation(node.value, self.current_scope, 'alias')
                return

        # if it wasn't a TypeAlias we need to visit the value expression
        self.visit(node.value)

    def visit_Assign(self, node: ast.Assign) -> ast.Assign:
        """
        Keep track of variable definitions.

        Assignments are quite complex and can contain multiple targets such as:

            `a = b = c = ...`

        But each target can also be one of many things, such as a single name, a
        list of names, a subscript or an attribute. We only care about names and
        lists of names, i.e.:

            `a = b, c = ...`

        But not something like:

            `foo[a] = foo.bar = ...`

        """
        in_type_checking_block = self.in_type_checking_block(node.lineno, node.col_offset)

        for target in node.targets:
            # each target can either be a single node or an ast.Tuple/ast.List of nodes
            for name in getattr(target, 'elts', [target]):
                if not hasattr(name, 'id'):
                    # if the node isn't an ast.Name we don't record anything
                    continue

                self.current_scope.symbols[name.id].append(
                    Symbol(
                        name.id,
                        name.lineno,
                        name.col_offset,
                        'definition',
                        in_type_checking_block=in_type_checking_block,
                    )
                )

        super().visit_Assign(node)
        return node

    def visit_Global(self, node: ast.Global) -> ast.Global:
        """
        Treat global statements like a normal assignment.

        We don't check if the symbol exists in the global scope, that isn't our job.
        """
        in_type_checking_block = self.in_type_checking_block(node.lineno, node.col_offset)

        for name in node.names:
            if not hasattr(name, 'id'):
                continue

            self.current_scope.symbols[name].append(
                Symbol(
                    name,
                    node.lineno,
                    node.col_offset,
                    'definition',
                    in_type_checking_block=in_type_checking_block,
                )
            )

        return node

    def visit_Nonlocal(self, node: ast.Nonlocal) -> ast.Nonlocal:
        """
        Treat nonlocal statements like a normal assignment.

        We don't check if the symbol exists in the outer scope, that isn't our job.
        """
        in_type_checking_block = self.in_type_checking_block(node.lineno, node.col_offset)

        for name in node.names:
            if not hasattr(name, 'id'):
                continue

            self.current_scope.symbols[name].append(
                Symbol(
                    name,
                    node.lineno,
                    node.col_offset,
                    'definition',
                    in_type_checking_block=in_type_checking_block,
                )
            )

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
            self.add_annotation(node.value, self.current_scope, 'new-alias')

            self.current_scope.symbols[node.name.id].append(
                Symbol(
                    node.name.id,
                    node.lineno,
                    node.col_offset,
                    'definition',
                    in_type_checking_block=self.in_type_checking_block(node.lineno, node.col_offset),
                )
            )

    def register_function_annotations(self, node: Function) -> None:
        """
        Map all annotations in a function signature.

        Annotations include:
            - Argument annotations
            - Keyword argument annotations
            - Return annotations

        And we also note down the start and end line number for the function.
        """
        in_type_checking_block = self.in_type_checking_block(node.lineno, node.col_offset)

        # some of the symbols/annotations need to be added to the head scope
        head_scope = self.current_scope.parent
        assert head_scope is not None
        assert head_scope.is_head

        # add PEP695 type parameters to function head scope
        for type_param in getattr(node, 'type_params', ()):
            head_scope.symbols[type_param.name].append(
                Symbol(
                    type_param.name,
                    type_param.lineno,
                    type_param.col_offset,
                    # we should be able to treat type vars like arguments
                    'argument',
                    in_type_checking_block=in_type_checking_block,
                )
            )

        for argument in chain(node.args.args, node.args.kwonlyargs, node.args.posonlyargs):
            # Map annotations
            if hasattr(argument, 'annotation') and argument.annotation:
                self.add_annotation(argument.annotation, head_scope)

            # argument names go into the function scope not the head scope
            self.current_scope.symbols[argument.arg].append(
                Symbol(
                    argument.arg,
                    argument.lineno,
                    argument.col_offset,
                    'argument',
                    in_type_checking_block=in_type_checking_block,
                )
            )

        for path in ('kwarg', 'vararg'):
            if arg := getattr(node.args, path, None):
                # Map annotations
                if getattr(arg, 'annotation', None):
                    self.add_annotation(arg.annotation, head_scope)

                # argument names go into the function scope not the head scope
                if name := getattr(arg, 'arg', None):
                    self.current_scope.symbols[name].append(
                        Symbol(
                            name, arg.lineno, arg.col_offset, 'argument', in_type_checking_block=in_type_checking_block
                        )
                    )

        # we need to visit the arguments in the head scope instead of the body scope
        with self.change_scope(head_scope):
            self.visit(node.args)

        if returns := getattr(node, 'returns', None):
            self.add_annotation(returns, head_scope)

        if name := getattr(node, 'name', None):
            head_scope.symbols[name].append(
                Symbol(
                    name,
                    node.lineno,
                    node.col_offset,
                    'definition',
                    in_type_checking_block=in_type_checking_block,
                )
            )

        if isinstance(node, ast.Lambda):
            self.visit(node.body)
        else:
            for stmt in node.body:
                self.visit(stmt)

    def visit_FunctionDef(self, node: FunctionDef) -> None:
        """Remove and map function argument- and return annotations."""
        for expr in node.decorator_list:
            self.visit(expr)

        with self.create_scope(node, is_head=True), self.create_scope(node, is_head=False):
            super().visit_FunctionDef(node)
            self.register_function_annotations(node)

    def visit_AsyncFunctionDef(self, node: AsyncFunctionDef) -> None:
        """Remove and map function argument- and return annotations."""
        for expr in node.decorator_list:
            self.visit(expr)

        with self.create_scope(node, is_head=True), self.create_scope(node, is_head=False):
            super().visit_AsyncFunctionDef(node)
            self.register_function_annotations(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        """Remove and map argument symbols."""
        with self.create_scope(node, is_head=True), self.create_scope(node, is_head=False):
            self.register_function_annotations(node)

    @contextmanager
    def set_context(self, node: Comprehension | ast.IfExp) -> Iterator[None]:
        """
        Set the active context for ast.NamedExpr/ast.comprehension.

        This is to deal with the fact that comprehensions and ast.IfExp are
        evaluated out of order, so in order for our symbol lookups to be a
        little bit more accurate we need to attach declarations to the active
        context, rather than the node itself.
        """
        old_context = self.active_context
        self.active_context = node
        yield
        self.active_context = old_context

    def visit_ListComp(self, node: ast.ListComp) -> None:
        """Map symbols in list comprehension."""
        with self.set_context(node):
            self.generic_visit(node)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        """Map symbols in set comprehension."""
        with self.set_context(node):
            self.generic_visit(node)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        """Map symbols in dict comprehension."""
        with self.set_context(node):
            self.generic_visit(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        """Map symbols in generator expressions."""
        with self.set_context(node):
            self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        """
        Map all the symbols in a comprehension.

        Comprehensions are a bit of a special case, since the expressions
        are evaluated out of order, which complicates the symbol lookup.

        We get around that by attaching all targets and all NamedExpr to
        the comprehesion rather than themselves. So everyone inside the
        comprehension can see the symbols.

        This is technically not quite correct, since inside an individual
        if expression the order of symbols still matters. But we don't try
        to catch every single case here, we just use this to figure out
        if type checking symbols are used at runtime, so it's fine if we're
        a little lax here, since there are no annotations inside comprehensions
        anyways.
        """
        assert self.active_context is not None
        in_type_checking_block = self.in_type_checking_block(self.active_context.lineno, self.active_context.col_offset)
        for name in getattr(node.target, 'elts', [node.target]):
            if not hasattr(name, 'id'):
                continue

            self.current_scope.symbols[name.id].append(
                Symbol(
                    name.id,
                    # these symbols can be used in elt/key/value even though
                    # those appear before the comprehension, so we use the
                    # start of the expression as the location of the definition
                    self.active_context.lineno,
                    self.active_context.col_offset,
                    'definition',
                    in_type_checking_block=in_type_checking_block,
                )
            )

        self.visit(node.iter)
        for if_expr in node.ifs:
            self.visit(if_expr)

    def visit_IfExp(self, node: ast.IfExp) -> ast.IfExp:
        """Set the context for named expressions."""
        with self.set_context(node):
            self.generic_visit(node)
            return node

    def visit_NamedExpr(self, node: ast.NamedExpr) -> ast.NamedExpr:
        """
        Keep track of variable definitions.

        If we're inside a comprehension/IfExp then we treat definitions as if
        they occured at the start of the expression to deal with the out of
        order evaluation of comprehensions and if expressions.
        """
        location_node = self.active_context or node
        self.current_scope.symbols[node.target.id].append(
            Symbol(
                node.target.id,
                location_node.lineno,
                location_node.col_offset,
                'definition',
                in_type_checking_block=self.in_type_checking_block(node.lineno, node.col_offset),
            )
        )
        self.visit(node.value)

        return node

    def register_unquoted_type_in_typing_cast(self, node: ast.Call) -> None:
        """Find typing.cast() calls with the type argument unquoted."""
        func = node.func

        if not self.is_typing(func, 'cast') or len(node.args) != 2:
            return  # Not typing.cast() (or an alias) or incorrect number of arguments.

        arg = node.args[0]

        visitor = CastTypeExpressionVisitor(self)
        visitor.visit(arg)
        self.quoted_type_names_in_casts.update(visitor.quoted_names)

        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return  # Type argument is already a string literal.

        self.unquoted_types_in_casts.append((arg.lineno, arg.col_offset, ast.unparse(arg)))

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
        'builtin_names',
        'used_type_checking_names',
        'visitor',
        'generators',
        'future_option_enabled',
    ]

    def __init__(self, node: ast.Module, options: Namespace | None) -> None:
        self.cwd = Path(os.getcwd())
        self.strict_mode = getattr(options, 'type_checking_strict', False)

        # we use the same option as pyflakes to extend the list of builtins
        self.builtin_names = builtin_names
        additional_builtins = getattr(options, 'builtins', [])
        if additional_builtins:
            self.builtin_names.union(additional_builtins)

        self.used_type_checking_names: set[str] = set()

        typing_modules = getattr(options, 'type_checking_typing_modules', [])
        exempt_modules = getattr(options, 'type_checking_exempt_modules', [])
        force_future_annotation = getattr(options, 'type_checking_force_future_annotation', False)
        pydantic_enabled = getattr(options, 'type_checking_pydantic_enabled', False)
        pydantic_enabled_baseclass_passlist = getattr(options, 'type_checking_pydantic_enabled_baseclass_passlist', [])
        sqlalchemy_enabled = getattr(options, 'type_checking_sqlalchemy_enabled', False)
        sqlalchemy_mapped_dotted_names = getattr(options, 'type_checking_sqlalchemy_mapped_dotted_names', [])
        fastapi_enabled = getattr(options, 'type_checking_fastapi_enabled', False)
        fastapi_dependency_support_enabled = getattr(options, 'type_checking_fastapi_dependency_support_enabled', False)
        cattrs_enabled = getattr(options, 'type_checking_cattrs_enabled', False)
        injector_enabled = getattr(options, 'type_checking_injector_enabled', False)

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
            typing_modules=typing_modules,
            exempt_modules=exempt_modules,
            force_future_annotation=force_future_annotation,
            sqlalchemy_enabled=sqlalchemy_enabled,
            sqlalchemy_mapped_dotted_names=sqlalchemy_mapped_dotted_names,
            fastapi_dependency_support_enabled=fastapi_dependency_support_enabled,
            pydantic_enabled_baseclass_passlist=pydantic_enabled_baseclass_passlist,
            injector_enabled=injector_enabled,
        )
        self.visitor.visit(node)

        self.generators = [
            # TC001 - TC003
            self.unused_imports,
            # TC004, TC009 this needs to run before TC100/TC200/TC007
            self.used_type_checking_symbols,
            # TC005
            self.empty_type_checking_blocks,
            # TC006
            self.unquoted_type_in_cast,
            # TC010
            self.invalid_string_literal_in_binop,
            # TC100, TC200, TC007
            self.missing_quotes_or_futures_import,
            # TC101
            self.futures_excess_quotes,
            # TC101, TC201, TC008
            self.excess_quotes,
        ]

    def unused_imports(self) -> Flake8Generator:
        """Yield TC001, TC002, and TC003 errors."""
        import_types = {
            Classified.APPLICATION: (self.visitor.application_imports, TC001),
            Classified.THIRD_PARTY: (self.visitor.third_party_imports, TC002),
            Classified.BUILTIN: (self.visitor.built_in_imports, TC003),
        }

        all_imports = {name for name, imp in self.visitor.imports.items() if not imp.exempt}
        unused_imports = all_imports - self.visitor.names - self.visitor.soft_uses
        used_imports = all_imports - unused_imports
        already_imported_modules = [self.visitor.imports[name].module for name in used_imports]
        annotation_names = list(
            chain(
                (n for i in self.visitor.wrapped_annotations for n in i.names),
                (i.annotation for i in self.visitor.unwrapped_annotations),
                (n for i in self.visitor.excess_wrapped_annotations for n in i.names),
                self.visitor.quoted_type_names_in_casts,
            )
        )

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

    def used_type_checking_symbols(self) -> Flake8Generator:
        """TC004 and TC009."""
        for symbol in self.visitor.type_checking_symbols():
            if symbol.name in self.builtin_names:
                # this symbol is always available at runtime
                continue

            uses = self.visitor.uses.get(symbol.name)
            if not uses:
                # the symbol is not used at runtime so we're fine
                continue

            for use, scope in uses:
                if symbol.type not in ('import', 'definition'):
                    # only imports and definitions can be moved around
                    continue

                if isinstance(use, ast.Constant):
                    # this is actually a quoted name, so it should exist
                    # as long as it's in the scope at all, we don't need
                    # to take the position into account
                    lookup_from = None
                else:
                    lookup_from = use

                if scope.lookup(symbol.name, lookup_from, runtime_only=True):
                    # the symbol is available at runtime so we're fine
                    continue
                elif scope.lookup(symbol.name, lookup_from, runtime_only=False) is not symbol:
                    # we are being shadowed so no need to emit an error, we can emit an error
                    # for the shadowed name instead, this relies more heavily on giving us the
                    # closest match when looking up symbols, so we may sometimes get this wrong
                    # in cases where the symbol has been redefined within the same scope. But
                    # the most important case is nested scopes, so this is probably fine.
                    continue

                if symbol.type == 'import':
                    msg = TC004.format(module=symbol.name)
                    col_offset = 0
                else:
                    msg = TC009.format(name=symbol.name)
                    col_offset = symbol.col_offset

                yield symbol.lineno, col_offset, msg, None

                self.used_type_checking_names.add(symbol.name)

                # no need to check the other uses, since the error is on the symbol
                break

    def empty_type_checking_blocks(self) -> Flake8Generator:
        """TC005."""
        for empty_type_checking_block in self.visitor.empty_type_checking_blocks:
            yield empty_type_checking_block[0], 0, TC005, None

    def unquoted_type_in_cast(self) -> Flake8Generator:
        """TC006."""
        for lineno, col_offset, annotation in self.visitor.unquoted_types_in_casts:
            yield lineno, col_offset, TC006.format(annotation=annotation), None

    def invalid_string_literal_in_binop(self) -> Flake8Generator:
        """TC010."""
        for node in self.visitor.invalid_binop_literals:
            yield node.lineno, node.col_offset, TC010, None

    def missing_quotes_or_futures_import(self) -> Flake8Generator:
        """TC100, TC200 and TC007."""
        encountered_missing_quotes = False

        for item in self.visitor.unwrapped_annotations:
            # A new style alias does never need to be wrapped
            if item.type == 'new-alias':
                continue

            if item.annotation in self.builtin_names:
                # this symbol is always available at runtime
                continue

            if item.annotation in self.used_type_checking_names:
                # this symbol already caused a TC004/TC009
                continue

            # Annotations inside `if TYPE_CHECKING:` blocks do not need to be wrapped
            # unless they're used before definition, which is already covered by other
            # flake8 rules (and also static type checkers)
            if self.visitor.in_type_checking_block(item.lineno, item.col_offset):
                continue

            if item.scope.lookup(item.annotation, item, runtime_only=False) and not item.scope.lookup(
                item.annotation, item, runtime_only=True
            ):
                # the symbol is only available for type checking
                if item.type == 'alias':
                    error = TC007.format(alias=item.annotation)
                else:
                    encountered_missing_quotes = True
                    error = TC200.format(annotation=item.annotation)
                yield item.lineno, item.col_offset, error, None

        # if any of the symbols imported/declared in type checking blocks are used
        # in an annotation outside a type checking block, then we need to emit TC100
        if (
            encountered_missing_quotes
            or (
                self.visitor.force_future_annotation
                and (self.visitor.unwrapped_annotations or self.visitor.wrapped_annotations)
            )
        ) and not self.visitor.futures_annotation:
            yield 1, 0, TC100, None

    def futures_excess_quotes(self) -> Flake8Generator:
        """TC101."""
        # If futures imports are present, any ast.Constant captured in add_annotation should yield an error
        if self.visitor.futures_annotation:
            for item in self.visitor.wrapped_annotations:
                if item.type != 'annotation':  # TypeAlias value will not be affected by a futures import
                    continue

                yield item.lineno, item.col_offset, TC101.format(annotation=item.annotation), None
        # If no futures imports are present, then we use the generic excess_quotes function
        # since the logic is the same as TC201

    def excess_quotes(self) -> Flake8Generator:
        """TC101, TC201 and TC008."""
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

            """
            With wrapped annotations, things get more tricky:

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

            if any(
                name not in self.builtin_names
                and (
                    item.scope.lookup(name, item, runtime_only=False) is not None
                    and item.scope.lookup(name, item, runtime_only=True) is None
                )
                for name in item.names
            ):
                # if any of the symbols are only available at type checking time we can't unwrap
                continue

            if item.type == 'alias':
                error = TC008.format(alias=item.annotation)
            else:
                error = TC201.format(annotation=item.annotation)

                if not self.visitor.futures_annotation:
                    yield item.lineno, item.col_offset, TC101.format(annotation=item.annotation), None

            yield item.lineno, item.col_offset, error, None

        for item in self.visitor.excess_wrapped_annotations:
            assert item.type == 'annotation'
            # This always generates an error in either case
            yield item.lineno, item.col_offset, TC101.format(annotation=item.annotation), None
            yield item.lineno, item.col_offset, TC201.format(annotation=item.annotation), None

    @property
    def errors(self) -> Flake8Generator:
        """
        Return relevant errors in the required flake8-defined format.

        Flake8 plugins must return generators in this format: https://flake8.pycqa.org/en/latest/plugin-development/
        """
        for generator in self.generators:
            yield from generator()
