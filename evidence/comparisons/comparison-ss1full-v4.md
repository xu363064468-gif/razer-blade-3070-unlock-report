# SS1=8 实机对比

UEFI RUN04：SS0=88888888，SS1=8；FINAL status=0 clean=1；MEMORY_RESTORE status=0 touched=0。
Windows 四项测试完成，CUDA 保持程序已退出，一次性启动项已删除。

|项目|原始 TFLOPS|本次 TFLOPS|变化|
|---|---:|---:|---:|
|FP16|32.43|30.47|-6.1%|
|BF16|33.17|32.59|-1.7%|
|TF32|16.71|16.75|+0.2%|
|FP32|7.70|7.83|+1.7%|

测试脚本哈希一致：True
结论：UEFI 阶段写入成功，但 Windows 端没有可验证的算力提升。尚未读取 Windows 运行时选择器，不能确定是否被驱动初始化或电源管理复位。
