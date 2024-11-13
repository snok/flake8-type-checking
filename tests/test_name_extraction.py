import sys

import pytest

from flake8_type_checking.checker import StringAnnotationVisitor

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
    ('T | S', {'T', 'S'}),
    ('Union[Dict[str, Any], Literal["Foo", "Bar"], _T]', {'Union', 'Dict', 'str', 'Any', 'Literal', '_T'}),
    # for attribute access only everything up to the first dot should count
    # this matches the behavior of add_annotation
    ('datetime.date | os.path.sep', {'datetime', 'os'}),
    ('Nested["str"]', {'Nested', 'str'}),
    ('Annotated[str, validator]', {'Annotated', 'str'}),
    ('Annotated[str, "bool"]', {'Annotated', 'str'}),
]

if sys.version_info >= (3, 11):
    examples.extend([
        ('*Ts', {'Ts'}),
    ])


@pytest.mark.parametrize(('example', 'expected'), examples)
def test_name_extraction(example, expected):
    visitor = StringAnnotationVisitor()
    visitor.parse_and_visit_string_annotation(example)
    assert visitor.names == expected
