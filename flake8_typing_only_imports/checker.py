import ast
import os
from importlib.util import find_spec
from pathlib import Path
from typing import Dict, Generator, Iterable, List, Set, TypedDict, Union

from flake8_typing_only_imports.constants import TYO100, TYO101


class AnnotationRemover(ast.NodeTransformer):
    """Remove all annotation objects from a Module."""

    __slots__: List[str] = []

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Remove all annotation assignments."""
        pass

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        """Remove all function arguments."""
        for path in [node.args.args, node.args.kwonlyargs]:
            for argument in path:
                if hasattr(argument, 'annotation'):
                    delattr(argument, 'annotation')
        if hasattr(node, 'returns'):
            delattr(node, 'returns')
        return node


class ImportsContent(TypedDict):
    """Describes the content of self.import."""

    node: Union[ast.Import, ast.ImportFrom]
    error: str


class ImportVisitor(ast.NodeVisitor):
    """Map all imports outside of type-checking blocks."""

    __slots__ = ('imports', 'exempt_imports', 'names')

    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd  # we need to know the current directory to guess at which imports are remote and which are not
        self.exempt_imports: List[str] = ['*']
        self.imports: Dict[str, ImportsContent] = {}
        self.names: Dict[str, str] = {}

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
        if '.' in import_name:
            spec = find_spec('.'.join(import_name.split('.')[:-1]), import_name.split('.')[-1])
        else:
            spec = find_spec(import_name)

        # assumption 1
        if not spec:
            return False

        # assumption 2
        if spec.origin and 'venv' in spec.origin:
            return False

        # assumption 3
        if spec.origin:
            origin = Path(spec.origin)
            return self.cwd in origin.parents

        return False

    def _add_import(self, node: Union[ast.Import, ast.ImportFrom], names: Iterable[str]) -> None:
        """
        Add relevant ast objects to import lists.

        :param node: ast.Import or ast.ImportFrom object
        :param names:  the string value of the code being imported
        """
        if node.col_offset != 0:
            # Type checking imports have an offset
            # This might be too naïve and might need to be upgraded in the future
            return
        for name in names:
            # print(f'{name=}')
            if name not in self.exempt_imports:
                # ImportFrom will have node.modules, while Imports won't
                import_name = f'{node.module}.{name}' if isinstance(node, ast.ImportFrom) else name

                self.imports[import_name] = {
                    'error': TYO100 if self._import_is_local(import_name) else TYO101,
                    'node': node,
                }
                self.names[name] = import_name

    def visit_Import(self, node: ast.Import) -> None:
        """Append objects to our import map."""
        modules = [alias.name for alias in node.names]
        self._add_import(node, modules)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Append objects to our import map."""
        names = [alias.name for alias in node.names]
        self._add_import(node, names)


class NameVisitor(ast.NodeTransformer):
    """Map all names of all non-import objects."""

    __slots__ = ['_names']

    def __init__(self) -> None:
        self._names: List[str] = []

    @property
    def names(self) -> Set[str]:
        """Return unique names."""
        return set(self._names)

    def visit_Name(self, node: ast.Name) -> None:
        """Map names."""
        self._names.append(node.id)

    def visit_Import(self, node: ast.Import) -> None:
        """Skip import objects."""
        pass

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Skip import-from objects."""
        pass


class TypingOnlyImportsChecker:
    """Checks for imports exclusively used by type annotation elements."""

    __slots__ = [
        'stripped_node',
        'names',
        'import_visitor',
        'cwd',
    ]

    def __init__(self, node: ast.Module) -> None:
        self.cwd = Path(os.getcwd())

        # Remove all annotations from the ast tree
        # - The reason this should make sense, is we assume there are no unused imports
        # - tooling for unused imports already exists, so we don't need to reinvent this
        self.stripped_node = AnnotationRemover().visit(node)

        # Get all imports
        # - The import visitor creates a map of all imports of different types
        self.import_visitor = ImportVisitor(self.cwd)
        # print(self.stripped_node)
        self.import_visitor.visit(self.stripped_node)

        # Get all 'name' attributes, for all ast objects except imports. This creates
        # a map of "all usages" which we can use to figure out which imports were used
        name_visitor = NameVisitor()
        name_visitor.visit(self.stripped_node)
        self.names: Set[str] = name_visitor.names

    @property
    def unused_imports(self) -> Iterable[str]:
        """
        Return the intersection of import names and usage names.

        The intersection *should* represent the imports that aren't used anywhere but in type annotations.
        In the future, if we wanted to get more specific we could limit this further by actively looking
        at the type annotations as well, but for now we'll assume this is good enough.
        """
        return set(self.import_visitor.names) - self.names

    @property
    def errors(self) -> Generator:
        """
        Return relevant errors in a preset format.

        Flake8 plugins must return generators in this format.
        https://flake8.pycqa.org/en/latest/plugin-development/
        """
        for name in self.unused_imports:
            unused_import = self.import_visitor.names[name]
            obj = self.import_visitor.imports[unused_import]
            error_message, node = obj['error'], obj['node']
            yield node.lineno, node.col_offset, error_message.format(module=unused_import), type(self)
