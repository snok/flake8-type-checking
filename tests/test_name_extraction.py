import ast
import sys

import pytest

from flake8_type_checking.checker import ImportVisitor, StringAnnotationVisitor

examples = [
    ('', set()),
    ('invalid_syntax]', set()),
    ('int', {'int'}),
    ('dict[str, int]', {'dict', 'str', 'int'}),
    # make sure literals don't add names for their contents
    ('Literal["a"]', {'Literal'}),
    ("Literal['a']", {'Literal'}),
    ('Literal[0]', {'Literal'}),
    ('Literal[1.0]', {'Literal'}),
    ('Literal[True]', {'Literal'}),
    ('L[a]', {'L'}),
    ('T | S', {'T', 'S'}),
    ('Union[Dict[str, Any], Literal["Foo", "Bar"], _T]', {'Union', 'Dict', 'str', 'Any', 'Literal', '_T'}),
    # for attribute access only everything up to the first dot should count
    # this matches the behavior of add_annotation
    ('datetime.date | os.path.sep', {'datetime', 'os'}),
    ('Nested["str"]', {'Nested', 'str'}),
    ('Annotated[str, validator(int, 5)]', {'Annotated', 'str'}),
    ('Annotated[str, "bool"]', {'Annotated', 'str'}),
]

if sys.version_info >= (3, 11):
    examples.extend(
        [
            ('*Ts', {'Ts'}),
        ]
    )


@pytest.mark.parametrize(('example', 'expected'), examples)
def test_name_extraction(example, expected):
    import_visitor = ImportVisitor(
        cwd='fake cwd',  # type: ignore[arg-type]
        pydantic_enabled=False,
        fastapi_enabled=False,
        fastapi_dependency_support_enabled=False,
        cattrs_enabled=False,
        sqlalchemy_enabled=False,
        sqlalchemy_mapped_dotted_names=[],
        injector_enabled=False,
        pydantic_enabled_baseclass_passlist=[],
    )
    import_visitor.visit(ast.parse('from typing import Annotated, Literal, Literal as L'))
    visitor = StringAnnotationVisitor(import_visitor)
    visitor.parse_and_visit_string_annotation(example)
    assert visitor.names == expected
