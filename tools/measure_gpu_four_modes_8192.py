from pathlib import Path
import importlib.util,inspect,subprocess,json,statistics,hashlib,datetime,sys
root=Path.cwd(); script=root/'work/rtx30-unlock-windows-toolkit/tools/bench/fp16_gemm_bench.py'
spec=importlib.util.spec_from_file_location('bench',script);b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
lib=root/'work/bench-runtime-flat';folder,cudart,cublas=b.find_dlls(str(lib))
source=inspect.getsource(b.run)
# Values taken from NVIDIA's installed cuBLAS header, not inferred thresholds.
modes={'FP16':(2,2,68,16,99,b'\x00\x3c'),
       'BF16':(14,2,68,16,99,b'\x80\x3f'),
       'TF32':(0,4,77,16,99,b'\x00\x00\x80\x3f'),
       'FP32':(0,4,69,2,-1,b'\x00\x00\x80\x3f')}
def runner(settings):
 dtype,width,compute,math,algo,pattern=settings
 s=source.replace('CUDA_R_16F = 2',f'CUDA_R_16F = {dtype}').replace('CUBLAS_COMPUTE_32F = 68',f'CUBLAS_COMPUTE_32F = {compute}').replace('CUBLAS_GEMM_DEFAULT_TENSOR_OP = 99',f'CUBLAS_GEMM_DEFAULT_TENSOR_OP = {algo}')
 s=s.replace('size * size * 2',f'size * size * {width}').replace('cublas.cublasSetMathMode(handle, 1)',f'check(cublas.cublasSetMathMode(handle, {math}), "math mode")')
 s=s.replace('    a = ctypes.c_void_p()', '    cudart.cudaMemcpy.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]\n    a = ctypes.c_void_p()')
 start=s.index('        check(cudart.cudaMemset(a,')
 end=s.index('        check(cudart.cudaMemset(c,',start)
 s=s[:start]+f'''        host = ctypes.create_string_buffer({pattern!r} * (size * size))
        check(cudart.cudaMemcpy(a, host, size*size*{width}, 1), "copy A")
        check(cudart.cudaMemcpy(b, host, size*size*{width}, 1), "copy B")
        del host
'''+s[end:]
 s=s.replace('        return {','''        first = ctypes.c_float()
        check(cudart.cudaMemcpy(ctypes.byref(first), c, 4, 2), "sample output")
        if first.value != float(size):
            raise RuntimeError(f"GEMM output sample mismatch: {first.value} != {size}")
        return {
            "sample_output": first.value,
''')
 ns=b.__dict__.copy();exec(compile(s,'<four-mode-cuBLAS>','exec'),ns)
 return ns['run']
def state():return subprocess.check_output(['nvidia-smi','--query-gpu=name,driver_version,pstate,temperature.gpu,power.draw,clocks.sm,memory.used','--format=csv'],text=True).strip()
phase=sys.argv[1] if len(sys.argv)>1 else 'before'
out=root/'outputs/RTX3070-Benchmark';out.mkdir(exist_ok=True)
target=out/(phase+'-four-modes.json')
if target.exists():raise RuntimeError('Refusing to replace existing measurements')
results={name:[] for name in modes}
for repeat in range(3):
 for name,settings in modes.items():
  before=state();v=runner(settings)(folder,cudart,cublas,8192,40,10);after=state()
  results[name].append(dict(run=repeat+1,**v,before=before,after=after))
  print(name,repeat+1,round(v['tflops'],2),'TFLOPS; output',v['sample_output'],flush=True)
payload=dict(phase=phase,captured_at=datetime.datetime.now().astimezone().isoformat(),size=8192,iters=40,warmup=10,
 method='cuBLAS GEMM FP16/BF16 FP32 accumulation with reduced-precision reduction disabled; TF32 FAST_TF32; FP32 PEDANTIC',
 input='All elements=1; first output checked against 8192, not a full matrix validation',
 benchmark_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),upstream_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),
 libraries={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in lib.glob('*.dll')},samples=results,
 median_tflops={k:statistics.median(x['tflops'] for x in v) for k,v in results.items()})
with target.open('x',encoding='utf-8') as f:json.dump(payload,f,ensure_ascii=False,indent=2)
print('MEDIANS:',payload['median_tflops'],flush=True)
text='| 项目 | 解锁前中位数 TFLOPS |\n|---|---:|\n'+''.join(f'| {k} | {v:.2f} |\n' for k,v in payload['median_tflops'].items())
(out/(phase+'-four-modes.md')).write_text(text,encoding='utf-8-sig')
if phase=='after':
 old=json.loads((out/'before-four-modes.json').read_text())
 assert old['benchmark_sha256']==payload['benchmark_sha256'] and old['libraries']==payload['libraries'], 'Different benchmark/library versions'
 print('GAINS %:',{k:round((v/old['median_tflops'][k]-1)*100,1) for k,v in payload['median_tflops'].items()})

