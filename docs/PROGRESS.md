# NuSol-T 项目进展报告

> 2026-07-05 | 当前分支：`refactor/yaml-solver-framework`

## 总体进度

**Phase 0-8 已完成，Phase 9 遗留清理进行中。**

| Phase | 内容 | 状态 | 说明 |
|-------|------|------|------|
| **0** | Legacy 基线冻结 | ✅ | Synthetic fixtures + 求解器快照 + deprecation 标记 |
| **1** | YAML Schema + Resolver + CLI | ✅ | SolveDocument Pydantic, extends, validate/resolve 命令 |
| **2** | 领域模型 + Composition + ProblemBuilder | ✅ | NutrientValue 四态, CompositionMatrix, IngredientProblem |
| **3** | 约束注册表 + 7 类约束 + IR 编译器 | ✅ | ConstraintRegistry, solver-neutral IR, capability check |
| **3.5** | FNDDS Spike | ✅ | IR 在 3 个真实 USDA recipe 上验证通过 |
| **4** | Backend 迁移 | ✅ | Slack-based QP + HiGHS LP, 不可行检测 (F0.2) |
| **5** | Solve API + CLI | ✅ | `nusol.solve(yaml_path)` 端到端可用 |
| **6** | 自定义约束插件 | ✅ | entry-point 发现 + 版本匹配 + 参数校验 |
| **7** | 数据适配器迁移 | ✅ | IngredientMapper 提取 + 稳定 ID |
| **8** | Metrics 修正 | ✅ | MAE 并集, feasible-bound coverage, G0⊂...⊂G7 |
| **9** | 文档对齐 | 🔄 | CURRENT_STATUS, README, PROGRESS 更新中 |

## 代码规模

| 指标 | 值 |
|------|-----|
| Python 源文件 | ~55 |
| 测试用例 | 246 (100% 通过) |
| 约束类型 | 7 内置 + 插件扩展 |
| 求解后端 | SLSQP + HiGHS LP |

## 关键里程碑

| 里程碑 | 日期 | 含义 |
|--------|------|------|
| M1: Schema Draft | Phase 1 | YAML draft 可 validate/resolve |
| M2: Domain Complete | Phase 2 | IngredientProblem 替代 context dict |
| M3: Schema 1.0 Stable | Phase 3.5 | FNDDS spike 验证后锁定 |
| M4: Backend Working | Phase 4 | QP/LP 在新架构中复现 |
| **M5: End-to-End** | **Phase 5** | **`nusol solve` 从干净 checkout 可运行** |
| M6: Plugin Ready | Phase 6 | 插件可安全注册和追踪 |
| M7: USDA Data | Phase 7 | 4 适配器可用 |
| M8: Benchmark Ready | Phase 8 | metrics 语义修正 |

## 求解器和指标演进

```
Legacy (main):          QPSolver + BoundSolver + context dict
                        QP 硬编码 3 类约束, 静默忽略 constraints 参数
                        BoundSolver 不可行返回 [0,1] + success=True
                        MAE 用交集, coverage 80=95, zero_slack 可为负

Refactored (refactor):  ScipySLSQP + HighsLPBackend + CompiledProblem IR
                        Slack-based QP + 约束不支持的显式报错
                        BoundSolver 不可行 → SolveError (F0.2)
                        MAE 用并集, feasible-bound coverage, zero_slack∈[0,1]
```

## 下一步

1. **合并到 main** — refactor 分支稳定后合并
2. **Phase 9 完成** — 文档对齐 + legacy 公开入口删除
3. **Branded Food 应用** — Phase 7 适配器迁移完成后退进
4. **Benchmark 重跑** — 在新架构上跑 200-recipe + synthetic benchmark
