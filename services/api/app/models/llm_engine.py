"""
LLM inference service using Ray Serve.
MINIMAL SETUP: CPU inference with HuggingFace transformers (TinyLlama)
PRODUCTION: GPU inference with vLLM (Llama 3 70B)
"""
from ray import serve
import os
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

@serve.deployment(
    autoscaling_config={"min_replicas": 1, "max_replicas": 2},
    ray_actor_options={
        "num_cpus": 2,
        "num_gpus": 0      # ← changed from 1, no GPU in minimal setup
    }
)
class VLLMDeployment:
    def __init__(self):
        # MINIMAL: TinyLlama on CPU
        # PRODUCTION: set MODEL_ID to meta-llama/Meta-Llama-3-70B-Instruct
        model_id = os.getenv("MODEL_ID", "TinyLlama/TinyLlama-1.1B-Chat-v1.0")

        self.tokenizer = AutoTokenizer.from_pretrained(model_id)

        # MINIMAL: HuggingFace transformers on CPU
        # PRODUCTION: replace with vLLM AsyncLLMEngine for GPU
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype=torch.float32,   # ← float32 for CPU
            device_map="cpu"             # ← explicit CPU
        )
        self.model.eval()

    async def __call__(self, request):
        body = await request.json()
        messages = body.get("messages", [])
        temperature = body.get("temperature", 0.7)
        max_tokens = body.get("max_tokens", 512)   # ← reduced from 1024

        # Format messages using chat template
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        inputs = self.tokenizer(prompt, return_tensors="pt")

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=temperature > 0,
                pad_token_id=self.tokenizer.eos_token_id
            )

        # Decode only the generated tokens (not the prompt)
        generated = outputs[0][inputs["input_ids"].shape[1]:]
        text_output = self.tokenizer.decode(generated, skip_special_tokens=True)

        return {
            "choices": [
                {"message": {"content": text_output, "role": "assistant"}}
            ]
        }

app = VLLMDeployment.bind()