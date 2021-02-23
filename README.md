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

flake8 plugin which flags imports which are exclusively used for type hinting.

## Installation

```shell
pip install flake8-typing-only-imports
```

## Codes

| Code   | Description                                  |
|--------|----------------------------------------------|
| TYO100 | Import '{module}' only used for type hinting |

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

This plugin eliminates that problem by flagging imports which can be put inside a type-checking block.

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

## Release process

1. Bump version in `setup.cfg`.
1. Add a commit "Release vX.Y.Z".
1. Make sure checks still pass.
1. [Draft a new release](https://github.com/sondrelg/flake8-typing-only-imports/releases/new) with a tag name "X.Y.Z" and describe changes which involved in the release.
1. Publish the release.
## Flake8 Type Hinting Only Imports

This is flake8 hook flags all your imports that are being exclusively used for type hinting.

Running the hook on
```python
import a

from b import c


def example(d: c):
    return a.transform(d)
```
Will produce this
```shell
> ../file.py:3:1: TYO100: Import 'c' only used for type annotation
```

## Motivation

- Circular imports
- Efficiency
- How are imports handled at compile time
- More type hinting -> exaggerated problem
