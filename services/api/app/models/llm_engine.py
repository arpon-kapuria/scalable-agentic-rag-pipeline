"""
This file deploys an LLM inference service using Ray Serve and vLLM.
It loads a large language model on a GPU and exposes it as an HTTP API endpoint that receives chat messages and returns generated responses.
"""

from ray import serve
import os
from services.api.app.models.llm_engine import EngineArgs, AsyncLLMEngine, SamplingParams
from transformers import AutoTokenizer


@serve.deployment(autoscaling_config={"min_replicas": 1, "max_replicas": 10}, ray_actor_operations={"num_gpus": 1})
class VLLMDeployment:
    def __init__ (self):
        model_id = os.getenv("MODEL_ID", "meta-llama/Llama-3-70b-Instruct")

        # 1. Load Tokenizer for correct chat formatting
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)

        # 2. Configuration for how the model should run
        args = EngineArgs(
            model=model_id,
            quantization="awq",
            gpu_memory_utilization=0.90,
            max_model_len=8192
        )

        # 3. Launch the vLLM inference engine
        self.engine = AsyncLLMEngine(args)

    async def __call__(self, request):
        body = await request.json()
        messages = body.get("messages", [])

        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        sampling_params = SamplingParams(
            temperature=body.get("temperature", 0.7),
            max_tokens=body.get("max_tokens", 1024),
            # Stop tokens are often handled by the tokenizer config, but safe to keep
            stop_token_ids=[self.tokenizer.eos_token_id, self.tokenizer.convert_tokens_to_ids("<|eot_id|>")]
        )

        request_id = str(os.urandom(8).hex())
        results_generator = self.engine.generate(prompt, sampling_params, request_id)

        final_output = None
        async for request_output in results_generator:
            final_output = request_output

        text_output = final_output.outputs[0].text
        return {
            "choices": [
                {"message": {"content": text_output, "role": "assistant"}}
            ]
        }

app = VLLMDeployment.bind()
