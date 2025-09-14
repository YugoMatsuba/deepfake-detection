import torch
from collections import OrderedDict

from ml.models.utils import (
    strip_module_prefix,
    fix_pointwise_separable_convs,
    drop_fc_keys,
)

def test_strip_module_prefix():
    sd = OrderedDict({
        "module.conv1.weight": torch.randn(32, 3, 3, 3),
        "module.bn1.weight": torch.randn(32),
        "last_linear.weight": torch.randn(2, 2048),
    })
    out = strip_module_prefix(sd)
    assert "conv1.weight" in out and "bn1.weight" in out
    assert "module.conv1.weight" not in out

def test_fix_pointwise_separable_convs_unsqueeze():
    # Simulate separable pointwise saved as [C_out, C_in]
    sd = OrderedDict({
        "block3.sepconv.pointwise.weight": torch.randn(64, 64),  # 2D -> must become 4D
        "something_else": torch.randn(3,3,3,3),
    })
    out = fix_pointwise_separable_convs(sd)
    w = out["block3.sepconv.pointwise.weight"]
    assert w.ndim == 4 and w.shape[-2:] == (1, 1)

def test_drop_fc_keys():
    sd = OrderedDict({
        "fea_part.weight": torch.randn(32, 32, 3, 3),
        "fc.weight": torch.randn(2, 2048),
        "fc.bias": torch.randn(2),
    })
    out = drop_fc_keys(sd)
    assert "fc.weight" not in out and "fc.bias" not in out
    assert "fea_part.weight" in out