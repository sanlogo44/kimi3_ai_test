import shutil, json, time
from pathlib import Path
from typing import List, Dict, Optional

class CheckpointManager:
    def __init__(self, base_dir="checkpoints"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.base_dir / "checkpoint_index.json"
        self._index = self._load_index()

    def _load_index(self):
        if self.index_file.exists():
            with open(self.index_file,'r') as f: return json.load(f)
        return {"checkpoints":[]}

    def _save_index(self):
        with open(self.index_file,'w') as f: json.dump(self._index,f,indent=2)

    def save_checkpoint(self, model, tokenizer, name: str, metadata=None) -> str:
        ts = time.strftime("%Y%m%d_%H%M%S")
        cp_name = f"{name}_{ts}"
        cp_dir = self.base_dir / cp_name
        cp_dir.mkdir(parents=True, exist_ok=True)
        mp = cp_dir / "model"
        model.save_pretrained(mp); tokenizer.save_pretrained(mp)
        meta = {"name":name,"timestamp":ts,"path":str(cp_dir),"model_path":str(mp),**(metadata or {})}
        self._index["checkpoints"].append(meta); self._save_index()
        return str(cp_dir)

    def list_checkpoints(self): return self._index.get("checkpoints",[])
    def get_checkpoint(self, name):
        for cp in self._index["checkpoints"]:
            if cp["name"]==name or name in cp["timestamp"]: return cp
        return None

    def load_checkpoint_adapter(self, checkpoint_path: str, base_model):
        from peft import PeftModel
        ap = Path(checkpoint_path) / "model"
        if not ap.exists(): raise FileNotFoundError(f"Kein Adapter unter {ap}")
        return PeftModel.from_pretrained(base_model, ap)

    def resume_training_copy(self, checkpoint_path: str, base_model, tokenizer):
        cp = Path(checkpoint_path)
        if not cp.exists(): raise FileNotFoundError(f"Checkpoint nicht gefunden: {checkpoint_path}")
        rn = f"resume_{cp.name}_{time.strftime('%H%M%S')}"
        rd = self.base_dir / rn
        shutil.copytree(cp, rd)
        from peft import PeftModel
        return PeftModel.from_pretrained(base_model, rd / "model"), tokenizer, str(rd)

    def delete_checkpoint(self, name: str) -> bool:
        rem = next((c for c in self._index["checkpoints"] if c["name"]==name or name in c["path"]), None)
        if rem:
            p = Path(rem["path"])
            if p.exists(): shutil.rmtree(p)
            self._index["checkpoints"].remove(rem); self._save_index(); return True
        return False