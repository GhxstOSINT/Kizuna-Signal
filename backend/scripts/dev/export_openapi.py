from __future__ import annotations

import json

from app.core.paths import OPENAPI_SNAPSHOT
from app.main import app


def main() -> None:
    destination = OPENAPI_SNAPSHOT
    destination.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {destination}")


if __name__ == "__main__":
    main()
