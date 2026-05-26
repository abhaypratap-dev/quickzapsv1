#!/usr/bin/env python
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")


def main():
    local_deps = Path(__file__).resolve().parent / ".deps"
    if local_deps.exists():
        sys.path.insert(0, str(local_deps))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
