import ast
import sys

import pytest

from flake8_type_checking.checker import ImportVisitor, StringAnnotationVisitor

examples = [
    ('', set(), set()),
    ('invalid_syntax]', set(), set()),
    ('int', {'int'}, set()),
    ('dict[str, int]', {'dict', 'str', 'int'}, set()),
    # make sure literals don't add names for their contents
    ('Literal["a"]', {'Literal'}, set()),
    ("Literal['a']", {'Literal'}, set()),
    ('Literal[0]', {'Literal'}, set()),
    ('Literal[1.0]', {'Literal'}, set()),
    ('Literal[True]', {'Literal'}, set()),
    ('L[a]', {'L'}, set()),
    ('T | S', {'T', 'S'}, set()),
    ('Union[Dict[str, Any], Literal["Foo", "Bar"], _T]', {'Union', 'Dict', 'str', 'Any', 'Literal', '_T'}, set()),
    # for attribute access only everything up to the first dot should count
    # this matches the behavior of add_annotation
    ('datetime.date | os.path.sep', {'datetime', 'os'}, set()),
    ('Nested["str"]', {'Nested', 'str'}, set()),
    ('Annotated[str, validator(int, 5)]', {'Annotated', 'str'}, {'validator', 'int'}),
    ('Annotated[str, "bool"]', {'Annotated', 'str'}, set()),
]

if sys.version_info >= (3, 11):
    examples.extend([
        ('*Ts', {'Ts'}, set()),
    ])


@pytest.mark.parametrize(('example', 'expected', 'soft_uses'), examples)
def test_name_extraction(example, expected, soft_uses):
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
