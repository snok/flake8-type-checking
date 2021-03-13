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

> Plugin is still a work in progress

A flake8 plugin to help you identify which imports to put into type-checking blocks.

Beyond this, it will also help you manage forward references however you would like to.

## Installation

```shell
pip install flake8-typing-only-imports
```

## Examples

Bad code:

```python
import bar

from typing import List

def listify(arg: bar.BarClass) -> List[bar.BarClass]:
    return [arg]
```

Good code:

```python
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    import bar

def listify(arg: 'bar.BarClass') -> 'List[bar.BarClass]':
    return [arg]
```

## Rationale
`TYO100` primarily (and to a lesser degree, `TYO101`) guards against [import cycles](https://mypy.readthedocs.io/en/stable/runtime_troubles.html?highlight=TYPE_CHECKING#import-cycles).

The remaining error codes are there to help manage [forward references](https://mypy.readthedocs.io/en/stable/runtime_troubles.html?highlight=TYPE_CHECKING#class-name-forward-references),
either by stringifying annotation or by enabling [postponed evaluation of annotations](https://www.python.org/dev/peps/pep-0563/), by
using a futures import in Python 3.7+. See [this](https://stackoverflow.com/a/55344418/8083459) stackoverflow answer for a great explanation.

## Codes

| Code   | Description                                         |
|--------|-----------------------------------------------------|
| TYO100 | Move import into a type-checking block  |
| TYO101 | Move third-party import into a type-checking block |
| TYO200 | Add 'from \_\_future\_\_ import annotations' import |
| TYO201 | Annotation does not need to be a string literal |
| TYO300 | Annotation needs to be made into a string literal |
| TYO301 | Annotation does not need to be a string literal |

## Suggested use

The split between `TYO100` and `TYO101` was made because venv imports don't really guard against import cycles like
module imports might. Enabling `TYO101` is not as beneficial, so enabling it should be given some thought.

Beyond import cycles, `TYO200` and `TYO300` are reserved for error codes to help manage forward references.
It does not make sense to enable both series, and they should be considered mutually exclusive.

If you're adding this to your project, we would recommend this setup

```python
select = TYO100, TYO200, TYO200  # or TYO300 and TYO301

ignore = TYO101, TYO300, TYO301  # or TYO200 and TYO201
```

## As a pre-commit hook

You can run this flake8 plugin as a [pre-commit](https://github.com/pre-commit/pre-commit) hook:

```yaml
- repo: https://gitlab.com/pycqa/flake8
  rev: 3.7.8
  hooks:
  - id: flake8
    additional_dependencies: [flake8-typing-only-imports]
```

## Supporting the project

Leave a&nbsp;⭐️&nbsp; if this project helped you!

Contributions are always welcome 👏
