from __future__ import annotations

import ast
import os
from ast import Index
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, cast

from aspy.refactor_imports.classify import ImportType, classify_import

from flake8_type_checking.constants import (
    ATTRIBUTE_PROPERTY,
    ATTRS_DECORATORS,
    ATTRS_IMPORTS,
    TC001,
    TC002,
    TC003,
    TC004,
    TC005,
    TC100,
    TC101,
    TC200,
    TC201,
    py38,
)
from flake8_type_checking.types import ImportTypeValue

if TYPE_CHECKING:
    from _ast import AsyncFunctionDef, FunctionDef
    from argparse import Namespace
    from typing import Any, Optional, Union

    from flake8_type_checking.types import (
        ErrorDict,
        Flake8Generator,
        FunctionRangesDict,
        FunctionScopeImportsDict,
        Import,
        Name,
    )

    MixinBase = 'ImportVisitor'

else:
    MixinBase = object


class AttrsMixin:
    """
    Contains necessary logic for cattrs + attrs support.

    When the cattrs_enabled option is specified as True,
    we treat type hints on attrs classes as needed at runtime.
    """

    remote_imports: dict[str, ErrorDict]

    def get_all_attrs_imports(self) -> dict[Optional[str], str]:
        """Return a map of all attrs/attr imports."""
        attrs_imports: dict[Optional[str], str] = {}  # map of alias to full import name

        for error_dict in self.remote_imports.values():
            module = getattr(error_dict['node'], 'module', '')
            names: list[Name] = getattr(error_dict['node'], 'names', [])

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


class DunderAllMixin(MixinBase):  # type: ignore
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


class FastAPIMixin(MixinBase):  # type: ignore
    """
    Contains the necessary logic for FastAPI support.

    For FastAPI app/route-decorated views, and for dependencies, we want
    to treat annotations as needed at runtime.
    """

    fastapi_enabled: bool
    fastapi_dependency_support_enabled: bool

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Remove and map function arguments and returns."""
        if (self.fastapi_enabled and node.decorator_list) or self.fastapi_dependency_support_enabled:
            self.handle_fastapi_decorator(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Remove and map function arguments and returns."""
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


class ImportVisitor(DunderAllMixin, AttrsMixin, FastAPIMixin, ast.NodeTransformer):
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
        self.pydantic_enabled = pydantic_enabled
        self.fastapi_enabled = fastapi_enabled
        self.fastapi_dependency_support_enabled = fastapi_dependency_support_enabled
        self.cattrs_enabled = cattrs_enabled
        self.pydantic_enabled_baseclass_passlist = pydantic_enabled_baseclass_passlist
        self.cwd = cwd  # we need to know the current directory to guess at which imports are remote and which are not

        # Import patterns we want to avoid mapping
        self.exempt_imports: list[str] = ['*', 'TYPE_CHECKING']
        self.exempt_modules: list[str] = exempt_modules or []

        # All imports in each bucket
        self.local_imports: dict[str, ErrorDict] = {}
        self.remote_imports: dict[str, ErrorDict] = {}

        # Map of import name to verbose import name and bool indicating whether it's a local or remote import
        self.import_names: dict[str, tuple[str, bool]] = {}

        # List of all names and ids, except type declarations - used to find otherwise unused imports
        self.uses: dict[str, ast.AST] = {}

        # Tuple of (node, import name) for all import defined within a type-checking block
        self.type_checking_block_imports: set[tuple[Import, str]] = set()
        self.class_names: set[str] = set()

        self.unused_type_checking_block_imports: set[tuple[Import, str]] = set()

        # All type annotations in the file, without quotes around them
        self.unwrapped_annotations: list[tuple[int, int, str]] = []

        # All type annotations in the file, with quotes around them
        self.wrapped_annotations: list[tuple[int, int, str]] = []

        # Whether there is a `from __futures__ import annotations` is present
        self.futures_annotation: Optional[bool] = None

        # Where the type checking block exists (line_start, line_end, col_offset)
        self.empty_type_checking_blocks: list[tuple[int, int, int]] = []
        self.type_checking_blocks: list[tuple[int, int, int]] = []

        # Function scopes can tell us if imports that appear in type-checking blocks
        # are repeated inside a function. This prevents false TC004 positives.
        self.function_scope_imports: dict[int, FunctionScopeImportsDict] = {}
        self.function_ranges: dict[int, FunctionRangesDict] = {}

        self.type_checking_alias: Optional[str] = None
        self.typing_alias: Optional[str] = None

    @property
    def names(self) -> set[str]:
        """Return unique names."""
        return set(self.uses.keys())

    # -- Map type checking block ---------------

    def in_type_checking_block(self, node: ast.AST) -> bool:
        """Indicate whether an import is defined inside an `if TYPE_CHECKING` block or not."""
        if node.col_offset == 0:
            return False
        if not self.type_checking_blocks and not self.empty_type_checking_blocks:
            return False

        return any(
            type_checking_block[0] <= node.lineno <= type_checking_block[1]
            for type_checking_block in self.type_checking_blocks + self.empty_type_checking_blocks
        )

    def visit_If(self, node: ast.If) -> Any:
        """Look for a TYPE_CHECKING block."""
        # True for `if typing.TYPE_CHECKING:` or `if T.TYPE_CHECKING:`
        typing_type_checking = (
            hasattr(node.test, 'attr') and node.test.attr == 'TYPE_CHECKING'  # type: ignore[attr-defined]
        )

        if typing_type_checking:
            # By default, TYPE_CHECKING is exempt from being noted as
            # an import which can be moved into a type-checking block.
            # When a user does `import typing\nif typing.TYPE_CHECKING`,
            # we also add typing to exempt imports and remove any already
            # found errors.
            # We could have just added typing as a blanket ignored module,
            # but that's a breaking change, so this will do for now.
            typing_module_name = self.typing_alias or 'typing'
            self.exempt_imports.append(typing_module_name)
            if typing_module_name in self.remote_imports:
                del self.remote_imports[typing_module_name]
            if typing_module_name in self.import_names:
                del self.import_names[typing_module_name]

        # True if `if TYPE_CHECKING:`
        type_checking = hasattr(node.test, 'id') and node.test.id == 'TYPE_CHECKING'  # type: ignore[attr-defined]

        type_checking_alias = (
            self.type_checking_alias
            and hasattr(node.test, 'id')
            and node.test.id == self.type_checking_alias  # type: ignore[attr-defined]
        )

        if type_checking or typing_type_checking or type_checking_alias:  # type: ignore[attr-defined]
            # Here we want to define the line-number-range where the type-checking block exists
            # Initially I just set the node.lineno and node.end_lineno, but it turns out that else blocks are
            # included in this span. Because of this, we now first look for else block to help us limit the range
            start_of_else_block = None
            if hasattr(node, 'orelse') and node.orelse:
                # Just set the lineno of the first element in the else block - 1
                start_of_else_block = node.orelse[0].lineno - 1

            # Type checking blocks that only contain 'pass' are appended to an empty-type-checking-block list
            # and flagged with TC005 errors.
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

    def add_import(self, node: Import) -> None:
        """Add relevant ast objects to import lists."""
        if self.in_type_checking_block(node):
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

        # 1/2 Skip checking the import if the module is passlisted.
        if isinstance(node, ast.ImportFrom) and node.module in self.exempt_modules:
            return

        for name_node in node.names:
            # 2/2 Skip checking the import if the module is passlisted
            if isinstance(node, ast.Import) and name_node.name in self.exempt_modules:
                return

            # Check for `from __futures__ import annotations`
            if self.futures_annotation is None:
                if getattr(node, 'module', '') == '__future__' and any(
                    name.name == 'annotations' for name in node.names
                ):
                    self.futures_annotation = True
                    return
                else:
                    # futures imports should always be the first line
                    # in a file, so we should only need to check this once
                    self.futures_annotation = False

            # Look for a TYPE_CHECKING import
            if name_node.name == 'TYPE_CHECKING' and name_node.asname is not None:
                self.type_checking_alias = name_node.asname

            # Look for typing import
            if name_node.name == 'typing' and name_node.asname is not None:
                self.typing_alias = name_node.asname

            # Map imports as belonging to the current module, or belonging to a third-party mod
            if name_node.name not in self.exempt_imports:
                module = f'{node.module}.' if isinstance(node, ast.ImportFrom) else ''
                if hasattr(name_node, 'asname') and name_node.asname:
                    name = name_node.asname
                    import_name = name_node.asname
                else:
                    name = name_node.name
                    import_name = module + name_node.name

                import_type = classify_import(f'{module}{name_node.name}')

                if import_type == ImportType.APPLICATION:
                    self.local_imports[import_name] = {'error': TC001, 'node': node}
                    self.import_names[name] = import_name, True
                else:
                    self.remote_imports[import_name] = {'error': TC002, 'node': node}
                    self.import_names[name] = import_name, False

                if node.lineno not in self.function_scope_imports:
                    self.function_scope_imports[node.lineno] = {'imports': []}
                self.function_scope_imports[node.lineno]['imports'].append(name)

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
        if self.in_type_checking_block(node):
            return node
        if hasattr(node, ATTRIBUTE_PROPERTY):
            self.uses[f'{node.id}.{getattr(node, ATTRIBUTE_PROPERTY)}'] = node

        self.uses[node.id] = node
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.Constant:
        """Map constants."""
        super().visit_Constant(node)

        if self.in_type_checking_block(node):
            return node

        return node

    def add_annotation(self, node: ast.AST) -> None:
        """
        Map all annotations on a generic ast node.

        This is a bit of a catch-all method.
        """
        if isinstance(node, ast.Ellipsis):
            return
        if py38 and isinstance(node, Index):
            return self.add_annotation(node.value)
        if isinstance(node, ast.Constant):
            if node.value is None:
                return
            self.wrapped_annotations.append((node.lineno, node.col_offset, node.value))
        elif isinstance(node, ast.Subscript):
            value = cast(ast.Name, node.value)
            if hasattr(value, 'id') and value.id == 'Literal':
                # Type hinting like `x: Literal['one', 'two', 'three']`
                # creates false positives unless excluded
                return
            self.add_annotation(node.value)
            self.add_annotation(node.slice)
        elif isinstance(node, ast.Name):
            self.unwrapped_annotations.append((node.lineno, node.col_offset, node.id))
        elif isinstance(node, (ast.Tuple, ast.List)):
            for n in node.elts:
                self.add_annotation(n)
        elif node is None:  # noqa: SIM114
            return
        elif isinstance(node, ast.Attribute):
            self.add_annotation(node.value)
        elif isinstance(node, ast.BinOp):
            return

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
        with suppress(Exception):
            parent = getattr(node, ATTRIBUTE_PROPERTY)
            node.attr = f'{node.attr}.{parent}'
        node = self.set_child_node_attribute(node, ATTRIBUTE_PROPERTY, node.attr)
        self.generic_visit(node)
        return node

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Remove all annotation assignments."""
        self.add_annotation(node.annotation)
        if getattr(node, 'value', None):
            self.generic_visit(node.value)  # type: ignore[arg-type]

    def register_function_annotations(self, node: Union[FunctionDef, AsyncFunctionDef]) -> None:
        """
        Map all annotations in a function signature.

        Annotations include:
            - Argument annotations
            - Keyword argument annotations
            - Return annotations

        And we also note down the start and end line number for the function.
        """
        for path in [node.args.args, node.args.kwonlyargs]:
            for argument in path:
                if hasattr(argument, 'annotation') and argument.annotation:
                    self.add_annotation(argument.annotation)
                    delattr(argument, 'annotation')

        if (
            hasattr(node.args, 'kwarg')
            and node.args.kwarg
            and hasattr(node.args.kwarg, 'annotation')
            and node.args.kwarg.annotation
        ):
            self.add_annotation(node.args.kwarg.annotation)
            delattr(node.args.kwarg, 'annotation')

        if (
            hasattr(node.args, 'vararg')
            and node.args.vararg
            and hasattr(node.args.vararg, 'annotation')
            and node.args.vararg.annotation
        ):
            self.add_annotation(node.args.vararg.annotation)
            delattr(node.args.vararg, 'annotation')

        if hasattr(node, 'returns') and node.returns:
            self.add_annotation(node.returns)
            delattr(node, 'returns')

        # Register function start and end
        end_lineno = cast(int, node.end_lineno)
        for i in range(node.lineno, end_lineno + 1):
            self.function_ranges[i] = {'start': node.lineno, 'end': end_lineno + 1}

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Remove and map function arguments and returns."""
        super().visit_FunctionDef(node)
        self.register_function_annotations(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Remove and map function arguments and returns."""
        super().visit_AsyncFunctionDef(node)
        self.register_function_annotations(node)
        self.generic_visit(node)


class TypingOnlyImportsChecker:
    """Checks for imports exclusively used by type annotation elements."""

    __slots__ = [
        'cwd',
        'visitor',
        'generators',
        'future_option_enabled',
    ]

    def __init__(self, node: ast.Module, options: Optional[Namespace]) -> None:
        self.cwd = Path(os.getcwd())

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
            # TC001
            self.unused_import,
            # TC002
            self.unused_third_party_import,
            # TC003
            self.multiple_type_checking_blocks,
            # TC004
            self.used_type_checking_imports,
            # TC005
            self.empty_type_checking_blocks,
            # TC100
            self.missing_futures_import,
            # TC101
            self.futures_excess_quotes,
            # TC200
            self.missing_quotes,
            # TC201
            self.excess_quotes,
        ]

    def unused_import(self) -> Flake8Generator:
        """TC001."""
        for name in set(self.visitor.import_names) - self.visitor.names:
            unused_import, local_import = self.visitor.import_names[name]
            if local_import and all(unused_import not in str(use) for use in self.visitor.uses):
                obj = self.visitor.local_imports.pop(unused_import)
                error_message, node = obj['error'], obj['node']
                yield node.lineno, node.col_offset, error_message.format(module=unused_import), None

    def unused_third_party_import(self) -> Flake8Generator:
        """TC002."""
        for name in set(self.visitor.import_names) - self.visitor.names:
            unused_import, local_import = self.visitor.import_names[name]
            if not local_import and all(unused_import not in str(use) for use in self.visitor.uses):
                obj = self.visitor.remote_imports.pop(unused_import)
                error_message, node = obj['error'], obj['node']
                yield node.lineno, node.col_offset, error_message.format(module=unused_import), None

    def multiple_type_checking_blocks(self) -> Flake8Generator:
        """TC003."""
        if len([i for i in self.visitor.type_checking_blocks if i[2] == 0]) > 1:
            yield self.visitor.type_checking_blocks[-1][0], 0, TC003, None

    def used_type_checking_imports(self) -> Flake8Generator:
        """TC004."""
        for _import, import_name in self.visitor.type_checking_block_imports:
            if import_name in self.visitor.uses:
                # If we get to here, we're pretty sure that the import
                # shouldn't actually live inside a type-checking block

                use = self.visitor.uses[import_name]

                # .. or whether there is another duplicate import inside the function scope
                # (if the use is in a function scope)
                if use.lineno in self.visitor.function_ranges:
                    for i in range(
                        self.visitor.function_ranges[use.lineno]['start'],
                        self.visitor.function_ranges[use.lineno]['end'],
                    ):
                        if (
                            i in self.visitor.function_scope_imports
                            and import_name in self.visitor.function_scope_imports[i]['imports']
                        ):
                            return

                yield _import.lineno, 0, TC004.format(module=import_name), None

    def empty_type_checking_blocks(self) -> Flake8Generator:
        """TC005."""
        for empty_type_checking_block in self.visitor.empty_type_checking_blocks:
            yield empty_type_checking_block[0], 0, TC005, None

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
            for lineno, col_offset, annotation in self.visitor.wrapped_annotations:
                yield lineno, col_offset, TC101.format(annotation=annotation), None
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

            Because we can't match exactly, I've erred on the side of caution below, opting for some false negatives
            instead of some false positives.

            For anyone with more insight into how this might be tackled, contributions are very welcome.
            """
            for lineno, col_offset, annotation in self.visitor.wrapped_annotations:
                for _, import_name in self.visitor.type_checking_block_imports:
                    if import_name in annotation:
                        break

                else:
                    for class_name in self.visitor.class_names:
                        if class_name == annotation:
                            break
                    else:
                        yield lineno, col_offset, TC101.format(annotation=annotation), None

    def missing_quotes(self) -> Flake8Generator:
        """TC200."""
        for lineno, col_offset, annotation in self.visitor.unwrapped_annotations:
            for _, name in self.visitor.type_checking_block_imports:
                if annotation == name:
                    yield lineno, col_offset, TC200.format(annotation=annotation), None

    def excess_quotes(self) -> Flake8Generator:
        """TC201."""
        for lineno, col_offset, annotation in self.visitor.wrapped_annotations:
            # See comment in futures_excess_quotes
            for _, import_name in self.visitor.type_checking_block_imports:
                if import_name in annotation:
                    break
            else:
                for class_name in self.visitor.class_names:
                    if class_name == annotation:
                        break
                else:
                    yield lineno, col_offset, TC201.format(annotation=annotation), None

    @property
    def errors(self) -> Flake8Generator:
        """
        Return relevant errors in the required flake8-defined format.

        Flake8 plugins must return generators in this format: https://flake8.pycqa.org/en/latest/plugin-development/
        """
        for generator in self.generators:
            yield from generator()
