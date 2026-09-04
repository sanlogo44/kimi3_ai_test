import json, csv
from datetime import datetime
from pathlib import Path
from typing import List, Dict

class MetricsTracker:
    def __init__(self, log_dir="dev_tools/metrics"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.session_file = self.log_dir / "training_sessions.jsonl"
        self.csv_file = self.log_dir / "metrics.csv"
        if not self.csv_file.exists():
            with open(self.csv_file,'w',newline='',encoding='utf-8') as f:
                csv.writer(f).writerow(["timestamp","model","accuracy","loss","tokens_used","train_time_sec","epochs","batch_size","hardware"])

    def log_session(self, model, accuracy, loss, tokens_used, train_time_sec, epochs, batch_size, hardware, notes=""):
        entry = {"timestamp":datetime.now().isoformat(),"model":model,"accuracy":round(accuracy,4),"loss":round(loss,4),
                 "tokens_used":tokens_used,"train_time_sec":round(train_time_sec,2),"epochs":epochs,"batch_size":batch_size,"hardware":hardware,"notes":notes}
        with open(self.session_file,'a',encoding='utf-8') as f: f.write(json.dumps(entry)+"\n")
        with open(self.csv_file,'a',newline='',encoding='utf-8') as f:
            csv.writer(f).writerow([entry["timestamp"],model,accuracy,loss,tokens_used,train_time_sec,epochs,batch_size,hardware])
        return entry

    def get_all_sessions(self) -> List[Dict]:
        if not self.session_file.exists(): return []
        with open(self.session_file,'r',encoding='utf-8') as f: return [json.loads(l) for l in f if l.strip()]

    def get_latest(self, n=10): return self.get_all_sessions()[-n:]
    def clear_history(self):
        if self.session_file.exists(): self.session_file.unlink()
        if self.csv_file.exists(): self.csv_file.unlink()
        self.__init__(str(self.log_dir))