import builtins
import enum

import flake8

ATTRIBUTE_PROPERTY = '_flake8-type-checking__parent'
ANNOTATION_PROPERTY = '_flake8-type-checking__is_annotation'
BINOP_OPERAND_PROPERTY = '_flake8-type-checking__is_binop_operand'

ATTRS_DECORATORS = [
    'attrs.define',
    'attrs.frozen',
    'attrs.mutable',
    'attr.define',
    'attr.frozen',
    'attr.mutable',
    'attr.s',
]
ATTRS_IMPORTS = {'attrs', 'attr'}

flake_version_gt_v4 = tuple(int(i) for i in flake8.__version__.split('.')) >= (4, 0, 0)

# Based off of what pyflakes does
builtin_names = set(dir(builtins)) | {'__file__', '__builtins__', '__annotations__', 'WindowsError'}

# SQLAlchemy 2.0 default mapped dotted names
sqlalchemy_default_mapped_dotted_names = {
    'sqlalchemy.orm.Mapped',
    'sqlalchemy.orm.DynamicMapped',
    'sqlalchemy.orm.WriteOnlyMapped',
}


# Sentinels
class _Sentinels(enum.Enum):
    MISSING = enum.auto()


MISSING = _Sentinels.MISSING

# Error codes
TC001 = "TC001 Move application import '{module}' into a type-checking block"
TC002 = "TC002 Move third-party import '{module}' into a type-checking block"
TC003 = "TC003 Move built-in import '{module}' into a type-checking block"
TC004 = "TC004 Move import '{module}' out of type-checking block. Import is used for more than type hinting."
TC005 = 'TC005 Found empty type-checking block'
TC006 = "TC006 Annotation '{annotation}' in typing.cast() should be a string literal"
TC007 = "TC007 Type alias '{alias}' needs to be made into a string literal"
TC008 = "TC008 Type alias '{alias}' does not need to be a string literal"
TC009 = "TC009 Move declaration '{name}' out of type-checking block. Variable is used for more than type hinting."
TC010 = 'TC010 Operands for | cannot be a string literal'
TC100 = "TC100 Add 'from __future__ import annotations' import"
TC101 = "TC101 Annotation '{annotation}' does not need to be a string literal"
TC200 = "TC200 Annotation '{annotation}' needs to be made into a string literal"
TC201 = "TC201 Annotation '{annotation}' does not need to be a string literal"
