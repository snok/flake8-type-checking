from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import List

TYO100 = "TYO100: Local import '{module}' only used for type hinting"  # noqa: FS003
TYO101 = "TYO101: Remote import '{module}' only used for type hinting"  # noqa: FS003

disabled_by_default: 'List[str]' = [TYO101]
