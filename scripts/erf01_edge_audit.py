#!/usr/bin/env python3
"""Legacy compatibility entrypoint; implementation lives in experiments.erf01.edge_audit."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.erf01.edge_audit import *  # noqa: F401,F403
from experiments.erf01.edge_audit import __dict__ as _impl_dict
# Preserve historically-imported private helpers without retaining their logic here.
globals().update({name: value for name, value in _impl_dict.items() if name.startswith("_") and not name.startswith("__")})

if __name__ == "__main__":
    main()
