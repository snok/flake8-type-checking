[![Package version](https://img.shields.io/pypi/v/flake8-type-checking.svg)](https://pypi.org/project/flake8-type-checking/)
[![Code coverage](https://codecov.io/gh/sondrelg/flake8-type-checking/branch/main/graph/badge.svg)](https://codecov.io/gh/sondrelg/flake8-type-checking)
[![Test status](https://github.com/sondrelg/flake8-type-checking/actions/workflows/testing.yml/badge.svg)](https://github.com/snok/flake8-type-checking/actions/workflows/testing.yml)
[![Supported Python versions](https://img.shields.io/badge/python-3.8%2B-blue)](https://pypi.org/project/flake8-type-checking/)
[![Checked with mypy](http://www.mypy-lang.org/static/mypy_badge.svg)](http://mypy-lang.org/)

# flake8-type-checking

Lets you know which imports to move in or out of
[type-checking](https://docs.python.org/3/library/typing.html#typing.TYPE_CHECKING) blocks.

The plugin assumes that the imports you only use for type hinting
*are not* required at runtime. When imports aren't strictly required at runtime, it means we can guard them.

Guarding imports provides 3 major benefits:

- 🔧&nbsp;&nbsp;It reduces import circularity issues,
- 🧹&nbsp;&nbsp;It organizes imports, and
- 🚀&nbsp;&nbsp;It completely eliminates the overhead of type hint imports at runtime

<br>

Essentially, this code:

```python
import pandas  # 15mb library

x: pandas.DataFrame
```

becomes this:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas  # <-- no longer imported at runtime

x: "pandas.DataFrame"
```

More examples can be found in the [examples](#examples) section.

<br>

If you're using [pydantic](https://pydantic-docs.helpmanual.io/),
[fastapi](https://fastapi.tiangolo.com/), or [cattrs](https://github.com/python-attrs/cattrs)
see the [configuration](#configuration) for how to enable support.

## Primary features

The plugin will:

- Tell you when an import should be moved into a type-checking block
- Tell you when an import should be moved out again

And depending on which error code range you've opted into, it will tell you

- Whether you need to add a `from __future__ import annotations` import
- Whether you need to quote an annotation
- Whether you can unquote a quoted annotation

## Error codes

| Code  | Description                                                                        |
|-------|------------------------------------------------------------------------------------|
| TC001 | Move application import into a type-checking block                                 |
| TC002 | Move third-party import into a type-checking block                                 |
| TC003 | Move built-in import into a type-checking block                                    |
| TC004 | Move import out of type-checking block. Import is used for more than type hinting. |
| TC005 | Found empty type-checking block                                                    |
| TC006 | Annotation in typing.cast() should be a string literal                             |

## Choosing how to handle forward references

You need to choose whether to opt-into using the
`TC100`- or the `TC200`-range of error codes.

They represent two different ways of solving the same problem, so please only choose one.

`TC100` and `TC101` manage forward references by taking advantage of
[postponed evaluation of annotations](https://www.python.org/dev/peps/pep-0563/).

| Code  | Description                                         |
|-------|-----------------------------------------------------|
| TC100 | Add 'from \_\_future\_\_ import annotations' import |
| TC101 | Annotation does not need to be a string literal     |

`TC200` and `TC201` manage forward references using [string literals](https://www.python.org/dev/peps/pep-0484/#forward-references).

| Code  | Description                                         |
|-------|-----------------------------------------------------|
| TC200 | Annotation needs to be made into a string literal   |
| TC201 | Annotation does not need to be a string literal     |

## Enabling error ranges

Add `TC` and `TC1` or `TC2` to your flake8 config like this:

```ini
[flake8]
max-line-length = 80
max-complexity = 12
...
ignore = E501
# You can use 'extend-select' (new in flake8 v4):
extend-select = TC, TC2
# OR 'select':
select = C,E,F..., TC, TC2  # or TC1
# OR 'enable-extensions':
enable-extensions = TC, TC2  # or TC1
```

If you are unsure which `TC` range to pick, see the [rationale](#rationale) for more info.

## Installation

```shell
pip install flake8-type-checking
```

## Configuration

These options are configurable, and can be set in your flake8 config.

### Exempt modules

If you wish to exempt certain modules from
needing to be moved into type-checking blocks, you can specify which
modules to ignore.

- **setting name**: `type-checking-exempt-modules`
- **type**: `list`

```ini
[flake8]
type-checking-exempt-modules = typing_extensions  # default []
```

### Strict

The plugin, by default, will report TC00[1-3] errors
for imports if there aren't already other imports from the same module.
When there are other imports from the same module,
the import circularity and performance benefits no longer
apply from guarding an import.

When strict mode is enabled, the plugin will flag all
imports that *can* be moved.

- **setting name**: `type-checking-strict`
- **type**: `bool`

```ini
[flake8]
type-checking-strict = true  # default false
```

### Pydantic support

If you use Pydantic models in your code, you should enable Pydantic support.
This will treat any class variable annotation as being needed during runtime.

- **name**: `type-checking-pydantic-enabled`
- **type**: `bool`
```ini
[flake8]
type-checking-pydantic-enabled = true  # default false
```
### Pydantic support base-class passlist

Disabling checks for all class annotations is a little aggressive.

If you feel comfortable that all base classes named, e.g., `NamedTuple` are *not* Pydantic models,
then you can pass the names of the base classes in this setting, to re-enable checking for classes
which inherit from them.

- **name**: `type-checking-pydantic-enabled-baseclass-passlist`
- **type**: `list`
```ini
[flake8]
type-checking-pydantic-enabled-baseclass-passlist = NamedTuple, TypedDict  # default []
```

### FastAPI support

If you're using the plugin for a FastAPI project,
you should enable support. This will treat the annotations
of any decorated function as needed at runtime.

Enabling FastAPI support will also enable Pydantic support.

- **name**: `type-checking-fastapi-enabled`
- **type**: `bool`
```ini
[flake8]
type-checking-fastapi-enabled = true  # default false
```

One more thing to note for FastAPI users is that dependencies
(functions used in `Depends`) will produce false positives, unless
you enable dependency support as described below.

### FastAPI dependency support

In addition to preventing false positives for decorators, we *can*
prevent false positives for dependencies. We are making a pretty bad
trade-off however: by enabling this option we treat every annotation
in every function definition across your entire project as a possible
dependency annotation. In other words, we stop linting all function
annotations completely, to avoid the possibility of false positives.
If you prefer to be on the safe side, you should enable this - otherwise
it might be enough to be aware that false positives can happen for functions
used as dependencies.

Enabling dependency support will also enable FastAPI and Pydantic support.

- **name**: `type-checking-fastapi-dependency-support-enabled`
- **type**: `bool`
```ini
[flake8]
type-checking-fastapi-dependency-support-enabled: true  # default false
```

### Cattrs support

If you're using the plugin in a project which uses `cattrs`,
you can enable support. This will treat the annotations
of any decorated `attrs` class as needed at runtime, since
`cattrs.unstructure` calls will fail when loading
classes where types are not available at runtime.

Note: the cattrs support setting does not yet detect and
ignore class var annotations on dataclasses or other non-attrs class types.
This can be added in the future if needed.

- **name**: `type-checking-cattrs-enabled`
- **type**: `bool`
```ini
[flake8]
type-checking-cattrs-enabled = true  # default false
```

## Rationale

Why did we create this plugin?

Good type hinting typically requires a lot of project imports, which can increase
the risk of [import cycles](https://mypy.readthedocs.io/en/stable/runtime_troubles.html?#import-cycles)
in a project. The recommended way of preventing this problem is to use `typing.TYPE_CHECKING` blocks
to guard these types of imports. In particular, `TC001` helps protect against this issue.

Once imports are guarded, they will no longer be evaluated/imported during runtime. The
consequence of this is that these imports can no longer be treated as if they
were imported outside the block. Instead we need to use [forward references](https://www.python.org/dev/peps/pep-0484/#forward-references).

For Python version `>= 3.7`, there are actually two ways of solving this issue.
You can either make your annotations string literals, or you can use a `__futures__` import to enable [postponed evaluation of annotations](https://www.python.org/dev/peps/pep-0563/).
See [this](https://stackoverflow.com/a/55344418/8083459) excellent stackoverflow answer
for a great explanation of the differences.

## Examples

<details>
<summary><b>Performance example</b></summary>

Imports for type hinting can have a performance impact.

```python
import pandas


def dataframe_length(df: pandas.DataFrame) -> int:
    return len(df)
```

In this example, we import a 15mb library, for a single type hint.

We don't need to perform this operation at runtime, *at all*.
If we know that the import will not otherwise be needed by surrounding code,
we can simply guard it, like this:

```python
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    import pandas  # <-- no longer imported at runtime


def dataframe_length(df: "pandas.DataFrame") -> int:
    return len(df)
```

Now the import is no longer made at runtime. If you're unsure about how this works, see the [mypy docs](https://mypy.readthedocs.io/en/stable/runtime_troubles.html?#typing-type-checking) for a basic introduction.
</details>

<details>
<summary><b>Import circularity example</b></summary>

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
# TC1
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.b import B

class A(Model):
    def foo(self, b: B): ...
```
or
```python
# TC2
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
</details>

<details>
<summary><b>Examples from the wild</b></summary>

Here are a few examples of public projects that use `flake8-type-checking`:

- [Example from the Poetry codebase](https://github.com/python-poetry/poetry/blob/714c09dd845c58079cff3f3cbedc114dff2194c9/src/poetry/factory.py#L1:L33)
- [Example from the asgi-correlation-id codebase](https://github.com/snok/asgi-correlation-id/blob/main/asgi_correlation_id/middleware.py#L1:L12)

</details>

## Running the plugin as a pre-commit hook

You can run this flake8 plugin as a [pre-commit](https://github.com/pre-commit/pre-commit) hook:

```yaml
- repo: https://github.com/pycqa/flake8
  rev: 4.0.1
  hooks:
    - id: flake8
      additional_dependencies:
        - flake8-type-checking
```

## Contributing

Please feel free to open an issue or a PR 👏
