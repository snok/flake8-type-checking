import ast
import os
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Dict, Generator, List, Set, Tuple, Union

from flake8_typing_only_imports.constants import TYO100, TYO101, TYO200


class ImportVisitor(ast.NodeTransformer):
    """Map all imports outside of type-checking blocks."""

    __slots__ = (
        'cwd',
        'exempt_imports',
        'local_imports',
        'remote_imports',
        'import_names',
        '_names',
        'unwrapped_annotations',
    )

    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd  # we need to know the current directory to guess at which imports are remote and which are not
        self.exempt_imports: List[str] = ['*']
        self.local_imports: Dict[str, dict] = {}
        self.remote_imports: Dict[str, dict] = {}
        self.import_names: Dict[str, Tuple[str, bool]] = {}
        self._names: List[str] = []

        self.type_checking_block_imports: Set[str] = set()
        self.unwrapped_annotations: List[Tuple[int, int, str]] = []

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

    def _add_import(self, node: Union[ast.Import, ast.ImportFrom]) -> None:
        """
        Add relevant ast objects to import lists.

        :param node: ast.Import or ast.ImportFrom object
        :param names:  the string value of the code being imported
        """
        if node.col_offset != 0:
            # Avoid recording imports that live inside a `if TYPE_CHECKING` block
            # The current handling is probably too naïve and could be upgraded
            for name_node in node.names:
                if hasattr(name_node, 'asname') and name_node.asname:
                    name = name_node.asname
                else:
                    name = name_node.name
                self.type_checking_block_imports.add(name)
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
        return set(self._names)

    def visit_Name(self, node: ast.Name) -> ast.Name:
        """Map names."""
        self._names.append(node.id)
        return node

    # Map annotations

    def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.AnnAssign:
        """Remove all annotation assignments."""
        if hasattr(node, 'annotation') and node.annotation:
            if isinstance(node.annotation, ast.Name):
                self.unwrapped_annotations.append((node.lineno, node.col_offset, node.annotation.id))
            else:
                print('UNHANDLED TYPE:', type(node.annotation))  # noqa  # todo: remove in a future iteration
            delattr(node, 'annotation')
        self.generic_visit(node)
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        """Remove all function arguments."""
        for path in [node.args.args, node.args.kwonlyargs]:
            argument: ast.arg
            for argument in path:
                if hasattr(argument, 'annotation') and hasattr(argument.annotation, 'id'):
                    self.unwrapped_annotations.append(
                        (argument.lineno, argument.col_offset, argument.annotation.id)  # type:ignore
                    )
                    delattr(argument, 'annotation')
        if hasattr(node, 'returns') and hasattr(node.returns, 'id'):
            self.unwrapped_annotations.append((node.lineno, node.col_offset, node.returns.id))  # type: ignore
            delattr(node, 'returns')
        self.generic_visit(node)
        return node


class TypingOnlyImportsChecker:
    """Checks for imports exclusively used by type annotation elements."""

    __slots__ = [
        'cwd',
        'visitor',
    ]

    def __init__(self, node: ast.Module) -> None:
        self.cwd = Path(os.getcwd())
        self.visitor = ImportVisitor(self.cwd)
        self.visitor.visit(node)

    @property
    def unused_imports(self) -> Generator[Tuple[int, int, str, Any], None, None]:
        """
        Return the intersection of import names and usage names.

        The intersection *should* represent the imports that aren't used anywhere but in type annotations.
        In the future, if we wanted to get more specific we could limit this further by actively looking
        at the type annotations as well, but for now we'll assume this is good enough.
        """
        for name in set(self.visitor.import_names) - self.visitor.names:
            unused_import, local_import = self.visitor.import_names[name]
            if local_import:
                obj = self.visitor.local_imports[unused_import]
            else:
                obj = self.visitor.remote_imports[unused_import]
            error_message, node = obj['error'], obj['node']
            yield node.lineno, node.col_offset, error_message.format(module=unused_import), type(self)

    @property
    def unwrapped_annotations(self) -> Generator[Tuple[int, int, str, Any], None, None]:
        """
        Return the intersection of type-checking imports and unwrapped annotation objects.

        Any annotation object that coincides with a type-checking block import, should be
        wrapped in quotes to be treated as a forward reference:

        https://www.python.org/dev/peps/pep-0484/#forward-references
        """
        for (lineno, col_offset, annotation) in self.visitor.unwrapped_annotations:
            if annotation in self.visitor.type_checking_block_imports:
                yield lineno, col_offset, TYO200.format(annotation=annotation), type(self)

    @property
    def errors(self) -> Generator[Tuple[int, int, str, Any], None, None]:
        """
        Return relevant errors in a preset format.

        Flake8 plugins must return generators in this format.
        https://flake8.pycqa.org/en/latest/plugin-development/
        """
        yield from self.unused_imports
        yield from self.unwrapped_annotations
