import os
import json

DEFAULT_CONFIG = {
    "logging": {"level": "INFO", "colored": True, "log_file": None},
    "hardware": {"device": "auto", "use_4bit": True, "use_fp16": True, "weights_dtype": "fp32"},
    "model": {"name": "meta-llama/Meta-Llama-3-8B-Instruct", "max_tool_iterations": 5},
    "training": {"output_dir": "./tool_model", "batch_size": 1, "gradient_accumulation_steps": 8,
                 "num_epochs": 3, "learning_rate": 2e-4, "max_length": 2048}
}

def load_config(path="config.yaml"):
    if not os.path.exists(path):
        print(f"[INFO] {path} nicht gefunden, nutze Defaults.")
        return DEFAULT_CONFIG
    try:
        if path.endswith(('.yaml', '.yml')):
            import yaml
            with open(path, 'r', encoding='utf-8') as f:
                user_cfg = yaml.safe_load(f) or {}
        elif path.endswith('.json'):
            with open(path, 'r', encoding='utf-8') as f:
                user_cfg = json.load(f)
        else:
            return DEFAULT_CONFIG
    except Exception:
        return DEFAULT_CONFIG

    def merge(base, override):
        for key, val in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(val, dict):
                merge(base[key], val)
            else:
                base[key] = val
        return base
    return merge(DEFAULT_CONFIG.copy(), user_cfg)