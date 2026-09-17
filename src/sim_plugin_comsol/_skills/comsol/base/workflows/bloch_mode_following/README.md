# COMSOL 6.4 三维 Bloch 参数扫描与 Mode Following 基础模型

该目录保存一个与具体器件无关的 COMSOL 案例：

```text
COMSOL64_3D_Bloch_ModeFollowing_Base.mph
```

模型只有五段基础结构：底部 PML、基底、结构占位层、上方介质、顶部
PML。它用于复用参数、Floquet 周期边界、参数化扫描和 Mode Following 设置，
不能当作任何 VCSEL/PCSEL 器件结果。

## 模型中实际存在的扫描入口

在模型开发器中展开：

```text
Study > Visible k Parametric Sweep with COMSOL 6.4 Mode Following
  Parametric Sweep: k sweep: -0.1 to 0.1
  Eigenfrequency
```

`Parametric Sweep` 直接扫描：

```text
k = range(-0.1,0.025,0.1)
```

全局参数默认 `use_k_scan=1`，所以直接运行该 Study 时，`k` 会通过
`qx_scan/qy_scan` 生成 `kBx,kBy`。`path_mode=0` 是 `q=(k,0)`；改为
`path_mode=1` 后，可把 k 列表改成 `range(0,step,3)`，得到
Gamma-X-M-Gamma。

研究步骤和 Eigenvalue 求解器都启用了 Mode Following。求解器下只有
`ModeFollowing` 属性，没有再叠加 `EigenvalueParam`，因此 k 只有一个扫描
所有者。该布局与 COMSOL 6.4 自带的 Wave Optics
`bandgap_photonic_crystal` 示例一致。

## 手工单点

另一个 Study 用于手工单点。使用前设置：

```text
use_k_scan = 0
qx = ...
qy = ...
```

## 重建与验证

`BuildBlochModeFollowingBase.java` 只运行几何和网格构建，不运行 Study 或
Solver。`VerifyBlochModeFollowingBase.java` 在新 COMSOL 进程中重新打开 MPH，
检查 Study Parametric Sweep、Mode Following、Floquet 周期边界、PML、网格以及
空 solution/result 状态。`VerifyBlochModeFollowingGammaSolve.java` 另行在内存
运行手工 Γ 点真实矩阵组装和 20 模本征求解，但不把解保存回基础 MPH。

`pcx/pcy` 直接持有 source/destination 边界，不建立额外 `pairx/pairy`
Identity Pair。COMSOL EWFD 默认 `dcont1` 会消费这类 pair；R3 实例已经复现
它会导致“源和目标网格不兼容”，因此不能把未使用 pair 当作被动审计元数据。

2026-09-17 的 Γ 点回归输出 `BASE_GAMMA=PASS`，总用时约 13 s，COMSOL
报告峰值物理/虚拟内存 1.13/1.23 GB。

该基础模型是设置案例，不证明候选模数量、网格、PML 或物理模式身份已经
收敛。正式器件模型仍需单独审查。
