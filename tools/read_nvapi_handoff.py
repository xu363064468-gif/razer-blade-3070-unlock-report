"""Read-only, narrow NVAPI RegisterOp probe. No driver install, no writes."""
import ctypes as c,json,datetime
from pathlib import Path
dll=c.WinDLL(str(Path('C:/Windows/System32/nvapi64.dll')))
query=dll.nvapi_QueryInterface;query.argtypes=[c.c_uint32];query.restype=c.c_void_p
def fn(ident,*args):
 p=query(ident)
 if not p:raise RuntimeError(f'NVAPI function unavailable {ident:x}')
 return c.WINFUNCTYPE(c.c_int,*args)(p)
class Op(c.Structure):
 _fields_=[('flags',c.c_uint16),('status',c.c_uint16),('offset',c.c_uint32),('mask',c.c_uint64),('value',c.c_uint64)]
class Packet(c.Structure):
 _fields_=[('version',c.c_uint32),('count',c.c_uint32),('ops',Op*256)]
assert c.sizeof(Op)==24 and c.sizeof(Packet)==6152
assert fn(0x0150E828)()==0,'NVAPI initialization failed'
handles=(c.c_void_p*64)();count=c.c_uint32()
assert fn(0xE5AC921F,c.POINTER(c.c_void_p),c.POINTER(c.c_uint32))(handles,c.byref(count))==0
reader=fn(0x2EB3C140,c.c_void_p,c.POINTER(Packet))
rows=[]
for i in range(count.value):
 for label,offset in [('PMC_BOOT_0',0),('FEAT_PLM',0x823804),('READOUT_1',0x823818),('SS0',0x82381c),('SS1',0x823820),('WPR2_HI',0x1fa828)]:
  packet=Packet();packet.version=6152|(1<<16);packet.count=1
  packet.ops[0].flags=0x15 # READ | 32BIT | GLOBAL; no write flags or masks
  packet.ops[0].offset=offset
  rc=reader(handles[i],c.byref(packet))
  row=dict(gpu=i,label=label,offset=hex(offset),rc=rc,status=packet.ops[0].status,value=hex(packet.ops[0].value))
  rows.append(row);print(row,flush=True)
output=dict(at=datetime.datetime.now().astimezone().isoformat(),read_only=True,gpu_count=count.value,registers=rows)
target=Path('outputs/RTX3070-Benchmark')/('nvapi-handoff-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')
target.write_text(json.dumps(output,indent=2),encoding='utf-8')
print(target)
