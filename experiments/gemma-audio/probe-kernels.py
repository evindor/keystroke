#!/usr/bin/env python3
"""Exercise Triton compilation and the actual vLLM INT4 XPU matrix kernel."""
import json
import torch
import triton
import triton.language as tl
from vllm.platforms import current_platform


@triton.jit
def add_one(source, target, BLOCK: tl.constexpr):
    offsets = tl.arange(0, BLOCK)
    tl.store(target + offsets, tl.load(source + offsets) + 1)


current_platform.import_kernels()
source = torch.arange(128, device='xpu', dtype=torch.float32)
target = torch.empty_like(source)
add_one[(1,)](source, target, 128)
torch.testing.assert_close(target, source + 1)
print(json.dumps({'triton_add': 'passed'}), flush=True)

# Every packed nibble is 1; symmetric zero point 8 -> weight -7.
packed = torch.full((16, 128), 0x11111111, device='xpu', dtype=torch.int32)
packed = packed.t().contiguous().t()
scales = torch.ones((1, 128), device='xpu', dtype=torch.bfloat16)
zeros = torch.tensor([8], device='xpu', dtype=torch.int8)
inputs = torch.ones((1, 128), device='xpu', dtype=torch.bfloat16)
output = torch.ops._xpu_C.int4_gemm_w4a16(inputs, packed, None, scales, zeros, 128, None)
torch.testing.assert_close(output, torch.full_like(output, -7 * 128))
print(json.dumps({'int4_w4a16': 'passed', 'output': float(output[0, 0])}), flush=True)
