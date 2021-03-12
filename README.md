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

A flake8 plugin to help you identify which imports to put into type-checking blocks.

Beyond this, it will also help you manage forward references however you would like to.

## Installation

```shell
pip install flake8-typing-only-imports
```

## Active codes

| Code   | Description                                         |
|--------|-----------------------------------------------------|
| TYO100 | Import should be moved to a type-checking block  |


## Deactivated (by default) codes
| Code   | Description                                         |
|--------|-----------------------------------------------------|
| TYO101 | Third-party import should be moved to a type-checking block |
| TYO200 | Missing 'from \_\_future\_\_ import annotations' import |
| TYO201 | Annotation is wrapped in unnecessary quotes |
| TYO300 | Annotation should be wrapped in quotes |
| TYO301 | Annotation is wrapped in unnecessary quotes |

If you wish to activate any of these checks, you need to pass them to flake8's `select` argument ([docs](https://flake8.pycqa.org/en/latest/user/violations.html)).

`TYO101` is deactivated by default, mostly because misplaced third party imports don't carry
with it the same level of consequence that local imports can have - they will
never lead to import circularity issues. Activating `TYO101` will mostly help the
initialization time of your app.

Please note, `TYO200s` and `TYO300s` are mutually exclusive. Don't activate both series.
Read on for an in-depth explanation.

## Motivation

Two common issues when annotating large code bases are:

1. Import circularity issues
2. Annotating not-yet-defined structures

These problems are largely solved by two Python features:

1. Type checking blocks

    <br>The builtin `typing` library, as of Python 3.7, provides a `TYPE_CHECKING` block you can put type annotation imports into (see [docs](https://docs.python.org/3/library/typing.html#constant)).

    ```python
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        # this code is not evaluated at runtime
        from foo import bar
    ```



2. Forward references
    <br><br>

    When you've got unevaluated imports (in type checking block), or you try to reference not-yet-defined structures, forward references are the answer. They can be used, like this:
    ```python
    class Foo:
        def bar(self) -> 'Foo':
            return Foo()
    ```

    And ever since [PEP563](https://www.python.org/dev/peps/pep-0563/#abstract) was implemented, you also have the option of doing this:
    ```python
    from __future__ import annotations

    class Foo:
        def bar(self) -> Foo:
            return Foo()
    ```

   See [this](https://stackoverflow.com/questions/55320236/does-python-evaluate-type-hinting-of-a-forward-reference) excellent stackoverflow response explaining forward references, if you'd like more context.

With that said, the aim of this plugin is to automate the management of type annotation
imports (type-checking block import management), and keeping track of the forward references that become necessary as a consequence.


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
