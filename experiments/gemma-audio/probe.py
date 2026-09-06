#!/usr/bin/env python3
"""Print hardware/runtime evidence without loading model weights."""
import ctypes, importlib.util, json, platform
from pathlib import Path

result={'python':platform.python_version(),'render_nodes':[str(p) for p in Path('/dev/dri').glob('renderD*')]}
try:
    ze=ctypes.CDLL('libze_loader.so.1')
    result['level_zero_init']=hex(ze.zeInit(1)&0xffffffff)
except OSError as error: result['level_zero_error']=str(error)
if importlib.util.find_spec('torch'):
    import torch
    result['torch']=torch.__version__
    result['xpu_available']=torch.xpu.is_available()
    if result['xpu_available']:
        result['xpu_device']=torch.xpu.get_device_name(0)
        # A tiny operation verifies kernels, not just enumeration.
        result['xpu_compute']=float((torch.ones(8,device='xpu')*2).sum().cpu())
if importlib.util.find_spec('vllm'):
    import vllm
    from vllm.platforms import current_platform
    result['vllm']=vllm.__version__
    result['vllm_device']=current_platform.device_type
print(json.dumps(result,indent=2))
