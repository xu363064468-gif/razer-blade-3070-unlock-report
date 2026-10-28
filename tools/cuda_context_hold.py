"""Temporary, bounded CUDA primary-context holder. No clocks/register writes."""
from pathlib import Path
import ctypes,json,os,time,datetime,sys
root=Path(__file__).resolve().parent
stop=root/'cuda-hold.stop'; log=root/'cuda-hold-status.json'
cuda=ctypes.WinDLL('nvcuda.dll')
def bind(name,args):
 f=getattr(cuda,name);f.argtypes=args;f.restype=ctypes.c_int;return f
init=bind('cuInit',[ctypes.c_uint]);get=bind('cuDeviceGet',[ctypes.POINTER(ctypes.c_int),ctypes.c_int])
retain=bind('cuDevicePrimaryCtxRetain',[ctypes.POINTER(ctypes.c_void_p),ctypes.c_int])
release=bind('cuDevicePrimaryCtxRelease_v2',[ctypes.c_int]);setctx=bind('cuCtxSetCurrent',[ctypes.c_void_p])
name=bind('cuDeviceGetName',[ctypes.c_void_p,ctypes.c_int,ctypes.c_int])
def check(code,label):
 if code:raise RuntimeError(f'{label}: CUDA error {code}')
def status(state,**kw):
 payload=dict(pid=os.getpid(),state=state,at=datetime.datetime.now().astimezone().isoformat(),**kw)
 temp=log.with_suffix('.tmp');temp.write_text(json.dumps(payload,indent=2),encoding='utf-8');temp.replace(log)
held=False;device=ctypes.c_int();ctx=ctypes.c_void_p()
try:
 check(init(0),'cuInit');check(get(ctypes.byref(device),0),'device')
 buf=ctypes.create_string_buffer(256);check(name(buf,256,device),'name')
 if b'RTX 3070 Laptop' not in buf.value:raise RuntimeError('Unexpected GPU')
 check(retain(ctypes.byref(ctx),device),'retain');held=True
 check(setctx(ctx),'set current')
 status('holding',gpu=buf.value.decode(),max_minutes=20)
 deadline=time.monotonic()+1200
 while time.monotonic()<deadline and not stop.exists():time.sleep(1)
 check(setctx(None),'clear current');check(release(device),'release');held=False
 status('stopped',reason='stop file' if stop.exists() else '20-minute timeout')
except Exception as e:
 status('failed',error=str(e));raise
finally:
 if held:
  setctx(None);release(device)
