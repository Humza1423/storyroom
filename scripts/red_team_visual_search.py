"""Run Storyroom's deterministic visual-search red-team suite in isolation.

This runner deliberately blanks cloud credentials and sets STORYROOM_DATA to a
temporary directory before importing the application through pytest. The test
provider returns synthetic vectors; this command never calls Gemini.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    test_file = repo / "tests" / "test_visual_search_redteam.py"
    os.chdir(repo)
    with tempfile.TemporaryDirectory(prefix="storyroom-red-team-") as isolated_data:
        os.environ["STORYROOM_DATA"] = isolated_data
        os.environ["GEMINI_API_KEY"] = ""
        os.environ["GOOGLE_API_KEY"] = ""

        # Import only after the isolated data path and empty credentials are set.
        import pytest

        print(f"Isolated STORYROOM_DATA: {isolated_data}")
        print("Provider: deterministic fake vectors; live Gemini calls: disabled")
        print("Each JSON line reports raw segment ranking, event ranking, and output.")
        result = pytest.main(["-q", "-s", str(test_file)], plugins=[])
        return int(result)


if __name__ == "__main__":
    raise SystemExit(main())
