from __future__ import annotations

from itertools import chain
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import ast
    from ast import AsyncFunctionDef, FunctionDef
    from collections.abc import Iterator


def iter_function_annotation_nodes(node: AsyncFunctionDef | FunctionDef) -> Iterator[ast.expr]:
    """Yield all the annotation expression nodes inside the given function node."""
    for arg in chain(node.args.args, node.args.kwonlyargs, node.args.posonlyargs):
        if arg.annotation:
            yield arg.annotation

    for opt_arg in (node.args.kwarg, node.args.vararg):
        if opt_arg and opt_arg.annotation:
            yield opt_arg.annotation

    if node.returns:
        yield node.returns
