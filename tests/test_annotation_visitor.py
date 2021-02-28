import ast
from typing import List, Tuple

import pytest

from flake8_typing_only_imports.checker import AnnotationRemover, NameVisitor


def _get_ast_body(example):
    remover = AnnotationRemover()
    cleaned_example = remover.visit(ast.parse(example))
    return [i for i in cleaned_example.body]


examples: List[Tuple[str, list]] = [
    ('x: int', []),
    ('x: list[int]', []),
    ('x: doesntmatterwhatiputhereaslongastheresnoillegalcharacters', []),
    ('x: int\ny: str', []),
]


@pytest.mark.parametrize('example, result', examples)
def test_basic_annotations_are_removed(example, result):
    for node in _get_ast_body(example):
        assert hasattr(node, 'annotation') is False


def test_function_annotations_are_removed():
    ast_objects = _get_ast_body('def example(x: int, y: str) -> bool:\n\tpass')

    assert len(ast_objects) == 1

    func = ast_objects[0]
    assert isinstance(func, ast.FunctionDef)

    for arg in func.args.args:
        assert arg.annotation is None

    assert func.returns is None
