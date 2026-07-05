# NuSol-T 当前实现状态

> 最后更新：2026-07-05 | 自动生成 + 手工标注  
> 配套文档：`REFACTOR_PLAN.md`（架构愿景）、`DEVELOPMENT_PLAN.md`（执行计划）

## 模块状态

### YAML 层 (config/)

| 模块 | 状态 | 测试 | 备注 |
|------|------|------|------|
| `schema.py` | ✅ 完成 | ✅ | SolveDocument Pydantic v2, extra="forbid" |
| `loader.py` | ✅ 完成 | ✅ | YAML parse + schema validation |
| `resolver.py` | ✅ 完成 | ✅ | extends merge + cycle detection + canonical output |
| `errors.py` | ✅ 完成 | ✅ | 3-layer error hierarchy |

### 领域模型 (domain/)

| 模块 | 状态 | 测试 | 备注 |
|------|------|------|------|
| `nutrient.py` | ✅ 完成 | ✅ | NutrientValue 四态 missingness |
| `ingredient.py` | ✅ 完成 | ✅ | 稳定 ID |
| `composition.py` | ✅ 完成 | ✅ | CompositionMatrix + inline/csv loaders |
| `problem.py` | ✅ 完成 | ✅ | IngredientProblem |
| `builder.py` | ✅ 完成 | ✅ | SolveDocument → IngredientProblem |
| `validation.py` | ✅ 完成 | ✅ | shape/unit/interval/missing 校验 |

### 约束系统 (constraints/)

| 模块 | 状态 | 测试 | 备注 |
|------|------|------|------|
| `registry.py` | ✅ 完成 | ✅ | 全局注册 + 插件发现 + capability 声明 |
| `builtin/mass_balance` | ✅ 完成 | ✅ | Σx=1 |
| `builtin/ingredient_order` | ✅ 完成 | ✅ | x_i ≥ x_{i+1} |
| `builtin/two_percent` | ✅ 完成 | ✅ | x_i ≤ 0.02 |
| `builtin/nutrient_interval` | ✅ 完成 | ✅ | lo ≤ Ax ≤ hi (soft) |
| `builtin/declared_percentage` | ✅ 完成 | ✅ | x_i = target |
| `builtin/linear_expression` | ✅ 完成 | ✅ | 通用线性约束 |
| `builtin/unique_source` | ⚠️ 骨架 | ⚠️ | 占位，需 compiler 扩展 |

### IR 编译器 (compiler/)

| 模块 | 状态 | 测试 | 备注 |
|------|------|------|------|
| `ir.py` | ✅ 完成 | ✅ | VariableIR, LinearConstraintIR, CompiledProblem |
| `compiler.py` | ✅ 完成 | ✅ | IngredientProblem → CompiledProblem |

### 求解后端 (backends/)

| 模块 | 状态 | 测试 | 备注 |
|------|------|------|------|
| `base.py` | ✅ 完成 | ✅ | Backend protocol |
| `registry.py` | ✅ 完成 | ✅ | Backend 注册 + capability matching |
| `scipy_slsqp.py` | ✅ 完成 | ✅ | Slack-based QP, infeasible → SolveError |
| `highs_lp.py` | ✅ 完成 | ✅ | LP bounds, infeasible → SolveError (F0.2 fixed) |

### 数据适配器 (adapters/)

| 模块 | 状态 | 测试 | 备注 |
|------|------|------|------|
| `mapping.py` | ✅ 完成 | ✅ | 4 级映射 fallback, 稳定 ID, fortificant 检测 |
| FNDDS adapter | ⏳ 待迁移 | — | 使用旧接口，迁移到新 builder |
| SR Legacy adapter | ⏳ 待迁移 | — | 同上 |
| Foundation adapter | ⏳ 待迁移 | — | 同上 |
| Branded adapter | ⏳ 待迁移 | — | 同上 |

### API 层

| 模块 | 状态 | 测试 | 备注 |
|------|------|------|------|
| `api.py` | ✅ 完成 | ✅ | solve(yaml_path) 唯一公开入口 |
| `cli.py` | ✅ 完成 | ✅ | validate/resolve/inspect/solve 四个命令 |

### 验证 (validation/)

| 模块 | 状态 | 测试 | 备注 |
|------|------|------|------|
| `metrics.py` | ✅ 修正 | ✅ | MAE 用并集, feasible-bound coverage, zero_slack ∈ [0,1] |
| `ablation.py` | ✅ 修正 | ✅ | G0⊂G1⊂...⊂G7 |

### 报告 (report/)

| 模块 | 状态 | 测试 | 备注 |
|------|------|------|------|
| `trust.py` | ⏳ 待重构 | — | 与新 backend 接口整合 |
| `trust_grade.py` | ⏳ 待重构 | — | Trust Grade 首版不做 |

### 核心 (core/)

| 模块 | 状态 | 测试 | 备注 |
|------|------|------|------|
| `nutrient_registry.py` | ✅ 修正 | ✅ | 脂肪酸 ID 修正 (F1.1) |
| `units.py` | ✅ 修正 | ✅ | IU 转换修正 (F1.5) |
| `schema.py` | ⏳ 待清理 | — | 保留为 legacy |

### 营养 (nutrition/)

| 模块 | 状态 | 测试 | 备注 |
|------|------|------|------|
| `forward.py` | ⏳ 待重构 | — | 水分单位 bug (F1.4) |
| `labelize.py` | ⏳ 待重构 | — | FDA rounding 表 |

### 旧系统 (legacy/)

| 模块 | 状态 | 测试 | 备注 |
|------|------|------|------|
| QPSolver | ⏳ 待移除 | ⚠️ | 被 ScipySLSQPBackend 替代 |
| BoundSolver | ⏳ 待移除 | ⚠️ | 被 HighsLPBackend 替代 |
| PointSolver | ✅ 已废弃 | ⚠️ | 已在 legacy baseline 中标记 |
| EnsembleSolver | ⏳ 待保留 | — | Phase 9 迁移 |

## Pipeline 完整性

| Pipeline | 状态 | 命令 |
|----------|------|------|
| YAML validate | ✅ | `nusol validate problem.yaml` |
| YAML resolve | ✅ | `nusol resolve problem.yaml` |
| Solve (point) | ✅ | `nusol solve problem.yaml` |
| Solve (bounds) | ✅ | 自动随 solve 运行 |
| 200-recipe benchmark | ❌ 待实现 | `scripts/benchmark_fndds_200.py` |
| FNDDS spike | ✅ | `scripts/spike_fndds_ir.py` |
| Branded Food | ❌ 待实现 | Phase 6-7 |

## 测试状态

| 指标 | 值 |
|------|-----|
| 测试总数 | 246 |
| 通过率 | 100% |
| Legacy 快照 | 3 synthetic fixtures, 13 tests |
| API/CLI tests | 9 CLI + 5 API |
| Config/Schema/Resolver | 11 config + 11 resolver |
| 无 USDA 数据依赖 | ✅ 所有测试可离线运行 |
