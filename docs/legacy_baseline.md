# Legacy Baseline

> 记录日期：2026-07-05  
> 用途：重构 Phase 0 — 锁定重构前行为，供后续 parity 测试对照  
> 此文件记录的基准数据不用于科学正确性验证

---

## Git 状态

| 项目 | 值 |
|------|-----|
| 分支 | `refactor/yaml-solver-framework` |
| Commit | `5579811` (docs: add YAML framework development plan) |
| 工作区 | 干净 |

## 测试状态

| 指标 | 值 |
|------|-----|
| 测试总数 | 208 |
| 通过 | 208 |
| 失败 | 0 |
| 运行时间 | 13.53s |

## 代码规模

| 指标 | 值 |
|------|-----|
| Python 源文件 | 48 |
| 测试文件 | 21 |
| 包版本 | 0.1.0 |

## 关键模块版本（重构后将被替换）

| 模块 | 当前实现 | 首行 |
|------|---------|------|
| QPSolver | SLSQP + 硬编码 3 类约束 | `src/nusol/solver/qp_solver.py:28` |
| BoundSolver | LP (HiGHS) + 硬编码 3 类约束，不可行时返回 `success=True` | `src/nusol/solver/bound_solver.py:22` |
| PointSolver | 已废弃 (deprecated in favor of QPSolver) | `src/nusol/solver/point_solver.py` |
| EnsembleSolver | multi-start + interval bootstrap | `src/nusol/solver/ensemble_solver.py:16` |
| ConfigLoader | YAML load + defaults，无 extends/merge | `src/nusol/config/loader.py:11` |
| ConstraintBuilder | 注册 10 个约束类，但 QPSolver 不使用 | `src/nusol/constraints/base.py:82` |
| ForwardModel | `x @ A` + moisture_factor (公式有 unit bug) | `src/nusol/nutrition/forward.py:20` |
| Metrics | MAE 用交集、coverage 80/95 相同、zero_slack 可为负 | `src/nusol/validation/metrics.py` |
| Ablation | G5=G6=G7 | `src/nusol/validation/ablation.py:13` |
| NutrientRegistry | 脂肪酸 ID 错位 (1292→sat, 正确为 1258) | `src/nusol/core/nutrient_registry.py:25` |
| Units | Vitamin E IU→mg 多乘 0.001 | `src/nusol/core/units.py:25` |
| FNDDS adapter | description 作 dict key，missing 当 0 | `src/nusol/data/fndds.py:129` |
| Branded adapter | basis 判断不可靠，mL 当 g | `src/nusol/data/branded.py:62` |
| CLI | 三个主命令为占位符 | `src/nusol/cli.py:68-101` |

## 已知问题索引

详见 `docs/FIX_PLAN.md`，共 35 项。

## 关于重构

- 本基线记录的重构前行为仅作为回归参考
- 新系统通过 YAML schema、领域模型、约束注册表、solver-neutral IR 和 typed backend 构建
- 当前 benchmark 数字（MAE=0.0731 等）不作为新系统的正确性标准
- Phase 8 在新架构上重跑 benchmark 后，产生新的可复现基线

## Synthetic Fixtures

| Fixture | 文件 | 类型 | 预期结果 |
|---------|------|------|---------|
| feasible_2_ingredient | `tests/fixtures/synthetic/feasible_2_ingredient.json` | 2 配料，唯一解 | QPSolver success, BoundSolver success |
| infeasible_conflict | `tests/fixtures/synthetic/infeasible_conflict.json` | 约束冲突 | QPSolver fails or violates, BoundSolver returns infeasible |
| underdetermined | `tests/fixtures/synthetic/underdetermined_3_ingredient.json` | 3 配料，1 营养约束 | QPSolver success, 宽 feasible bounds |

详见 `tests/fixtures/synthetic/` 目录。
