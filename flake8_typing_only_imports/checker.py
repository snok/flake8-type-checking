import ast
import os
from importlib.util import find_spec
from pathlib import Path
from typing import Dict, Generator, Iterable, List, Set, Tuple, Union

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


class ImportVisitor(ast.NodeVisitor):
    """Map all imports outside of type-checking blocks."""

    __slots__ = ('imports', 'exempt_imports', 'names')

    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd  # we need to know the current directory to guess at which imports are remote and which are not
        self.exempt_imports: List[str] = ['*']
        self.local_imports: Dict[str, dict] = {}
        self.remote_imports: Dict[str, dict] = {}
        self.names: Dict[str, Tuple[str, bool]] = {}

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
        if not spec.origin or 'venv' in spec.origin:
            return False

        # assumption 3
        origin = Path(spec.origin)
        return self.cwd in origin.parents

    def _add_import(self, node: Union[ast.Import, ast.ImportFrom]) -> None:
        """
        Add relevant ast objects to import lists.

        :param node: ast.Import or ast.ImportFrom object
        :param names:  the string value of the code being imported
        """
        if node.col_offset != 0:
            # Avoid recording imports that live inside a `if TYPE_CHECKING` block
            # The current handling is probably too naïve and could be upgraded
            return
        for name_node in node.names:
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
                    self.names[name] = import_name, True
                else:
                    self.remote_imports[import_name] = {'error': TYO101, 'node': node}
                    self.names[name] = import_name, False

    def visit_Import(self, node: ast.Import) -> None:
        """Append objects to our import map."""
        self._add_import(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Append objects to our import map."""
        self._add_import(node)


class NameVisitor(ast.NodeVisitor):
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

        # Get all 'name' attributes, for all ast objects except imports. This creates
        # a map of "all usages" which we can use to figure out which imports were used
        name_visitor = NameVisitor()
        name_visitor.visit(self.stripped_node)
        self.names: Set[str] = name_visitor.names

        # Get all imports
        # - The import visitor creates a map of all imports of different types
        self.import_visitor = ImportVisitor(self.cwd)
        self.import_visitor.visit(self.stripped_node)

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
            unused_import, local_import = self.import_visitor.names[name]
            if local_import:
                obj = self.import_visitor.local_imports[unused_import]
            else:
                obj = self.import_visitor.remote_imports[unused_import]
            error_message, node = obj['error'], obj['node']
            yield node.lineno, node.col_offset, error_message.format(module=unused_import), type(self)
