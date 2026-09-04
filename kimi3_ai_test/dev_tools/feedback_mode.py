import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict

class FeedbackStore:
    def __init__(self, store_path="dev_tools/feedback/feedback_db.jsonl"):
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

    def add_feedback(self, prompt: str, response: str, rating: int, comment="", model_name="unknown"):
        entry = {"timestamp":datetime.now().isoformat(),"model":model_name,"prompt":prompt,"response":response,"rating":rating,"comment":comment}
        with open(self.store_path,'a',encoding='utf-8') as f: f.write(json.dumps(entry,ensure_ascii=False)+"\n")

    def get_all(self) -> List[Dict]:
        if not self.store_path.exists(): return []
        with open(self.store_path,'r',encoding='utf-8') as f: return [json.loads(l) for l in f if l.strip()]

    def get_positive(self): return [e for e in self.get_all() if e["rating"]==1]
    def get_negative(self): return [e for e in self.get_all() if e["rating"]==-1]

    def export_for_training(self, output_path="dev_tools/feedback/training_export.json"):
        data = self.get_all()
        with open(output_path,'w',encoding='utf-8') as f: json.dump(data,f,indent=2,ensure_ascii=False)
        return output_path

    def clear(self):
        if self.store_path.exists(): self.store_path.unlink()