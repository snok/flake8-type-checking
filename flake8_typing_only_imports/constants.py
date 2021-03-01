# flake8: noqa
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import List

TYO100 = "TYO100: Local import '{module}' only used for type hinting"
TYO101 = "TYO101: Remote import '{module}' only used for type hinting"
TYO200 = "TYO200: Annotation '{annotation}' needs to be wrapped in quotes to be treated as a forward reference"

disabled_by_default: 'List[str]' = ['TYO101']
