import ast
import os
from pathlib import Path

from flake8_typing_only_imports import Plugin

REPO_ROOT = Path(os.getcwd()).parent
mod = 'flake8_typing_only_imports'


def _get_error(example, ignore=None):
    os.chdir(REPO_ROOT)
    plugin = Plugin(ast.parse(example))
    return {f'{line}:{col} {msg}' for line, col, msg, _ in plugin.run()}
