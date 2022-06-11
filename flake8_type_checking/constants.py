import sys

ATTRIBUTE_PROPERTY = '_flake8-type-checking_parent'

ATTRS_DECORATORS = ['attrs.define', 'attr.define', 'attr.s']
ATTRS_IMPORTS = {'attrs', 'attr'}

py38 = sys.version_info.major == 3 and sys.version_info.minor == 8
