from benchmark.pytorch.gemm import run_gemm

import torch
import time
import json
import gc
from tqdm import tqdm

from transformers import AutoModelForCausalLM, AutoTokenizer

import logging

logger = logging.getLogger(__name__)


def main():
    benchmark_forward()


def benchmark_forward():
    logger.info("Running Forward benchmark")
    results = run_forward_benchmark()

    save_results(results)


def run_forward_benchmark():

    models = select_appropriate_models_for_this_machine()

    warmup(
        model_name=models[0][0],
        batch_size=models[0][1],
        input_tokens=models[0][2],
        output_tokens=models[0][3],
    )

    results = {}

    for model_name, batch_size, input_tokens, output_tokens in tqdm(models):
        result = run_forward(
            model_name=model_name,
            batch_size=batch_size,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        if model_name not in results:
            results[model_name] = result
        else:
            results[model_name].update(result)

    return results


def warmup(model_name, batch_size, input_tokens, output_tokens):
    run_forward(
        model_name=model_name,
        batch_size=batch_size,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def run_forward(model_name, batch_size, input_tokens, output_tokens):

    model = AutoModelForCausalLM.from_pretrained(model_name)

    model.to(torch.bfloat16)
    model.to(get_device())

    # Input tokens are randomly generated ints between 0 and the model's vocab size
    input_ids = torch.randint(
        low=0, high=model.config.vocab_size, size=(batch_size, input_tokens),
        device=get_device()
    )

    # Run the forward pass
    start = time.time()
    iterations = 0
    with torch.no_grad():
        while time.time() - start < 3:
            outputs = model.generate(input_ids, max_length=input_tokens + output_tokens)
            iterations += 1
    end = time.time()

    iteration_time = (end - start) / iterations

    flop_count = calculate_flop_count(model, batch_size, input_tokens, output_tokens)
    byte_count = calculate_byte_count(model, batch_size, input_tokens, output_tokens)

    logger.info(f"Deleting model {model_name}")
    del model
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return {
        input_tokens: {
            output_tokens: {
                batch_size: {
                    "time": iteration_time,
                    "GFLOP/s": flop_count / iteration_time / 1e9,
                    "flop/s": flop_count / iteration_time,
                    "flop_count": flop_count,
                    "byte_count": byte_count,
                    "operational_intensity": flop_count / byte_count,
                    "batch_size": batch_size,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                }
            }
        }
    }


def calculate_flop_count(model, batch_size, input_tokens, output_tokens):
    # parameter count
    param_count = sum(p.numel() for p in model.parameters())

    # GEMM flops
    gemm_flops = 2 * batch_size * (input_tokens + output_tokens) * param_count

    return gemm_flops


def calculate_byte_count(model, batch_size, input_tokens, output_tokens):
    # parameter count
    param_count = sum(p.numel() for p in model.parameters())

    # Get the number of bytes in the model
    model_byte_count = param_count * 2  # 2 bytes per bfloat16

    # Input and output byte count
    input_byte_count = batch_size * input_tokens * 4  # 4 bytes per int32
    output_byte_count = batch_size * output_tokens * 4  # 4 bytes per int32

    return input_byte_count + output_byte_count + model_byte_count

def get_device():
    if torch.cuda.is_available():
        return torch.device("cuda")
    else:
        return torch.device("cpu")


def save_results(results):
    # Save results to a json file
    path = "/app/cray/data/benchmark_forward.json"

    with open(path, "w") as f:
        json.dump(results, f)


def select_appropriate_models_for_this_machine():
    # Run a GEMM operation to determine the peak GEMM flops of the machine
    # This will be used to determine which models to run the benchmark on

    gemm_flops = calculate_gemm_flops()

    # Machines with over 1TFLOP/s peak GEMM performance can run the llama models
    # Over 10 TFLOP/s can run the 70B model

    logger.info(f"Peak GEMM performance: {gemm_flops / 1e12} TFLOP/s")

    if gemm_flops > 10e12:
        return benchmark_model_list
    elif gemm_flops > 1e12:
        return benchmark_model_list[:-1]
    else:
        return benchmark_model_list[:1]


def calculate_gemm_flops():
    m, n, k = 256, 256, 2048

    metrics = run_gemm((m, n, k))

    return metrics["flop/s"]

benchmark_model_list = [
    ["masint/tiny-random-llama", 1, 128, 16],
    ["meta-llama/Llama-3.2-1B-Instruct", 1, 128, 16],
    ["meta-llama/Llama-3.1-8B-Instruct", 1, 128, 16],
    ["meta-llama/Llama-3.3-70B-Instruct", 1, 128, 16],
]
