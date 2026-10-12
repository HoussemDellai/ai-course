"""Run inside the ACA GPU replica; fails if CUDA 13 A100 operations do not work."""

import json
import platform
import subprocess

import torch
import torch.nn.functional as functional


def main():
    print(subprocess.check_output(["nvidia-smi"], text=True), flush=True)
    if not torch.version.cuda or not torch.version.cuda.startswith("13."):
        raise RuntimeError(f"Expected CUDA 13.x, received {torch.version.cuda}")
    if not torch.cuda.is_available() or "A100" not in torch.cuda.get_device_name(0):
        raise RuntimeError(
            f"Expected an available A100 CUDA device; available={torch.cuda.is_available()}, "
            f"count={torch.cuda.device_count()}"
        )
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError("BF16 is not supported")
    matrix = torch.ones((128, 128), device="cuda", dtype=torch.bfloat16)
    product = matrix @ matrix
    query = torch.ones((1, 2, 64, 64), device="cuda", dtype=torch.bfloat16)
    attention = functional.scaled_dot_product_attention(query, query, query)
    torch.cuda.synchronize()
    if not torch.all(product == 128).item() or not torch.allclose(attention, query):
        raise RuntimeError("CUDA matrix/attention result validation failed")
    print(json.dumps({
        "python": platform.python_version(),
        "pytorch": torch.__version__,
        "cuda_runtime": torch.version.cuda,
        "device": torch.cuda.get_device_name(0),
        "capability": torch.cuda.get_device_capability(0),
        "bf16_matrix_and_attention": "PASS",
        "nvidia_smi": subprocess.check_output(["nvidia-smi"], text=True),
        "comfyui_commit": subprocess.check_output(
            ["git", "-C", "/root/ComfyUI", "rev-parse", "HEAD"], text=True
        ).strip(),
    }, indent=2), flush=True)


if __name__ == "__main__":
    main()
