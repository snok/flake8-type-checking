import ast
from typing import Dict, Generator, Iterable, List, Set, Union

from flake8_typing_only_imports.constants import TYO100


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

    __slots__ = ('imports', 'exempt_imports')

    def __init__(self) -> None:
        self.imports: Dict[str, Set[Union[ast.Import, ast.ImportFrom]]] = {}
        self.exempt_imports: List[str] = ['*']

    def _add_import(self, node: Union[ast.Import, ast.ImportFrom], names: Iterable[str]) -> None:
        """
        Add relevant ast objects to self.imports.

        :param node: ast.Import or ast.ImportFrom object
        :param names:  the string value of the code being imported
        """
        if node.col_offset != 0:
            # Type checking imports have an offset
            # This might be too naïve and might need to be upgraded in the future
            return
        if any(name not in self.exempt_imports for name in names):
            for name in names:
                if name not in self.imports:
                    self.imports[name] = set()
                self.imports[name].add(node)

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


class Checker:
    """Scans for unused imports after stripping the ast Module of annotation elements."""

    __slots__ = [
        'stripped_node',
        'names',
        'imports',
    ]

    def __init__(self, node: ast.Module) -> None:
        self.stripped_node = AnnotationRemover().visit(node)

        import_visitor = ImportVisitor()
        import_visitor.visit(self.stripped_node)
        self.imports = import_visitor.imports

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
        return set(self.imports) - self.names

    @property
    def errors(self) -> Generator:
        """
        Return relevant errors in a preset format.

        Flake8 plugins must return generators in this format.
        https://flake8.pycqa.org/en/latest/plugin-development/
        """
        for unused_import in self.unused_imports:
            nodes = self.imports[unused_import]
            for node in nodes:
                yield node.lineno, node.col_offset, TYO100.format(module=unused_import), type(self)
