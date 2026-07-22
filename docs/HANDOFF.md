# NuSol-T 项目交接记录

> 日期: 2026-07-22 | 分支: `refactor/yaml-solver-framework` | 268 tests passing
> GitHub: https://github.com/CedarJin/NuSol-T

---

## 一、项目一句话概述

NuSol-T 是一个从包装食品 Nutrition Facts 标签 + 配料表反推配料比例的 YAML 驱动约束求解框架。已在 6 个 USDA/Australia 数据库上验证了 24,348 个配方，中位成功率 ~99%，中位误差 1.7-2.5pp（JSON FNDDS）/ 2.4pp（Australia）。

---

## 二、当前处于哪个 Phase

```
Phase 0-4 (FNDDS 验证阶段) ← ✅ 全部完成
Phase 5   (Branded Food Adapter) ← ⬜ 下一步，尚未开始
Phase 6-7 (应用+论文) ← ⬜ 未开始
```

**Phase 5 是当前瓶颈**：需要 IngredientParser（标签文本→结构化配料表）和 IngredientMapper（短名→USDA 标准名→营养成分）。FNDDS 验证已证明只要配料映射正确，求解器能以 1.7-2.5pp 中位误差反推比例。现在需要把 FNDDS 验证的成功经验搬到真实品牌食品上。

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
| 4 | CSV 2020 | `db/FoodData_Central_survey_food_json_2020-csv.json` | 6,054 | 99.1% | 6.3 pp | CSV→JSON转换 |
| 5 | CSV 2019 | `db/FoodData_Central_survey_food_json_2019-csv.json` | 5,802 | 98.9% | 8.6 pp | CSV→JSON转换 |
| 6 | AFCD Aus | `db/Australia Food Composition Database/` | 220 | 100% | 2.4 pp | Excel→Python adapter |

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

**Phase 5 尚未开始**。FNDDS 验证阶段已完成，需要切换到 Branded Food 应用。核心差距：

1. **FNDDS 配料名 = USDA 标准名**，映射准确率 99.9%（code-assisted L1-L4）
2. **Branded food 标签用短名**（"OATS" 不是 "Cereals, oats, regular and quick, not fortified, dry"）
3. **纯名称搜索 10% 找不到匹配**（from `mapping analysis`, section below）

需要建立一个短名→标准名的映射层。这是 Phase 5 的全部内容。

---

## 五、下一步具体怎么做

### 5.1 立即可做的

**IngredientParser** (标签文本→IngredientTree)：
- 输入: `"WATER, SUGAR, OATS, CANOLA OIL, CONTAINS 2% OR LESS OF: SALT, VITAMIN D2"`
- 输出: `{main: [...], two_percent: [...]}` 结构化配料表
- 已有基础代码: `src/nusol/ingredient/parser.py` (IngredientParser class)
- 需要: 处理括号嵌套, "CONTAINS 2% OR LESS OF:" 标记, 逗号分隔, 句号终止

**IngredientMapper** (短名→USDA标准名):
- 输入: `"OATS"` → 输出: `"Cereals, oats, regular and quick, not fortified, dry"` + SR Legacy profile
- 策略: 先试 exact match, 再试 substring, 再试 word-overlap (SR Legacy 已有这些)
- 还需要: manual mapping table for common branded food names

### 5.2 架构参考

```
Branded Food Label Text
  → IngredientParser → IngredientTree
  → IngredientMapper → USDA standard names + nutrient profiles
  → YAML 生成 (同 export_fndds_recipes.py 的逻辑)
  → solve(yaml_path)
```

### 5.3 从哪里开始写代码

1. 读 `src/nusol/ingredient/parser.py` — 了解现有 parser
2. 读 `src/nusol/adapters/mapping.py` — 了解现有 mapper
3. 读 `scripts/export_fndds_recipes.py` — 了解 YAML 生成逻辑 (这段可以直接复用)
4. 写一个新的 `scripts/export_branded_yaml.py` — branded food label → YAML

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
├── fndds_csv_2019/           ← 2019 CSV benchmark
├── fndds_csv_2020/           ← 2020 CSV benchmark
├── afcd/                     ← Australia AFCD benchmark
└── spike_fndds_ir/           ← 初期 spike 脚本

docs/
├── CURRENT_STATUS.md         ← 最新项目进度
├── BENCHMARK_RESULTS.md      ← Benchmark 完整结果
├── TECHNICAL_PRINCIPLES.md   ← 营养学原理 + 求解器设计
├── DETAILED_IMPROVEMENT_PLAN.md ← 深度 review + 改进路线
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
