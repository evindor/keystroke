"""Complete one Omarchy dmenu request with a selection-before-done ordering."""
import sys
from pathlib import Path


def reply(selection_file, done_file, value):
    if selection_file:
        Path(selection_file).write_text("" if value is None else value + "\n")
    Path(done_file).touch()


if __name__ == "__main__":
    reply(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
