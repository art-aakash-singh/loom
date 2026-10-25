"""The pure modules may not reach for I/O or the clock (ruff TID251, see pyproject.toml)."""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[3]
PACKAGE = REPO_ROOT / "apps/api/src/loom_api"
PURE_MODULES = ["context/build.py", "context/budget.py", "chat/tree.py"]

FORBIDDEN = {
    "sqlalchemy": "import sqlalchemy\n",
    "sqlalchemy submodule": "from sqlalchemy.ext.asyncio import AsyncSession\n",
    "repository": "from loom_api.chat.repository import ChatRepository\n",
    "datetime.now": "from datetime import datetime\n\nNOW = datetime.now()\n",
    "time.time": "import time\n\nT = time.time()\n",
}


def banned_import_errors(module: str, source: str) -> str:
    """Lint `source` as if it were `module`; return any TID251 findings."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--no-cache",
            "--select",
            "TID251",
            "--output-format",
            "concise",
            "--stdin-filename",
            str(PACKAGE / module),
            "-",
        ],
        input=source,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    return result.stdout if result.returncode else ""


@pytest.mark.parametrize("module", PURE_MODULES)
@pytest.mark.parametrize("source", FORBIDDEN.values(), ids=FORBIDDEN.keys())
def test_pure_modules_cannot_import_io_or_read_the_clock(module: str, source: str) -> None:
    assert "TID251" in banned_import_errors(module, source)


def test_build_importing_sqlalchemy_fails_lint() -> None:
    assert "`sqlalchemy` is banned" in banned_import_errors(
        "context/build.py", "import sqlalchemy\n"
    )


@pytest.mark.parametrize("source", FORBIDDEN.values(), ids=FORBIDDEN.keys())
def test_gather_may_do_io(source: str) -> None:
    assert banned_import_errors("context/gather.py", source) == ""


@pytest.mark.parametrize("module", PURE_MODULES)
def test_pure_modules_pass_as_written(module: str) -> None:
    assert banned_import_errors(module, (PACKAGE / module).read_text()) == ""
