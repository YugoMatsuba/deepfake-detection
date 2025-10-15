import torch
import pytest

from ml.models.xception_infer import load_xception, predict_probs_xception
from ml.models.spsl_infer import load_spsl, predict_probs_spsl
from ml.models.ucf_infer import load_ucf, predict_probs_ucf

ADAPTERS = [
    ("xception", load_xception, predict_probs_xception),
    ("spsl",     load_spsl,     predict_probs_spsl),
    ("ucf",      load_ucf,      predict_probs_ucf),
]

@pytest.mark.parametrize("name,load,pred", ADAPTERS)
def test_adapter_api_shapes_and_probs_cpu(name, load, pred):
    device = "cpu"
    N = 4
    x = torch.randn(N, 3, 256, 256, device=device, dtype=torch.float32)

    m = load(weights_path="", device=device)
    out = pred(m, x)

    # Dict API
    assert set(out.keys()) == {"cls", "prob", "feat"}

    # Shapes
    assert out["cls"].shape == (N, 2)
    assert out["prob"].shape == (N,)
    assert out["feat"].shape[0] == N

    # Ranges / dtypes
    assert out["prob"].dtype == torch.float32
    assert (out["prob"] >= 0).all() and (out["prob"] <= 1).all()

@pytest.mark.parametrize("name,load,pred", ADAPTERS)
def test_adapter_empty_batch(name, load, pred):
    device = "cpu"
    x = torch.empty(0, 3, 256, 256, device=device, dtype=torch.float32)

    m = load(weights_path="", device=device)
    out = pred(m, x)

    assert out["cls"].shape == (0, 2)
    assert out["prob"].shape == (0,)
    assert out["feat"].shape[0] == 0

@pytest.mark.parametrize("name,load,pred", ADAPTERS)
def test_adapter_dtype_guard_throws(name, load, pred):
    device = "cpu"
    x_wrong = torch.randn(2, 3, 256, 256, device=device, dtype=torch.float64)

    m = load(weights_path="", device=device)
    with pytest.raises(AssertionError):
        pred(m, x_wrong)