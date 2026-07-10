from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectn_lab.theory_book import default_paths, write_book


def main() -> None:
    paths = write_book(default_paths())
    print(f"Wrote Markdown: {paths.markdown}")
    print(f"Wrote HTML: {paths.html}")
    print(f"Wrote figures: {paths.figures}")


if __name__ == "__main__":
    main()
