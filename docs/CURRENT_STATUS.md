# NuSol-T 项目进度

> 2026-07-15 | 分支: `refactor/yaml-solver-framework` | 259 tests passing | GitHub: [CedarJin/NuSol-T](https://github.com/CedarJin/NuSol-T)

---

## 一、核心成果

NuSol-T 已完成从 legacy 代码到 YAML 驱动、科学可验证的重构。通过 FNDDS 200-recipe benchmark 验证了方法有效性：

**仅凭 Nutrition Facts 标签 + 配料名称，反推配料比例，197 个 USDA 配方中 189 个成功（95.9%），中位误差 2.53 个百分点。**

---

## 二、FNDDS Benchmark 结果

```
197 个多配料配方 (剔除 3 个 NFS 配方)

  Export 成功:  194 (98.5%)
  Solve 成功:   189 (95.9%)
  Export 失败:    3 (1.5%) ← fortified cereals (大量 fortificant 配料)
  Solve 失败:     5 (2.5%) ← 配料营养高度同质的简单配方

MAE 分布 (189 个成功配方):
  Mean:   3.04 pp
  Median: 2.53 pp
  Best:   0.00 pp (14 个完全命中)
  Worst: 14.96 pp
```

**注**：MAE = Mean Absolute Error in percentage points（百分点）。例如真实比例 50%，求解给出 47%，则误差 = 3pp。

---

## 三、已完成模块

### Phase 0-4: 核心重构 ✅

| 模块 | 文件 | 功能 |
|------|------|------|
| **Config** | `config/schema.py`, `resolver.py`, `loader.py`, `errors.py` | Pydantic v2 Schema、extends 继承链、YAML 验证 |
| **Domain** | `domain/problem.py`, `composition.py`, `nutrient.py`, `builder.py`, `validation.py` | IngredientProblem、四态 missingness、CompositionMatrix |
| **Compiler** | `compiler/compiler.py`, `ir.py` | YAML 约束 → Solver-Neutral IR |
| **Constraints** | `constraints/registry.py`, `builtin/*.py` | 7 个 builtin：mass_balance、ingredient_order、two_percent、nutrient_interval、declared_percentage、linear_expression、plugin |
| **Backends** | `backends/scipy_slsqp.py`, `highs_lp.py`, `registry.py` | Slack-based QP (point) + HiGHS LP (bounds) |
| **Priors** | `priors/registry.py`, `priors/builtin/*.py` | Level 2 prior 机制初版：支持 YAML 显式声明 fraction interval、group total、recipe center、anti-extreme、ratio；参数尚未科学标定 |
| **Results** | `results/schema.py`, `api.py` | Typed SolveResult、constraint diagnostics、prior contributions、bounds type |
| **API** | `api.py` | `solve(yaml_path)` 单入口 |
| **CLI** | `cli.py` | `validate`、`resolve`、`inspect`、`solve` |

### Data Adapters ✅

| 文件 | 功能 |
|------|------|
| `data/fndds.py` | FNDDS 数据加载、recipe 提取、四级 ingredient mapper (L1 FNDDS→L2 Foundation→L3 SR Legacy ndb→L4 fuzzy) |
| `data/sr_legacy.py` | SR Legacy 配料营养成分查找 (7793 种)、三种名称搜索 (exact/substring/word-overlap) |
| `data/foundation.py` | Foundation Foods 适配器 (2026 最新 USDA 数据) |
| `data/branded.py` | Branded Food 适配器（Phase 5 前置，已 stub） |

### 脚本与示例 ✅

| 文件 | 功能 |
|------|------|
| `scripts/export_fndds_recipes.py` | FNDDS recipe → branded-food-conditions YAML（四级 mapper、kJ→kcal 修正、fortificant 过滤） |
| `scripts/run_fndds_benchmark.py` | 批量导出 + 求解 + MAE 统计 |
| `examples/bread_minimal.yaml` | 简单面包配方示例 |
| `examples/oat_milk.yaml` | Oat milk 手写 YAML（演示完整流程） |

### 文档 ✅

| 文件 | 内容 |
|------|------|
| `docs/TECHNICAL_PRINCIPLES.md` | 营养学原理、数学推导、求解器设计、Mapper 设计、Slack/Budget 机制 |
| `docs/NuSol-T.md` | 总体规划书 |
| `docs/DEVELOPMENT.md` | 分 Phase 任务清单与接口设计 |
| `docs/DATA.md` | 数据字典 & 配料映射策略 |
| `docs/REFACTOR_PLAN.md` | 重构架构设计 |
| `docs/FIX_PLAN.md` | 35 项 bug 列表 + 修复记录 |

---

## 四、关键设计决策

1. **YAML 驱动**：所有实验通过 YAML 配置，保证可复现。单入口 `solve(yaml_path)`
2. **Solver-Neutral IR**：约束编译为 solver-agnostic 中间表示 (`CompiledProblem`)，后端可替换
3. **Slack-based QP**：软约束通过 slack 变量 + 二次惩罚实现，而非硬区间；`objective = Σ w·s²`
4. **四级 Ingredient Mapper**：`FNDDS code → Foundation Foods → SR Legacy ndb → 名称搜索`，code-based 优先于 text-based
5. **Fortificant 显式处理**：纯营养素添加剂（code 999xxx）识别并排除，受影响营养素通过 `max_ing_val < 50% label` 自动跳过
6. **kJ→kcal 自动修正**：Atwater 4-4-9 公式 (`4×protein + 4×carbs + 9×fat`) 检测能量单位错误（`ratio > 3.0` → 除以 4.184）
7. **Branded-food 条件模拟**：FNDDS 仅用配料名称 + Nutrition Facts 标签作为输入，不泄露 FNDDS code 和真实比例
8. **Prior 机制边界**：当前 prior 参数来自 YAML 显式声明；测试和示例中的 prior 数值只用于验证机制，不代表已完成 FNDDS calibration 或食品科学先验库

---

## 五、测试

```
259 tests passed (pytest)
```

覆盖：Config schema 验证、Domain model（NutrientValue 四态、CompositionMatrix 缺失处理）、Compiler（约束编译、IR 生成）、Backend（SLSQP point solve + 10x retry、HiGHS bounds solve + infeasibility check）、API（端到端、点估计/界限/独立/组合配置）、CSV 校验（SHA-256、ingredient 顺序对齐）、declaration-aware constraints、Level 2 priors、prior ablation variant generation。

其中 Level 2 priors 的测试覆盖的是 schema/registry/compiler/backend/result diagnostics 机制，不是 prior 参数科学有效性的实证验证。真正的 prior 参数需要后续基于 FNDDS category-level statistics、独立验证集或专家规则进行 calibration，并通过 ablation/sensitivity 检查其贡献。

---

## 六、待完成

### 近期

| # | 任务 | 优先级 |
|---|------|--------|
| 1 | Fortificant 营养素对照表（解决 3 个 fortified cereal export 失败） | 中 |
| 2 | SLSQP 收敛改进或备选 point solver（IPOPT） | 低 |
| 3 | Foundation Foods 数据集成（替换 SR Legacy 中质量较低的条目） | 中 |
| 4 | Prior calibration、ablation 和 sensitivity | 中 |

### Phase 5-6: Branded Food 应用

| # | 任务 | 说明 |
|---|------|------|
| 5 | **IngredientParser** | 标签配料文本 `"WATER, SUGAR, OATS, CONTAINS 2% OR LESS OF: SALT"` → 结构化 IngredientTree |
| 6 | **IngredientMapper** | 标签短名 `"OATS"` → USDA 标准名 `"Cereals, oats, regular and quick, not fortified, dry"` → SR Legacy 营养成分 |
| 7 | Branded Food adapter | 连接 USDA Branded Food 数据库 |
| 8 | Branded Food end-to-end | 标签文本 → parse → map → solve → TrustReport |

### 远期

| # | 任务 |
|---|------|
| 9 | 200-recipe FNDDS ablation study (G0-G7 消融实验) |
| 10 | TrustReport + TrustGrade (A/B/C/D) |
| 11 | 论文 |

---

## 七、推荐的 Next Step

**Phase 5: IngredientMapper + IngredientParser**

Branded food 应用最关键的一步。当前 FNDDS 验证中配料名已是 USDA 标准名（100% 匹配），但真实品牌食品标签是短名（`"OATS"`、`"ENRICHED FLOUR"`）。需要：

1. **IngredientParser**：解析标签配料文本 → IngredientTree（处理括号嵌套、逗号分隔、"CONTAINS 2% OR LESS OF" 标记）
2. **IngredientMapper**：标签短名 → USDA 标准名映射。这是 Phase 5 的核心挑战——名称匹配质量直接决定后续求解精度

两个模块完成后，品牌食品的端到端流程就通了。FNDDS 验证已经证明只要配料映射正确，求解器能以 2.5pp 中位误差反推比例。

---

## 八、仓库

- GitHub: https://github.com/CedarJin/NuSol-T
- 分支: `main` (原始 legacy)、`refactor/yaml-solver-framework` (当前开发分支)
- 数据: `../db/` (FNDDS、SR Legacy、Foundation Foods、Branded Food JSON)
