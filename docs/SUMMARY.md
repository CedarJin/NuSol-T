# NuSol-T 项目进度摘要

> 2026-07-15 | 当前状态以 `docs/CURRENT_STATUS.md` 为准

## 当前状态

NuSol-T 已完成 YAML solver framework 的核心重构。当前系统可以用 YAML 声明原料、营养组成、标签观测、约束、solver 和输出要求，并通过统一入口执行原料比例逆向求解。

当前最新结果：

| 项目 | 结果 |
|---|---:|
| Pytest | 259 passed |
| FNDDS benchmark | 197 个多配料配方 |
| Solve 成功 | 189 个 |
| 成功率 | 95.9% |
| 成功样本中位 MAE | 2.53 pp |

## 已完成

1. YAML schema、resolver、validate / resolve / inspect / solve CLI。
2. `IngredientProblem`、`CompositionMatrix`、四态 nutrient missingness 等 domain model。
3. Constraint registry 和 solver-neutral IR。
4. SLSQP point backend 与 HiGHS bounds backend。
5. `solve(yaml_path)` 单一公开求解入口。
6. CSV resource checksum、ingredient 顺序对齐、resolved YAML 和 manifest 记录。
7. FNDDS / SR Legacy / Foundation / Branded 数据适配器基础模块。
8. FNDDS branded-food 条件模拟 benchmark。
9. Level 2 prior 初版与 prior contribution diagnostics。

## 当前能力边界

当前框架已经可以支撑：

- 基础逆向食物原料比例求解；
- YAML 驱动的可复现配置；
- 基础硬约束、软约束和可行边界；
- 在受控 FNDDS 条件下验证求解框架有效性。

当前还不能声称：

- 恢复真实商业配方；
- 已完成真实包装食品端到端应用；
- 已完成校准食品科学先验；
- 已提供 Bayesian credible interval；
- TrustGrade 已具有科学校准意义。

## 下一阶段

优先级最高的是 Branded Food 应用链路：

1. `IngredientParser`：解析真实包装食品 ingredient list。
2. `IngredientMapper`：将标签短名映射到 USDA 标准原料记录。
3. Prior calibration / ablation / sensitivity：验证食品科学先验的稳定性和贡献。
4. G0-G7 消融实验：基于当前新架构重新跑可复现 benchmark。
5. TrustReport：在完成先验校准和外部验证后再定义可信等级。

## 文档说明

历史 review 文档保留问题审查记录，不直接代表当前实现状态。当前项目进度以：

1. `docs/CURRENT_STATUS.md`
2. `docs/PROGRESS.md`
3. `docs/FIX_PLAN.md`

为准。
