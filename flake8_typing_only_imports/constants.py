# flake8: noqa
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import List

TYO100 = "TYO100: Import '{module}' should be moved to a type-checking block"
TYO101 = "TYO101: Third-party import '{module}' should be moved to a type-checking block"
TYO200 = "TYO200: Missing 'from __future__ import annotations' import"
TYO201 = "TYO201: Annotation '{annotation}' should be wrapped in quotes"
TYO202 = "TYO202: Annotation '{annotation}' is wrapped in unnecessary quotes"

disabled_by_default: 'List[str]' = ['TYO101']
