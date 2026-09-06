"""Training einzelner Schichten mit Fortschrittsmeldung.

Erlaubt das gezielte Training ausgewählter Schichten eines Modells, mit
Lernraten-Planer, vorzeitigem Abbruch und Rückmeldungen während des Laufs.
Dieses Modul benötigt PyTorch und wird deshalb erst bei Bedarf geladen.
"""
import time
from typing import Any, Callable, Dict, List, Optional

import torch
import torch.nn as nn


class LayerTrainer:
    """Trainiert ausgewählte Schichten und friert die übrigen ein."""

    def __init__(self, model: nn.Module, device: str = "cpu",
                 loss_fn: Optional[nn.Module] = None):
        self.model = model
        self.device = device
        self.loss_fn = loss_fn or nn.CrossEntropyLoss()
        self._original_state: Dict[str, bool] = {}
        self._save_grad_state()

    def _save_grad_state(self):
        """Merkt sich, welche Parameter ursprünglich trainierbar waren."""
        self._original_state = {
            name: param.requires_grad
            for name, param in self.model.named_parameters()
        }

    def freeze_all(self):
        """Friert alle Parameter ein."""
        for param in self.model.parameters():
            param.requires_grad = False

    def unfreeze_layers(self, layer_names: List[str]):
        """Gibt die gewählten Schichten wieder zum Training frei."""
        for name, param in self.model.named_parameters():
            if any(name.startswith(l) for l in layer_names):
                param.requires_grad = True

    def reset_grad_state(self):
        """Stellt den ursprünglichen Trainingszustand wieder her."""
        for name, param in self.model.named_parameters():
            param.requires_grad = self._original_state.get(name, True)

    def get_trainable_layers(self) -> List[str]:
        """Gibt die Namen aller aktuell trainierbaren Schichten zurück."""
        return [
            name for name, param in self.model.named_parameters()
            if param.requires_grad
        ]

    def train(self, X: torch.Tensor, y: torch.Tensor,
              layer_names: Optional[List[str]] = None,
              epochs: int = 10, lr: float = 1e-2,
              weight_decay: float = 0.0,
              scheduler_type: Optional[str] = None,  # "step" (stufenweise), "cosine" (Kosinus) oder None
              early_stop_patience: Optional[int] = None,
              progress_callback: Optional[Callable[[int, int, float], None]] = None,
              epoch_callback: Optional[Callable[[int, Dict[str, Any]], None]] = None
              ) -> Dict[str, Any]:
        """Trainiert das Modell; ohne ``layer_names`` alle Schichten."""

        if layer_names:
            self.freeze_all()
            self.unfreeze_layers(layer_names)

        trainable = [p for p in self.model.parameters() if p.requires_grad]
        if not trainable:
            raise ValueError("Keine trainierbaren Parameter gefunden!")

        opt = torch.optim.Adam(trainable, lr=lr, weight_decay=weight_decay)

        scheduler = None
        if scheduler_type == "step":
            scheduler = torch.optim.lr_scheduler.StepLR(
                opt, step_size=max(1, epochs // 3), gamma=0.5
            )
        elif scheduler_type == "cosine":
            scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)

        Xd, yd = X.to(self.device), y.to(self.device)
        self.model.train()

        best_loss = float("inf")
        patience_counter = 0
        history: List[Dict[str, Any]] = []
        # Vorbelegung: verhindert nicht gesetzte Variablen bei epochs <= 0
        durchlaufene_epochen = 0
        loss_val = float("nan")
        t0 = time.time()

        for ep in range(epochs):
            opt.zero_grad()
            out = self.model(Xd)
            loss = self.loss_fn(out, yd)
            loss.backward()
            opt.step()

            if scheduler:
                scheduler.step()

            current_lr = opt.param_groups[0]["lr"]
            loss_val = loss.item()
            durchlaufene_epochen = ep + 1
            history.append({"epoch": ep + 1, "loss": loss_val, "lr": current_lr})

            if progress_callback:
                progress_callback(ep + 1, epochs, loss_val)

            if epoch_callback:
                epoch_callback(ep + 1, {"loss": loss_val, "lr": current_lr})

            # Vorzeitiger Abbruch, wenn sich der Verlust nicht mehr verbessert
            if early_stop_patience:
                if loss_val < best_loss:
                    best_loss = loss_val
                    patience_counter = 0
                else:
                    patience_counter += 1
                    if patience_counter >= early_stop_patience:
                        break

        # Abschließende Bewertung
        self.model.eval()
        with torch.no_grad():
            pred = self.model(Xd).argmax(1)
            accuracy = (pred == yd).float().mean().item()

        self.reset_grad_state()

        return {
            "accuracy": accuracy,
            "train_time": time.time() - t0,
            "epochs_trained": durchlaufene_epochen,
            "final_loss": loss_val,
            "history": history,
            "layers_trained": list(layer_names) if layer_names else "alle",
        }

    def quick_eval(self, X: torch.Tensor, y: torch.Tensor) -> float:
        """Bewertet das Modell ohne zu trainieren."""
        was_training = self.model.training
        self.model.eval()
        Xd, yd = X.to(self.device), y.to(self.device)
        with torch.no_grad():
            pred = self.model(Xd).argmax(1)
            acc = (pred == yd).float().mean().item()
        if was_training:
            self.model.train()
        return acc