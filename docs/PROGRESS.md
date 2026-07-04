# NuSol-T 开发进展报告

> 2026-07-04

## 总体进度

**已完成 Phase 0-4（Stage 1: FNDDS 验证），202 个测试全部通过。**

| Phase | 状态 | 内容 |
|-------|------|------|
| Phase 0 | ✅ 完成 | 基础框架：项目初始化、Schema、NutrientRegistry、单位系统、YAML 配置、Typer CLI |
| Phase 1 | ✅ 完成 | FNDDS/SR Legacy/Branded 数据适配器、ForwardNutritionModel、Labelized Simulation |
| Phase 2 | ✅ 完成 | P0-P4 约束系统、PointSolver/BoundSolver/EnsembleSolver、多初值策略 |
| Phase 3 | ✅ 完成 | TrustReport/TrustGrade、Validation Metrics、IngredientParser、FNDDS 集成 |
| Phase 4 | ✅ 完成 | G0-G7 Ablation 配置生成、运行器、汇总 |
| Phase 5 | ⏳ 待开发 | Branded Food Adapter + 完整配料映射 |
| Phase 6 | ⏳ 待开发 | Branded Food 批量 pipeline + NutrientExpander |
| Phase 7 | ⏳ 待开发 | 文档完善、论文准备 |

## 项目规模

| 指标 | 数量 |
|------|------|
| Python 源文件 | 41 个 |
| 测试文件 | 19 个 |
| 测试用例 | 202 个 |
| 文档 | 4 份（NuSol-T.md, DEVELOPMENT.md, DATA.md, PROGRESS.md） |

## 技术栈

- **Python 3.12** + **uv** 包管理
- **Pydantic v2** 数据校验
- **SciPy.optimize** 约束求解
- **Typer** CLI 框架
- **pytest** + **ruff** + **mypy** 质量保障
- **src layout** 标准 Python 包结构

## 核心模块

### `nusol/core/` — 数据模型

- **schema.py**: 8 个 Pydantic 模型（NutrientRecord, NutrientProfile, IngredientTree, ProductObservation, TrustReport, SolverResult 等）
- **nutrient_registry.py**: 40+ USDA 营养素的标准化注册表（ID ↔ name ↔ unit）
- **units.py**: 单位换算（g/mg/µg, kcal/kJ, IU），per_100g ↔ per_serving
- **enums.py**: ConstraintPriority(P0-P4), TrustGrade(A/B/C/D), DataSource

### `nusol/data/` — 数据适配器

- **FNDDSDataAdapter**: 读取 FNDDS JSON，提取 recipe、ingredient weights、retention codes
  - 三级配料映射 fallback：ndbNumber → foodCode → fuzzy search
  - 8 个强化营养素代码检测
- **SRLegacyDataAdapter**: ndbNumber 直查 + 子串搜索 + 多词重叠搜索 + 手动映射表
- **BrandedDataAdapter**: 读取 Branded Food JSON（骨架已就绪）

### `nusol/constraints/` — 约束系统

| 优先级 | 约束 | 类型 |
|--------|------|------|
| P0 | MassBalance (Σx=1, x≥0) | 硬约束 → SciPy |
| P1 | IngredientOrder (降序) | 可微量 slack |
| P1 | TwoPercentRule (≤2%) | 可微量 slack |
| P2 | LabelIntervalFit | 软约束 → 目标函数罚项 |
| P3 | EnergyClosure (Atwater) | 软约束 |
| P4 | CategoryPrior | 软约束 |

### `nusol/solver/` — 求解器

- **PointSolver**: trust-constr + 多初值 Dirichlet 采样
- **BoundSolver**: 逐变量 min/max feasible range
- **EnsembleSolver**: 多初值 + label bootstrap → percentile intervals
- **initializer.py**: 4 种初值策略（dirichlet, uniform_random, uniform_grid, decreasing）

### `nusol/nutrition/` — 营养计算

- **ForwardNutritionModel**: `predicted_j = (100/Y) × Σ x_i × A_ij × r_ij`
  - 支持 retention factors、moisture/yield adjustment
  - Atwater 能量估算辅助方法
- **labelize.py**: exact → per serving → FDA rounding → label intervals 全流程模拟

### `nusol/report/` — 报告系统

- **TrustReportBuilder**: 从 SolverResult 生成结构化 TrustReport
- **trust_grade.py**: 5 维度评分（成功/冲突/残差/区间宽度/自由度）→ A/B/C/D + 0-100 分

### `nusol/ingredient/` — 配料解析

- **IngredientParser**: 括号子配料、CONTAINS 2% OR LESS、AND/OR、标点清理

### `nusol/validation/` — 验证系统

- **metrics.py**: ForwardMetrics（MAE, relative error）, InverseMetrics（MAE, rank corr, coverage, solve rate）
- **ablation.py**: G0-G7 消融配置生成、运行器、汇总

### `nusol/config/` — 配置

- **loader.py**: YAML 加载 + 默认值注入 + 校验

### `nusol/utils/` — 工具

- **numerics.py**: FDA 21 CFR 101.9 四舍五入规则（arithmetic rounding）、label value → interval 逆向

## 配料映射策略

FNDDS 的 2,336 个唯一配料编码通过三级 fallback 实现 ~99.8% 覆盖率：

```
FNDDS ingredientCode
  ├── Level 1: SR Legacy ndbNumber (71.7%)
  ├── Level 2: FNDDS foodCode 自闭环 (93.8% cumulative)
  └── Level 3: description 模糊匹配 → 手动映射表 (99.8% cumulative)
```

详见 `docs/DATA.md`。

## FNDDS 验证数据

| 条件 | 可用数量 |
|------|----------|
| 总 FNDDS 食品 | 5,432 |
| 有配料 + 营养素 | 5,431 |
| ≥ 2 配料（推荐验证集） | 3,829 |
| ≥ 5 配料（中等复杂度） | 1,379 |
| ≥ 10 配料（复杂配方） | 247 |
| 每食品营养素数 | 65（统一） |

## 下一步

1. **Phase 5**: 完善 Branded Food IngredientParser（处理真实包装食品配料表的复杂结构）
2. **Phase 6**: Branded Food 批量求解 pipeline + 扩展完整营养成分估计
3. **端到端验证**: 在 FNDDS 上跑完整 forward → inverse → labelized 流程，收集 benchmark 数据
4. **论文图表**: 基于验证结果生成方法论文所需图表
