import sys

ATTRIBUTE_PROPERTY = '_flake8-type-checking_parent'

ATTRS_DECORATORS = ['attrs.define', 'attr.define', 'attr.s']

py38 = sys.version_info.major == 3 and sys.version_info.minor == 8
