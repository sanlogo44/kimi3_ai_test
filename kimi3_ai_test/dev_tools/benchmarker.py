import time, torch, json
from typing import List, Dict, Optional
from pathlib import Path

class Benchmarker:
    def __init__(self, output_dir="dev_tools/benchmarks"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results_file = self.output_dir / "benchmark_results.jsonl"

    def run_benchmark(self, model, tokenizer, test_prompts, expected_outputs=None, max_new_tokens=50) -> Dict:
        model.eval()
        res = {"timestamp":time.strftime("%Y-%m-%d %H:%M:%S"),"num_prompts":len(test_prompts),
               "avg_inference_time_ms":0.0,"avg_tokens_per_sec":0.0,"perplexity":0.0,"samples":[]}
        total_time, total_tok = 0.0, 0
        for i,prompt in enumerate(test_prompts):
            inputs = tokenizer(prompt, return_tensors="pt")
            if hasattr(model,'device') and str(model.device)!='cpu': inputs = {k:v.to(model.device) for k,v in inputs.items()}
            t0 = time.perf_counter()
            with torch.no_grad():
                out = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False, pad_token_id=tokenizer.eos_token_id)
            elapsed = time.perf_counter()-t0
            gen = tokenizer.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
            nt = out.shape[1]-inputs["input_ids"].shape[1]
            total_time += elapsed; total_tok += nt
            sample = {"prompt":prompt,"generated":gen,"time_ms":round(elapsed*1000,2),"tokens":nt}
            if expected_outputs and i < len(expected_outputs):
                sample["expected"]=expected_outputs[i]; sample["match"]=gen.strip().lower()==expected_outputs[i].strip().lower()
            res["samples"].append(sample)
        n = len(test_prompts)
        res["avg_inference_time_ms"] = round((total_time/n)*1000,2)
        res["avg_tokens_per_sec"] = round(total_tok/total_time,2) if total_time>0 else 0
        try:
            tl,c = 0.0,0
            for prompt in test_prompts[:5]:
                inputs = tokenizer(prompt, return_tensors="pt")
                if hasattr(model,'device') and str(model.device)!='cpu': inputs = {k:v.to(model.device) for k,v in inputs.items()}
                with torch.no_grad(): tl += model(**inputs, labels=inputs["input_ids"]).loss.item(); c += 1
            res["perplexity"] = round(torch.exp(torch.tensor(tl/c)).item(),4) if c else 0
        except: res["perplexity"] = -1.0
        self._save(res); return res

    def _save(self, res):
        with open(self.results_file,'a',encoding='utf-8') as f: f.write(json.dumps(res)+"\n")
    def get_all_results(self):
        if not self.results_file.exists(): return []
        with open(self.results_file,'r',encoding='utf-8') as f: return [json.loads(l) for l in f if l.strip()]
    def get_latest(self): r=self.get_all_results(); return r[-1] if r else None