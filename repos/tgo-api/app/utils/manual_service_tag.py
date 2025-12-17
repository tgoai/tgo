"""Shared constants for the manual service (human handoff) tag.

Keep this module dependency-light so it can be imported from both internal and
public API modules without pulling in ORM models.
"""

from __future__ import annotations

import base64


MANUAL_SERVICE_TAG_NAME: str = "Manual Service"
MANUAL_SERVICE_TAG_NAME_ZH: str = "转人工"

# TagCategory.VISITOR.value == "visitor"
MANUAL_SERVICE_TAG_ID: str = base64.b64encode(f"{MANUAL_SERVICE_TAG_NAME}@visitor".encode()).decode()

