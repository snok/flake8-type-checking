import pytest

from flake8_type_checking.constants import NAME_RE

examples = [
    ('', []),
    ('int', ['int']),
    ('dict[str, int]', ['dict', 'str', 'int']),
    # make sure literals don't add names for their contents
    ('Literal["a"]', ['Literal']),
    ("Literal['a']", ['Literal']),
    ('Literal[0]', ['Literal']),
    ('Literal[1.0]', ['Literal']),
    # booleans are a special case and difficult to reject using a RegEx
    # for now it seems harmless to include them in the names, but if
    # we do something more sophisticated with the names we may want to
    # explicitly remove True/False from the result set
    ('Literal[True]', ['Literal', 'True']),
    # try some potentially upcoming syntax
    ('*Ts | _T & S', ['Ts', '_T', 'S']),
    # even when it's formatted badly
    ('*Ts|_T&P', ['Ts', '_T', 'P']),
    ('Union[Dict[str, Any], Literal["Foo", "Bar"], _T]', ['Union', 'Dict', 'str', 'Any', 'Literal', '_T']),
]


@pytest.mark.parametrize(('example', 'expected'), examples)
def test_name_extraction(example, expected):
    assert NAME_RE.findall(example) == expected
