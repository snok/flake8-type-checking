<a href="https://pypi.org/project/flake8-type-checking/">
    <img src="https://img.shields.io/pypi/v/flake8-type-checking.svg" alt="Package version">
</a>
<a href="https://codecov.io/gh/sondrelg/flake8-type-checking">
    <img src="https://codecov.io/gh/sondrelg/flake8-type-checking/branch/master/graph/badge.svg" alt="Code coverage">
</a>
<a href="https://github.com/snok/flake8-type-checking/actions/workflows/testing.yml">
    <img src="https://github.com/sondrelg/flake8-type-checking/actions/workflows/testing.yml/badge.svg" alt="Test status">
</a>
<a href="https://pypi.org/project/flake8-type-checking/">
    <img src="https://img.shields.io/badge/python-3.8%2B-blue" alt="Supported Python versions">
</a>
<a href="http://mypy-lang.org/">
    <img src="http://www.mypy-lang.org/static/mypy_badge.svg" alt="Checked with mypy">
</a>

# flake8-type-checking

Lets you know which imports to put in [type-checking](https://docs.python.org/3/library/typing.html#typing.TYPE_CHECKING) blocks.

For the imports you've already defined inside type-checking blocks, it can
also help you manage [forward references](https://www.python.org/dev/peps/pep-0484/#forward-references)
using [PEP 484](https://www.python.org/dev/peps/pep-0484) or [PEP 563](https://www.python.org/dev/peps/pep-0563/) style references.

## Codes


| Code   | Description                                         |
|--------|-----------------------------------------------------|
| TC001 | Move import into a type-checking block  |
| TC002 | Move third-party import into a type-checking block |
| TC003 | Found multiple type checking blocks |
| TC004 | Move import out of type-checking block. Import is used for more than type hinting. |
| TC005 | Empty type-checking block |

### Forward reference codes

These code ranges are opt-in. They represent two different ways of solving the same problem,
so please only choose one.

`TC100` and `TC101` manage forward references by taking advantage of
[postponed evaluation of annotations](https://www.python.org/dev/peps/pep-0563/).

| Code   | Description                                         |
|--------|-----------------------------------------------------|
| TC100 | Add 'from \_\_future\_\_ import annotations' import |
| TC101 | Annotation does not need to be a string literal |

`TC200` and `TC201` manage forward references using [string literals](https://www.python.org/dev/peps/pep-0484/#forward-references).

| Code   | Description                                         |
|--------|-----------------------------------------------------|
| TC200 | Annotation needs to be made into a string literal |
| TC201 | Annotation does not need to be a string literal |

To select one of the ranges, just specify the code in your flake8 config:

```
[flake8]
max-line-length = 80
max-complexity = 12
...
ignore = E501
select = C,E,F,W,..., TC, TC2  # or TC1
# alternatively:
enable-extensions = TC, TC2  # or TC1
```

## Rationale

Good type hinting requires a lot of imports, which can increase the risk of
[import cycles](https://mypy.readthedocs.io/en/stable/runtime_troubles.html?highlight=TYPE_CHECKING#import-cycles)
in your project.
The recommended way of preventing this problem is to use `typing.TYPE_CHECKING` blocks
to guard these types of imports.

Both `TC001` and `TC002` help alleviate this problem; the reason there are two
codes instead of one, is because the import cycles rarely occur from
library/third-party imports, so this artificial split provides a way to filter down
the total pool of imports for users that want to guard against import cycles,
but don't want to manage every import in their projects *this* strictly.

Once imports are guarded, they will no longer be evaluated during runtime. The
consequence of this is that these imports can no longer be treated as if they
were imported outside the block. Instead we need to use [forward references](https://www.python.org/dev/peps/pep-0484/#forward-references).

For Python version `>= 3.7`, there are actually two ways of solving this issue.
You can either make your annotations string literals, or you can use a `__futures__` import to enable [postponed evaluation of annotations](https://www.python.org/dev/peps/pep-0563/).
See [this](https://stackoverflow.com/a/55344418/8083459) excellent stackoverflow answer
for a better explanation of the differences.

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
>> a.py: TC002 Move third-party import 'models.b.B' into a type-checking block
>> b.py: TC002 Move third-party import 'models.a.A' into a type-checking block
```

and consequently trigger these errors if imports are purely moved into type-checking block, without proper forward reference handling

```shell
>> a.py: TC100 Add 'from __future__ import annotations' import
>> b.py: TC100 Add 'from __future__ import annotations' import
```

or

```shell
>> a.py: TC200 Annotation 'B' needs to be made into a string literal
>> b.py: TC200 Annotation 'A' needs to be made into a string literal
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
# TC1
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.a import A

class B(Model):
    def bar(self, a: A): ...
```

or

```python
# TC2
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.a import A

class B(Model):
    def bar(self, a: 'A'): ...
```

## As a pre-commit hook

You can run this flake8 plugin as a [pre-commit](https://github.com/pre-commit/pre-commit) hook:

```yaml
- repo: https://github.com/pycqa/flake8
  rev: 3.9.2
  hooks:
    - id: flake8
      additional_dependencies: [ flake8-type-checking ]
```
