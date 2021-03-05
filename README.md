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

> This module is still a work in progress.

flake8 plugin to help identify imports to put in type-checking blocks, and to manage related annotations.

## Installation

```shell
pip install flake8-typing-only-imports
```

## Codes

| Code   | Description                                         |
|--------|-----------------------------------------------------|
| TYO100 | Import should be moved to a type-checking block  |
| TYO101 | Third-party import should be moved to a type-checking block |
| TYO200 | Missing 'from __future__ import annotations' import |
| TYO201 | Annotation should be wrapped in quotes |
| TYO202 | Annotation is wrapped in unnecessary quotes |

`TYO101` is disabled by default because third-party imports usually
aren't a concern wrt. import circularity issues.

`TYO200` and `TYO201` should be considered mutually exclusive as they represent 
two different ways of solving the same problem.

## Motivation

Two common issues when annotating large code bases are:

1. Import circularity issues
2. Annotating not-yet-defined structures

These problems are largely solved by two features:

1. Type checking blocks

    ```python
    from typing import TYPE_CHECKING
   
    if TYPE_CHECKING:  # <-- not evaluated at runtime
       from app import something
    ```
2. Forward references
    <br><br>
    Which can be created like this
    ```python
    class Foo:
        def bar(self) -> 'Foo':
            return Foo()
    ```
    
    or since [PEP563](https://www.python.org/dev/peps/pep-0563/#abstract) was implemented, like this:
    ```python
    from __future__ import annotations
   
    class Foo:
        def bar(self) -> Foo:
            return Foo()
    ```

   (See [this](https://stackoverflow.com/questions/55320236/does-python-evaluate-type-hinting-of-a-forward-reference) excellent stackoverflow response explaining forward references)

The aim of this plugin is to make it easier to clean up your type annotation imports,
and the forward references that then become necessary.


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
