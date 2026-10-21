"""Write the FastAPI OpenAPI schema to a file (no running server needed)."""

import json
import sys
from pathlib import Path

from loom_api.main import app

out = Path(sys.argv[1])
out.write_text(json.dumps(app.openapi(), indent=2) + "\n")
print(f"wrote {out}")
