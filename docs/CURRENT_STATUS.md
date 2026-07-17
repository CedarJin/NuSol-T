# NuSol-T 项目进度

> 2026-07-16 | 分支: `refactor/yaml-solver-framework` | 268 tests passing | GitHub: [CedarJin/NuSol-T](https://github.com/CedarJin/NuSol-T)

---

## 一、核心成果

NuSol-T 已完成从 legacy 代码到 YAML 驱动、科学可验证的重构。

### 三年跨版本 FNDDS 验证

| FNDDS 版本 | 配方数 | 成功率 | MAE 中位 |
|-----------|--------|--------|----------|
| 2021-10-28 | 4,715 | 99.5% | 1.7 pp |
| 2022-10-28 | 3,823 | 99.3% | 1.8 pp |
| 2024-10-31 | 3,734 | 99.8%* | 1.74 pp |
| **合计** | **12,272** | **~99.5%** | **1.7-1.8 pp** |

*2024 是完整修复后数据（含自动 weight fallback）。

### 修复 pipeline

```
初始自动 pipeline (2024):  3,542/3,734 (94.9%)    MAE 中位 1.74 pp
+ max_iter 500→2000:         +147 solve 失败
+ 手动 YAML fortificant:      +16 export 失败
+ yield factor (raw→cooked): +21 之前不可解的
+ weight fallback (w=10→1): 全 8 个剩下的 solve 失败
─────────────────────────────────────────────────
最终可达:                   ~3,725/3,734 (99.8%)
仅剩 9 个结构性不可能（单配料/同品种混合）
```

### Ingredient Mapping 质量

| 映射方式 | 命中率 | 置信度 | 适用场景 |
|---------|--------|--------|---------|
| Code-assisted (L1-L3) | 99.9% | 96% | FNDDS benchmark |
| Name-only (L4) | ~90% | 95 | Branded food 模拟 |
| 短名→标准名 | **未实现** | — | **Phase 5 目标** |

---

## 二、FNDDS Benchmark 结果

### 全量 3,734 配方 (扩展 benchmark)

```
3,734 个多配料配方 (排除 95 个 NFS)
──────────────────────────────────────
  Export 成功:  3,701 (99.1%)
  Solve 成功:   3,542 (94.9%)
  Export 失败:     33 ( 0.9%)
  Solve 失败:     159 ( 4.3%)
──────────────────────────────────────
  MAE mean:   2.48 pp
  MAE median: 1.74 pp
  耗时: 250s
```

### 修复后结果

| 修复策略 | 修复数 | 方法 |
|----------|--------|------|
| SLSQP `max_iter` 500→2000 | 147/159 (92.5%) | 纯粹增加迭代步数 |
| 手动过滤 fortificant 配料 | 16/33 (48%) | 去除无营养数据的 fortificant code |
| Yield factor (raw→cooked) | 21 个新修复 | 能量守恒估算烹饪失水率 |
| **修复后成功率** | **3,717/3,734 (99.5%)** | |

### 不可求解的 17 个

| 类别 | 数量 | 原因 |
|------|------|------|
| 单配料（去 fortificant 后） | 6 | Yogurt、OJ、Shredded wheat → 本质是单配料食品 |
| 同品种混合 | 3 | Banana、Tomato、Onion → 营养不可区分 |
| 贝类/器官肉 | 5 | Clams、Shrimp、Hog maws → yield+收敛 |
| 其他 | 3 | Bagel、Turkey、Tomato canned → 营养重叠 |

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
| **Backends** | `backends/scipy_slsqp.py`, `highs_lp.py`, `registry.py` | Slack-based QP (point, adaptive retry trace) + HiGHS LP (bounds) |
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
| `scripts/export_fndds_recipes.py` | FNDDS recipe → branded-food-conditions YAML（四级 mapper、kJ→kcal 修正、fortificant 分离、可量化 contribution adjustment 与 diagnostics） |
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
5. **Fortificant 显式处理**：纯营养素添加剂（code 999xxx / 名称规则）从普通 ingredient fraction 求解中分离，写入 `fortification` diagnostics；calcium/iron/fiber 等可量化贡献会先从 label observation 中扣除，potency 不明确的 vitamin premix 仍只做 suspected metadata
6. **kJ→kcal 自动修正**：Atwater 4-4-9 公式 (`4×protein + 4×carbs + 9×fat`) 检测能量单位错误（`ratio > 3.0` → 除以 4.184）
7. **Yield factor（生→熟修正）**：能量守恒检测烹饪失水浓缩（`label_energy / Σ(raw_frac × raw_energy)`），用 raw weight fraction 计算，不依赖 ground truth。Branded food 可通过迭代或 USDA 烹饪 yield 表复用
8. **Branded-food 条件模拟**：FNDDS 仅用配料名称 + Nutrition Facts 标签作为输入，不泄露 FNDDS code 和真实比例
8. **Prior 机制边界**：当前 prior 参数来自 YAML 显式声明；测试和示例中的 prior 数值只用于验证机制，不代表已完成 FNDDS calibration 或食品科学先验库

---

## 五、测试

```
268 tests passed (pytest)
```

覆盖：Config schema 验证、Domain model（NutrientValue 四态、CompositionMatrix 缺失处理）、Compiler（约束编译、IR 生成）、Backend（SLSQP point solve + adaptive retry trace、HiGHS bounds solve + infeasibility check）、API（端到端、点估计/界限/独立/组合配置）、CSV 校验（SHA-256、ingredient 顺序对齐）、declaration-aware constraints、Level 2 priors、prior ablation variant generation。

其中 Level 2 priors 的测试覆盖的是 schema/registry/compiler/backend/result diagnostics 机制，不是 prior 参数科学有效性的实证验证。真正的 prior 参数需要后续基于 FNDDS category-level statistics、独立验证集或专家规则进行 calibration，并通过 ablation/sensitivity 检查其贡献。

---

## 六、Phase 进度

| Phase | 内容 | 状态 |
|-------|------|------|
| **Phase 0** | 基础框架：Schema、YAML 配置、NutrientRegistry | ✅ |
| **Phase 1** | FNDDS 数据适配 + Forward Calculation | ✅ |
| **Phase 2** | Inverse Solver：约束系统 P0-P2、Point/Bound Solver | ✅ |
| **Phase 3** | FNDDS Inverse Validation（3 年跨版本，12,272 配方） | ✅ |
| **Phase 4** | Ablation Study（G0-G2）+ Sensitivity Analysis | ✅ |
| **Phase 5** | **Branded Food Adapter：配料解析器、映射器** | ⬜ **← 下一步** |
| **Phase 6** | Branded Food Application：pipeline、报告 | ⬜ |
| **Phase 7** | 文档、论文 | 部分完成 |

### Phase 5 核心挑战

当前 FNDDS 配料名已是 USDA 标准名（code-assisted 99.9% 匹配）。Branded food 标签用短名：

```
"OATS" → 需映射到 → "Cereals, oats, regular and quick, not fortified, dry"
"ENRICHED FLOUR" → "Flour, wheat, all-purpose, enriched, bleached"
```

纯名称搜索当前 ~10% 找不到匹配。Phase 5 需建立短名→标准名的映射层。

---

## 七、待完成

| # | 任务 | 优先级 |
|---|------|--------|
| 1 | **IngredientParser** — 标签文本→IngredientTree | **P0 (Phase 5)** |
| 2 | **IngredientMapper** — 短名→USDA 标准名 | **P0 (Phase 5)** |
| 3 | Fortificant contribution table / additive solver | 中 |
| 4 | IPOPT backend（备选 point solver） | 低 |
| 5 | Prior calibration + ablation | 中 |
| 6 | Branded Food end-to-end pipeline | Phase 6 |
| 7 | 论文 | Phase 7 |

---

## 八、推荐的 Next Step

**Phase 5: IngredientParser + IngredientMapper**

FNDDS 验证已证明：只要配料映射正确，求解器能以 1.7-1.8pp 中位误差反推比例（12,272 配方跨 3 年验证）。现在需要补上 branded food 的关键一环——把标签短名映射到 USDA 标准名。

---

## 八、仓库

- GitHub: https://github.com/CedarJin/NuSol-T
- 分支: `main` (原始 legacy)、`refactor/yaml-solver-framework` (当前开发分支)
- 数据: `../db/` (FNDDS、SR Legacy、Foundation Foods、Branded Food JSON)
