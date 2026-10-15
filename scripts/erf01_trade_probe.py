#!/usr/bin/env python3
"""Compatibility CLI; implementation: experiments.erf01.economic_probe."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.erf01.economic_probe import *  # noqa: F401,F403
from experiments.erf01.economic_probe import __dict__ as _implementation
globals().update({k:v for k,v in _implementation.items() if k.startswith("_") and not k.startswith("__")})

if __name__ == "__main__":
    main()
