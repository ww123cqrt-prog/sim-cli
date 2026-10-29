# COMSOL 6.4 三维 Bloch 参数扫描与 Mode Following 基础模型

> **状态：Mode Following 是不稳定的实验性新功能。** 本案例保留它用于观察和
> 学习，不把完整模式追踪作为验收目标，也不继续通过调候选数、步长或阈值强行
> 追求“全部跟踪成功”。逐个 k 点的参数化本征频率结果是主数据；Mode Following
> 曲线只作辅助参考，非有限或停止跟踪的分量必须标为未解析。

该目录保存一个与具体器件无关的 COMSOL 案例：

```text
COMSOL64_3D_Bloch_ModeFollowing_Base.mph
```

模型包含五段纵向基础结构：底部 PML、基底、结构占位层、上方介质、顶部
PML。结构层中央加入了一个 `0.46a × 0.22a`、折射率 1.5 的长方体测试柱，
背景结构层折射率为 3.4。这个有意设置的 x/y 不对称结构只用于证明 X、Y
路径确实不同，不能当作任何 VCSEL/PCSEL 器件结果。为了继续使用稳定的扫掠
网格，一根几何分区柱贯穿五层；只有结构层中的中央分段使用测试柱折射率，
其余分段仍使用各自宿主材料，因此物理不连续只存在于结构层。

## 模型中实际存在的扫描入口

在模型开发器中展开：

```text
Study > EXPERIMENTAL / UNSTABLE: k sweep with COMSOL 6.4 Mode Following
  Parametric Sweep: k sweep: M-Gamma-X/Y-M demonstration
  Eigenfrequency
```

`Parametric Sweep` 默认直接扫描：

```text
k = range(0,0.25,3)
```

全局参数默认 `use_k_scan=1`、`path_mode=2`、`path_axis=0`，所以直接运行
该 Study 时，`k` 会通过 `qx_scan/qy_scan` 生成 `kBx,kBy`：

- `path_axis=0`：`M -> Gamma -> X -> M`；
- `path_axis=1`：`M -> Gamma -> Y -> M`。

两条路径共用同一个有序标量 `k` 和同一组 Floquet 边界。分段定义为：

```text
0 <= k <= 1: M -> Gamma
1 <= k <= 2: Gamma -> X（path_axis=0）或 Gamma -> Y（path_axis=1）
2 <= k <= 3: X/Y -> M
```

`range(0,1,2)` 只有 M、Gamma、X/Y 三个锚点，适合快速检查，不是连续
能带。正式绘制路径应把步长改小，例如 `range(0,0.01,3)`。历史兼容入口仍
保留：`path_mode=0` 是 `q=(k,0)`，`path_mode=1` 是
`Gamma-X-M-Gamma`。

研究步骤和 Eigenvalue 求解器都启用了实验性 Mode Following。求解器下只有
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
检查 Study Parametric Sweep、双路径锚点、Mode Following、Floquet 周期边界、
PML、网格以及空 solution/result 状态。`VerifyBlochModeFollowingGammaSolve.java`
另行在内存运行手工 Γ 点真实矩阵组装和 20 模本征求解。
`VerifyBlochModeFollowingDualPathSolve.java` 分别计算两次 Gamma、X 和 Y；
`VerifyBlochModeFollowingParametricSweep.java` 通过 Study 层运行两条路径各自的
`range(0,1,2)` 三点参数化扫描，并逐一核对 COMSOL 生成的
`ParametricStore`。不能用 `solmf.runAll()` 验证参数扫描：它只计算求解器序列
当前参数点。`VerifyBlochModeFollowingDenseConvergence.java` 另外测量正反向、
20/30 个候选以及基础/细网格的差异。所有验证均不把解保存回基础 MPH。

`pcx/pcy` 直接持有 source/destination 边界，不建立额外 `pairx/pairy`
Identity Pair。COMSOL EWFD 默认 `dcont1` 会消费这类 pair；R3 实例已经复现
它会导致“源和目标网格不兼容”，因此不能把未使用 pair 当作被动审计元数据。

2026-09-18 的验证结果：

- Gamma 点 20 模回归通过，约 15.17 s；
- 两条路径在 Gamma 点的 20 个排序频率集合最大相对差
  `1.69e-14`，符合路径无关性；
- X 与 Y 的排序频率集合最大相对差 `4.539e-3`，证明长方体柱确实打破了
  x/y 互换对称性，也证明第二条 Y 路径没有退化成 X 路径；
- Study 层参数扫描能真实生成每个 k 点的独立结果存储；三点 smoke 会同时报告
  请求模态数与实际有限跟踪模态数；
- 基础网格为 37,594 自由度。13 点、每点请求20模的 X/Y 正扫分别约
  155.89/149.50 s，反扫约147.36/152.82 s；
- 细网格为81,282自由度，7点 X/Y 扫描约214.98/218.63 s；本轮观测峰值
  工作集约3.75 GB，当前机器没有资源压力；
- 数值 readiness 结论为 `PARTIAL`：20模正扫中，除起点外的12个点均有
  Mode Following 分量停止，实际有限跟踪模数最少为1；X正反向13个公共点的
  有限模数全部不同，Y有4个点不同；
- 把候选数从20提高到30后，7个共享点的最近有限频率最大相对变化为
  X `3.164%`、Y `3.214%`；基础网格到细网格为 X/Y 约 `2.048%`。

因此，已经确认的是参数化扫频、双路径映射、Floquet边界和非对称案例能够实际
求解，而且计算成本较低。尚未确认的是完整20条模式身份、候选数收敛、网格收敛
和PML收敛。COMSOL在停止追踪某一分量时会留下非有限本征参数；后处理必须把它
标为未解析，不能让 `NaN` 通过数值门槛。

该基础模型是设置案例，不证明候选模数量、网格、PML、完整路径收敛或物理
模式身份已经收敛。建议把直接参数扫描作为快速局部频谱入口；Mode Following
只作为不稳定的实验性辅助信息，并检查每点有限跟踪模数。无需为了本案例继续
调参追求完整跟踪。正式器件模型仍需单独审查。
