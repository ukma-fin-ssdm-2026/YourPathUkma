import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(ROOT / "src" / "api"))

from src.api.main import app  

OUT_DIR = ROOT / "docs" / "api"


def main() -> None:
    schema = app.openapi()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    (OUT_DIR / "openapi-generated.yaml").write_text(
        yaml.dump(schema, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    (OUT_DIR / "openapi-generated.json").write_text(
        json.dumps(schema, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print("OpenAPI spec generated from code -> docs/api/openapi-generated.{yaml,json}")


if __name__ == "__main__":
    main()