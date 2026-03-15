
import outlines
from llama_cpp import Llama

MODEL_PATH = "./models/qwen2.5-coder-14b-instruct-q4_k_m.gguf"

llm = Llama(
    model_path=MODEL_PATH,
    n_gpu_layers=-1, 
    n_ctx=4096,
    verbose=False
)
model = outlines.from_llamacpp(llm)
