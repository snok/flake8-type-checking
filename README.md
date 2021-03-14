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

Tells you which imports to put inside type-checking blocks.

## Codes

| Code   | Description                                         |
|--------|-----------------------------------------------------|
| TYO100 | Move import into a type-checking block  |
| TYO101 | Move third-party import into a type-checking block |
| TYO102 | Found multiple type checking blocks |
| TYO200 | Add 'from \_\_future\_\_ import annotations' import |
| TYO201 | Annotation does not need to be a string literal |
| TYO300 | Annotation needs to be made into a string literal |
| TYO301 | Annotation does not need to be a string literal |

## Rationale

`TYO100` guards
against [import cycles](https://mypy.readthedocs.io/en/stable/runtime_troubles.html?highlight=TYPE_CHECKING#import-cycles)
. `TYO101` applies the same logic, for `venv` or `stdlib` imports.

Remaining error codes are there to help manage
[forward references](https://mypy.readthedocs.io/en/stable/runtime_troubles.html?highlight=TYPE_CHECKING#class-name-forward-references),
either by telling your to use string literals where needed, or by enabling
[postponed evaluation of annotations](https://www.python.org/dev/peps/pep-0563/).
The error code series `TYO2XX` and `TYO3XX` should therefore be considered
mutually exclusive, as they represent two different ways of managing forward
references.

See [this](https://stackoverflow.com/a/55344418/8083459) excellent stackoverflow answer for a
quick explanation of forward references.

## Installation

```shell
pip install flake8-typing-only-imports
```

## Suggested use

Only enable `TYO101` if you're after micro performance gains on start-up.

`TYO2XX` and `TYO3XX` are reserved for error codes to help manage forward references.
It does not make sense to enable both series, and they should be considered mutually exclusive.

If you're adding this to your project, we would recommend something like this:

```python
select = TYO100, TYO200, TYO200  # or TYO300 and TYO301

ignore = TYO101, TYO300, TYO301  # or TYO200 and TYO201
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
>> a.py: TYO101: Move third-party import 'models.b.B' into a type-checking block
>> b.py: TYO101: Move third-party import 'models.a.A' into a type-checking block
```

and consequently trigger these errors if imports are purely moved into type-checking block, without proper forward reference handling

```shell
>> a.py: TYO300: Annotation 'B' needs to be made into a string literal
>> b.py: TYO300: Annotation 'A' needs to be made into a string literal
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
      additional_dependencies: [ flake8-typing-only-imports ]
```

## Supporting the project

Leave a&nbsp;⭐️&nbsp; if this project helped you!

Contributions are always welcome 👏
