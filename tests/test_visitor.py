import ast
import textwrap

from flake8_typing_only_imports import Plugin
from flake8_typing_only_imports.ast import ImportVisitor, NameVisitor
from flake8_typing_only_imports.constants import TYO100


def _get_usages(example):
    visitor = NameVisitor()
    visitor.visit(ast.parse(example))
    return visitor.names


class TestUsage:
    def test_find_basic_assignments(self):
        assert _get_usages('x = y') == {'x', 'y'}
        assert _get_usages('x, y = z') == {'x', 'y', 'z'}
        assert _get_usages('x, y, z = a, b, c()') == {'x', 'y', 'z', 'a', 'b', 'c'}

    def test_find_basic_calls(self):
        assert _get_usages('x()') == {'x'}
        assert _get_usages('x = y()') == {'x', 'y'}
        assert _get_usages('def example(): x = y(); z()') == {'x', 'y', 'z'}

    def test_attribute_call(self):
        assert _get_usages('x.y') == {'x'}

    def test_assignment_inside_function(self):
        example = textwrap.dedent(
            """
        def example(c):
            a = 2
            b = c * 2
        """
        )
        assert _get_usages(example) == {'a', 'b', 'c'}

    def test_class_assignment(self):
        example = textwrap.dedent(
            """
        class Test:
            x = 13

            def __init__(self, z):
                self.y = z

        a = Test()
        b = a.y
        """
        )
        assert _get_usages(example) == {'self', 'x', 'z', 'a', 'b', 'Test'}

    def test_type_assignment(self):
        example = textwrap.dedent(
            """
        import ast

        ImportType = Union[Import, ImportFrom]
        """
        )
        # ast should not be a part of this
        assert _get_usages(example) == {'Union', 'Import', 'ImportFrom', 'ImportType'}

    def test_bundled_calls_and_attributes(self):
        example = textwrap.dedent(
            """
        import ast
        def _get_usages(example):
            visitor = UnusedImportVisitor()
            visitor.visit(parse(example))
            return visitor.usage_names
        """
        )
        assert _get_usages(example) == {'visitor', 'UnusedImportVisitor', 'parse', 'example'}

    def test_imports_are_not_collected(self):
        example = textwrap.dedent(
            """
        import x
        from y import z
        """
        )
        assert _get_usages(example) == set()


def _get_imports(example):
    visitor = ImportVisitor()
    visitor.visit(ast.parse(example.replace('; ', '\n')))
    return list(visitor.imports.keys())


class TestImports:
    def test_find_basic_imports(self):
        assert _get_imports('import x') == ['x']
        assert _get_imports("import x; print('something'); import y") == ['x', 'y']
        assert _get_imports("import x; print(''); import y; print(''); import z") == [
            'x',
            'y',
            'z',
        ]

    def test_find_basic_from_imports(self):
        assert _get_imports('from _ import x') == ['x']
        assert _get_imports("from _ import x; print('something'); from _ import y") == [
            'x',
            'y',
        ]
        assert _get_imports("from _ import x; print(''); from _ import y; print(''); from _ import z") == [
            'x',
            'y',
            'z',
        ]

    def test_mixed_imports(self):
        example = textwrap.dedent(
            """
        import x
        from y import *
        from y import z

        def test():
            pass

        import a; import b
        """
        )
        assert _get_imports(example) == ['x', 'z', 'a', 'b']


def _get_error(example):
    plugin = Plugin(ast.parse(example))
    return {f'{line}:{col} {msg}' for line, col, msg, _ in plugin.run()}


class TestError:
    def test_basic_error(self):
        assert _get_error('') == set()
        assert _get_error('import x') == {'1:0 ' + TYO100.format(module='x')}
        assert _get_error('\nimport x') == {'2:0 ' + TYO100.format(module='x')}
        assert _get_error('\n\nfrom x import y') == {'3:0 ' + TYO100.format(module='y')}

    def test_no_error_raised_when_unused_imports_declared_in_type_checking_block(self):
        example = textwrap.dedent(
            """
        import x
        from y import z

        if TYPE_CHECKING:
            import a

            # arbitrary whitespace

            from b import c

        def test():
            pass
        """
        )
        assert _get_error(example) == {
            '2:0 ' + TYO100.format(module='x'),
            '3:0 ' + TYO100.format(module='z'),
        }
