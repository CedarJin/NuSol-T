# NuSol-T 项目进度摘要

> 2026年7月4日

## 当前状态

已完成 **Stage 1（FNDDS 验证）全部开发**，即规划书中 Phase 0-4。项目进入了可运行、可验证的状态。

## 已完成的工作

### 1. 计算框架搭建

按照规划书设计的模块化架构，完成了 9 个核心模块、~10,700 行代码：

- **数据层**：FNDDS、SR Legacy、Branded Food 三个 USDA 数据库的适配器，支持三级配料映射（代码直查 → 自闭环 → 模糊匹配），覆盖率 99.8%
- **营养计算**：Forward model（配料比例 × 营养矩阵 → 预测营养素）、FDA 四舍五入规则、labelized simulation
- **约束系统**：5 级优先级约束（质量守恒、配料顺序、≤2%规则、标签区间拟合、能量闭合、类别先验）
- **求解器**：PointSolver（最优点估计）、BoundSolver（可行区间）、EnsembleSolver（bootstrap 不确定性）
- **报告系统**：TrustReport + A/B/C/D 可信等级

### 2. 测试覆盖

**202 个测试用例，100% 通过。** 包括单元测试和基于真实 FNDDS/SR Legacy 数据的集成测试。

### 3. 验证数据准备

FNDDS（2021-2023）共 5,432 个食品，其中 **3,829 个** 含 ≥2 个配料的 recipe 可直接用于验证。SR Legacy（2018）7,793 条配料营养数据已全部索引。

## 待完成

| 阶段 | 内容 |
|------|------|
| Phase 5-6 | 将框架应用到 USDA Branded Food Database（真实包装食品标签） |
| 端到端验证 | 在 FNDDS 上跑完整 forward → inverse → labelized 流程，产出 benchmark 数据 |
| 论文 | 基于验证结果撰写方法论文 |

## 技术细节

Python 3.12 + uv 包管理 + src layout 标准结构。`uv run pytest` 即可运行全部测试。
