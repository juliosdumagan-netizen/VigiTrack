# Core VigiTrack application package
import sys
import types
from enum import IntEnum

# Compatibility guard for PyTorch 2.5+ legacy datapipes imports
try:
    import torch.utils.data.datapipes  # type: ignore
except (ImportError, ModuleNotFoundError):
    try:
        import torch.utils.data as tud  # type: ignore

        class SHARDING_PRIORITIES(IntEnum):
            DEFAULT = 1

        sharding_mod = types.ModuleType("torch.utils.data.datapipes.iter.sharding")
        sharding_mod.SHARDING_PRIORITIES = SHARDING_PRIORITIES  # type: ignore

        iter_mod = types.ModuleType("torch.utils.data.datapipes.iter")
        iter_mod.sharding = sharding_mod  # type: ignore

        dp_mod = types.ModuleType("torch.utils.data.datapipes")
        dp_mod.iter = iter_mod  # type: ignore

        tud.datapipes = dp_mod  # type: ignore
        sys.modules["torch.utils.data.datapipes"] = dp_mod
        sys.modules["torch.utils.data.datapipes.iter"] = iter_mod
        sys.modules["torch.utils.data.datapipes.iter.sharding"] = sharding_mod
    except Exception:
        pass
