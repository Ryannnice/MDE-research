"""Runtime-only compatibility for TransCG's unmodified 2022 test entrypoint."""

from __future__ import annotations

import os
import sys
import types

import numpy as np
import torch


if "bool" not in np.__dict__:
    np.bool = np.bool_  # type: ignore[attr-defined]

# PyTorch 2.6 changed torch.load's default to weights_only=True.  The released
# trusted checkpoint predates that change and the unmodified test.py does not
# pass the old default explicitly.
_torch_load = torch.load


def _legacy_torch_load(*args, **kwargs):
    kwargs.setdefault("weights_only", False)
    return _torch_load(*args, **kwargs)


torch.load = _legacy_torch_load

datasets_dir = os.environ.get("TRANSCG_OFFICIAL_DATASETS")
if datasets_dir:
    package = types.ModuleType("datasets")
    package.__path__ = [datasets_dir]
    package.__package__ = "datasets"
    sys.modules["datasets"] = package
