<a href="https://pypi.org/project/flake8-typing-only-imports/">
    <img src="https://img.shields.io/pypi/v/flake8-typing-only-imports.svg" alt="Package version">
</a>
<a href="https://codecov.io/gh/sondrelg/flake8-typing-only-imports">
    <img src="https://codecov.io/gh/sondrelg/flake8-typing-only-imports/branch/master/graph/badge.svg" alt="Code coverage">
</a>
<a href="https://pypi.org/project/flake8-typing-only-imports/">
    <img src="https://github.com/sondrelg/flake8-typing-only-imports/actions/workflows/testing.yml/badge.svg" alt="Test status">
</a>
<a href="https://pypi.org/project/flake8-typing-only-imports/">
    <img src="https://img.shields.io/badge/python-3.7%2B-blue" alt="Supported Python versions">
</a>
<a href="http://mypy-lang.org/">
    <img src="http://www.mypy-lang.org/static/mypy_badge.svg" alt="Checked with mypy">
</a>

# flake8-typing-only-imports

flake8 plugin that flags imports which are exclusively used for type hinting.

## Installation

```shell
pip install flake8-typing-only-imports
```

## Codes

| Code   | Description                                         |
|--------|-----------------------------------------------------|
| TYO100 | Local import '{module}' only used for type hinting  |
| TYO101 | Remote import '{module}' only used for type hinting |

## Rationale

A common trade-off for annotating large code bases is you will end up with a
large number of extra imports. In some cases, this can lead to
import circularity problems.

One (good) solution, as proposed in [PEP484](https://www.python.org/dev/peps/pep-0484/)
is to use [forward references](https://www.python.org/dev/peps/pep-0484/#forward-references)
and [type checking](https://www.python.org/dev/peps/pep-0484/#runtime-or-type-checking) blocks, like this:

```python
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from app.models import foo


def bar() -> 'foo':
    ...
```

At the same time, this is often easier said than done, because in larger code bases you can be dealing
with hundreds of lines of imports for thousands of lines of code.

This plugin solves the issue of figuring out which imports to put inside your type-checking blocks 🚀

## As a pre-commit hook

See [pre-commit](https://github.com/pre-commit/pre-commit) for instructions

Sample `.pre-commit-config.yaml`:

```yaml
- repo: https://gitlab.com/pycqa/flake8
  rev: 3.7.8
  hooks:
  - id: flake8
    additional_dependencies: [flake8-typing-only-imports]
```
