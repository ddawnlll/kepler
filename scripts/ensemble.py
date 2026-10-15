#!/usr/bin/env python3
"""Compatibility CLI; implementation: experiments.ensemble_v1.runner."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.ensemble_v1.runner import *  # noqa: F401,F403
from experiments.ensemble_v1.runner import __dict__ as _implementation
globals().update({k:v for k,v in _implementation.items() if k.startswith("_") and not k.startswith("__")})

if __name__ == "__main__":
    main()
