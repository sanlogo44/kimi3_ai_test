
"""Modellverwaltung: Checkpoints, Layer-Training, SOUP, Weitertraining ohne Original-Verlust."""
import copy
import os
import json
import time
import uuid
import torch
import torch.nn as nn

CKPT_DIR = os.path.join(os.path.dirname(__file__), "data", "checkpoints")
os.makedirs(CKPT_DIR, exist_ok=True)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


class ToyModel(nn.Module):
    """Demo-Netz mit benannten Layern (layer1..layer4) für selektives Training."""
    def __init__(self, in_dim=16, hidden=32, out_dim=3):
        super().__init__()
        self.layer1 = nn.Linear(in_dim, hidden)
        self.layer2 = nn.Linear(hidden, hidden)
        self.layer3 = nn.Linear(hidden, hidden)
        self.layer4 = nn.Linear(hidden, out_dim)
        self.activation = nn.ReLU()

    def forward(self, x):
        x = self.activation(self.layer1(x))
        x = self.activation(self.layer2(x))
        x = self.activation(self.layer3(x))
        return self.layer4(x)

    def layer_names(self):
        return [n for n, _ in self.named_children() if n.startswith("layer")]


def freeze_except(model, train_layers):
    """Alle Layer einfrieren außer den ausgewählten (Toggle 3: Einzel-Layer-Training)."""
    for name, param in model.named_parameters():
        param.requires_grad = any(name.startswith(l) for l in train_layers)


def soup(models):
    """SOUP: gleichgewichtetes Mitteln der Gewichte mehrerer Modelle."""
    assert models, "SOUP braucht mindestens ein Modell"
    avg = copy.deepcopy(models[0])
    sd = avg.state_dict()
    for key in sd:
        sd[key] = torch.stack([m.state_dict()[key].float() for m in models]).mean(0)
    avg.load_state_dict(sd)
    return avg


def synthetic_data(n=512, in_dim=16, out_dim=3, seed=0):
    g = torch.Generator().manual_seed(seed)
    X = torch.randn(n, in_dim, generator=g)
    W = torch.randn(in_dim, out_dim, generator=g)
    y = (X @ W + 0.1 * torch.randn(n, out_dim, generator=g)).argmax(1)
    return X, y


def evaluate(model, X, y):
    model.eval()
    with torch.no_grad():
        pred = model(X.to(DEVICE)).argmax(1)
        return (pred == y.to(DEVICE)).float().mean().item()


def train_step(model, X, y, epochs=10, lr=1e-2, train_layers=None,
               token_callback=None, progress_callback=None):
    """
    Training. train_layers=None -> alle Layer, sonst nur die gewaehlten.
    token_callback(tokens): meldet simulierten Token-Verbrauch (Toggle: Token-Usage).
    """
    if train_layers:
        freeze_except(model, train_layers)
    opt = torch.optim.Adam([p for p in model.parameters() if p.requires_grad], lr=lr)
    loss_fn = nn.CrossEntropyLoss()
    Xd, yd = X.to(DEVICE), y.to(DEVICE)
    model.train()
    tokens_used = 0
    t0 = time.time()
    for ep in range(epochs):
        opt.zero_grad()
        out = model(Xd)
        loss = loss_fn(out, yd)
        loss.backward()
        opt.step()
        tokens_used += Xd.numel() + out.numel()   # simulierte Token-Zaehlung
        if token_callback:
            token_callback(tokens_used)
        if progress_callback:
            progress_callback(ep + 1, epochs, loss.item())
    return {"train_time": time.time() - t0, "tokens": tokens_used,
            "accuracy": evaluate(model, Xd, yd)}


# ---------------- Checkpoints ----------------

def save_checkpoint(model, name, meta=None):
    cid = uuid.uuid4().hex[:8]
    path = os.path.join(CKPT_DIR, f"{cid}_{name}.pt")
    torch.save({
        "state_dict": model.state_dict(),
        "meta": {
            "id": cid,
            "name": name,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            **(meta or {}),
        },
    }, path)
    return cid

def list_checkpoints():
    out = []
    for fn in sorted(os.listdir(CKPT_DIR)):
        if fn.endswith(".pt"):
            try:
                d = torch.load(os.path.join(CKPT_DIR, fn), map_location=DEVICE, weights_only=False)
                out.append(d["meta"])
            except Exception:
                pass
    return out

def load_checkpoint(cid):
    """Laedt ein gespeichertes Modell als FRISCHE Kopie - das Original bleibt unberuehrt."""
    for fn in os.listdir(CKPT_DIR):
        if fn.startswith(cid) and fn.endswith(".pt"):
            d = torch.load(os.path.join(CKPT_DIR, fn), map_location=DEVICE, weights_only=False)
            model = ToyModel()
            model.load_state_dict(d["state_dict"])
            return model, d["meta"]
    raise FileNotFoundError(cid)

def delete_checkpoint(cid):
    for fn in os.listdir(CKPT_DIR):
        if fn.startswith(cid) and fn.endswith(".pt"):
            os.remove(os.path.join(CKPT_DIR, fn))
            return True
    return False
