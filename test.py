import torch
from torch.utils._pytree import tree_map_only
from torch.utils._python_dispatch import TorchDispatchMode
from torch._subclasses.fake_tensor import FakeTensorMode
from torch.utils.weak import WeakIdKeyDictionary
import weakref
import math
import torchvision

# Track all the memory being used by Tensors.
# Only max is tracked but others can be added.
MEMORY_USE = WeakIdKeyDictionary()
MEMORY_MAX = 0
MEMORY_ID = 0

def update_stats():
    global MEMORY_MAX
    curr_use = 0
    for k, v in MEMORY_USE.items():
        curr_use += math.ceil(k.size() * k.element_size()/512) * 512

    if MEMORY_MAX < curr_use:
        MEMORY_MAX = curr_use

# Should be called on every Tensor created
def track(t:torch.Tensor):
    def cb(_):
        update_stats()
    st = t.untyped_storage()
    wt = weakref.ref(st, cb)
    MEMORY_USE[st] = wt
    update_stats()

# Use this Mode to call track on every Tensor being created by functions
class MemoryTrackingMode(TorchDispatchMode):
    def __torch_dispatch__(self, func, types, args, kwargs=None):
        res = func(*args, **kwargs or {})

        tree_map_only(torch.Tensor, track, res)
        return res


if __name__ == "__main__":
    # Use FakeTensorMode to run the code without any actual data
    fake_mode = FakeTensorMode()
    torch.set_default_device("cuda")
    torch.cuda.reset_peak_memory_stats()
    with fake_mode, MemoryTrackingMode():
        model = torchvision.models.resnet18()
        optim = torch.optim.Adam(model.parameters())
        input = torch.randn(256, 3, 224, 224)
        output = model(input)
        output.sum().backward()
        optim.step()
        optim.zero_grad()
        print(MEMORY_MAX)
    print(torch.cuda.max_memory_allocated())
    print(torch.cuda.max_memory_reserved())
