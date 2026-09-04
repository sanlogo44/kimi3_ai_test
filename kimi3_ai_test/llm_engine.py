from typing import List, Dict, Any, Optional
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, StoppingCriteria, StoppingCriteriaList
from mcp_protocol import MCPClient, ToolCall, ToolResult
from logger import get_logger

class ToolStopCriteria(StoppingCriteria):
    def __init__(self, tokenizer, stop_phrases): self.stop_phrases = stop_phrases; self.tokenizer = tokenizer
    def __call__(self, input_ids, scores, **kwargs):
        return any(p in self.tokenizer.decode(input_ids[0][-50:], skip_special_tokens=True) for p in self.stop_phrases)

class ToolAugmentedLLM:
    def __init__(self, model_name=None, device=None, load_in_4bit=None, max_tool_iterations=None, config=None):
        if config is None:
            from config_loader import load_config
            config = load_config()
        self.log = get_logger(config)
        hw, md = config.get("hardware",{}), config.get("model",{})
        self.model_name = model_name or md.get("name","meta-llama/Meta-Llama-3-8B-Instruct")
        self.max_tool_iterations = max_tool_iterations or md.get("max_tool_iterations",5)

        req = (device or hw.get("device","auto")).lower()
        cuda = torch.cuda.is_available()
        self.device = "cuda" if (req=="auto" and cuda) else ("cpu" if req=="auto" else req)
        if self.device=="cuda" and not cuda: raise RuntimeError("CUDA nicht verfügbar")

        wd = hw.get("weights_dtype","auto").lower()
        if wd=="fp32" or self.device=="cpu":
            self.dtype, self.use_4bit = torch.float32, False
            self.log.info("Modus: float32 (CPU oder fp32 erzwungen)")
        else:
            self.use_4bit = load_in_4bit if load_in_4bit is not None else hw.get("use_4bit",True)
            self.dtype = torch.float16 if hw.get("use_fp16",True) else torch.float32
            self.log.info(f"GPU-Modus | 4-Bit: {self.use_4bit} | dtype: {self.dtype}")

        self.log.info(f"Lade {self.model_name} auf {self.device.upper()}")
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=True, padding_side="left")
        self.tokenizer.pad_token = self.tokenizer.eos_token

        kwargs = {"device_map":"cpu" if self.device=="cpu" else "auto", "torch_dtype":self.dtype, "trust_remote_code":True}
        if self.use_4bit:
            from transformers import BitsAndBytesConfig
            kwargs["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_compute_dtype=torch.float16,bnb_4bit_use_double_quant=True,bnb_4bit_quant_type="nf4")
        self.model = AutoModelForCausalLM.from_pretrained(self.model_name, **kwargs)
        self.model.eval()
        self.stop_criteria = StoppingCriteriaList([ToolStopCriteria(self.tokenizer, ["[/TOOL]","[TOOL_RESULT]"])])
        self.log.info("Modell geladen.")

    def _build_chat_prompt(self, messages, system_prompt=None):
        if system_prompt: messages = [{"role":"system","content":system_prompt}] + messages
        prompt = ""
        for m in messages:
            r,c = m["role"],m["content"]
            if r=="system": prompt += f" 的系统\n{c}<|eot_id|>"
            elif r=="user": prompt += f" 的用户\n{c}<|eot_id|>"
            elif r=="assistant": prompt += f" 的助手\n{c}<|eot_id|>"
        return prompt + " 的助手\n"

    def generate(self, prompt, max_new_tokens=512, temperature=0.7, top_p=0.9, stop_on_tool=True):
        inputs = self.tokenizer(prompt, return_tensors="pt")
        if self.device=="cuda": inputs = {k:v.to(self.model.device) for k,v in inputs.items()}
        with torch.no_grad():
            outputs = self.model.generate(**inputs, max_new_tokens=max_new_tokens, temperature=temperature, top_p=top_p, do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id, stopping_criteria=self.stop_criteria if stop_on_tool else None)
        return self.tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)

    def chat_with_tools(self, user_message, mcp_client, conversation_history=None):
        if conversation_history is None: conversation_history = []
        system = mcp_client.get_system_prompt_with_tools()
        messages = conversation_history + [{"role":"user","content":user_message}]
        tool_calls_made, final = [], ""
        for _ in range(self.max_tool_iterations):
            prompt = self._build_chat_prompt(messages, system)
            response = self.generate(prompt, stop_on_tool=True)
            tc = mcp_client.parse_tool_call(response)
            if tc is None:
                final = response; messages.append({"role":"assistant","content":response}); break
            self.log.info(f"Tool-Call: {tc.tool_name}({tc.arguments})")
            tool_calls_made.append(tc)
            result = mcp_client.format_tool_result(asyncio.get_event_loop().run_until_complete(mcp_client.server.execute(tc)))
            messages.append({"role":"assistant","content":f'{{"tool_call":{{"name":"{tc.tool_name}","arguments":{tc.arguments}}}}}'})
            messages.append({"role":"user","content":result})
        return {"response":final,"tool_calls":tool_calls_made,"conversation":messages}