#!/usr/bin/env python3
"""Thin wrapper so `python3 refcode-sync.py ...` keeps working; the real
implementation lives in refcode_sync.py (importable by refcode.py)."""
import sys

from refcode_sync import main

if __name__ == "__main__":
    sys.exit(main())
