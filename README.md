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

> Plugin is still a work in progress

Tells you which imports to put inside type-checking blocks.

## Codes

| Code   | Description                                         |
|--------|-----------------------------------------------------|
| TCH001 | Move import into a type-checking block  |
| TCH101 | Move third-party import into a type-checking block |
| TCH102 | Found multiple type checking blocks |

| Code   | Description                                         |
|--------|-----------------------------------------------------|
| TCHA001 | Add 'from \_\_future\_\_ import annotations' import |
| TCHA002 | Annotation does not need to be a string literal |

| Code   | Description                                         |
|--------|-----------------------------------------------------|
| TCHB001 | Annotation needs to be made into a string literal |
| TCHB002 | Annotation does not need to be a string literal |

## Rationale

`TCH100` guards
against [import cycles](https://mypy.readthedocs.io/en/stable/runtime_troubles.html?highlight=TYPE_CHECKING#import-cycles)
. `TCH101` applies the same logic, for `venv` or `stdlib` imports.

Remaining error codes are there to help manage
[forward references](https://mypy.readthedocs.io/en/stable/runtime_troubles.html?highlight=TYPE_CHECKING#class-name-forward-references),
either by telling your to use string literals where needed, or by enabling
[postponed evaluation of annotations](https://www.python.org/dev/peps/pep-0563/).
The error code series `TCH2XX` and `TCH3XX` should therefore be considered
mutually exclusive, as they represent two different ways of managing forward
references.

See [this](https://stackoverflow.com/a/55344418/8083459) excellent stackoverflow answer for a
quick explanation of forward references.

## Installation

```shell
pip install flake8-type-checking
```

## Suggested use

Only enable `TCH101` if you're after micro performance gains on start-up.

`TCH2XX` and `TCH3XX` are reserved for error codes to help manage forward references.
It does not make sense to enable both series, and they should be considered mutually exclusive.

If you're adding this to your project, we would recommend something like this:

```python
select = TCH100, TCHA001, TCHA001  # or TCHB001 and TCHB002

ignore = TCH101, TCHB001, TCHB002  # or TCHA001 and TCHA002
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

Which will first result in these errors
```shell
>> a.py: TCH101: Move third-party import 'models.b.B' into a type-checking block
>> b.py: TCH101: Move third-party import 'models.a.A' into a type-checking block
```

and consequently trigger these errors if imports are purely moved into type-checking block, without proper forward reference handling

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

Leave a&nbsp;⭐️&nbsp; if this project helped you!

Contributions are always welcome 👏
