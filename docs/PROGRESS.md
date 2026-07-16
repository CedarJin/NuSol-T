# NuSol-T 项目进展报告

> 2026-07-15 | 当前分支：`refactor/yaml-solver-framework`
> 最新事实源：`docs/CURRENT_STATUS.md`

## 总体进度

当前项目已完成 YAML solver framework 的核心重构，进入 Branded Food 应用前的功能扩展阶段。

一句话状态：

> NuSol-T 已经具备以 YAML 为唯一求解输入的原料比例逆向求解框架，可以执行基础约束、点估计、可行边界求解和 YAML-declared prior 机制；下一阶段重点是真实包装食品标签解析、配料映射、prior calibration 和可信报告。

## 当前验证结果

以 `docs/CURRENT_STATUS.md` 为准：

| 项目 | 当前结果 |
|---|---:|
| Pytest | 266 passed |
| FNDDS 多配料配方 | 197 |
| Solve 成功 | 189 / 197 |
| Solve 成功率 | 95.9% |
| 成功样本 MAE mean | 3.04 pp |
| 成功样本 MAE median | 2.53 pp |
| 最佳样本 | 0.00 pp |
| 最差成功样本 | 14.96 pp |

说明：这里的 FNDDS benchmark 是在受控条件下使用 Nutrition Facts 标签和配料名称进行的 branded-food 条件模拟。它证明当前求解框架具备可用性，但不等价于真实商业配方外部验证。

## 阶段状态

| Phase | 内容 | 状态 | 当前口径 |
|---|---|---|---|
| 0 | Legacy 基线冻结 | ✅ | 已完成 |
| 1 | YAML Schema + Resolver + CLI | ✅ | 已完成 |
| 2 | 领域模型 + Composition + ProblemBuilder | ✅ | 已完成 |
| 3 | Constraint registry + Solver-neutral IR | ✅ | 已完成 |
| 4 | SLSQP point backend + HiGHS bounds backend | ✅ | 已完成 |
| 5 | 唯一 solve API + CLI workflow | ✅ | 已完成 |
| 6 | 自定义约束插件机制 | ✅ | 基础机制已完成 |
| 7 | USDA 数据适配器迁移 | ✅ | FNDDS / SR Legacy / Foundation / Branded adapter 基础可用 |
| 8 | Metrics 与 benchmark 修正 | ✅ | 当前 FNDDS benchmark 已记录在 `CURRENT_STATUS.md` |
| 9 | 文档对齐与高级食品科学接口 | 🔄 | Level 2 Prior 初版已完成；TrustReport / Bayesian 后端仍属后续扩展 |

## 已打通的核心能力

1. **YAML 单入口**

   所有求解输入通过 YAML 声明，公开 API 使用 `solve(yaml_path)`。

2. **Resolved YAML 执行语义**

   `extends`、默认值、资源路径和 checksum 进入实际求解链路，而不是只用于文档或校验。

3. **Solver-neutral IR**

   YAML 约束先编译为中间表示，再交给不同 backend 执行，避免约束逻辑散落在求解器内部。

4. **点估计 + 可行边界**

   SLSQP 负责 slack-based point solve，HiGHS LP 负责 bounds solve。失败和不可行问题不应静默返回成功。

5. **数据资源可追踪**

   CSV composition 支持 SHA-256 校验、路径解析、ingredient 顺序对齐和 manifest 记录。

6. **配置错误显式失败**

   未注册 prior、未注册约束、能力不匹配等情况必须显式报错，不能静默忽略。

7. **Level 2 Prior 机制初版**

   当前支持 `fraction_interval_prior`、`group_total_prior`、`recipe_center_prior`、`anti_extreme_prior` 和 `ratio_prior`，并输出 `prior_contributions`。这些 prior 目前由 YAML 显式声明；仓库中的测试/示例参数用于验证机制，不代表已完成科学标定。

## 仍未完成的关键能力

| 方向 | 状态 | 说明 |
|---|---|---|
| Branded Food label parser | 未完成 | 需要把真实标签文本解析为结构化 IngredientTree |
| Ingredient mapper | 未完成 | 真实品牌食品短名到 USDA 标准原料的映射仍是核心挑战 |
| Prior registry / compiler / backend | 初版完成 | 已支持 5 类 YAML-declared Level 2 priors，并可输出 contribution |
| 科学标定 prior 库 | 未完成 | 当前没有从 FNDDS 自动估计 prior 参数；需要基于独立数据校准 prior weight、分布和适用条件 |
| Bayesian / hierarchical backend | 未完成 | 属于 Level 4 扩展，应复用 YAML / domain / provenance |
| TrustReport / TrustGrade | 未完成 | 在完成校准和外部验证前，不应声称科学可信等级 |
| G0-G7 消融实验 | 待完成 | 需要基于当前新架构重新跑完整消融 |

## 和历史 review 文档的关系

`docs/REVIEW.md`、`docs/SCIENCE_REVIEW.md`、`docs/DESIGN_IMPLEMENTATION_REVIEW.md` 记录的是 2026-07-05 的历史审查结论。它们指出的问题中，部分已经在当前重构分支修复，部分仍是后续科学建模和产品化阶段的风险。

当前进度判断以以下顺序为准：

1. `docs/CURRENT_STATUS.md`
2. `docs/PROGRESS.md`
3. `docs/FIX_PLAN.md`
4. 历史 review 文档

## 下一步

1. 完成 Phase 9 文档对齐，避免旧文档继续描述已废弃架构。
2. 实现 Branded Food `IngredientParser`。
3. 实现真实标签短名到 USDA 原料记录的 `IngredientMapper`。
4. 做 Level 2 priors 的 calibration、ablation 和 sensitivity。
5. 重跑 G0-G7 消融实验，并输出可复现实验产物。
