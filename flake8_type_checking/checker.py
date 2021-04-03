from __future__ import annotations

import ast
import os
from contextlib import suppress
from importlib.util import find_spec
from pathlib import Path
from typing import TYPE_CHECKING, Tuple

from flake8_type_checking.constants import TC001, TC002, TC003, TC004, TC100, TC101, TC200, TC201

if TYPE_CHECKING:
    from typing import Any, List, Optional

    from flake8_type_checking.types import Flake8Generator, ImportType

possible_local_errors = ()
with suppress(ModuleNotFoundError):
    # noinspection PyUnresolvedReferences
    from django.core.exceptions import AppRegistryNotReady, ImproperlyConfigured

    possible_local_errors += (AppRegistryNotReady, ImproperlyConfigured)  # type: ignore


class ImportVisitor(ast.NodeTransformer):
    """Map all imports outside of type-checking blocks."""

    __slots__ = (
        'cwd',
        'exempt_imports',
        'local_imports',
        'remote_imports',
        'import_names',
        'uses',
        'unwrapped_annotations',
    )

    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd  # we need to know the current directory to guess at which imports are remote and which are not

        # Import patterns we want to avoid mapping
        self.exempt_imports: list[str] = ['*', 'TYPE_CHECKING']

        # All imports in each bucket
        self.local_imports: dict[str, dict] = {}
        self.remote_imports: dict[str, dict] = {}

        # Map of import name to verbose import name and bool indicating whether it's a local or remote import
        self.import_names: dict[str, tuple[str, bool]] = {}

        # List of all names and ids, except type declarations - used to find otherwise unused imports
        self.uses: dict[str, ast.AST] = {}

        # Tuple of (node, import name) for all import defined within a type-checking block
        self.type_checking_block_imports: set[tuple[ImportType, str]] = set()
        self.class_names: set[str] = set()

        self.unused_type_checking_block_imports: set[tuple[ImportType, str]] = set()

        # All type annotations in the file, without quotes around them
        self.unwrapped_annotations: list[tuple[int, int, str]] = []

        # All type annotations in the file, with quotes around them
        self.wrapped_annotations: list[tuple[int, int, str]] = []

        # Whether there is a `from __futures__ import annotations` is present
        self.futures_annotation: Optional[bool] = None

        # Where the type checking block exists (line_start, line_end, col_offset)
        self.type_checking_blocks: List[tuple[int, int, int]] = []

        # Function scopes can tell us if imports that appear in type-checking blocks
        # are repeated inside a function. This prevents false TC004 positives.
        self.function_scopes: dict[int, dict] = {}

    @property
    def names(self) -> set[str]:
        """Return unique names."""
        return set(self.uses.keys())

    # -- Map type checking block ---------------

    def _in_type_checking_block(self, node: ast.AST) -> bool:
        """Indicate whether an import is defined inside an `if TYPE_CHECKING` block or not."""
        if node.col_offset == 0:
            return False
        if not self.type_checking_blocks:
            return False
        return any(
            type_checking_block[0] <= node.lineno <= type_checking_block[1]
            for type_checking_block in self.type_checking_blocks
        )

    def visit_If(self, node: ast.If) -> Any:
        """Look for a TYPE_CHECKING block."""
        if hasattr(node.test, 'id') and node.test.id == 'TYPE_CHECKING':  # type: ignore
            self.type_checking_blocks.append((node.lineno, node.end_lineno or node.lineno, node.col_offset))
        self.generic_visit(node)
        return node

    # -- Map imports -------------------------------

    def _import_is_local(self, import_name: str) -> bool:
        """
        Guess at whether an import is remote or a part of the local repo.

        Not sure if there is a best-practice way of asserting whether an import is made from the current project.
        The assumptions made below are:

            1. It's definitely not a local imports if we can't import it
            2. If we can import it, but 'venv' is in the path, it's not a local import
            3. If the current working directory (where flake8 is called from) is not present in the parent
            directories (excluding venv) it's probably a remote import (probably stdlib)

        The second and third assumptions are not iron clad, and could
        generate false positives, but should work for a first iteration.
        """
        try:
            if '.' in import_name:
                spec = find_spec('.'.join(import_name.split('.')[:-1]), import_name.split('.')[-1])
            else:
                spec = find_spec(import_name)
        except ModuleNotFoundError:
            return False
        except possible_local_errors:
            return True
        except ValueError:
            return False

        if not spec:
            return False

        if not spec.origin or 'venv' in spec.origin:
            return False

        origin = Path(spec.origin)
        return self.cwd in origin.parents

    def _add_import(self, node: ImportType) -> None:
        """
        Add relevant ast objects to import lists.

        :param node: ast.Import or ast.ImportFrom object
        """
        if self._in_type_checking_block(node):
            # For type checking blocks we want to
            # 1. Record annotations for TCH2XX errors
            # 2. Avoid recording imports for TCH1XX errors, by returning early
            for name_node in node.names:
                if hasattr(name_node, 'asname') and name_node.asname:
                    name = name_node.asname
                else:
                    name = name_node.name
                self.type_checking_block_imports.add((node, name))
            return None

        for name_node in node.names:
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

            # Map imports as belonging to the current module, or belonging to a third-party mod
            if name_node.name not in self.exempt_imports:
                module = f'{node.module}.' if isinstance(node, ast.ImportFrom) else ''
                if hasattr(name_node, 'asname') and name_node.asname:
                    name = name_node.asname
                    import_name = name_node.asname
                else:
                    name = name_node.name
                    import_name = module + name_node.name
                is_local = self._import_is_local(f'{module}{name_node.name}')
                if is_local:
                    self.local_imports[import_name] = {'error': TC001, 'node': node}
                    self.import_names[name] = import_name, True

                else:
                    self.remote_imports[import_name] = {'error': TC002, 'node': node}
                    self.import_names[name] = import_name, False

                if node.lineno not in self.function_scopes:
                    self.function_scopes[node.lineno] = {'imports': []}
                self.function_scopes[node.lineno]['imports'].append(name)

    def visit_Import(self, node: ast.Import) -> None:
        """Append objects to our import map."""
        self._add_import(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Append objects to our import map."""
        self._add_import(node)

    # -- Map uses in a file ---------------------------

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        """Note down class names."""
        self.class_names.add(node.name)
        self.generic_visit(node)
        return node

    def visit_Name(self, node: ast.Name) -> ast.Name:
        """Map names."""
        if hasattr(node, 'parent'):
            self.uses[f'{node.id}.{node.parent}'] = node  # type: ignore
        self.uses[node.id] = node
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.Constant:
        """Map constants."""
        self.uses[node.value] = node
        return node

    # -- Map annotations ------------------------------

    def _add_annotation(self, node: ast.AST) -> None:
        if isinstance(node, ast.Ellipsis):
            return
        if isinstance(node, ast.Constant):
            if node.value is None:
                return
            self.wrapped_annotations.append((node.lineno, node.col_offset, node.value))
        elif isinstance(node, ast.Subscript):
            if hasattr(node.value, 'id') and node.value.id == 'Literal':  # type: ignore
                # Type hinting like `x: Literal['one', 'two', 'three']`
                # creates false TCHX01 positives unless excluded
                return
            self._add_annotation(node.value)
            self._add_annotation(node.slice)
        elif isinstance(node, ast.Name):
            self.unwrapped_annotations.append((node.lineno, node.col_offset, node.id))
        elif isinstance(node, (ast.Tuple, ast.List)):
            for n in node.elts:
                self._add_annotation(n)
        elif node is None:
            return
        elif isinstance(node, ast.Attribute):
            self._add_annotation(node.value)
        elif isinstance(node, ast.BinOp):
            return

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        # Set the attribute of the current node
        try:
            parent = node.parent  # type: ignore
            node.attr = f'{node.attr}.{parent}'
        except Exception:
            pass

        # Set the parent attribute on the current node children
        for key, value in node.__dict__.items():
            if type(value) not in [int, str]:
                setattr(node.__dict__[key], 'parent', node.attr)

        self.generic_visit(node)
        return node

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Remove all annotation assignments."""
        self._add_annotation(node.annotation)
        if getattr(node, 'value', None):
            self.generic_visit(node.value)  # type: ignore

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Remove and map function arguments and returns."""
        # Map annotations
        for path in [node.args.args, node.args.kwonlyargs]:
            argument: ast.arg
            for argument in path:
                if hasattr(argument, 'annotation'):
                    self._add_annotation(argument.annotation)  # type: ignore
                    delattr(argument, 'annotation')
        if hasattr(node.args, 'kwarg'):
            kwarg = node.args.kwarg
            if hasattr(kwarg, 'annotation'):
                self._add_annotation(kwarg.annotation)  # type: ignore
                delattr(kwarg, 'annotation')
        if hasattr(node.args, 'vararg'):
            vararg = node.args.vararg
            if hasattr(vararg, 'annotation'):
                self._add_annotation(vararg.annotation)  # type: ignore
                delattr(vararg, 'annotation')
        if hasattr(node, 'returns'):
            self._add_annotation(node.returns)  # type: ignore
            delattr(node, 'returns')

        # Register function start and end
        for i in range(node.lineno, node.end_lineno + 1):  # type: ignore
            # TODO: Find a better data structure for this
            if i not in self.function_scopes:
                self.function_scopes[i] = {'imports': []}
            self.function_scopes[i]['start'] = node.lineno
            self.function_scopes[i]['end'] = node.end_lineno + 1  # type: ignore

        self.generic_visit(node)


class TypingOnlyImportsChecker:
    """Checks for imports exclusively used by type annotation elements."""

    __slots__ = [
        'cwd',
        'visitor',
        'generators',
        'future_option_enabled',
    ]

    def __init__(self, node: ast.Module) -> None:
        self.cwd = Path(os.getcwd())
        self.visitor = ImportVisitor(self.cwd)
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
            if local_import:
                if not any(unused_import in str(use) for use in self.visitor.uses):
                    obj = self.visitor.local_imports.pop(unused_import)
                    error_message, node = obj['error'], obj['node']
                    yield node.lineno, node.col_offset, error_message.format(module=unused_import), None

    def unused_third_party_import(self) -> Flake8Generator:
        """TC002."""
        for name in set(self.visitor.import_names) - self.visitor.names:
            unused_import, local_import = self.visitor.import_names[name]
            if not local_import:
                if not any(unused_import in str(use) for use in self.visitor.uses):
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

                # before we yield we just want to check one thing: whether the use is inside a type checking block..
                if self.visitor._in_type_checking_block(use):
                    return

                # .. or whether there is another duplicate import inside the function scope
                # (if the use is in a function scope)
                if use.lineno in self.visitor.function_scopes:
                    for i in range(
                        self.visitor.function_scopes[use.lineno]['start'],
                        self.visitor.function_scopes[use.lineno]['end'],
                    ):
                        print(import_name)
                        print(self.visitor.function_scopes[i]['imports'])
                        if import_name in self.visitor.function_scopes[i]['imports']:
                            return

                yield _import.lineno, 0, TC004.format(module=import_name), None

    def missing_futures_import(self) -> Flake8Generator:
        """TC100."""
        if (
            not self.visitor.futures_annotation
            and {name for _, name in self.visitor.type_checking_block_imports} - self.visitor.names
        ):
            yield 1, 0, TC100, None

    def futures_excess_quotes(self) -> Flake8Generator:
        """TC101."""
        # If futures imports are present, any ast.Constant captured in _add_annotation should yield an error
        if self.visitor.futures_annotation:
            for (lineno, col_offset, annotation) in self.visitor.wrapped_annotations:
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
            for (lineno, col_offset, annotation) in self.visitor.wrapped_annotations:
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
        for (lineno, col_offset, annotation) in self.visitor.unwrapped_annotations:
            for _, name in self.visitor.type_checking_block_imports:
                if annotation == name:
                    yield lineno, col_offset, TC200.format(annotation=annotation), None

    def excess_quotes(self) -> Flake8Generator:
        """TC201."""
        for (lineno, col_offset, annotation) in self.visitor.wrapped_annotations:
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
