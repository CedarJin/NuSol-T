# NuSol-T 项目交接记录

> 日期: 2026-07-22 | 分支: `refactor/yaml-solver-framework` | 268 tests passing
> GitHub: https://github.com/CedarJin/NuSol-T
> 重要：这是新会话第一入口。若本文与旧进度文档冲突，优先相信本文、`docs/CURRENT_STATUS.md` 和 `output/*/benchmark_summary.json` 的原始结果文件。

---

## 零、新会话先读这个

当前工作不是在重写 solver，而是在把已经跑通的 YAML-driven constrained solver 推向更真实的数据场景。

**当前分支和状态**

- 分支：`refactor/yaml-solver-framework`
- 最近确认状态：working tree clean，已同步到 `origin/refactor/yaml-solver-framework`
- 最近一批 commits 已经完成：多数据库 benchmark、fortification 修复、fallback solve、status/handoff 文档
- 最新 handoff 相关 commit：`d9d6d3e docs: handoff record — full project status, Phase 5 next, 9 pitfalls, 6 databases, 24k recipes`

**当前主线任务**

1. Phase 0-4 已完成：证明在 FNDDS/AFCD 这类 recipe-level 数据上，只要 ingredient identity 和 nutrient composition 足够可靠，框架可以稳定求解配料比例。
2. 下一步是 Phase 5：把 workflow 推到真实包装食品/Branded Food/OFF 这类 messy label 数据。
3. 当前真正卡点不是数值优化器，而是 `IngredientParser + IngredientMapper + partial-truth validation`。
4. 用户已经明确：目前主要 focus 仍是验证 workflow 可行性；Branded Food 是后续应用方向，不是当前唯一目标。

**最重要的科学边界**

- OFF/OpenFoodFacts 大量 ingredient percentage 是 Product Opener / Recipe Estimator 的估计值，不是 ground truth。
- OFF 只能可靠使用两类信息：
  - label 明确声明的 ingredient percentage，例如 `Tomatoes 62%`，可作为 partial truth；
  - Nutrition Facts + ingredient order + 2% group，可作为 NuSol-T 的正常输入。
- OFF 的 `percent_estimate` / `percent_min` / `percent_max` 可以作为 baseline 或弱标签参考，但不能当作真实答案训练/校准 prior。
- 不能把 FNDDS recipe benchmark 和 OFF real-world label benchmark 直接当成 apples-to-apples 比较。

**最重要的工程边界**

- NuSol-T 的唯一求解输入仍然应该是 YAML；parser/mapper/exporter 只能负责把外部数据转成 YAML。
- 自定义约束要通过 YAML 和 constraint registry 接入，不要把临时逻辑硬编码进 solver。
- 目前 priors 是“YAML 可声明的先验机制”，不是已经被外部数据系统校准过的科学 prior library。
- Fortification 已经有初步识别/分离逻辑，但 vitamin D / B vitamins / folic acid / premix potency / true additive-variable solver 还没有完成。不要在论文或 README 中写成已解决。

## 一、项目一句话概述

NuSol-T 是一个从 Nutrition Facts 标签 + 配料表 + 可解释先验约束反推食物原料比例的 YAML 驱动约束求解框架。已在 6 个 USDA/Australia 数据库上验证了 24,348 个配方，中位成功率 ~99%，中位误差 1.7-2.5pp（JSON FNDDS）/ 2.4pp（Australia）。

注意：这句话里的 “包装食品” 是目标应用方向；当前最扎实的实证结果来自 FNDDS/AFCD recipe-level validation，不等于真实 Branded Food 端到端已经完成。

---

## 二、当前处于哪个 Phase

```
Phase 0-4 (FNDDS 验证阶段) ← ✅ 全部完成
Phase 5   (Branded/OFF messy label adapter) ← 🟡 下一步，基础件存在，端到端未完成
Phase 6-7 (应用+论文) ← ⬜ 未开始
```

**Phase 5 是当前瓶颈**：需要 IngredientParser（标签文本→结构化配料表）、IngredientMapper（短名→USDA 标准名→营养成分）和 partial-truth validation（只用真实声明百分比验证，不把估计百分比当 truth）。

FNDDS 验证已证明：只要配料映射正确，求解器能以 1.7-2.5pp 中位误差反推比例。现在的挑战是把 “干净 recipe 数据” 转到 “真实标签文本 + 短名 + 添加剂 + 估计百分比” 的场景。

**不要误判 Phase 5 状态**：

- `src/nusol/ingredient/parser.py` 已有基础 parser，但只支持简单逗号/括号/2% group，不支持完整 declared percentage extraction、复杂嵌套、多语言/OFF 标签。
- `src/nusol/adapters/mapping.py` 已有 mapper，但它是 FNDDS code-assisted mapper，不是真正 branded/OFF 短名 mapper。
- `src/nusol/data/branded.py` 是数据读取基础，不代表 Branded Food 端到端 pipeline 已经可用。

---

## 三、已完成的工作

### 核心框架（src/nusol/）

| 模块 | 路径 | 功能 |
|------|------|------|
| Config | `config/schema.py`, `resolver.py`, `loader.py`, `errors.py` | Pydantic v2 YAML schema, extends 继承链, 三级错误 |
| Domain | `domain/problem.py`, `composition.py`, `nutrient.py`, `builder.py`, `validation.py` | IngredientProblem, 四态 missingness, CompositionMatrix |
| Compiler | `compiler/compiler.py`, `ir.py` | YAML 约束 → solver-neutral IR (CompiledProblem) |
| Constraints | `constraints/registry.py`, `builtin/*.py` | 7 个 builtin: mass_balance, ingredient_order (declaration-group-aware), two_percent (auto from declaration_group), nutrient_interval, declared_percentage, linear_expression, plugin |
| Backends | `backends/scipy_slsqp.py`, `highs_lp.py`, `registry.py` | Slack-based QP (point) + HiGHS LP simplex (bounds) |
| Priors | `priors/registry.py`, `builtin/*.py` | 5 个 Level 2 prior: fraction_interval, group_total, recipe_center, anti_extreme, ratio |
| Results | `results/schema.py` | Typed SolveResult + constraint/observation diagnostics |
| API | `api.py` | `solve(yaml_path)` 单入口 |
| CLI | `cli.py` | validate, resolve, inspect, solve |
| Data | `data/fndds.py`, `sr_legacy.py`, `foundation.py`, `branded.py`, `afcd.py` | FNDDS(JSON)/SR Legacy/Foundation Foods/Australia AFCD adapters |

### Benchmark 脚本

| 脚本 | 功能 |
|------|------|
| `scripts/export_fndds_recipes.py` | FNDDS recipe → YAML (含四级 mapper, kJ→kcal, yield factor, fortificant filter, weight fallback 1.0→15%) |
| `scripts/run_fndds_benchmark.py` | 批量导出+solve+MAE统计，支持 `--full` 跑全量，`--limit N` 测试 |
| `scripts/run_afcd_benchmark.py` | Australia AFCD benchmark (220 recipes) |
| `scripts/retry_failures.py` | 手动修复 export/solve 失败的配方 |

### Benchmark 结果（6 个数据库，24,348 配方）

| # | 数据库 | 路径 | 配方数 | 成功率 | MAE 中位 | 说明 |
|---|--------|------|--------|--------|----------|------|
| 1 | JSON 2024 | `db/FoodData_Central_survey_food_json_2024-10-31/` | 3,734 | 99.8% | 1.7 pp | 主力验证集 |
| 2 | JSON 2022 | `db/FoodData_Central_survey_food_json_2022-10-28.json` | 3,823 | 99.3% | 1.8 pp | 跨年验证 |
| 3 | JSON 2021 | `db/FoodData_Central_survey_food_json_2021-10-28.json` | 4,715 | 99.5% | 1.7 pp | 跨年验证 |
| 4 | CSV 2020 | `db/FoodData_Central_survey_food_json_2020-csv.json` | 6,054 | 99.1% | 6.3 pp | CSV→JSON转换，高 MAE 需继续诊断 |
| 5 | CSV 2019 | `db/FoodData_Central_survey_food_json_2019-csv.json` | 5,802 | 98.9% | 8.6 pp | CSV→JSON转换，高 MAE 需继续诊断 |
| 6 | AFCD Aus | `db/Australia Food Composition Database/` | 220 | 100% | 2.4 pp | Excel→Python adapter |

**Benchmark 数字的 source of truth**

优先看下面这些结果文件，不要只看文档摘要：

| 数据集 | 结果文件 | 备注 |
|--------|----------|------|
| FNDDS JSON 2024 baseline | `output/fndds_benchmark/benchmark_full.json` | 早期 baseline：attempted 3,734，success 3,542，export_failed 33，solve_failed 159，median MAE 1.74pp；后续修复已改善失败数，引用时要说明版本 |
| FNDDS JSON 2021 | `output/fndds_2021/benchmark_summary.json` | usable 4,715，success 4,691，99.49%，median MAE 1.67pp |
| FNDDS JSON 2022 | `output/fndds_2022/benchmark_summary.json` | usable 3,823，success 3,797，99.32%，median MAE 1.77pp |
| FNDDS CSV 2020 | `output/fndds_2020_csv/benchmark_summary.json` | usable 6,054，success 5,998，99.07%，median MAE 6.33pp |
| FNDDS CSV 2019 | `output/fndds_2019_csv/benchmark_summary.json` | usable 5,802，success 5,738，98.90%，median MAE 8.59pp |
| AFCD | `output/afcd/benchmark_summary.json` | usable 220，success 220，100%，median MAE 2.4pp |

不要使用下面两个 stale 目录作为结果来源：

- `output/fndds_csv_2019/benchmark_summary.json`
- `output/fndds_csv_2020/benchmark_summary.json`

这两个是早期失败 run，曾出现 0 success。真实可用的是 `output/fndds_2019_csv/` 和 `output/fndds_2020_csv/`。

**CSV 2019/2020 的 caveat**

CSV 2019/2020 成功率高，但 median MAE 显著高于 JSON FNDDS/AFCD。现在不能把它们和 JSON FNDDS 一样当作强证据。后续如果要写论文/报告，需要先诊断：

- CSV→JSON 转换是否丢失 nutrient 或 recipe metadata；
- food code / ingredient code 是否跨年份语义不一致；
- yield factor / retention / cooked-vs-raw 处理是否不一致；
- label nutrient observation 是否由转换过程引入偏差。

### 关键修复历程

```
1. max_iter 500→2000:     147/159 solve 失败修复
2. Fortificant 手动过滤:    16/33 export 失败修复 (fortified cereals)
3. Yield factor:           21 个 raw→cooked 配方修复 (能量守恒)
4. Weight fallback:         8 个剩余失败修复 (w=10→1.0→1.0+±15%)
5. CSV→JSON 转换:          修复 CSV FNDDS 的 nutrient name 缺失 (ID→name mapping)
```

---

## 四、当前卡在什么地方

**Phase 5 的端到端 pipeline 尚未完成**。FNDDS 验证阶段已完成，需要切换到 Branded/OFF messy label 应用。核心差距：

1. **FNDDS 配料名 = USDA 标准名**，映射准确率 99.9%（code-assisted L1-L4）
2. **Branded food 标签用短名**（"OATS" 不是 "Cereals, oats, regular and quick, not fortified, dry"）
3. **纯名称搜索 10% 找不到匹配**（from `mapping analysis`, section below）
4. **OFF 百分比大多是估计值**，不能直接作为验证 truth
5. **真实标签里 additives/fortification/premix 更常见**，需要把 fortificant 当外源营养贡献处理，而不是强行让基础食材解释所有 micronutrients

需要建立一个短名→标准名的映射层。这是 Phase 5 的全部内容。

---

## 五、下一步具体怎么做

### 5.1 立即可做的

**IngredientParser** (标签文本→IngredientTree)：
- 输入: `"WATER, SUGAR, OATS, CANOLA OIL, CONTAINS 2% OR LESS OF: SALT, VITAMIN D2"`
- 输出: `{main: [...], two_percent: [...]}` 结构化配料表
- 已有基础代码: `src/nusol/ingredient/parser.py` (IngredientParser class)
- 需要: 处理括号嵌套, "CONTAINS 2% OR LESS OF:" 标记, 逗号分隔, 句号终止, declared percentages (`Tomatoes 62%`)

**IngredientMapper** (短名→USDA标准名):
- 输入: `"OATS"` → 输出: `"Cereals, oats, regular and quick, not fortified, dry"` + SR Legacy profile
- 策略: 先试 exact match, 再试 substring, 再试 word-overlap (SR Legacy 已有这些)
- 还需要: manual mapping table for common branded food names

**OFF partial-truth validation**:
- 输入: OFF products with Nutrition Facts + ingredient text + declared ingredient percentages
- 输出: YAML + partial truth constraints/metrics
- 只把 label-declared percentages 作为验证点
- 把 OFF estimator 的 `percent_estimate` 作为 baseline，不作为 truth

### 5.2 架构参考

```
Branded Food Label Text
  → IngredientParser → IngredientTree
  → IngredientMapper → USDA standard names + nutrient profiles
  → YAML 生成 (同 export_fndds_recipes.py 的逻辑)
  → solve(yaml_path)
```

OFF 的推荐架构：

```
OpenFoodFacts product
  → extract nutrition facts
  → parse ingredient text
  → extract declared percentages only
  → map ingredients to USDA/SR/Foundation/other DB profiles
  → generate YAML
  → solve
  → evaluate only on declared percentages + plausibility diagnostics
  → compare against OFF percent_estimate as baseline
```

### 5.3 从哪里开始写代码

1. 读 `src/nusol/ingredient/parser.py` — 了解现有 parser
2. 读 `src/nusol/adapters/mapping.py` — 了解现有 mapper
3. 读 `scripts/export_fndds_recipes.py` — 了解 YAML 生成逻辑 (这段可以直接复用)
4. 写一个新的 `scripts/export_branded_yaml.py` — branded food label → YAML

### 5.4 建议下一轮执行顺序

1. **文档清理**：统一 `docs/CURRENT_STATUS.md`、`docs/BENCHMARK_RESULTS.md`、`docs/PROGRESS.md`、`docs/SUMMARY.md` 的口径。当前 `PROGRESS.md` / `SUMMARY.md` 仍可能保留早期 197 recipe 的旧叙述。
2. **诊断 CSV 高 MAE**：优先解释 `output/fndds_2019_csv/` 和 `output/fndds_2020_csv/` 为什么成功率高但误差大。这个问题不解决，不要把 CSV 结果包装成同等强度的 validation。
3. **写 OFF validation plan**：建议新增 `docs/OFF_VALIDATION_PLAN.md`，明确 OFF 哪些字段可当 truth、哪些只能当 weak label/baseline。
4. **扩展 parser**：给 `IngredientParser` 增加 declared percentage extraction，并补 tests。
5. **设计 mapper provenance**：mapper 输出必须带 `confidence`、`source`、`matched_food_id`、`method`，否则后续科学解释站不住。
6. **partial truth evaluator**：新增只评估 declared percentage subset 的 metric，避免把未声明百分比的配料当成 known truth。

---

## 六、踩过的坑（不能再犯）

### 坑 1：CSV FNDDS 的 nutrient name 是空的

CSV 格式的 FNDDS 中 `food_nutrient.csv` 只有 `nutrient_id`（数字），没有 name（字符串）。直接转 JSON 后 `FNDDSDataAdapter` 无法匹配标签营养素（全部返回 0 匹配）→ export 失败。

**解决方案**: CSV→JSON 转换时必须填充 `ID_TO_NAME` 映射表（见 `scripts/` 中的转换脚本）。核心 USDA nutrient ID: 1008=Energy, 1003=Protein, 1004=Fat, 1005=Carbs, 1079=Fiber, 2000=Sugars, 1258=Saturated fat, 1093=Sodium, 1087=Calcium, 1089=Iron, 1092=Potassium, 1114=Vitamin D, 1253=Cholesterol。

### 坑 2：YAML dump 不能有 numpy scalar

`yaml.safe_dump()` 不接受 `np.float64`/`np.int64` 等 numpy 类型。所有数值必须转成 Python 原生 `float`/`int`。

**解决方案**: 在 YAML dump 前做 json roundtrip: `yaml.safe_dump(json.loads(json.dumps(doc, default=float)), ...)`。

### 坑 3：SLSQP 对 weight=10.0 太敏感

默认 soft constraint weight=10.0 在 organ meats/shellfish 等数据不确定性高的配方上会导致 SLSQP 不收敛（`Positive directional derivative for linesearch`）。

**解决方案**: `_solve_with_fallback()` 三级回退:
1. weight=10.0 (default)
2. weight=1.0 (lower penalty)
3. weight=1.0 + ±15% intervals (wider tolerance)

### 坑 4：FNDDS `get_recipe()` 返回的 key 是 `ingredients`，不是 `inputFoods`

`fndds.get_recipe(fid)` 返回的 dict 中，配料列表的 key 是 `ingredients`（经过处理的），不是原始 JSON 中的 `inputFoods`。用 `.get("inputFoods", [])` 会返回空列表。

### 坑 5：Excel 文件 header 行不固定

Australia AFCD 的 Excel 文件第一行是标题（"Release 3 - Recipes"），第二行是空行，第三行才是列名。必须 `header=2` 读取。

### 坑 6：CSV FNDDS 目录名有空格

2019 的 CSV 目录名是 `FoodData_Central_survey_food_csv_ 2019-04-02`（`csv_` 后面有个空格）。2020 没有空格：`FoodData_Central_survey_food_csv_2020-03-31`。路径拼接时要小心。

### 坑 7：ingredient_order 的 declaration_group 意识

`ingredient_order` builtin 默认对所有连续配料强制 x_i ≥ x_{i+1}。但 FDA 规定 ≤2% group 内无需排序。修复后 `ingredient_order` 只对 `main` group 强制降序（通过 `groups: ["main"]` config）。`two_percent` builtin 支持 `source: declaration_group` 从 ingredient groups 自动生成 x_i ≤ 0.02。

### 坑 8：Fortificant 过滤不能靠名称

纯 nutrient additive (code 999xxx) 在 SR Legacy 中不存在。必须识别并排除，且被它们主导的营养素（如 calcium 155mg 中 150mg 来自 fortificant）要从 observations 中跳过。

当前用的是 `max_ing_val < 50% label_val` heuristic — 如果任何单一配料无法提供标签值的一半，就标记为 "likely fortified" 并跳过该营养素。

### 坑 9：Oat milk 的 Energy 单位

SR Legacy 中 canola oil 和 sugar 的 Energy 字段可能是 kJ 不是 kcal (oil=3700 vs 884)。用 Atwater 4-4-9 公式检测：如果 `reported > 3× expected`（预期=4×protein + 4×carbs + 9×fat），除以 4.184。

### 坑 10：OFF 的 percent_estimate 不是 truth

OpenFoodFacts 里的大量 ingredient percentages 是 Product Opener / Recipe Estimator 根据配料顺序和营养成分估出来的，不是厂家标签真实声明。

**规则**：只把原标签里明示的百分比当 partial truth。`percent_estimate` / `percent_min` / `percent_max` 只能作为 baseline 或 weak evidence，不能作为 NuSol-T 的 ground truth、不能用来校准 priors。

### 坑 11：两个 FNDDS CSV output 目录名容易搞反

不要用：

- `output/fndds_csv_2019/`
- `output/fndds_csv_2020/`

这两个是早期失败目录。要用：

- `output/fndds_2019_csv/`
- `output/fndds_2020_csv/`

### 坑 12：文档之间有旧口径冲突

`docs/CURRENT_STATUS.md` 相对最新；`docs/PROGRESS.md`、`docs/SUMMARY.md` 可能仍有早期 “197 recipes” 阶段的旧叙述；`docs/BENCHMARK_RESULTS.md` 混合了 baseline、post-fix、yield-fix、fallback-fix 等不同阶段结果。

**规则**：引用 benchmark 数字前先打开对应 `output/*/benchmark_summary.json` 或 `benchmark_full.json` 核对。

### 坑 13：fortification 逻辑有重复实现风险

`src/nusol/adapters/mapping.py` 里有早期 fortificant code list；后续更应该以 `src/nusol/data/fortification.py` 的集中策略为准。不要在多个脚本里继续复制 fortificant 判断规则。

### 坑 14：不要过度声称 Branded Food 已经完成

Branded adapter/data reader 存在，不等于真实标签端到端可用。当前还缺：

- robust ingredient text parser；
- short-name ingredient mapper；
- additive/fortification provenance；
- partial-truth evaluator；
- branded/OFF YAML exporter。

### 坑 15：fallback solve 是恢复策略，不是 baseline

`weight=10 → weight=1 → wider interval` 能显著提高 solve success，但这属于 recovery path。报告时要分清：

- strict/default setting 的表现；
- fallback 后的表现；
- fallback 是否改变了 error distribution。

否则 reviewer 会质疑是不是通过放宽约束换来了高成功率。

### 坑 16：prior 目前主要来自专家规则和工程经验，不是数据校准模型

当前 Level 2 priors（fraction interval/group total/recipe center/anti-extreme/ratio）是可声明的机制。具体 prior 值多来自 nutrition/computation 经验、FNDDS/OFF 文献理解和人工规则，不是从大规模数据库统计学习出来的 calibrated priors。

**规则**：写文档时必须区分 “prior mechanism exists” 和 “prior library has been empirically calibrated”。

---

## 七、关键文件和入口点

### 求解入口
```bash
uv run nusol solve examples/oat_milk.yaml
uv run python -c "import nusol; print(nusol.solve('examples/oat_milk.yaml'))"
```

### Benchmark 运行
```bash
# 验证集快速测试
uv run python scripts/run_fndds_benchmark.py --limit 10

# 全量 FNDDS
uv run python scripts/run_fndds_benchmark.py --full --skip-export 2>&1

# Australia AFCD
uv run python scripts/run_afcd_benchmark.py
```

### 测试
```bash
uv run pytest -q                    # 全部 268 tests
uv run pytest tests/test_core/ -q   # 核心模块
```

### 代码结构
```
src/nusol/
├── api.py              ← solve() 单入口
├── cli.py              ← 命令行
├── config/             ← YAML schema + resolver
├── domain/             ← IngredientProblem, CompositionMatrix
├── compiler/           ← ConstraintCompiler → IR
├── constraints/        ← builtin constraint plugins
├── backends/           ← ScipySLSQP, HiGHS LP
├── priors/             ← Level 2 priors
├── results/            ← Typed SolveResult
├── data/               ← FNDDS, SR Legacy, Foundation, AFCD adapters
├── ingredient/         ← Parser (Phase 5 需要扩展)
└── adapters/           ← IngredientMapper (Phase 5 需要扩展)

scripts/
├── export_fndds_recipes.py   ← 核心: FNDDS→YAML (含全部修复)
├── run_fndds_benchmark.py    ← 批量 benchmark runner
├── run_afcd_benchmark.py     ← Australia AFCD benchmark
└── retry_failures.py         ← 手动修复失败配方

output/
├── fndds_benchmark/          ← 2024 JSON benchmark 结果
├── fndds_2021/               ← 2021 JSON benchmark
├── fndds_2022/               ← 2022 JSON benchmark
├── fndds_2019_csv/           ← 2019 CSV benchmark，真实可用目录
├── fndds_2020_csv/           ← 2020 CSV benchmark，真实可用目录
├── fndds_csv_2019/           ← stale failed run，不要引用
├── fndds_csv_2020/           ← stale failed run，不要引用
├── afcd/                     ← Australia AFCD benchmark
└── spike_fndds_ir/           ← 初期 spike 脚本

docs/
├── CURRENT_STATUS.md         ← 最新项目进度
├── BENCHMARK_RESULTS.md      ← Benchmark 完整结果
├── TECHNICAL_PRINCIPLES.md   ← 营养学原理 + 求解器设计
├── DETAILED_IMPROVEMENT_PLAN.md ← 深度 review + 改进路线
├── openfoodfacts_ingredient_estimate_deep_dive.md ← OFF 百分比估计机制分析
├── HANDOFF.md                ← 本文档
├── nutrition_scientist_report.html ← 面向营养学家的英文报告
└── fndds_benchmark_report.html     ← 面向开发者的英文报告
```

### 数据库路径
```
../db/
├── FoodData_Central_survey_food_json_2024-10-31/  ← 主力 FNDDS
├── FoodData_Central_survey_food_json_2022-10-28.json
├── FoodData_Central_survey_food_json_2021-10-28.json
├── FoodData_Central_survey_food_json_2019-csv.json  ← CSV 转换
├── FoodData_Central_survey_food_json_2020-csv.json  ← CSV 转换
├── FoodData_Central_sr_legacy_food_json_2018-04/   ← SR Legacy 配料数据库
├── FoodData_Central_foundation_food_json_2026-04-30/ ← Foundation Foods
├── FoodData_Central_branded_food_json_2026-04-30/   ← Branded Food (Phase 5备用)
└── Australia Food Composition Database/             ← AFCD Release 3 (Excel)
```

---

## 八、环境

- Python 3.12+ (via `uv`), macOS
- `uv sync` 安装依赖
- `uv add <package>` 添加新依赖
- `uv run pytest` 跑测试
- `uv run nusol solve ...` 跑求解器
- GitHub: `git push origin refactor/yaml-solver-framework`
