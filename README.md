# Razer Blade 15 / RTX 3070 Laptop：混合模式失效，独显直连后解锁生效

**本机实测：UEFI 内成功不代表 Windows 中仍然有效。混合模式下进入 Windows 后权限与速率值回到原状态；切换 Dedicated GPU Only 后，相同原版启动程序的解锁状态保留，FP16/BF16/TF32 实测提高约 50%。**

This is a single-machine compatibility report, not a new unlocker or a universal fix. On this Razer Blade, the EFI unlock survived into Windows only after switching to Dedicated GPU Only. Both register readback and throughput were checked.

## 硬件与程序来源

| 项目 | 本机配置 |
|---|---|
| 笔记本 | Razer Blade 15 Base Early 2021，RZ09-0369 |
| 屏幕 | 内置 QHD 2560×1440，165 Hz 配置 |
| BIOS | 1.00 |
| GPU | RTX 3070 Laptop，GA104M，8 GiB |
| PCI / Subsystem | 10DE:249D / 1A58:2012，0000:01:00.0 |
| PMC_BOOT_0 | 0xb74000a1 |
| VBIOS | 94.04.40.00.18，未刷写 |
| NVIDIA 驱动 | 617.42 |
| 最终使用程序 | physicsdolphin/nv-uefi-unlocker v2.1.0，作者原版预编译 EFI |
| 对应源码 | e629c5ed4e5fb00f1d07b75badad5aca1ad33f46 |
| EFI SHA-256 | b5e96f4e0ca162b98693af00452a6933ea47dd7e24f0d4b3c804b48a05ec9dea |

最终成功的 EFI **没有本地修改**。本地工作是生成并核验 ga102 家族配套资产、布置独立 FAT32 U盘、限定目标 BDF、增加入口 D0 标记，以及采集日志和测量。早期 craftingmod 适配包有本地修改，不能与最终原版程序混为一谈。本报告不打包 EFI、NVIDIA 固件、VBIOS/PROM、内核驱动或 CUDA DLL。

## 从失败到成功

1. 最初基于 [craftingmod/rtx30-unlock](https://github.com/craftingmod/rtx30-unlock) 做本机 Probe。混合模式下显卡 PCI Command=0，需临时启用 MEMORY 解码后才能读取完整 PROM。探测与恢复记录完成。
2. 旧适配包先试保留 SS1，后试同时写 SS0=88888888、SS1=8；还试过登录后保持 CUDA context。UEFI 读回成功，Windows 性能仍接近原始水平。最初一次 PCI 配置恢复校验因 FLR 清除了既存 W1C 错误状态位而停止，后续修正严格比较范围；该阶段不能声称性能解锁成功。
3. 改用 [nv-uefi-unlocker v2.1.0](https://github.com/physicsdolphin/nv-uefi-unlocker/releases/tag/v2.1.0) 作者原版。资产用作者 maker 的 ga102 路线从固定输入生成并校验。Windows 重启 → USB → 空格确认 → 原程序直接链到 Windows Boot Manager。仍在混合模式，仍无收益。
4. 通过 NVIDIA 已安装驱动的管理员 NVAPI RegisterOp，只读六个已知寄存器，终于确认：Windows 内权限和值确实锁回。没有加载 ssdiag 附带的 PMXDRV 驱动。
5. BIOS 切换 **Dedicated GPU Only**，保存后重新从同一U盘执行。Windows 确认内屏由 NVIDIA 驱动，Intel 不再是显示输出设备；此时权限和值保留，三轮测试出现明确收益。

未修改 Windows 内部 EFI 分区、BootOrder、VBIOS、电压或功耗上限。用户手动重启并在 EFI 界面确认。Secure Boot 在试验时关闭。独立 USB，不是内部 ESP 安装。

## 关键证据：同一个原版 EFI，两个显示模式

| 寄存器 | UEFI 交接前（两次） | 混合模式 Windows | 独显直连 Windows |
|---|---|---|---|
| FEAT_PLM | ffffffff | ffffff8f（重新关闭） | ffffffff |
| SS0 | 88888888 | 45220023 | 88888888 |
| SS1 | 8 | 7 | 8 |
| FEAT_READOUT_1 | 0 | 00400080（受限） | 0（全速读回） |

Windows 读回原始 JSON 在 evidence/benchmarks/nvapi-handoff-*.json。031631 是非管理员失败记录（rc=-1，**不能把其中零值当成真实读数**）；031702 是混合模式管理员读回；033619 是独显直连管理员读回。UEFI 完整文本日志在 evidence/uefi/。

## 性能结果

TFLOPS，每项三次中位数；同一个脚本、cuBLAS/CUDA DLL 哈希一致。

| 模式 | 最初混合模式基线 | 原版 EFI + 混合模式 | 原版 EFI + 独显直连 | 相对最初变化 |
|---|---:|---:|---:|---:|
| FP16，FP32累加 | 32.43 | 32.67 | 48.47 | +49.5% |
| BF16，FP32累加 | 33.17 | 33.46 | 50.43 | +52.0% |
| TF32 | 16.71 | 16.84 | 25.35 | +51.7% |
| FP32 SIMT 对照 | 7.70 | 7.90 | 7.59 | -1.4% |

方法：4096×4096 GEMM，30次 warmup，300次计时，CUDA events，三个交错轮次；FP16/BF16 禁用低精度 reduction；TF32 使用 FAST_TF32；FP32 PEDANTIC。A/B 全1，只检查输出首个元素=4096，**不是完整矩阵数值验证**。8192 补测另外留档，不与4096混算。

限制：没有“独显直连、未解锁”的同显示模式基线，所以表中约50%是相对此前整体状态的变化，不能严谨地全部独立归因于解锁。温度/时钟是前后快照而非连续轨迹。没有长期稳定性、睡眠恢复、游戏或实际AI工作流测试。

## 到底是什么原因

**已证实：本机混合模式中，EFI交接后的解锁状态丢失；独显直连试验中保留。** 不是只看日志或体感下结论。

作者文档把“FEAT_PLM 也重新锁住，SS与READOUT回到受限值”列为供电域掉电/D3cold 的指纹。我们的读数符合这一候选机制，但没有直接捕获电源切换或复位事件，不能声称已证明究竟是 EC、runtime D3、固件还是驱动哪一步触发。没有发现 Code 43；不能以此完全排除恢复路径。

独显直连是本机有效的规避方案，**不是所有混合显卡笔记本都无法解锁**，也不能保证所有雷蛇同型号有效。

## 复现与文件边界

本仓库是证据与方法，不提供即插即用固件包。启动包请从原项目获取，按目标 GPU 家族生成并校验资产。使用原版 v2.1.0 时 EFI 在 EFI/BOOT/BOOTX64.EFI，7个 ga102 所需资产在盘根；tx-select-bdf.txt 为 0000:01:00.0，tx-require-d0.txt 存在，无自动运行标记。不要把本机 BDF 当成其他电脑的通用配置。

复跑测量：在仓库根运行 tools/measure_gpu_four_modes.py <唯一阶段名>，需要自行准备匹配的 CUDA runtime/cuBLAS DLL 到 work/bench-runtime-flat/；DLL 不随仓库分发。原始证据中的哈希对应当时脚本，公开整理后路径可能不同。tools/read_nvapi_handoff.py 需管理员，固定只读6个偏移，无写入和内核驱动安装；NVAPI接口非公开保证，不保证其他驱动可用。代码运行必须由设备所有者自行评估。

原始记录已去除本地账户路径和 USB 序列号，保留测量时间、硬件型号与寄存器信息。原始未脱敏版本在本机保留。主机物理地址仅是当时日志，不能拿去其他启动会话直接访问。

## 参考与致谢

- [physicsdolphin/nv-uefi-unlocker](https://github.com/physicsdolphin/nv-uefi-unlocker) — 最终使用程序与诊断思路。
- [warm/resume 与交接失效判别](https://github.com/physicsdolphin/nv-uefi-unlocker/blob/main/docs/warm-resume-entry.md)
- [同ID 3070 Laptop 成功案例 #28](https://github.com/physicsdolphin/nv-uefi-unlocker/issues/28)、[混合输出无收益案例 #6](https://github.com/physicsdolphin/nv-uefi-unlocker/issues/6)
- [craftingmod/rtx30-unlock](https://github.com/craftingmod/rtx30-unlock)、[Siselea/rtx30-unlock-windows-toolkit](https://github.com/Siselea/rtx30-unlock-windows-toolkit)、[Zagitta/gpu-unlock](https://github.com/Zagitta/gpu-unlock)
- [Skyworks-Neo/nvoc](https://github.com/Skyworks-Neo/nvoc) — NVAPI RegisterOp布局参考。

试验由设备所有者手动执行 BIOS/UEFI 操作，准备、诊断和报告整理有 AI 协助。不是新漏洞或独立原创解锁实现。
