<a href="https://pypi.org/project/flake8-type-checking/">
    <img src="https://img.shields.io/pypi/v/flake8-type-checking.svg" alt="Package version">
</a>
<a href="https://codecov.io/gh/sondrelg/flake8-type-checking">
    <img src="https://codecov.io/gh/sondrelg/flake8-type-checking/branch/master/graph/badge.svg" alt="Code coverage">
</a>
<a href="https://pypi.org/project/flake8-type-checking/">
    <img src="https://github.com/sondrelg/flake8-type-checking/actions/workflows/testing.yml/badge.svg" alt="Test status">
</a>
<a href="https://pypi.org/project/flake8-type-checking/">
    <img src="https://img.shields.io/badge/python-3.7%2B-blue" alt="Supported Python versions">
</a>
<a href="http://mypy-lang.org/">
    <img src="http://www.mypy-lang.org/static/mypy_badge.svg" alt="Checked with mypy">
</a>

# flake8-type-checking

Lets you know which imports to put inside [type-checking blocks](https://docs.python.org/3/library/typing.html#typing.TYPE_CHECKING).

Also helps you manage [forward references](https://mypy.readthedocs.io/en/stable/runtime_troubles.html?highlight=TYPE_CHECKING#class-name-forward-references).

## Codes

### Primary codes

| Code   | Description                                         |
|--------|-----------------------------------------------------|
| TCH001 | Move import into a type-checking block  |
| TCH101 | Move third-party import into a type-checking block |
| TCH102 | Found multiple type checking blocks |

### Secondary codes

Choose `TCHA` or `TCHB` as they are mutually exclusive.

| Code   | Description                                         |
|--------|-----------------------------------------------------|
| TCHA001 | Add 'from \_\_future\_\_ import annotations' import |
| TCHA002 | Annotation does not need to be a string literal |

| Code   | Description                                         |
|--------|-----------------------------------------------------|
| TCHB001 | Annotation needs to be made into a string literal |
| TCHB002 | Annotation does not need to be a string literal |

See [rationale](#rationale) or [examples](#examples) for a better explanation of the difference.

## Rationale

We generally want to use `TYPE_CHECKING` blocks for imports where we can, to guard
against [import cycles](https://mypy.readthedocs.io/en/stable/runtime_troubles.html?highlight=TYPE_CHECKING#import-cycles).
An added bonus is that guarded imports are not loaded when you start your app, so
theoretically you should get a slight performance boost there as well.

Once imports are guarded, type hints should be treated as [forward references](https://mypy.readthedocs.io/en/stable/runtime_troubles.html?highlight=TYPE_CHECKING#class-name-forward-references).
Remaining error codes are there to help manage that,
either by telling your to use string literals where needed, or by enabling
[postponed evaluation of annotations](https://www.python.org/dev/peps/pep-0563/).

The error code series `TCHA` and `TCHB` should therefore be considered
mutually exclusive, as they represent two different ways of solving the same problem.

See [this](https://stackoverflow.com/a/55344418/8083459) excellent stackoverflow answer for a
quick explanation of forward references.

## Installation

```shell
pip install flake8-type-checking
```

## Examples

**Bad code**

`models/a.py`
```python
from models.b import B

class A(Model):
    def foo(self, b: B): ...
```

`models/b.py`
```python
from models.a import A

class B(Model):
    def bar(self, a: A): ...
```

Will result in these errors

```shell
>> a.py: TCH101: Move third-party import 'models.b.B' into a type-checking block
>> b.py: TCH101: Move third-party import 'models.a.A' into a type-checking block
```

and consequently trigger these errors if imports are purely moved into type-checking block, without proper forward reference handling

```shell
>> a.py: TCHA001: Add 'from __future__ import annotations' import
>> b.py: TCHA001: Add 'from __future__ import annotations' import
```

or

```shell
>> a.py: TCHB001: Annotation 'B' needs to be made into a string literal
>> b.py: TCHB001: Annotation 'A' needs to be made into a string literal
```

**Good code**

`models/a.py`
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.b import B

class A(Model):
    def foo(self, b: 'B'): ...
```
`models/b.py`
```python
# TCHA
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.a import A

class B(Model):
    def bar(self, a: A): ...
```

or

```python
# TCHB
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.a import A

class B(Model):
    def bar(self, a: 'A'): ...
```

## As a pre-commit hook

You can run this flake8 plugin as a [pre-commit](https://github.com/pre-commit/pre-commit) hook:

```yaml
- repo: https://gitlab.com/pycqa/flake8
  rev: 3.7.8
  hooks:
    - id: flake8
      additional_dependencies: [ flake8-type-checking ]
```

## Supporting the project

Leave a ✯ if this project helped you!

Contributions are always welcome 👏
