# NuSol-T 项目代码 Review

> Review 日期：2026-07-05  
> 范围：核心模型、求解器、约束系统、数据适配器、验证指标、报告、CLI、配置与工程质量  
> 说明：本次 review 仅进行只读检查与最小反例验证，未修改业务代码。
>
> **状态说明（2026-07-15）**：本文是历史审查记录。当前实现状态以 `docs/CURRENT_STATUS.md` 和 `docs/PROGRESS.md` 为准；本文指出的问题中，部分已在 `refactor/yaml-solver-framework` 分支修复，未修复项继续作为后续风险跟踪。

## 1. 总体结论

项目已经具备较完整的模块划分和单元测试基础，但目前更接近算法实验代码，端到端产品链路尚未闭合。主要风险集中在以下方面：

1. QPSolver 和 BoundSolver 没有执行完整的配置化约束体系。
2. BoundSolver 会把不可行问题报告为成功，并返回无信息量的 `[0, 1]` 区间。
3. 验证指标存在系统性美化结果的可能，包括漏预测不计入 MAE、80%/95% coverage 实际相同等。
4. 水分变化、软约束 penalty、water-solid closure 等存在数值或食品科学定义错误。
5. CLI 默认路径和主命令当前不可正常完成实际工作流。
6. 文档中“Phase 0–4 已完成”的表述与 CLI、约束接入和消融实现的实际状态不一致。

建议在继续扩展 Branded Food 和论文实验前，先修复求解语义、指标计算和端到端测试，否则现有 benchmark、coverage 和 Trust Grade 结论可能不可靠。

## 2. 检查结果

| 检查项 | 结果 |
|---|---|
| `pytest` | 208 passed |
| Python 包构建 | 成功生成 sdist 和 wheel |
| Ruff | 166 个问题，其中 91 个可自动修复 |
| mypy | 12 个错误或缺失类型存根问题 |
| Git 工作区 | Review 开始时干净 |
| README | 当前无有效项目说明内容 |

Ruff 问题主要包括未使用导入、导入排序、超长行和 Python 3.12 类型语法。mypy 除缺失 `types-PyYAML`、`scipy-stubs` 外，还发现真实接口错误，例如 `IngredientOrderConstraint.to_scipy_constraint()` 的返回类型与基类不兼容。

## 3. 高优先级问题

### 3.1 QPSolver 忽略传入的约束体系

位置：`src/nusol/solver/qp_solver.py:42-55, 102-140`

`solve()` 接收 `constraints` 和 `builder`，但文档和实现都明确不使用它们。求解器只硬编码：

- 质量守恒；
- 主配料顺序；
- 标签区间及 slack；
- 基础变量上下界。

因此以下配置不会影响 QPSolver 结果：

- `two_percent_rule`；
- `energy_closure`；
- `water_solid_balance`；
- `sodium_balance`；
- `added_sugar_balance`；
- `fatty_acid_closure`；
- `category_prior`；
- YAML 中声明的品类约束和其他扩展约束。

这意味着配置化约束、品类约束和消融实验与当前主求解器没有真正连接。

建议：为线性约束定义统一的 QP/LP 表示；对非线性软约束明确采用支持它们的求解器，或在 QP 中给出可验证的凸近似。不能保留一个接收约束但静默忽略的接口。

### 3.2 BoundSolver 对不可行问题仍返回成功

位置：`src/nusol/solver/bound_solver.py:113-149`

每次 `linprog` 失败时，代码分别把下界设为 `0.0`、上界设为 `1.0`，最后无条件返回 `success=True`。

最小反例：唯一配料的营养值为 1，目标区间为 `[2, 3]`，质量守恒要求配料比例为 1。该问题显然不可行，但当前返回：

```text
success=True
x_lower={'a': 0.0}
x_upper={'a': 1.0}
```

影响：

- 不可行问题被伪装为“完整可行区间”；
- coverage 被人为提高；
- identifiability 被错误判为较差而不是不可行；
- TrustReport 无法区分“信息不足”和“问题无解”。

建议：先执行一次可行性 LP；任一 bound 求解失败时保存状态和原因；只有全部必要 LP 成功才返回 `success=True`。不可行、无界、数值失败应使用不同状态。

### 3.3 CLI 配置路径会被重复拼接

位置：

- `src/nusol/config/loader.py:31-35`
- `src/nusol/cli.py:26-33, 47-60, 73-85`

`ConfigLoader()` 默认以 `config` 为根目录，但 CLI 将用户提供的 `config/...yaml` 直接传入 `load()`，最终查找：

```text
config/config/...yaml
```

实际执行 `nusol validate-config config/constraints/default.yaml` 已稳定复现 `FileNotFoundError`。

此外，CLI 默认使用的 `config/fndds_forward.yaml` 和 `config/fndds_inverse.yaml` 当前并不存在。

建议：CLI 对用户路径统一使用 `load_from_path()` 或顶层 `load_config()`；只有纯配置名才相对 `config_dir` 解析。增加 CLI subprocess 端到端测试。

### 3.4 水分变化参数单位前后矛盾

位置：

- `src/nusol/nutrition/forward.py:33-65`
- `src/nusol/config/loader.py:74-77`
- `tests/test_nutrition/test_forward.py:37-50`

接口文档声明 `0.05` 表示 5%，配置范围也是 `[-0.30, 0.30]`，但公式使用：

```python
100.0 / (100.0 - moisture_change)
```

该公式把输入当作百分数。实测 10% 损失传入 `0.10` 时，100 只变成 `100.1001`，正确值应约为 `111.1111`。现有测试传入 `10.0`，与接口和配置约定冲突，因此掩盖了错误。

建议：统一使用 fraction，公式改为 `1 / (1 - moisture_change)`；或统一使用百分数并同步修改接口、配置范围和所有调用方。优先建议 fraction。

### 3.5 Inverse MAE 忽略漏预测配料

位置：`src/nusol/validation/metrics.py:148-175`

代码只计算真实值和预测值名称的交集：

```python
common = set(true_frac) & set(est_frac)
```

例如：

```python
true = {"a": 0.5, "b": 0.5}
estimated = {"a": 0.5}
```

当前 MAE 为 `0.0`，完全漏掉的 `b` 不受惩罚。这会系统性美化 benchmark，尤其是在数据映射或字典键覆盖导致配料缺失时。

建议：使用名称并集，缺失项按 0 处理；同时单独报告 mapping coverage，避免把名称映射失败与比例估计误差混在一起。

### 3.6 80% 与 95% coverage 使用同一组边界

位置：`src/nusol/validation/metrics.py:176-195`

代码使用同一组 `estimated_lower/estimated_upper` 同时填充 `coverages_80` 和 `coverages_95`，两者必然相等。

另外，BoundSolver 返回的是约束可行域极值，不是统计意义上的 80% 或 95% 概率区间，因此不能直接称为 credible interval coverage。

建议：

- 可行域边界单独命名为 feasible-bound coverage；
- 80%/95% 区间应来自 bootstrap、后验采样或明确的分位数估计；
- API 分别接收 80% 和 95% 边界。

### 3.7 软约束被重复平方

位置：

- `src/nusol/constraints/base.py:26-31`
- `src/nusol/constraints/label_interval.py:39-58`
- `src/nusol/constraints/energy_closure.py:72-80`
- `src/nusol/constraints/water_solid.py:77-85`
- `src/nusol/constraints/fatty_acid_closure.py:62-70`
- `src/nusol/constraints/added_sugar_balance.py:56-79`

多个 constraint 已将偏差平方后写入 `violation`，而 `ConstraintEval.penalty` 又计算：

```python
self.weight * self.violation**2
```

最终形成四次惩罚。实测标签偏差为 2、权重为 10 时：

- 预期二次 penalty：40；
- 当前 penalty：160。

影响：大偏差被异常放大，配置中的 weight 不再具有直观含义，不同约束之间的权重比较失真。

建议：统一约定 `violation` 必须是未平方的非负偏差，由 `penalty` 负责平方；多维约束则直接返回最终 penalty，并取消基类再次平方。两种语义只能保留一种。

### 3.8 G5、G6、G7 消融级别完全相同

位置：`src/nusol/validation/ablation.py:13-23`

G5、G6、G7 的约束列表完全一致，即使约束系统正确接入，三个实验结果也不会有差异。这与 G0–G7 渐进添加约束的实验定义冲突。

结合 QPSolver 忽略大部分约束的问题，当前消融结果不能证明各约束的效果。

建议：为每个 level 明确定义唯一增量，并增加测试断言：后一层集合严格包含前一层，或显式记录为什么不是严格包含。

## 4. 中优先级问题

### 4.1 YAML 约束名与代码注册名不一致

位置：

- `config/constraints/default.yaml`
- `src/nusol/constraints/base.py:99-139`

YAML 使用：

- `unique_source_lower_bound`；
- `sodium_source_balance`；
- `added_sugar_source`；
- `similarity_anti_extreme`。

代码注册表识别：

- `sodium_balance`；
- `added_sugar_balance`；
- 没有 unique-source 和 similarity 对应实现。

未知配置会被静默忽略；注册表中没有出现在 YAML 的约束，因为 `enabled` 默认为 true，反而会被自动启用。

建议：配置解析采用严格 schema，未知名称直接报错；所有约束默认禁用，只有显式配置或明确的系统默认才能启用。

### 4.2 主 CLI 工作流仍是占位实现

位置：`src/nusol/cli.py:68-101`

`run-forward`、`run-inverse` 和 `run-ablation` 只输出 “to be implemented”，没有执行实际 pipeline。`run-forward` 创建 adapter 后也未使用。

这与 `docs/PROGRESS.md` 中 Phase 0–4 已完成的状态不一致。

建议：把“模块实现完成”和“端到端 pipeline 完成”拆分记录；在 CLI 真正连接数据、解析、求解、验证和报告前，不应宣称对应 phase 完成。

### 4.3 `zero_slack_rate` 可能为负数

位置：`src/nusol/validation/metrics.py:198-210`

当前公式是：

```python
1 - 冲突总数 / 样本数
```

当一个样本有两个冲突时，单样本结果为 `-1.0`。

建议：计算没有任何 active constraint 的样本比例；如果目标是平均冲突数，应使用独立字段。

### 4.4 PointSolver 没有记录真实 slack

位置：

- `src/nusol/solver/point_solver.py:133-154`
- `src/nusol/constraints/base.py:13-24`

PointSolver 保存 `ev.slack`，但约束实现基本只设置 `violation`，`slack` 保持默认 0。因此报告可能同时显示“约束违反”和“slack 为 0”。QPSolver 又把平方后的 label violation 当作 slack，两个求解器的字段语义不一致。

建议：定义统一字段语义：value、raw violation、optimization slack、penalty 必须区分，并通过 schema validator 保证非负和单位一致。

### 4.5 Water-solid closure 重复计算 fiber

位置：`src/nusol/constraints/water_solid.py:52-85`

模型同时加入 `Carbohydrate, by difference` 和 `Fiber, total dietary`。USDA 的 carbohydrate by difference 已包含 dietary fiber，再次加入 fiber 会导致质量总和虚高。

建议：根据采用的 carbohydrate 定义决定是否单独加入 fiber。对 USDA by-difference 模式，不应重复加入 fiber。

### 4.6 Energy closure 可能重复计算 fiber

位置：

- `src/nusol/constraints/energy_closure.py:59-73`
- `src/nusol/nutrition/forward.py:99-122`

公式使用 `4 * carbohydrate + 2 * fiber`，但输入是 `Carbohydrate, by difference`。如果 carbohydrate 已包含 fiber，则这相当于先按 4 kcal/g 计算 fiber，再额外加 2 kcal/g。

建议：明确 carbohydrate 是 total、available 还是 by-difference，并使用一致的能量公式。若要对 fiber 使用 2 kcal/g，应从按 4 kcal/g 计算的 carbohydrate 中扣除 fiber。

### 4.7 Added-sugar 约束没有使用糖源贡献

位置：`src/nusol/constraints/added_sugar_balance.py:49-79`

代码计算了 `sugar_from_sources`，最终却比较：

```python
added_sugar <= total_sugar
```

这通常天然成立，无法约束 added sugar 是否来自识别出的糖类配料。

建议：使用 `sugar_from_sources` 构建约束；同时确认 nutrient matrix 中是否真实包含 added sugar。若数据库没有该字段，应避免把缺失值 0 当作已知事实。

### 4.8 FNDDS 使用配料描述作为唯一字典键

位置：

- `src/nusol/data/fndds.py:129-145`
- `src/nusol/data/fndds.py:268-297`

真实比例、profile、matrix 和 mapping metadata 都使用 description 作为键。若同一 recipe 中存在描述相同但 code 或 sequence 不同的项目，后面的值会覆盖前面的值，而不是合并。

影响：

- 真实比例和不再等于 1；
- 配料数减少；
- benchmark MAE 因交集计算进一步被美化；
- matrix 与原始 recipe 无法一一对应。

建议：内部使用稳定 ingredient ID，例如 `(ingredient_code, sequence_number)`；展示层再使用 description。若业务上需要合并，应显式求和并验证 nutrient profile 是否一致。

### 4.9 Branded nutrient basis 判断不可靠

位置：`src/nusol/data/branded.py:62-74, 97-121`

只要记录有 serving size，就把 nutrient profile 标记为 `per_serving`，但没有根据原始数据字段实际 basis 进行换算。同时 serving size unit 被读取却没有参与转换，mL、oz 等会直接当克处理。

建议：依据 FoodData Central 字段定义确定 nutrient amount 的 basis；保留 serving unit，并在密度未知时拒绝把体积直接转换为质量。

### 4.10 复杂配料解析不支持嵌套括号

位置：`src/nusol/ingredient/parser.py:93-160`

虽然 `_smart_split()` 会跟踪括号深度，但单项解析使用：

```python
re.search(r"\(([^)]+)\)", text)
```

它只截取到第一个右括号，无法正确处理常见结构：

```text
ENRICHED FLOUR (WHEAT FLOUR (NIACIN, IRON), MALTED BARLEY FLOUR)
```

另外，括号不平衡时 `_smart_split()` 不报错，depth 可能变成负数。

建议：使用栈式解析器统一处理嵌套结构，并为括号不平衡、多个 parenthetical group 和冒号子列表增加测试。

### 4.11 Trust score 混用不同单位的绝对残差

位置：`src/nusol/report/trust_grade.py:35-45`

Trust Grade 直接取所有营养素的最大绝对残差，并统一使用 1、5、20 阈值。但 kcal、g、mg、µg 的数值尺度完全不同。例如 10 mg sodium 与 10 g fat 会受到同样处罚。

建议：按 label interval 宽度、法规容差或相对误差归一化，使用无量纲 residual score。还应区分数据库缺失导致的残差和真正模型不匹配。

### 4.12 Identifiability 的自由度计算过度简化

位置：`src/nusol/report/trust.py:119-154`

自由度简单计算为：

```python
n_ingredients - n_label_nutrients - 1
```

但标签营养约束可能线性相关、没有有效区间、对应 matrix 全零或因 slack 而不构成等式约束。真正的可识别性取决于约束矩阵秩和活跃约束，而不是营养素数量。

此外，`n_label_nutrients` 来源是 `nutrient_residuals` 数量，而不是 observation 的有效 label 数量。

建议：基于有效设计矩阵的数值秩、null space 或 LP/QP feasible width 计算 identifiability。

### 4.13 Ensemble 的区间字段语义错误

位置：

- `src/nusol/solver/ensemble_solver.py:105-129`
- `src/nusol/report/trust.py:102-115`

EnsembleSolver 计算了 `x_p5` 和 `x_p95`，但没有写入 `SolverResult`；实际写入 `x_lower/x_upper` 的是样本最小值和最大值。TrustReport 又把同一组 min/max 同时写入 `interval_80` 和 `interval_95`。

建议：扩展 schema，显式保存 p5、p10、p90、p95；不要用 feasible bounds 或样本极值冒充 credible intervals。

### 4.14 PointSolver 配置值可能不是合法 SciPy method

位置：

- `src/nusol/config/loader.py:87-91`
- `src/nusol/solver/point_solver.py:24-30`

默认配置写入 `scipy_trust_constr`，而 SciPy method 名为 `trust-constr`。如果将 `inverse_solver` 配置直接传给 PointSolver，会导致所有尝试失败并返回 uniform fallback。

建议：配置使用内部 enum，再集中映射到 SciPy method；加载时严格验证，不把任意字符串直接传给 SciPy。

## 5. 低优先级与工程问题

### 5.1 README 缺失

当前 README 没有有效内容。至少应包含：

- 项目目标和当前成熟度；
- Python 与数据依赖；
- 安装方法；
- 最小 forward/inverse 示例；
- USDA 数据目录约定；
- 测试、lint、type-check 命令；
- 已知限制。

### 5.2 配置验证过弱

位置：`src/nusol/config/loader.py:112-126`

当前只检查三个 section 是否存在，不验证字段类型、取值范围、未知键、约束名称、solver method 或相互依赖。

建议：使用 Pydantic/OmegaConf structured config，并禁止未知字段。

### 5.3 广泛吞掉异常

位置包括：

- `src/nusol/solver/point_solver.py:82-99, 182-200`
- `src/nusol/solver/bound_solver.py:117-138`
- `src/nusol/solver/ensemble_solver.py:64-95`

异常通常被静默忽略，导致算法失败退化为 uniform 或 `[0,1]`，但调用方无法知道具体原因。

建议：捕获可预期的数值异常，记录 solver status/message；未知异常应向上传播或至少进入结构化 diagnostics。

### 5.4 输入形状和数值缺少验证

Forward model、QPSolver 和 BoundSolver 没有统一验证：

- 配料数是否与 matrix 行数一致；
- nutrient names 是否与 matrix 列数一致；
- fraction 是否非负且和为 1；
- interval 是否满足 `lo <= hi`；
- 是否存在 NaN/Inf；
- variables 是否为空；
- main/two-percent indices 是否越界。

建议：在进入求解器前构造经过验证的问题对象，避免直接依赖松散的 `dict[str, Any]` context。

### 5.5 Ruff 与 mypy 未进入质量门禁

测试全绿，但静态检查存在大量问题，说明 CI 很可能只运行 pytest。建议最低质量门禁为：

```text
pytest
ruff check src tests
mypy src
uv build
```

## 6. 测试覆盖缺口

现有 208 个测试主要验证正常路径和基本返回结构，没有覆盖关键失败语义。建议补充以下测试：

1. QPSolver 对每类已启用约束确实产生不同解或不同可行域。
2. BoundSolver 对 infeasible、unbounded、数值失败返回正确状态。
3. CLI 使用相对路径、绝对路径和默认参数的 subprocess 测试。
4. 水分参数使用 fraction 的边界测试。
5. MAE 对漏预测、额外预测、名称不一致的处理。
6. 80%/95% coverage 使用不同区间。
7. zero-slack rate 在多冲突样本下仍处于 `[0,1]`。
8. 重复 description 的 FNDDS recipe。
9. Branded serving unit 为 mL、oz、字符串和缺失值的情况。
10. 嵌套括号、不平衡括号、多层 compound ingredient。
11. NaN、Inf、空 variables、matrix shape mismatch、非法 interval。
12. 配置未知约束名和非法 solver method 必须失败。
13. G0–G7 的启用集合和预期严格一致。
14. Trust score 对不同单位缩放保持合理一致性。

## 7. 建议修复顺序

### 第一阶段：保证结果语义正确

1. 修复 BoundSolver 的不可行/失败状态。
2. 修复 MAE、coverage 和 zero-slack 指标。
3. 修复水分单位和重复平方 penalty。
4. 统一 SolverResult 中 violation、slack、bounds、quantiles 的语义。

### 第二阶段：闭合约束与配置链路

1. 建立严格配置 schema 和统一约束注册表。
2. 让 QPSolver/BoundSolver 明确执行支持的约束；不支持时直接报错。
3. 修正 G0–G7 消融定义。
4. 修复食品科学 closure 公式。

### 第三阶段：端到端可用性

1. 修复 CLI 路径并提供实际存在的默认配置。
2. 实现 forward、inverse、ablation pipeline。
3. 增加 CLI 和 200-recipe 端到端回归测试。
4. 完善 README，并同步修正进展文档。

### 第四阶段：数据与报告可信度

1. 修复 FNDDS 重复键和 Branded basis/unit。
2. 重写嵌套配料解析。
3. 基于无量纲残差和矩阵秩重构 Trust Grade/Identifiability。
4. 重新运行 benchmark 和消融实验，并记录修复前后差异。

## 8. 发布前建议门槛

在将现有 benchmark 用于论文结论或对外发布前，建议至少满足：

- 所有不可行问题能够被正确识别；
- 主求解器不再静默忽略已启用约束；
- MAE 按配料并集计算；
- feasible bounds 与概率区间明确区分；
- G0–G7 每一级配置和实际执行路径可验证；
- CLI 可以从仓库内默认配置完成一次真实端到端运行；
- pytest、Ruff、mypy、build 全部通过；
- 修复后重新生成全部 benchmark、coverage 和 Trust Grade 数据。
