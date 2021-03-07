from __future__ import annotations

TYO100 = "TYO100: Import '{module}' should be moved to a type-checking block"
TYO101 = "TYO101: Third-party import '{module}' should be moved to a type-checking block"
TYO200 = "TYO200: Missing 'from __future__ import annotations' import"
TYO201 = "TYO201: Annotation '{annotation}' is wrapped in unnecessary quotes"
TYO300 = "TYO300: Annotation '{annotation}' should be wrapped in quotes"
TYO301 = "TYO301: Annotation '{annotation}' is wrapped in unnecessary quotes"

disabled_by_default: list[str] = ['TYO101', 'TYO300', 'TYO301']
