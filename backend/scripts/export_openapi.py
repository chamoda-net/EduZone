"""Write the API's OpenAPI document as JSON, for the frontend's generated client.

    python -m scripts.export_openapi ../frontend/packages/api-client/openapi.json
"""

import json
import sys
from pathlib import Path

from app.main import app


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("openapi.json")
    out.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
