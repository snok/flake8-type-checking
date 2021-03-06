import ast
import os
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from flake8_typing_only_imports.constants import TYO100, TYO101, TYO200, TYO201
from flake8_typing_only_imports.types import ImportType, flake8_generator


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
        self.exempt_imports: List[str] = ['*']

        # All imports in each bucket
        self.local_imports: Dict[str, dict] = {}
        self.remote_imports: Dict[str, dict] = {}

        # Map of import name to verbose import name and bool indicating whether it's a local or remote import
        self.import_names: Dict[str, Tuple[str, bool]] = {}

        # List of all names and ids, except type declarations - used to find otherwise unused imports
        self.uses: List[str] = []

        # Tuple of (node, import name) for all import defined within a type-checking block
        self.type_checking_block_imports: Set[Tuple[ImportType, str]] = set()

        # All type annotations in the file, without quotes around them
        self.unwrapped_annotations: List[Tuple[int, int, str]] = []

        # All type annotations in the file, with quotes around them
        self.wrapped_annotations: List[Tuple[int, int, str]] = []

        # Whether there is a `from __futures__ import annotations` is present
        self.futures_annotation: Optional[bool] = None

        # Where the type checking block exists (line_start, line_end)
        self.type_checking: Optional[Tuple[int, int]] = None

    # Map imports

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

        # assumption 1
        if not spec:
            return False

        # assumption 2
        if not spec.origin or 'venv' in spec.origin:
            return False

        # assumption 3
        origin = Path(spec.origin)
        return self.cwd in origin.parents

    def _import_defined_inside_type_checking_block(self, node: ImportType) -> bool:
        """Indicate whether an import is defined inside an `if TYPE_CHECKING` block or not."""
        if node.col_offset == 0:
            return False
        if self.type_checking is None:
            return False
        return self.type_checking[0] <= node.lineno <= self.type_checking[1]

    def visit_If(self, node: ast.If) -> Any:
        """Look for a TYPE_CHECKING block."""
        if hasattr(node.test, 'id') and node.test.id == 'TYPE_CHECKING':  # type: ignore
            self.type_checking = (node.lineno, node.end_lineno or node.lineno)
        self.generic_visit(node)
        return node

    def _add_import(self, node: ImportType) -> None:
        """
        Add relevant ast objects to import lists.

        :param node: ast.Import or ast.ImportFrom object
        """
        if self._import_defined_inside_type_checking_block(node):
            # For type checking blocks we want to
            # 1. Record annotations for TYO2XX errors
            # 2. Avoid recording imports for TYO1XX errors, by returning early
            for name_node in node.names:
                if hasattr(name_node, 'asname') and name_node.asname:
                    name = name_node.asname
                else:
                    name = name_node.name
                self.type_checking_block_imports.add((node, name))
            return None
        for name_node in node.names:
            # Check for `from __futures__ import annotations`
            if (
                self.futures_annotation is False
                and not self.futures_annotation
                and getattr(node, 'module', '') == '__future__'
                and any(name.name == 'annotations' for name in node.names)
            ):
                self.futures_annotation = True
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
                    self.local_imports[import_name] = {'error': TYO100, 'node': node}
                    self.import_names[name] = import_name, True
                else:
                    self.remote_imports[import_name] = {'error': TYO101, 'node': node}
                    self.import_names[name] = import_name, False

    def visit_Import(self, node: ast.Import) -> ast.Import:
        """Append objects to our import map."""
        self._add_import(node)
        return node

    def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.ImportFrom:
        """Append objects to our import map."""
        self._add_import(node)
        return node

    # Map uses in a file

    @property
    def names(self) -> Set[str]:
        """Return unique names."""
        return set(self.uses)

    def visit_Name(self, node: ast.Name) -> ast.Name:
        """Map names."""
        self.uses.append(node.id)
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.Constant:
        """Map constants."""
        self.uses.append(node.value)
        return node

    # Map annotations

    def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.AnnAssign:
        """Remove all annotation assignments."""
        if hasattr(node, 'annotation') and node.annotation:
            if isinstance(node.annotation, ast.Name):
                self.unwrapped_annotations.append((node.lineno, node.col_offset, node.annotation.id))
                delattr(node, 'annotation')
            elif isinstance(node.annotation, ast.Constant):
                self.wrapped_annotations.append((node.lineno, node.col_offset, node.annotation.value))
                delattr(node, 'annotation')
        self.generic_visit(node)
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        """Remove all function arguments."""
        for path in [node.args.args, node.args.kwonlyargs]:
            argument: ast.arg
            for argument in path:
                if hasattr(argument, 'annotation'):
                    if hasattr(argument.annotation, 'id'):
                        self.unwrapped_annotations.append(
                            (argument.lineno, argument.col_offset, argument.annotation.id)  # type:ignore
                        )
                    elif hasattr(argument.annotation, 'value'):
                        self.wrapped_annotations.append(
                            (argument.lineno, argument.col_offset, argument.annotation.value)
                        )
                    delattr(argument, 'annotation')
        if hasattr(node, 'returns'):
            if hasattr(node.returns, 'id'):
                self.unwrapped_annotations.append((node.lineno, node.col_offset, node.returns.id))  # type: ignore
            elif hasattr(node.returns, 'value'):
                self.wrapped_annotations.append((node.lineno, node.col_offset, node.returns.value))
            delattr(node, 'returns')
        self.generic_visit(node)
        return node


class TypingOnlyImportsChecker:
    """Checks for imports exclusively used by type annotation elements."""

    __slots__ = [
        'cwd',
        'visitor',
        'generators',
    ]

    def __init__(self, node: ast.Module) -> None:
        self.cwd = Path(os.getcwd())
        self.visitor = ImportVisitor(self.cwd)
        self.visitor.visit(node)

        self.generators = [
            self.unused_import,
            self.unused_third_party_import,
            self.missing_futures_import,
            self.missing_quotes,
            # self.excess_quotes,
        ]

    def unused_import(self) -> flake8_generator:
        """TYO100."""
        for name in set(self.visitor.import_names) - self.visitor.names:
            unused_import, local_import = self.visitor.import_names[name]
            if local_import:
                obj = self.visitor.local_imports.pop(unused_import)
                error_message, node = obj['error'], obj['node']
                yield node.lineno, node.col_offset, error_message.format(module=unused_import), None

    def unused_third_party_import(self) -> flake8_generator:
        """TYO101."""
        for name in set(self.visitor.import_names) - self.visitor.names:
            unused_import, local_import = self.visitor.import_names[name]
            if not local_import:
                obj = self.visitor.remote_imports.pop(unused_import)
                error_message, node = obj['error'], obj['node']
                yield node.lineno, node.col_offset, error_message.format(module=unused_import), None

    def missing_futures_import(self) -> flake8_generator:
        """TYO200."""
        if not self.visitor.futures_annotation and self.visitor.type_checking_block_imports:
            yield 0, 0, TYO200, None

    def missing_quotes(self) -> flake8_generator:
        """TYO201."""
        if not self.visitor.futures_annotation:
            for (lineno, col_offset, annotation) in self.visitor.unwrapped_annotations:
                if any(annotation == name for _, name in self.visitor.type_checking_block_imports):
                    yield lineno, col_offset, TYO201.format(annotation=annotation), None

    def excess_quotes(self) -> flake8_generator:
        """TYO202."""
        if self.visitor.futures_annotation:
            for (lineno, col_offset, annotation) in self.visitor.wrapped_annotations:
                if any(annotation == name for _, name in self.visitor.type_checking_block_imports):
                    yield lineno, col_offset, TYO201.format(annotation=annotation), None
        elif self.visitor.type_checking_block_imports:
            print(f'{self.visitor.type_checking_block_imports=}')  # noqa

    @property
    def errors(self) -> flake8_generator:
        """
        Return relevant errors in the required flake8-defined format.

        Flake8 plugins must return generators in this format: https://flake8.pycqa.org/en/latest/plugin-development/
        """
        for generator in self.generators:
            yield from generator()
