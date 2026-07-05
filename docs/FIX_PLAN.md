# NuSol-T 修复计划

> 基于 `REVIEW.md`、`SCIENCE_REVIEW.md`、`DESIGN_IMPLEMENTATION_REVIEW.md` 三份 review 的真实代码核实结果
>
> 核实日期：2026-07-05 | 计划日期：2026-07-05
>
> **核实结论：三份 review 对代码的指控全部成立。所有标记为"严重"和"高"的问题均已在代码中确认。**

---

## 重构分支最新实现问题（2026-07-05 Review）

> 审查范围：`5579811..f21b68c`，即 YAML solver framework 的 Phase 0-9 实现。
>
> 验证结果：`pytest` 246 项通过；Ruff 仍有 262 个问题；mypy 未通过。测试通过不代表 YAML 声明已正确进入求解语义。

### 优先级总览

```text
R0（阻塞性——可能静默产生错误结果）:
  R0.1  CSV composition 按 YAML ingredient 顺序对齐
  R0.2  solve() 必须使用 resolved document
  R0.3  约束只能由 YAML 显式启用
  R0.4  constraint mode/weight 必须进入 IR 和 objective
  R0.5  solver、variable bounds 和 bounds region 必须按 YAML 执行

R1（高优先级——配置被接受但未执行）:
  R1.1  priors 不得静默丢弃
  R1.2  unique_source 未实现时必须显式失败
  R1.3  校验 CSV checksum，并记录资源 manifest
```

### R0.1 — CSV composition 与变量顺序可能错配

**文件**：
- `src/nusol/domain/composition.py:165-201`
- `src/nusol/domain/validation.py:22-32`
- `src/nusol/compiler/compiler.py:33-35`

**问题**：CSV loader 按 CSV 行顺序生成矩阵，compiler 却按 YAML ingredient 顺序解释矩阵行。当前验证只检查 YAML 原料是否存在于 CSV，不检查顺序，也不重新排序。两边集合相同但顺序不同时，A 原料的营养组成会静默应用到 B 变量。

**修复**：CSV loader 接收 YAML `ingredient_ids` 和声明的 nutrient schema，按 YAML 顺序选择并排列行列；拒绝缺失、重复和未授权的额外原料/营养素。

**测试**：构造 YAML 顺序 `[a, b]`、CSV 顺序 `[b, a]`，验证编译后的每一行仍对应正确原料。

---

### R0.2 — `solve()` 没有使用 resolved YAML

**文件**：`src/nusol/api.py:65-75`

**问题**：API 使用 `ConfigLoader.load_from_path()` 返回的原始文档构建 domain model；`ConfigResolver` 的结果仅用于 manifest checksum。`extends`、父配置、merge 和 resolver defaults 因而不会进入实际求解。

**修复**：只调用 `ConfigResolver.resolve()` 获取唯一的 `SolveDocument`，domain builder、compiler、solver 和 manifest 全部基于同一个 resolved document。避免分别加载两次配置。

**测试**：父 YAML 提供 composition/constraints，子 YAML 通过 `extends` 覆盖 observation；验证 `solve(child)` 使用合并后的配置并与显式 resolved YAML 结果一致。

---

### R0.3 — 未声明的 mass balance 和 ingredient order 被自动启用

**文件**：
- `src/nusol/domain/builder.py:73-85`
- `src/nusol/compiler/compiler.py:48-76`

**问题**：`constraint_configs` 以约束实例 ID 为键，例如 `total_mass`；compiler 却读取固定键 `mass_balance` 和 `ingredient_order`，查找失败后以 `enabled=True` 为默认值。因此即使 YAML 没有声明这些约束，它们也会被加入 IR。

**修复**：compiler 仅遍历 enabled constraint instances，根据其 `type` 调用 registry。删除 special-case 默认启用逻辑；若质量守恒是模型不变量，应在 schema/model 中明确声明为不可关闭的模型语义，而不是伪装成可选 constraint。

**测试**：空 constraints、仅 mass balance、仅 ingredient order、使用自定义 constraint ID 四种情况分别断言 IR 内容。

---

### R0.4 — constraint `mode` 和 `weight` 没有进入真实求解目标

**文件**：
- `src/nusol/compiler/compiler.py:78-117`
- `src/nusol/backends/scipy_slsqp.py:54-74,138-142`

**问题**：observation 被固定编译为 `mode="soft"`、`weight=10.0`，忽略 YAML constraint 的 mode/weight。SLSQP 虽读取了 IR weight，但 objective 只计算 `sum(slack²)`，没有乘权重。因此修改 YAML weight 不会改变最优解，hard nutrient interval 也无法表达。

**修复**：明确 observation 与 `nutrient_interval` constraint instance 的关联；将 mode、loss 和 weight 编译进 IR。SLSQP objective 使用 `sum(weight_i * slack_i²)`，并为 hard interval 生成无 slack 的硬约束。

**测试**：
- 同一冲突问题使用不同 weight，最优点应向高权重 observation 移动；
- hard interval 不可满足时必须返回 infeasible；
- weight=1 与 weight=100 的 objective 数值和解均符合预期。

---

### R0.5 — solver、变量边界和 bounds region 配置被忽略

**文件**：
- `src/nusol/api.py:77-97`
- `src/nusol/compiler/compiler.py:38-42`
- `src/nusol/config/schema.py:202-238`

**问题**：API 无条件实例化并运行 SLSQP 和 HiGHS，不读取 YAML backend/options；point-only 配置仍执行 bounds，bounds-only 配置仍执行 point。变量上下界固定为 `[0,1]`。`explicit_slack_budget` 及其 budgets 也没有进入 bounds IR。

**修复**：由 resolved solver spec 选择 backend、传递 options 并决定执行哪些任务；VariableIR 使用 YAML bounds；为 `explicit_slack_budget` 定义明确 IR，无法支持时在 compile-time 报 capability error。

**测试**：覆盖 point-only、bounds-only、自定义 bounds、自定义 SLSQP options、显式 slack budget，以及不兼容 backend 的失败路径。

---

### R1.1 — priors 被 schema 接受但静默丢弃

**文件**：
- `src/nusol/domain/builder.py:86-99`
- `src/nusol/domain/problem.py:48-51`
- `src/nusol/compiler/compiler.py`

**问题**：builder 只保留 prior ID，丢失 type、weight、config 和 evidence；compiler 完全不处理 prior。合法 YAML prior 对结果没有任何作用，也没有 warning/error。

**修复**：在 prior registry 和 IR 实现前，包含 enabled prior 的文档必须显式报 `UnsupportedPriorError`；实现后保留完整 typed prior 并通过 registry 编译。禁止静默忽略。

**测试**：未支持 prior 必须失败；已注册 prior 必须改变 IR，并在 manifest 中记录名称、版本和 evidence。

---

### R1.2 — `unique_source` 注册为可用但 compile 永远返回空

**文件**：`src/nusol/constraints/builtin/unique_source.py:14-27`

**问题**：registry 对外宣称支持 `unique_source`，但其 compile function 无条件返回空列表。YAML 启用该约束后既不报错，也不生成任何 IR。

**修复**：完成 composition-aware compiler context 之前，从 builtin registry 移除该类型或抛出 `UnsupportedConstraintError`。实现后至少验证 dominance threshold、营养素存在性和下界推导。

**测试**：当前阶段启用必须显式失败；完成后断言唯一营养来源产生正确的 ingredient lower bound。

---

### R1.3 — CSV `sha256` 未校验且资源未进入 manifest

**文件**：
- `src/nusol/config/schema.py:86-93`
- `src/nusol/domain/builder.py:51-57`
- `src/nusol/api.py:132-171`

**问题**：schema 要求 CSV checksum，但 builder 加载文件时完全未校验；manifest 只记录 resolved config checksum，没有记录数据文件路径和实际 checksum。数据文件被替换后，相同 YAML 可以得到不同结果而不被检测。

**修复**：相对资源路径以 YAML 文件目录为基准解析；加载前计算实际 SHA-256 并与声明值比较；manifest 保存 resolved path、declared checksum、actual checksum 和验证状态。

**测试**：正确 checksum 通过，错误 checksum 在 build 前失败；相对路径不依赖当前工作目录；manifest 可追溯实际资源。

---

## 修复优先级总览

```
Priority 0 (阻塞性 — 结果完全不可信):
  F0.1  MAE 改用配料并集计算
  F0.2  BoundSolver 不可行返回正确失败状态
  F0.3  penalty 四次方 → 二次方
  F0.4  80%/95% coverage 使用不同区间
  F0.5  zero_slack_rate 范围修正为 [0, 1]

Priority 1 (科学基础 — 公式/常量错误):
  F1.1  脂肪酸 nutrient ID 修正
  F1.2  energy closure fiber 重复计能修正
  F1.3  water-solid closure fiber 重复计数修正
  F1.4  水分参数单位统一
  F1.5  IU 转换 bug 修正
  F1.6  added-sugar 约束逻辑修正

Priority 2 (约束体系 — 配置与求解器断开):
  F2.1  QPSolver/BoundSolver 接入完整约束体系
  F2.2  YAML 约束名与代码注册名对齐
  F2.3  实现 YAML extends/merge 逻辑
  F2.4  实现缺失的约束类 (unique_source, similarity_anti_extreme)
  F2.5  G0-G7 消融定义修正

Priority 3 (端到端 — CLI/Pipeline/可复现):
  F3.1  实现 CLI forward/inverse/ablation 命令
  F3.2  修复 CLI config 路径拼接
  F3.3  创建默认主配置文件
  F3.4  200-recipe benchmark 可复现脚本 + manifest

Priority 4 (数据质量 — 适配器/解析器):
  F4.1  FNDDS 使用稳定 ingredient ID 作键
  F4.2  Branded Food basis/unit 正确处理
  F4.3  嵌套括号解析器重写
  F4.4  缺失/零/低于检出限 营养值区分

Priority 5 (Trust & Reporting):
  F5.1  Trust score 按营养素单位归一化
  F5.2  Identifiability 改用矩阵秩
  F5.3  Ensemble 保存 p5/p95 到 SolverResult
  F5.4  区分 feasible bounds / ensemble quantile / credible interval

Priority 6 (文档对齐):
  F6.1  新增 CURRENT_STATUS.md
  F6.2  PROGRESS.md 修正完成状态
  F6.3  DEVELOPMENT.md 标记为 target design
  F6.4  SUMMARY.md 修正
  F6.5  README 补全
```

---

## Priority 0：阻塞性修复（结果语义正确性）

### F0.1 — MAE 改用配料并集计算

**文件**：`src/nusol/validation/metrics.py:148-155`

**问题**：当前 `common = set(true_frac) & set(est_frac)` 只计算交集，漏预测的配料完全不参与 MAE，系统性美化 benchmark。

**修复**：
```python
# 当前 (错误)
common = set(true_frac) & set(est_frac)
if common:
    errors = [abs(true_frac[k] - est_frac.get(k, 0)) for k in common]

# 修复后
all_ingredients = set(true_frac) | set(est_frac)
errors = [abs(true_frac.get(k, 0.0) - est_frac.get(k, 0.0)) for k in all_ingredients]
```

同时新增 `mapping_coverage` 指标：`len(common) / len(all_ingredients)`，把"名称映射失败"和"比例估计误差"分开。

**测试**：新增 test — true={"a":0.5,"b":0.5}, est={"a":0.5} → MAE 应为 0.25 而非 0.0。

---

### F0.2 — BoundSolver 不可行返回正确失败状态

**文件**：`src/nusol/solver/bound_solver.py:113-149`

**问题**：linprog 失败或异常时，`x_lower=0.0, x_upper=1.0`，最后无条件 `success=True`。不可行被伪装为"完整可行区间"。

**修复**：
1. 在求解前增加可行性检测 LP（单独跑一次 linprog 检测 feasibility）
2. 任一 bound LP 失败时，记录状态和原因（infeasible / unbounded / numerical_error）
3. 只有全部 LP 成功才返回 `success=True`
4. 在 SolverResult 中增加 `bound_status: dict[str, str]` 字段，记录每个 bound 的状态

**测试**：新增 test — 不满足约束的 context（如唯一配料营养值=1 但标签要求 [2,3]），应返回 `success=False`。

---

### F0.3 — penalty 四次方 → 二次方

**文件**：
- `src/nusol/constraints/base.py:26-31`（penalty property）
- `src/nusol/constraints/energy_closure.py:73`
- `src/nusol/constraints/water_solid.py:78`
- `src/nusol/constraints/sodium_balance.py:52`
- `src/nusol/constraints/added_sugar_balance.py:72`
- `src/nusol/constraints/fatty_acid_closure.py:63`

**问题**：各约束已在 `evaluate()` 中将偏差平方写入 `violation`，`penalty` property 又平方一次 → 四次方。实际 penalty = weight × deviation⁴。

**修复（方案 A — 推荐）**：
- `violation` 统一存储**未平方**的非负偏差
- `penalty` property 负责平方：`self.weight * self.violation ** 2`
- 所有 constraint 的 `evaluate()` 改为存储原始偏差（不平方）

**修复（方案 B）**：
- `violation` 存储平方偏差
- `penalty` property 改为：`self.weight * self.violation`（不再平方）

推荐方案 A，因为 `violation` 字段语义更清晰（"偏差大小"而非"偏差平方"）。

**测试**：新增 test — 偏差=2、weight=10 → penalty=40（非 160）。

---

### F0.4 — 80%/95% coverage 使用不同区间

**文件**：`src/nusol/validation/metrics.py:176-195`

**问题**：`coverages_80` 和 `coverages_95` 使用相同的 `lo`/`hi`（来自 BoundSolver 的 feasible bounds），两者永远相等。

**修复**：
1. `compute_inverse_metrics()` 分别接收 `estimated_lower_80`/`estimated_upper_80` 和 `estimated_lower_95`/`estimated_upper_95`（或单独接收 ensemble 结果从中抽取 p10/p90 和 p2.5/p97.5）
2. feasible bounds（BoundSolver）单独称为 `feasible_bound_coverage`
3. 80%/95% interval 来自 EnsembleSolver 的分位数

**测试**：新增 test — 提供不同的 80% 和 95% 边界，验证 coverage 不同。

---

### F0.5 — zero_slack_rate 范围修正

**文件**：`src/nusol/validation/metrics.py:198-210`

**问题**：公式 `1 - sum(counter.values()) / len(active_constraints)`，单个样本有多个冲突时结果为负。

**修复**：
```python
# 改为计算"没有任何冲突的样本比例"
n_no_conflict = sum(1 for ac in active_constraints if not ac)
metrics.zero_slack_rate = n_no_conflict / len(active_constraints) if active_constraints else 1.0
```

如需"平均冲突数"，用独立字段 `avg_conflicts_per_sample`。

**测试**：新增 test — active_constraints 包含 [["a","b"], ["a"]] → zero_slack_rate=0.0, avg_conflicts=1.5。

---

## Priority 1：科学基础修复

### F1.1 — 脂肪酸 nutrient ID 修正

**文件**：`src/nusol/core/nutrient_registry.py:25-27`

**问题**：
```python
# 当前 (错误)
(1292, "606", "Fatty acids, total saturated", "g", 970),       # 应为 1258
(1293, "607", "Fatty acids, total monounsaturated", "g", 11400), # 应为 1292
(1294, "608", "Fatty acids, total polyunsaturated", "g", 11500), # 应为 1293
```

**USDA FNDDS 正确 ID**（依据 USDA FNDDS 2017-2018 Documentation）：
- 1258 → Fatty acids, total saturated
- 1292 → Fatty acids, total monounsaturated
- 1293 → Fatty acids, total polyunsaturated

**修复**：
```python
(1258, "606", "Fatty acids, total saturated", "g", 970),
(1292, "607", "Fatty acids, total monounsaturated", "g", 11400),
(1293, "608", "Fatty acids, total polyunsaturated", "g", 11500),
```

如需保留 1294，应确认其对应哪个脂肪酸类型。

**测试**：新增 test — `registry.get_by_id(1258)["name"]` == "Fatty acids, total saturated"。

---

### F1.2 — energy closure fiber 重复计能修正

**文件**：`src/nusol/constraints/energy_closure.py:59-70`

**问题**：`Carbohydrate, by difference` 已包含 dietary fiber。代码又加 `2 × fiber`，等于 fiber 被算了 6 kcal/g（4 kcal from carb + 2 kcal separately）。

**修复**：
```python
# 当前 (错误)
calc_energy = 4*protein + 9*fat + 4*carb + 2*fiber + 7*alcohol

# 修复后 — 使用 carb-by-diff 时不单独加 fiber
calc_energy = 4*protein + 9*fat + 4*carb + 7*alcohol
```

如果确实想区分 fiber 的能量贡献（2 kcal/g vs 4 kcal/g），则需要使用 available carbohydrate 而非 by-difference，公式改为：`4*protein + 9*fat + 4*available_carb + 2*fiber + 7*alcohol`。当前 USDA 数据为 by-difference 模式，推荐第一种修复。

同样修复 `src/nusol/nutrition/forward.py:116-122` 的 `compute_energy_from_macronutrients()`。

**测试**：新增 test — carb=50g, fiber=5g (carb-by-diff 已含 fiber) → energy 应排除 fiber 单独计能。

---

### F1.3 — water-solid closure fiber 重复计数修正

**文件**：`src/nusol/constraints/water_solid.py:60-75`

**问题**：同时加入 `Carbohydrate, by difference` 和 `Fiber, total dietary`。carb-by-diff 本身 = 100 - water - protein - fat - ash - alcohol，已包含 fiber。

**修复**：
```python
# 如果使用 carb-by-diff：不加 fiber
total = water + protein + fat + carb + ash + alcohol

# 如果必须加入 fiber：改用 "available carbohydrate" 替代 carb-by-diff
```

推荐第一种（与 USDA derivation 一致）。

**测试**：新增 test — 验证总和在 100±2g 范围内（不含重复 fiber）。

---

### F1.4 — 水分参数单位统一

**文件**：
- `src/nusol/nutrition/forward.py:33-67`
- `src/nusol/config/loader.py:74-77`
- `tests/test_nutrition/test_forward.py:37-50`

**问题**：docstring 说 `0.05 = 5%`（暗示 fraction=0.05），但公式 `100/(100-x)` 把 x 当百分数（5 而非 0.05）。测试传 `10.0`（百分数），与接口文档矛盾。

**修复（推荐方案 — 统一为 fraction）**：
```python
# forward.py
def compute(self, ..., moisture_change: float = 0.0):
    ...
    if self.moisture_enabled and abs(moisture_change) > 1e-10:
        yield_factor = 1.0 / (1.0 - moisture_change)  # fraction 版本
        predicted = predicted * yield_factor
```

同步修改：
- `config/loader.py:77` 的 `default_bounds` 改为 `[-0.30, 0.30]`（已经是 fraction，不变）
- docstring 改为：`moisture_change: 0.05 = 5% moisture loss (as fraction)`
- 测试改用 fraction：`moisture_change=0.10` → 期望浓度因子 ≈1.111

**测试**：修复已有 test（传 fraction 0.10 而非百分数 10.0），新增边界测试（0%、-20%、+30%）。

---

### F1.5 — IU 转换 bug 修正

**文件**：`src/nusol/core/units.py:22-68`

**问题**：`_IU_CONVERSIONS` 把 Vitamin E 标为 `0.67 (IU → mg)`，即 1 IU = 0.67 mg。但 `convert_iu()` 中 `to_unit == "mg"` 分支执行 `value * 0.67 * 0.001 = 0.00067 mg`，多除了 1000。

Vitamin A 的 0.3 µg RAE/IU 同样有问题：racemic retinol 0.3 µg RAE/IU，dietary beta-carotene 0.05 µg RAE/IU。无化学形式信息时不可确定。

**修复**：
```python
# 修正 _IU_CONVERSIONS 为统一到 µg 的因子
_IU_CONVERSIONS: dict[str, dict[str, float]] = {
    "Vitamin D": {"to_unit": "µg", "factor": 0.025},
    "Vitamin E (alpha-tocopherol)": {"to_unit": "mg", "factor": 0.67},
    # Vitamin A: 需要化学形式，移除硬编码
}

@classmethod
def convert_iu(cls, value: float, nutrient_name: str, to_unit: str) -> float | None:
    """Returns None if conversion is not possible (e.g., unknown form)."""
    conv = cls._IU_CONVERSIONS.get(nutrient_name)
    if conv is None:
        return None  # 不可转换
    base_value = value * conv["factor"]
    # 从 conv["to_unit"] 转换到目标 to_unit
    ...
```

对 Vitamin A，未知形式时返回 `None` 而非猜测。

**测试**：新增 test — 1 IU Vitamin E → mg 应为 0.67（非 0.00067）；Vitamin A 未知形式返回 None。

---

### F1.6 — added-sugar 约束逻辑修正

**文件**：`src/nusol/constraints/added_sugar_balance.py:56-72`

**问题**：计算了 `sugar_from_sources`（来自 sugar keyword 配料的总糖贡献），但 violation 用的是 `max(0, added_sugar - total_sugar)`，`sugar_from_sources` 完全没有参与约束判断。

**修复**：
```python
# 有 sugar ingredients 时：added sugar 不应超过 sugar_from_sources
violation = max(0, added_sugar - sugar_from_sources) ** 2  # ← 用 sugar_from_sources

# 无 sugar ingredients 时：added sugar 应接近 0（保持不变，逻辑正确）
```

同时确认 `Sugars, added` 列是否真实存在于配料 nutrient matrix 中——多数 SR Legacy/Foundation 记录没有此字段，缺失值不应被当 0。

**测试**：新增 test — 有 sugar source 配料但 added sugar 超标 → 应产生 violation。

---

## Priority 2：约束体系连通

### F2.1 — QPSolver/BoundSolver 接入完整约束体系

**文件**：
- `src/nusol/solver/qp_solver.py:42-55, 102-140`
- `src/nusol/solver/bound_solver.py:34-149`

**问题**：两个求解器都忽略了传入的 `constraints` 和 `builder` 参数，只硬编码 mass balance、ingredient order、label interval 三类约束。这是项目核心设计承诺未实现。

**修复分两步**：

**Step 1 — 线性约束自动转化**：
在 QPSolver 和 BoundSolver 中增加约束注册机制，将支持线性表达的约束自动转化为 scipy 约束矩阵：

```python
# 约束分为两类：
# A) 可线性化 → 自动转为 Ax ≤ b 或 scipy constraint
# B) 非线性/软约束 → 仅 PenaltySolver 或增强 QP objective 处理

LINEARIZABLE_CONSTRAINTS = {
    "mass_balance",        # → A_eq
    "ingredient_order",    # → A_ub
    "label_interval_fit",  # → A_ub (already handled)
    "two_percent_rule",    # → A_ub: x_i ≤ 0.02 for 2% ingredients
    "fatty_acid_closure",  # → A_ub: Σsat+mono+poly ≤ total_fat
}
```

QPSolver.solve() 改为：
1. 接收 builder 构建的约束列表
2. 对每个约束调用 `to_scipy_constraint()` 或 `to_linear_matrix()` 
3. 无法线性化的约束 → 记录 warning 而非静默忽略
4. 未知约束名 → 报错

**Step 2 — 未知约束显式报错**：
```python
UNSUPPORTED_IN_QP = {"category_prior", "sodium_balance", "added_sugar_balance",
                      "energy_closure", "water_solid_balance"}
# 如果这些约束 enabled=True 但传入 QPSolver → 报错/user warning
# 用户在 config 中必须显式选择支持非线性约束的求解器
```

**测试**：新增 test — 传入包含 two_percent_rule 的约束列表，验证 QPSolver 确实施加了 ≤2% 约束。传入不支持的约束，验证报 warning 或 error。

---

### F2.2 — YAML 约束名与代码注册名对齐

**文件**：
- `src/nusol/constraints/base.py:110-121`（代码注册表）
- `config/constraints/default.yaml`
- `config/constraints/*.yaml`

**问题**：

| YAML 名称 | 代码注册名 | 状态 |
|-----------|-----------|------|
| `mass_balance` | `mass_balance` | ✅ 一致 |
| `ingredient_order` | `ingredient_order` | ✅ 一致 |
| `label_interval_fit` | `label_interval_fit` | ✅ 一致 |
| `sodium_source_balance` | `sodium_balance` | ❌ 不一致 |
| `added_sugar_source` | `added_sugar_balance` | ❌ 不一致 |
| `unique_source_lower_bound` | — | ❌ 无对应代码 |
| `similarity_anti_extreme` | — | ❌ 无对应代码 |
| `water_mass_prior` | — | ❌ 无对应代码 |
| `flour_mass_prior` | — | ❌ 无对应代码 |
| `oil_vs_meat_prior` | — | ❌ 无对应代码 |

**修复**：
1. 建立**唯一权威注册表** → 从 Pydantic model 生成，代码和 YAML 共用
2. 统一命名：全部改为代码中的注册名（`sodium_balance`、`added_sugar_balance`）
3. 更新所有 YAML 文件匹配
4. ConfigLoader 加载时对未知约束名 **报错而非静默忽略**
5. 所有约束 **默认 disabled**，只有显式配置才启用

---

### F2.3 — 实现 YAML extends/merge 逻辑

**文件**：`src/nusol/config/loader.py`、`config/constraints/*.yaml`

**问题**：所有品类 YAML 声明 `extends: default`，但 ConfigLoader 完全没有继承/合并逻辑。

**修复**：
```python
class ConfigLoader:
    def load_with_extends(self, config_path: str) -> dict:
        """Load YAML and resolve extends chain."""
        data = self.load(config_path)
        base_name = data.get("extends")
        if base_name:
            base_path = self.config_dir / f"{base_name}.yaml"
            base_data = self.load_with_extends(str(base_path))
            data = self._deep_merge(base_data, data)  # child overrides parent
        return data

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """Recursively merge override into base."""
        result = copy.deepcopy(base)
        for k, v in override.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = ConfigLoader._deep_merge(result[k], v)
            else:
                result[k] = copy.deepcopy(v)
        return result
```

**测试**：新增 test — dairy_desserts.yaml extends default → 验证继承了 default 的所有约束且覆盖了特定字段。

---

### F2.4 — 实现缺失的约束类

**需要新增的约束**（按实现难度排序）：

**a) `UniqueSourceLowerBound`**（P3 硬约束，已在测试中验证有效）：
```python
class UniqueSourceLowerBound(ConstraintBase):
    """当某营养素 >90% 来自唯一配料时，x_i ≥ lo_j / density_i."""
    priority = ConstraintPriority.P3
    name = "unique_source_lower_bound"

    def to_scipy_constraint(self, context):
        # 找出唯一来源营养素 → 构建 x_i ≥ lb 的线性不等式
        ...
```

**b) `SimilarityAntiExtreme`**（P4 软约束，防止相似配料极端分布）：
```python
class SimilarityAntiExtreme(ConstraintBase):
    """当两个配料 cosine similarity > 0.95 时，防止比例极端不对称."""
    priority = ConstraintPriority.P4
    name = "similarity_anti_extreme"

    def evaluate(self, x, context):
        # 找出高相似度配料对 → 惩罚 |x_i - x_j| > max_imbalance
        ...
```

**c) 品类特定约束**（P4，YAML 已有定义）：
- `FlourMassPrior`（烘焙：面粉 40-70%）
- `OilVsMeatPrior`（肉类：油不超过肉）
- `WaterMassPrior`（汤类：水 40-90%）

这些作为 soft penalty constraint 实现，只在对应品类配置启用时才生效。

---

### F2.5 — G0-G7 消融定义修正

**文件**：`src/nusol/validation/ablation.py:13-23`

**问题**：G5、G6、G7 约束列表完全相同。G4 加 two_percent，但文档描述为 moisture。

**修复**：唯一定义，与文档对齐：
```python
ABLATION_LEVELS: dict[str, list[str]] = {
    "G0": ["mass_balance"],
    "G1": ["mass_balance", "ingredient_order"],
    "G2": ["mass_balance", "ingredient_order", "label_interval_fit"],
    "G3": ["mass_balance", "ingredient_order", "label_interval_fit",
           "energy_closure"],
    "G4": ["mass_balance", "ingredient_order", "label_interval_fit",
           "energy_closure", "two_percent_rule"],
    "G5": ["mass_balance", "ingredient_order", "label_interval_fit",
           "energy_closure", "two_percent_rule", "water_solid_balance",
           "sodium_balance"],
    "G6": ["mass_balance", "ingredient_order", "label_interval_fit",
           "energy_closure", "two_percent_rule", "water_solid_balance",
           "sodium_balance", "added_sugar_balance", "fatty_acid_closure"],
    "G7": ["mass_balance", "ingredient_order", "label_interval_fit",
           "energy_closure", "two_percent_rule", "water_solid_balance",
           "sodium_balance", "added_sugar_balance", "fatty_acid_closure",
           "category_prior"],
}
```

要求：后一级严格包含前一级 + 一个新约束。增加测试断言 `set(G{i}) ⊂ set(G{i+1})`。

---

## Priority 3：端到端 Pipeline

### F3.1 — 实现 CLI forward/inverse/ablation 命令

**文件**：`src/nusol/cli.py:46-101`

**修复 `run-forward`**：
```python
@app.command()
def run_forward(...):
    """Run forward nutrition calculation on FNDDS recipes."""
    config = load_config(config_path)
    adapter = FNDDSDataAdapter(config.get("data", {}))
    adapter.load(config["data"]["fndds_path"])
    model = ForwardNutritionModel(config.get("forward_model", {}))

    recipe = adapter.get_recipe(fdc_id)
    fractions = adapter.get_ingredient_fractions(fdc_id)
    matrix, profiles, nut_names, _ = adapter.get_ingredient_nutrient_matrix(fdc_id, ...)

    x = np.array(list(fractions.values()))
    A = _build_numpy_matrix(matrix, nut_names)
    predicted = model.compute(x, A)

    true_nutrients = recipe["final_nutrients"]
    _print_comparison(nut_names, predicted, true_nutrients)
    _save_output(output_dir, ...)
```

**修复 `run-inverse`**：
完整链路：config → adapter → context → QPSolver → BoundSolver → TrustReport → 输出。

**修复 `run-ablation`**：
遍历 G0-G7 → 每个 level 跑 inverse → 汇总 MAE/Coverage → 输出表格。

---

### F3.2 — 修复 CLI config 路径拼接

**文件**：
- `src/nusol/config/loader.py:31`
- `src/nusol/cli.py:47-60`

**问题**：`ConfigLoader("config")` + `load("config/fndds_forward.yaml")` → `config/config/fndds_forward.yaml`。

**修复**：
CLI 中统一使用 `load_config()` 顶层函数（`loader.py:129-146`），它自动判断是路径还是 config name：

```python
# cli.py 中改为
from nusol.config import load_config
data = load_config(config_path)  # 自动处理路径 vs 名称
```

或者 CLI 中将绝对路径传给 `load_from_path()`。

---

### F3.3 — 创建默认主配置文件

**新建文件**：
- `config/fndds_forward.yaml` — FNDDS forward 验证配置
- `config/fndds_inverse.yaml` — FNDDS inverse 求解配置
- `config/fndds_labelized.yaml` — FNDDS 标签化模拟配置
- `config/branded_inverse.yaml` — Branded Food inverse 配置

**fndds_inverse.yaml 示例**：
```yaml
run_id: fndds_inverse_200
data:
  fndds_path: ../db/FoodData_Central_survey_food_json_2024-10-31/surveyDownload.json
  foundation_path: ../db/FoodData_Central_foundation_food_json_2026-04-30/...
  sr_legacy_path: ../db/FoodData_Central_sr_legacy_food_json_2018-04/...
  validation_ids: config/validation_recipes.json

inverse_solver:
  solver:
    qp_method: SLSQP
    max_iter: 500
    bound_solver:
      enabled: true
  constraints:
    mass_balance: {enabled: true, priority: P0}
    ingredient_order: {enabled: true, priority: P1}
    label_interval_fit: {enabled: true, priority: P2}
    # P3/P4 constraints default to disabled for FNDDS validation
    energy_closure: {enabled: false}
    water_solid_balance: {enabled: false}
    # ... etc

reporting:
  output_dir: ./output/fndds_inverse
  formats: [json, csv]
```

---

### F3.4 — 200-recipe benchmark 可复现脚本

**新建**：`scripts/benchmark_fndds_200.py`

```python
"""200-recipe FNDDS inverse benchmark — 完全可复现.

Usage:
    uv run python scripts/benchmark_fndds_200.py

Output:
    output/benchmark_200/
      ├── manifest.json       # config hash, git commit, timestamps
      ├── results.csv         # per-recipe MAE, coverage, trust grade
      ├── failures.csv        # failed recipes with reasons
      ├── summary.json        # aggregate metrics
      └── config_snapshot.yaml
"""
```

**manifest 必须包含**：
- git commit hash
- 数据库文件 checksum (SHA256)
- 完整 config
- Python / 依赖版本 (pip freeze)
- 运行时间戳
- 成功/失败/跳过计数
- per-recipe 诊断（映射源分布、active constraints、bound widths）

---

## Priority 4：数据质量

### F4.1 — FNDDS 使用稳定 ingredient ID 作键

**文件**：`src/nusol/data/fndds.py:129-145, 268-297`

**修复**：
- 内部使用 `(ingredient_code, sequence_number)` 或生成 UUID 作为稳定 key
- `get_ingredient_fractions()` 返回 `dict[str, float]`，key = `f"{code}_{seq}"`，value 额外带 description
- `get_ingredient_nutrient_matrix()` 同上
- 展示层（TrustReport）再映射回 description

如果业务上需要合并同名配料，显式检测并 sum，同时验证 nutrient profile 是否一致。

---

### F4.2 — Branded Food basis/unit 正确处理

**文件**：`src/nusol/data/branded.py:62-74, 97-121`

**修复**：
1. 根据 USDA GBFPD 的 `derivationCode` 判断 basis（per 100g / per 100mL / per serving）
2. 保留 `servingSizeUnit`（g, mL, oz...）
3. 实现 density map（饮料 ~1 g/mL，油 ~0.92 g/mL...），未知密度时标记而非假设 1 g/mL
4. 已经是 per 100g 的数据不再标为 per_serving

---

### F4.3 — 嵌套括号解析器重写

**文件**：`src/nusol/ingredient/parser.py:93-160`

**问题**：`_smart_split()` 可以跟踪括号深度但只用于逗号分割。`_parse_single_ingredient()` 用 `r"\(([^)]+)\)"` 无法处理嵌套。

**修复**：使用栈式解析器：
```python
def _extract_parenthetical(self, text: str) -> tuple[str, str | None]:
    """用栈匹配最外层括号，正确处理嵌套."""
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == '(':
            if depth == 0:
                start = i
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0 and start >= 0:
                inner = text[start+1:i]
                outer = (text[:start] + text[i+1:]).strip()
                return outer, inner
    return text, None  # 无括号或不平衡
```

同时：括号不平衡时报错而非静默继续（当前 `_smart_split` 的 depth 可能变负数）。

---

### F4.4 — 缺失/零/低于检出限 营养值区分

**文件**：
- `src/nusol/data/fndds.py:63-70`
- `src/nusol/data/sr_legacy.py:229-246`
- `src/nusol/data/foundation.py:78-95`

**修复**：扩展 NutrientRecord schema：
```python
class NutrientRecord(BaseModel):
    ...
    missingness: str = "measured"  # measured | calculated | imputed | below_loq | missing | omitted
    loq: Optional[float] = None   # Limit of quantification
    sample_count: Optional[int] = None
```

Matrix 构建时：
- `missing` → NaN（不参与约束，不假设为 0）
- `below_loq` → [0, LOQ] 区间
- `measured` → 正常值
- 求解器处理 NaN：跳过对应营养素约束

这是一个较大的改动，需要逐步推进。短期方案：至少把 `missing` 和 `true zero` 区分，用 NaN 标记缺失。

---

## Priority 5：Trust & Reporting

### F5.1 — Trust score 按营养素单位归一化

**文件**：`src/nusol/report/trust_grade.py:35-45`

**修复**：不使用绝对残差（mg 和 g 不可比），改用相对残差或 label interval width 归一化：

```python
# 方案 A：按 label interval width 归一化
for name, residual in residuals.items():
    interval = label_intervals.get(name)
    if interval and interval[1] - interval[0] > 0:
        normalized = residual / (interval[1] - interval[0])
    else:
        normalized = residual / max(abs(target_value), 1.0)
    max_normalized = max(max_normalized, normalized)
```

同样：区分"数据库缺失导致的残差"和"模型不匹配"。

---

### F5.2 — Identifiability 改用矩阵秩

**文件**：`src/nusol/report/trust.py:119-154`

**修复**：
```python
def _build_identifiability(self, ...):
    # 构建有效约束矩阵
    # identifiability = n_ingredients - rank(effective_constraint_matrix)
    # null_space = 无法识别的方向
    A_eff = self._build_effective_constraint_matrix(...)
    rank = np.linalg.matrix_rank(A_eff, tol=1e-8)
    degrees_of_freedom = max(0, n_ingredients - 1 - rank)
    ...
```

---

### F5.3 — Ensemble 保存 p5/p95 到 SolverResult

**文件**：
- `src/nusol/solver/ensemble_solver.py:105-131`
- `src/nusol/core/schema.py:266-302`

**修复**：
1. `SolverResult` 增加字段：`x_p5: dict[str, float]`、`x_p95: dict[str, float]`
2. `EnsembleSolver.solve()` 将计算好的 `x_p5`/`x_p95` 写入返回结果
3. `TrustReport._build_ingredient_estimates()` 分别使用 ensemble 的分位数和 BoundSolver 的 feasible bounds

---

### F5.4 — 区分 feasible bounds / ensemble quantile / credible interval

**涉及文件**：
- `src/nusol/core/schema.py:169-181`（IngredientEstimate）
- `src/nusol/report/trust.py:89-117`
- `src/nusol/validation/metrics.py:44-45`

**修复**：重命名字段，明确语义：
```python
class IngredientEstimate(BaseModel):
    point_estimate: float           # QPSolver 点估计
    feasible_lower: float           # BoundSolver LP feasible minimum
    feasible_upper: float           # BoundSolver LP feasible maximum
    ensemble_p10: float             # Ensemble 10th percentile
    ensemble_p90: float             # Ensemble 90th percentile
    ensemble_p025: float | None     # 95% interval lower
    ensemble_p975: float | None     # 95% interval upper
```

在 TrustReport 和 metrics 中停止混用这些概念。

---

## Priority 6：文档对齐

### F6.1 — 新增 CURRENT_STATUS.md

```markdown
# NuSol-T 当前实现状态

> 最后更新：2026-07-05 | 自动生成 + 手工标注

## 模块状态

| 模块 | 状态 | 测试 | 备注 |
|------|------|------|------|
| core/schema | ✅ 完成 | ✅ | Pydantic v2, 208 tests pass |
| core/nutrient_registry | ⚠️ 有 bug | ✅ | F1.1 脂肪酸 ID 待修正 |
| core/units | ⚠️ 有 bug | ✅ | F1.5 IU 转换待修正 |
| data/fndds | ⚠️ 有 bug | ✅ | F4.1/F4.4 待修正 |
| data/sr_legacy | ✅ 可用 | ✅ | |
| data/foundation | ✅ 可用 | ✅ | |
| data/branded | ⚠️ 原型 | ❌ 弱 | F4.2 basis/unit 待修正 |
| ingredient/parser | ⚠️ 有 bug | ✅ | F4.3 嵌套括号待修正 |
| nutrition/forward | ⚠️ 有 bug | ✅ | F1.4 水分单位待修正 |
| nutrition/labelize | ⚠️ 不完整 | ✅ | F1.1-adjacent, FDA table 待完善 |
| constraints/* | ⚠️ 有 bug | ✅ | F0.3/F1.2/F1.3/F1.6 待修正 |
| solver/qp_solver | ⚠️ 不完整 | ✅ | F2.1 未接约束体系 |
| solver/bound_solver | ⚠️ 有 bug | ✅ | F0.2 失败语义错误 |
| solver/bohn2022 | ⚠️ 不完整 | ✅ | 非精确 replica |
| solver/ensemble | ⚠️ 有 bug | ✅ | F5.3 p5/p95 未保存 |
| validation/metrics | ❌ 有 bug | ✅ | F0.1/F0.4/F0.5 待修正 |
| validation/ablation | ❌ 有 bug | ✅ | F2.5 G5=G6=G7 |
| report/trust | ⚠️ 有 bug | ✅ | F5.1/F5.2/F5.4 |
| report/trust_grade | ⚠️ 有 bug | ✅ | F5.1 单位未归一化 |
| config/loader | ⚠️ 不完整 | ✅ | F2.3 extends 未实现 |
| cli | ❌ 占位 | ❌ | F3.1 三大命令未实现 |

## Pipeline 完整性

| Pipeline | 状态 |
|----------|------|
| FNDDS forward (已知配方 → 营养素) | ⚠️ 模块有，未端到端接通 |
| FNDDS inverse (标签 → 配料) | ⚠️ 模块有，CLI 占位 |
| FNDDS labelized (标签化模拟) | ❌ 未实现 |
| 200-recipe benchmark | ❌ 不可从仓库复现 |
| Branded Food inverse | ❌ 未实现 |
| Nutrient expansion | ❌ 未实现 |
```

### F6.2 — PROGRESS.md 修正

- Phase 0: 部分完成（schema/loader/CLI 有，但 config schema 不完整）
- Phase 1: 部分完成（adapters 有，retention/moisture 未接通）
- Phase 2: 原型完成（QP/LP 可运行，约束体系/失败语义不完整）
- Phase 3: 部分完成（metrics/report 原型有，指标语义有 bug）
- Phase 4: 不可复现（levels 冲突，YAML 未接 solver，缺实验产物）
- 移除所有不可复现的 benchmark 数字或标记为 historical/unverified

### F6.3 — DEVELOPMENT.md 标记为 target design

在文件头部添加：
```markdown
> ⚠️ **本文是目标架构设计文档 (Target Design)，不代表所有模块已实现。**
> 当前实现状态见 `docs/CURRENT_STATUS.md`。
> 标记说明: [CURRENT] 已实现 | [TARGET] 计划中 | [LEGACY] 已废弃 | [INVALIDATED] 被 review 否定
```

对每节增加状态标签。

### F6.4 — SUMMARY.md 修正

- "Stage 1 全部开发完成" → "Stage 1 原型完成，端到端 pipeline 建设中"
- 移除具体 benchmark 数字或标记来源不可复现

### F6.5 — README 补全

最少内容：
- 项目目标（1 段）
- 当前成熟度（研究原型）
- Python 3.12 + uv 安装
- USDA 数据目录约定
- 最小运行示例
- pytest/ruff/mypy 命令
- 已知限制

---

## 修复执行顺序建议

```
第 1 周:  Priority 0 (阻塞性) — F0.1 ~ F0.5
           → 修复后现有测试仍应通过 + 新增针对性测试

第 2 周:  Priority 1 (科学基础) — F1.1 ~ F1.6
           → 每个修复附带针对性单元测试

第 3 周:  Priority 2 (约束连通) — F2.1 ~ F2.5
           → 核心架构改动，需要仔细设计接口

第 4 周:  Priority 3 (端到端) — F3.1 ~ F3.4
           → 首次打通完整 forward→inverse→report 链路
           → 重跑 200-recipe benchmark，产生可复现结果

第 5 周:  Priority 4 (数据质量) — F4.1 ~ F4.4
           → 数据层改进，影响下游

第 6 周:  Priority 5 (Trust) — F5.1 ~ F5.4
           → 报告可信度提升

第 7 周:  Priority 6 (文档) — F6.1 ~ F6.5
           → 持续进行，第 7 周集中收尾

此后:    进入 Phase 5 (Branded Food)
```

---

## 每个修复的验收标准

- [ ] 修复代码已提交
- [ ] 针对性单元测试通过（red→green）
- [ ] 全量回归测试通过（208 → 200+）
- [ ] Ruff + mypy 无新增问题
- [ ] 修复影响记录在 commit message 中
- [ ] 如果修复改变了 benchmark 相关行为，在 CURRENT_STATUS.md 中标记 "需要重跑 benchmark"

---

## 修复完成后的正确状态声明

> NuSol-T 是一个研究原型，具备以下已验证的能力：
> - 凸 QP + LP 约束优化求解器，在选定线性约束下恢复配料比例
> - 四级配料映射 fallback (FNDDS → Foundation → SR Legacy → fuzzy)
> - FNDDS 同源闭环验证 MAE ≈ 0.02（可复现）
> - TrustReport 输出 feasible bounds 和 heuristic quality diagnostics
>
> 以下仍在建设中：
> - 跨数据库/商业食品验证
> - 完整的 P3/P4 食品科学先验约束
> - 加工模型（retention/yield/moisture）
> - 扩展营养成分估计
> - 校准后的统计不确定性量化
