import torch
from ml.models.xception_infer import load_xception, predict_probs_xception
from ml.models.spsl_infer import load_spsl, predict_probs_spsl
from ml.models.ucf_infer import load_ucf, predict_probs_ucf

def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    N = 5
    fake = torch.randn(N, 3, 256, 256, device=device, dtype=torch.float32)

    tests = [
        ("xception", load_xception, predict_probs_xception),
        ("spsl",     load_spsl,     predict_probs_spsl),
        ("ucf",      load_ucf,      predict_probs_ucf),
    ]

    for name, load, pred in tests:
        m = load(weights_path="", device=device)  # skeletons ignore weights
        out = pred(m, fake)
        assert set(out.keys()) == {"cls","prob","feat"}
        assert (out["prob"] >= 0).all() and (out["prob"] <= 1).all()
        print(f"{name:8s}",
              out["cls"].shape, out["prob"].shape, out["feat"].shape,
              float(out["prob"].min()), float(out["prob"].max()))

    for name, load, pred in tests:
        m = load(weights_path="", device=device)
        out = pred(m, fake[:0])
        print(f"{name:8s} (empty)", out["cls"].shape, out["prob"].shape, out["feat"].shape)

if __name__ == "__main__":
    main()
