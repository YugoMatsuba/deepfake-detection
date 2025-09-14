import torch
from ml.models.spsl_infer import compute_phase_channel

def test_phase_channel_shape_dtype_device_and_determinism():
    device = "cpu"
    x = torch.randn(3, 3, 256, 256, device=device, dtype=torch.float32)

    p1 = compute_phase_channel(x)
    p2 = compute_phase_channel(x.clone())  # same input

    # shape/dtype/device
    assert p1.shape == (3, 1, 256, 256)
    assert p1.dtype == torch.float32
    assert p1.device.type == "cpu"

    # deterministic for identical input
    assert torch.allclose(p1, p2, atol=1e-6)

    # basic sanity: non-trivial signal
    assert torch.isfinite(p1).all()