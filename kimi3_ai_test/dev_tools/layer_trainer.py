import torch, torch.nn as nn
from typing import List, Dict, Optional
from pathlib import Path
import json, copy

class LayerTrainer:
    def __init__(self, model: nn.Module):
        self.model = model
        self.layer_map = self._build_layer_map()

    def _build_layer_map(self):
        return {name:m for name,m in self.model.named_modules() if isinstance(m,(nn.Linear,nn.Conv1d,nn.Conv2d,nn.LayerNorm))}

    def list_layers(self): return list(self.layer_map.keys())
    def freeze_all(self):
        for p in self.model.parameters(): p.requires_grad = False
    def unfreeze_all(self):
        for p in self.model.parameters(): p.requires_grad = True
    def freeze_layer(self, name):
        if name in self.layer_map:
            for p in self.layer_map[name].parameters(): p.requires_grad = False
    def unfreeze_layer(self, name):
        if name in self.layer_map:
            for p in self.layer_map[name].parameters(): p.requires_grad = True

    def apply_soup_noise(self, name, magnitude=0.01):
        if name not in self.layer_map: return
        with torch.no_grad():
            for p in self.layer_map[name].parameters():
                if p.dtype in (torch.float32,torch.float16): p.add_(torch.randn_like(p)*magnitude)

    def apply_soup_scale(self, name, scale=1.0):
        if name not in self.layer_map: return
        with torch.no_grad():
            for p in self.layer_map[name].parameters(): p.mul_(scale)

    def soup_average_checkpoints(self, checkpoint_paths: List[str], output_path: str, weights: Optional[List[float]]=None):
        if not checkpoint_paths: raise ValueError("Mindestens ein Checkpoint nötig.")
        sds = [torch.load(p, map_location="cpu") for p in checkpoint_paths]
        if weights is None: weights = [1.0/len(sds)]*len(sds)
        avg = copy.deepcopy(sds[0])
        for k in avg:
            if isinstance(avg[k], torch.Tensor):
                avg[k] = sum(sd.get(k,torch.zeros_like(avg[k]))*w for sd,w in zip(sds,weights))
        torch.save(avg, output_path); return output_path

    def save_layer_config(self, path: str):
        cfg = {name: {"frozen":not any(p.requires_grad for p in m.parameters())} for name,m in self.layer_map.items()}
        with open(path,'w') as f: json.dump(cfg,f,indent=2)

    def load_layer_config(self, path: str):
        with open(path,'r') as f:
            for name,settings in json.load(f).items():
                if name in self.layer_map:
                    for p in self.layer_map[name].parameters(): p.requires_grad = not settings.get("frozen",False)