# NuSol-T 文档设计与代码实现一致性 Review

> Review 日期：2026-07-05  
> 审查范围：`docs/`、`config/`、`src/nusol/`、`tests/`、CLI 与构建配置  
> 关联文档：`docs/REVIEW.md`、`docs/SCIENCE_REVIEW.md`  
> 目标：核验文档设计、进度声明、配置体系和实际代码是否一致，并指出设计文档中本身不正确或已被前两轮 review 否定的内容。

## 1. 总体结论

项目当前存在明显的“规划文档、进展文档和实际实现三套状态”。其中：

- `docs/DEVELOPMENT.md` 主要是一份目标架构和伪代码设计，但大量段落使用“实现细节”“关键接口”等措辞，容易被误读为当前实现。
- `docs/SUMMARY.md` 和 `docs/PROGRESS.md` 把 Stage 1、Phase 0–4、消融实验和验证体系描述为已完成，但仓库中的 CLI 仍是占位实现，缺少完整 pipeline、主配置、结果产物和可复现 benchmark 入口。
- `config/constraints/*.yaml` 描述了代码不存在或不会被主求解器执行的约束。
- 主求解器已经切换为 QPSolver/LP BoundSolver，但开发文档仍以 PointSolver/trust-constr 和“所有约束共同求解”为主线。
- 科学 review 已确认若干默认设计不成立，包括简单舍入反演、错误的质量基准、water-solid/fiber 重复计数、统一 Atwater closure、未校准 Trust Grade 等；这些内容仍在规划和配置中作为有效设计出现。

因此，当前文档不能作为可靠的使用说明、API 说明、实验复现说明或项目完成度依据。

建议立即将文档分为三类并明确标记：

1. `CURRENT_IMPLEMENTATION`：只描述当前可运行行为；
2. `TARGET_DESIGN`：描述尚未实现的目标架构；
3. `EXPERIMENT_RECORD`：包含可执行命令、提交哈希、输入数据版本和结果文件。

## 2. 审计基线

当前仓库实际状态：

| 项目 | 实际状态 |
|---|---|
| Python 源文件 | 48 个 |
| Python 源码行数 | 约 5,174 行，不含测试和文档 |
| 测试文件 | 18 个 `test_*.py` |
| 测试用例 | 208 个 |
| YAML 文件 | 6 个，全部位于 `config/constraints/` |
| 主运行配置 | `fndds_forward.yaml`、`fndds_inverse.yaml` 等均不存在 |
| scripts 目录 | 不存在 |
| notebooks 目录 | 不存在 |
| output/benchmark 产物 | 不存在 |
| CLI | version/config validation 基本入口存在；forward/inverse/ablation 为占位输出 |
| 主点求解器 | `QPSolver`；`PointSolver` 已在 package docstring 中标记 deprecated |
| 完整 pipeline | 不存在 |

## 3. 严重不一致

### 3.1 “Stage 1 / Phase 0–4 已完成”与仓库实际状态冲突

文档：

- `docs/SUMMARY.md:7`：Stage 1 全部开发完成，项目“可运行、可验证”。
- `docs/PROGRESS.md:7-18`：Phase 0–4 全部完成。
- `docs/PROGRESS.md:15`：Phase 4 消融实验完成。

实际：

- `src/nusol/cli.py:68-101` 的 forward、inverse、ablation 命令仅输出 “to be implemented”。
- `docs/PROGRESS.md:118` 自己又把“实现 YAML 约束解析器、将配置连接到 solver”列为下一步。
- `docs/PROGRESS.md:121` 又把 “FNDDS 端到端验证”列为下一步。
- `docs/SUMMARY.md:34` 同样承认端到端验证待完成。

这是文档内部及文档—代码双重矛盾。更准确的状态应是：

```text
基础模块原型：部分完成
端到端 Stage 1：未完成
配置驱动约束：未接通
Phase 4 消融：有配置生成函数和零散实验记录，但不可从仓库复现
```

建议：撤销“Phase 0–4 已完成”表述，按验收条件重新定义阶段状态。

### 3.2 200-recipe benchmark 无法从仓库复现

文档：`docs/PROGRESS.md:41-100` 给出 MAE、coverage、运行时间、Trust Grade、与 Bohn 2022 的比较和误差来源百分比分解。

实际审查：

- 仓库中没有运行 200-recipe benchmark 的 script 或 pipeline；
- 没有结果 CSV/JSON、日志、图表、环境记录或命令；
- 除 `docs/PROGRESS.md` 外，代码和测试中找不到 `0.0731`、`0.0840`、`0.1059`、`99.5%` 等结果值；
- `config/validation_recipes.json` 仅提供 recipe ID，不能复现求解过程；
- 当前 metrics 和 BoundSolver 已在 `docs/REVIEW.md` 中确认会扭曲 MAE、coverage 和成功状态。

因此，这些数值目前属于不可审计的外部实验记录，不能视为仓库可复现结果。

建议每个 benchmark 必须提交：

```text
run command
git commit hash
data release/checksum
full config
result table
per-recipe diagnostics
failure list
environment lock
metric implementation version
```

在重新运行前，进展文档应标记结果为 historical/unverified，而不是当前有效基线。

### 3.3 DEVELOPMENT 目录结构大量描述不存在的文件

文档：`docs/DEVELOPMENT.md:25-159`

文档列出但仓库不存在的主要内容包括：

- `LICENSE`；
- `docs/API.md`；
- 四个主 YAML 配置和 `config/ablation/`；
- `ingredient/parser_utils.py`、`mapper.py`、`compound.py`；
- `nutrition/retention.py`、`moisture.py`；
- `solver/base.py`；
- `validation/compare.py`；
- `report/html_report.py`、`provenance.py`；
- `config/config_schema.py`；
- `utils/logging.py`、`parallel.py`；
- 整个 `scripts/`、`notebooks/`、`output/` 结构。

文档还使用非 src-layout 的 `nusol/` 路径，而实际包位于 `src/nusol/`。

建议：如果该章节是目标架构，标题必须改为“目标目录结构（未全部实现）”，并给每项标记 planned/current。另增加自动生成的当前目录树，避免长期漂移。

### 3.4 DEVELOPMENT 中的 pipeline API 不能执行

文档：`docs/DEVELOPMENT.md:1145-1215`

示例引用或调用了不存在/不兼容的接口：

- `ForwardValidator` 不存在；
- `adapter.load_recipes()` 不存在；
- `recipe.fractions`、`recipe.nutrient_matrix` 等对象模型不存在；
- `compare()` 不存在；
- `PointSolver` 不再从 `nusol.solver` 导出；
- `ConstraintBuilder.build()` 实际接收 context dict，而示例传 `ProductObservation`；
- `PointSolver.solve()` 实际需要 variables、constraints、context，示例签名不同；
- `BoundSolver.solve()` 和 `EnsembleSolver.solve()` 示例签名不同；
- `TrustReportBuilder.build()` 示例多传了 `config.reporting`；
- 对 `dict` 配置使用 `config.data` 属性访问，与 `ConfigLoader` 返回值不一致。

这类示例不是“略去实现细节”，而是会直接误导调用方。

建议：所有文档代码块进入 doctest 或独立 smoke test；不能执行的伪代码明确标注 `pseudocode`。

### 3.5 文档设计为“所有约束进入统一求解”，代码却静默忽略

文档：

- `docs/NuSol-T.md:30`：所有约束和数据库先验整合到同一优化框架。
- `docs/DEVELOPMENT.md:386-404`：ConstraintBuilder 后由 Point/Bound/Ensemble 对所有 constraints 求解。
- `docs/DEVELOPMENT.md:640-675`：BoundSolver 对所有约束求 min/max。

实际：

- `QPSolver.solve()` 明确不使用传入的 `constraints` 和 `builder`；
- 只硬编码 mass、order、label interval；
- `BoundSolver` 同样只硬编码 mass、order、label interval；
- two-percent、P3、P4、品类约束不进入主 QP/LP；
- 约束 YAML 没有被 CLI 或 pipeline 加载。

这不是缺少一个边缘功能，而是项目核心设计承诺没有实现。

建议：文档暂时改为“QPSolver/BoundSolver 当前仅支持三类线性约束”，并在求解器遇到不支持的 enabled constraint 时显式失败。

## 4. 求解器与不确定性设计不一致

### 4.1 主求解器架构已经变化，文档仍以 PointSolver 为核心

文档：`docs/DEVELOPMENT.md:600-637` 将 PointSolver/trust-constr 描述为点估计核心。

实际：

- `src/nusol/solver/__init__.py` 声明 PointSolver 已 deprecated；
- package 只导出 QPSolver、BoundSolver、EnsembleSolver；
- `docs/PROGRESS.md` 又将 QPSolver 描述为最终主路径。

建议：文档要么更新为当前 QP/LP 架构，要么保留 PointSolver 章节但明确标记 legacy。不能同时把二者都描述成当前主实现。

### 4.2 文档把 QPSolver 称为“凸 QP”，实际使用通用 SLSQP 表达

文档：`docs/PROGRESS.md:13, 36-38, 57`。

实际 `QPSolver` 的目标和约束在数学上可形成凸 QP，但代码通过 Python lambda 和 `scipy.optimize.minimize(method="SLSQP")` 求解，并没有显式 QP matrix、凸性验证或专业 QP solver。

“问题形式是凸二次规划”可以成立，但“使用凸 QP solver 获得全局最优”不能由当前实现保证。文件头中“unique global minimum”也不普遍成立：当 ingredient matrix 存在不可识别方向时，ingredient fractions 可以有多个等价最优解，即使 slack objective 唯一。

建议文档写为：

> 使用 SLSQP 求解具有凸二次目标和线性约束的模型；当前实现未提供全局最优证书，配料比例可能非唯一。

### 4.3 Ensemble 文档声明了未实现的扰动与输出

文档：`docs/DEVELOPMENT.md:678-715` 声明：

- mapping candidate 扰动；
- nutrient matrix 高斯噪声；
- 5/25/50/75/95 分位数；
- kernel density estimate。

实际 `src/nusol/solver/ensemble_solver.py`：

- 没有 mapping perturbation；
- `noise_std` 被读取但没有使用，database perturbation 未实现；
- 只运行 multi-start 和最多 50 次 interval perturbation；
- 计算 p5/p95 后没有写入结果；
- `x_lower/x_upper` 保存的是 min/max；
- 没有 p25/p75 或 KDE。

此外，类 docstring 也宣称 database perturbation 已实现，与类本身代码矛盾。

建议删除未实现声明，或实现后增加验证每种 uncertainty source 确实改变结果的测试。

### 4.4 BoundSolver “可行区间”文档遗漏失败语义

文档将 lower/upper 称为 subject to all constraints 的可行边界；实际既没有 all constraints，也在不可行时返回 `[0,1]` 并标记成功。

因此 `docs/SUMMARY.md:18` 和 `docs/PROGRESS.md:47,61` 中的“可行区间”和 coverage 描述目前不成立。

### 4.5 Bohn2022 comparison 的设计与实现存在单位和算法偏差

文档：`docs/PROGRESS.md:52-70` 将 `Bohn2022Solver` 结果用于精确方法比较。

实际：

- 代码注释承认论文使用 salt，而实现使用 USDA sodium；
- sodium matrix 单位是 mg/100g，但 EU tolerance thresholds 在代码中按 0.5 g 量级书写，未进行 mg/g 转换；
- 缺失 target 时人为使用 `b=10, tolerance=2`；
- processing water 被放进质量和约束后，最终 ingredient fractions 又重新归一化到 1，改变了优化解的表示；
- 结果没有 nutrient residuals；
- 没有论文测试数据或逐项 reproduction test。

因此当前最多是受 Bohn 方法启发的 baseline，不能无保留称为 replica，也不足以支持“好 26%”的严格方法结论。

## 5. 配置设计与实现不一致

### 5.1 文档中的主配置文件全部缺失

`docs/DEVELOPMENT.md` 和 CLI 引用：

- `config/fndds_forward.yaml`；
- `config/fndds_inverse.yaml`；
- `config/fndds_labelized.yaml`；
- `config/branded_inverse.yaml`。

实际只有 `config/constraints/*.yaml` 和 validation ID JSON。这也是 CLI 默认命令无法运行的直接原因之一。

### 5.2 `extends: default` 没有加载实现

所有 category YAML 都声明 `extends: default`，但 `ConfigLoader` 没有继承、合并或 category resolution 逻辑。`all_categories.yaml` 甚至明确写着“仅做文档说明”。

因此 `docs/PROGRESS.md:104` 所说“YAML 驱动、支持品类特定约束”并未实现。

### 5.3 YAML 中大量约束没有代码实现

配置存在但 ConstraintBuilder 不识别：

- `unique_source_lower_bound`；
- `similarity_anti_extreme`；
- `flour_mass_prior`；
- `oil_vs_meat_prior`；
- `water_mass_prior`。

名称不一致：

- YAML `sodium_source_balance`，代码 `sodium_balance`；
- YAML `added_sugar_source`，代码 `added_sugar_balance`。

进展文档却把 unique-source 的具体改善案例当作已完成成果。这意味着相关实验要么来自未提交代码，要么与当前仓库实现不一致。

### 5.4 YAML 参数大多不会传入约束实例

ConstraintBuilder 当前只读取：

- `enabled`；
- `weight` 或 `penalty_weight`；
- `slack`。

它不读取 YAML 中的：

- `priority`；
- `type`；
- `params`；
- tolerance；
- keywords；
- thresholds；
- min/max fraction。

因此即使约束名称匹配，大部分配置仍只是注释性数据。

### 5.5 DEVELOPMENT 的 G0–G7 与代码 G0–G7 不一致

文档 `docs/DEVELOPMENT.md:1289-1317`：

- G4 添加 moisture；
- G5 添加 sodium；
- G6 添加 category prior；
- G7 添加 added sugar 和 fatty acid。

实际 `src/nusol/validation/ablation.py:14-23`：

- G4 添加 two-percent；
- G5 添加 category prior；
- G5、G6、G7 完全相同；
- 没有 moisture、sodium、added sugar、fatty acid。

两套消融定义不能共存。任何报告必须记录实际使用的是哪一套。

### 5.6 ConfigLoader 的层级约定与 ConstraintBuilder 不统一

`ConfigLoader` 把 constraints 预期在 `inverse_solver.constraints`；`ConstraintBuilder` 则从传入对象的顶层 `constraints` 读取。只有调用方正确传入 `config["inverse_solver"]` 才能工作，但没有 pipeline 统一这一约定。

现有 constraint YAML 又把 `constraints` 放在文件顶层，和完整主配置属于另一种 schema。

建议提供唯一的 Pydantic config model，禁止三种层级并存。

## 6. 数据流与适配器不一致

### 6.1 FNDDS 文档声称读取 moisture adjustment，代码没有

文档：

- `docs/DEVELOPMENT.md:344-356`；
- `docs/DEVELOPMENT.md:946-965`；
- `docs/NuSol-T.md` 的 FNDDS data flow。

实际 `FNDDSDataAdapter.get_recipe()` 只提取 inputFoods、foodPortions 等，没有读取或返回 moisture adjustment。全仓库中也没有 FNDDS moisture field 的解析实现。

### 6.2 文档声称从 retention code 应用 factor，代码只保存 code

adapter 保存 `retention_code`，但没有 retention table loader，也没有构造 ingredient × nutrient factor matrix。文档的数据流把这一步画成已存在处理。

### 6.3 配料映射层级在三个文档和代码中各不相同

`docs/DATA.md`：SR Legacy code → FNDDS self → fuzzy，称三级 fallback。  
`docs/PROGRESS.md`：ndb → FNDDS → Foundation → fuzzy。  
`src/nusol/data/fndds.py`：FNDDS self → Foundation NDB → SR Legacy NDB → SR fuzzy。  

实际顺序会显著影响 benchmark 的 same-source leakage 和 composition error，必须有唯一权威说明。

### 6.4 DATA 的 fortificant 处理描述与代码相反

`docs/DATA.md:122-135` 声称 fortificant 不参与 mass balance，但作为对应营养素直接来源处理。

代码：

- `map_ingredient_to_profile()` 返回 `None`；
- 小重量 fortificant 被过滤；
- 未过滤者得到空 nutrient profile；
- 没有 direct nutrient addition。

结果是营养贡献被丢弃，而不是“直接来源处理”。

### 6.5 DEVELOPMENT 描述独立 IngredientMapper，实际不存在

文档声明 top-k candidates、synonym map、exact/fuzzy/manual、多数据库候选和 confidence。实际只有 FNDDS adapter 内部的单结果 fallback；BrandedDataAdapter 没有调用 parser 或 mapper。

因此 ProductObservation 的 `mapping_candidates` 和 TrustReport 的 mapping provenance 设计没有端到端数据来源。

### 6.6 Branded data flow 尚未实现

文档：`docs/DEVELOPMENT.md:422-457` 描述完整 Branded pipeline。

实际：

- Branded adapter 不解析 ingredients string；
- `to_product_observation()` 不设置 ingredient tree；
- 没有 LabelNutrientConverter；
- 没有 IngredientMapper；
- 没有 NutrientExpander；
- TrustReport `expanded_nutrients` 固定为空。

`docs/SUMMARY.md` 把 Branded adapter 列为数据层完成可以接受，但不能据此暗示 Branded application data flow 已存在。

## 7. Schema 与报告设计不一致

### 7.1 TrustReport 被描述为“完整可信报告”，实际多个字段是占位值

实际 `TrustReportBuilder`：

- `expanded_nutrients=[]`；
- `mapping_confidence=1.0`；
- mapping provenance 仅依赖外部调用方传入；
- data versions 硬编码；
- bounds 缺失时默认 `[0,1]`；
- interval_80 和 interval_95 完全相同；
- warnings 不检查 bounds failure、mapping failure 或 missing data。

因此 `docs/SUMMARY.md:19` 和 `docs/NuSol-T.md:74` 对 TrustReport 能力的描述超出实现。

### 7.2 Mapping confidence 设计没有进入求解或报告链路

Schema 定义了 confidence，规划文档把 mapping uncertainty 作为核心可信信息；但 QPSolver、BoundSolver、EnsembleSolver 和 TrustGrade 都不使用 mapping confidence。报告又固定为 1.0。

### 7.3 Moisture change 在 schema/config 中存在但主求解器不估计

文档配置将 `moisture_change: true` 设计为优化变量。实际 QPSolver 和 BoundSolver 的 decision vector 不包含 moisture；只有 Bohn baseline 返回一个名为 moisture_change 的 water variable。

### 7.4 Constraint priority 和 slack 语义与设计不一致

文档设计 P1 “尽量硬、可小量 slack”，并定义 `slack_max`。实际基类没有 `slack_max`；ingredient order 在 Point/QP/LP 中作为硬约束；`slack_allowed` 配置不会改变求解行为。

文档设计 `ConstraintEval` 返回真实 slack，实际多数 constraint 从未设置该字段。

## 8. 测试与质量声明不一致

### 8.1 测试数量文档漂移

- `docs/SUMMARY.md`：202 tests；
- `docs/PROGRESS.md`：208 tests；
- 实际：208 tests。

这是小问题，但说明手工维护统计容易失效。建议 CI 自动生成 badges 或 release manifest。

### 8.2 “集成测试”和“端到端测试”表述过强

测试确实包含可选的真实 USDA 数据 adapter 测试，但缺少：

- CLI subprocess 的真实 forward/inverse run；
- config → adapter → matrix → solver → report 的完整链路；
- retention/moisture reproduction；
- 200 recipe benchmark regression；
- category YAML → constraint → solver 的验证。

因此不能把当前测试集合概括为完整 pipeline 集成验证。

### 8.3 测试通过掩盖了文档要求未实现

典型例子：

- QPSolver 测试总是传空 constraints，因此无法发现 constraints 被忽略；
- BoundSolver 测试只检查 `[0,1]` 和 lower≤upper，不检查 infeasible；
- ablation 测试没有真正断言 progressive levels；
- moisture 测试采用与接口文档相反的百分数单位；
- TrustReport 测试接受相同的 80/95 interval。

测试证明的是当前局部行为自洽，不证明文档设计已实现。

## 9. 设计文档本身需要纠正的科学错误

以下内容即使未来完全按文档实现，也仍然不科学或需要更严格限定。详细证据见 `docs/SCIENCE_REVIEW.md`。

### 9.1 “法规感知区间 = 舍入反演区间”不成立

`docs/NuSol-T.md:68` 和 `docs/DEVELOPMENT.md:719-793` 把简单 rounding interval 称为法规感知区间。FDA 合规容差具有营养素类别和方向性，另有分析、批次与数据库换算误差。设计应区分 display rounding 与 regulatory compliance observation model。

### 9.2 `Σ x_i = 1` 的变量定义不清

文档同时把 `x_i` 称为配料比例、应用 ingredient-list order，并将预测值解释为成品每 100g。加工前投料比例与成品来源质量比例不是同一变量；有 moisture/yield 时不能无条件共用一个 mass balance。

### 9.3 Water-solid 设计重复加入 fiber

默认 YAML 明确写 `water + protein + fat + carbohydrate + fiber + ash ≈ 100g`。当 carbohydrate 是 USDA `Carbohydrate, by difference` 时已经包含 fiber，设计会重复计数。

### 9.4 Energy closure 设计重复计算 fiber，且忽略 specific Atwater factors

默认 YAML 使用 `4*carb + 2*fiber`。若 carb 是 by-difference，则 fiber 已在 carb 内。文档还把统一 4/9/4 当作普遍 closure，没有处理 food-specific factors、sugar alcohol 和 organic acids。

### 9.5 Fatty-acid closure 被过度解释为化学守恒

USDA total lipid 和 fatty-acid classes 的分析/表达基础不同，脂肪酸和不必精确等于 total lipid。该规则最多是带方法条件的诊断。

### 9.6 Added-sugar source 设计把缺失数据库字段当可观测量

Added sugar 是配方和法规分类属性，普通 ingredient composition record 中经常缺失。仅靠 `Sugars, added` 列和关键词无法形成可靠质量守恒。

### 9.7 Category priors 缺少数据校准

面粉 40–70%、乳基 60–90%、水 50–80%、单配料不超过某阈值等规则没有在仓库中提供数据来源、拟合过程或外部验证。它们应标记为待验证假设，不应作为默认“食品科学约束”。

### 9.8 FNDDS true fractions 不应称为商业配方 gold standard

FNDDS recipe ingredients 用于生成代表性 nutrient profile，不一定等于实际产品 label ingredients。可以称为 FNDDS calculation recipe reference，不应外推为商业配方真值。

### 9.9 Feasible bounds、bootstrap range 和 credible interval 必须分开

规划文档混用 lower/upper、80/95 interval、percentile interval 和可信范围。必须明确：

- LP feasible extrema；
- ensemble empirical quantiles；
- statistical confidence interval；
- Bayesian credible interval。

四者含义不同。

### 9.10 Trust Grade 不是已校准的科学可信度

当前设计没有建立 grade 与真实误差/coverage 的经验对应关系。在外部校准前应改名为 diagnostic grade 或 model-quality heuristic。

## 10. 文档之间的直接矛盾

| 主题 | 文档 A | 文档 B / 实际 |
|---|---|---|
| Stage 1 | SUMMARY：全部完成 | SUMMARY：端到端验证待完成 |
| Phase 4 | PROGRESS：消融已完成 | PROGRESS：YAML 尚未连接 solver |
| 主 solver | DEVELOPMENT：PointSolver | PROGRESS/代码：QPSolver |
| 映射顺序 | DATA：SR→FNDDS→fuzzy | 代码：FNDDS→Foundation→SR→fuzzy |
| G0–G7 | DEVELOPMENT：逐级到 fatty acid | 代码：G5=G6=G7 |
| uncertainty | DEVELOPMENT：mapping+DB perturbation+KDE | 代码：未实现这些项 |
| fortificant | DATA：直接贡献营养素 | 代码：贡献被丢弃 |
| moisture | DEVELOPMENT：读取并估计 | 代码：FNDDS 不读取，QP 不估计 |
| category YAML | PROGRESS：支持品类约束 | 代码：无 extends/解析/对应 constraint |
| report | 文档：expanded nutrients + calibrated trust | 代码：expanded 空，grade 为启发式 |
| tests | SUMMARY：202 | 实际/PROGRESS：208 |
| 文档日期 | PROGRESS：2026-07-06 | 当前审查日期：2026-07-05 |

最后一项说明 `PROGRESS.md` 的日期晚于当前工作区日期，至少需要确认是预写日期还是时间记录错误。

## 11. 建议的文档重构

### 11.1 建立唯一当前状态页

建议新增 `docs/CURRENT_STATUS.md`，由可验证事实组成：

```text
implemented
partially implemented
planned
deprecated
blocked by scientific redesign
```

每个模块必须链接到真实文件和测试。

### 11.2 将 DEVELOPMENT 改为目标设计文档

在标题和开头明确：

> 本文包含目标架构和伪代码，不代表所有模块已经实现。

对每节增加状态标签，例如 `[CURRENT]`、`[TARGET]`、`[LEGACY]`、`[INVALIDATED]`。

### 11.3 为实验建立 manifest

建议结构：

```text
experiments/
  2026-xx-xx_fndds_200/
    README.md
    config.yaml
    command.txt
    environment.txt
    results.csv
    failures.csv
    summary.json
```

`docs/PROGRESS.md` 只能引用 manifest 中的结果。

### 11.4 配置、代码和文档使用同一 schema

从 Pydantic config model 自动生成：

- YAML example；
- CLI validation；
- constraint registry；
- documentation table。

未知 constraint、未知 params 和不支持的 solver combination 必须报错。

### 11.5 自动验证文档代码

CI 增加：

- 文档示例 smoke tests；
- 检查文档引用的本地文件是否存在；
- 检查 CLI 默认配置存在；
- 检查统计数字由脚本生成；
- 检查实验结果有 manifest；
- 检查 CURRENT API signature 与文档一致。

## 12. 建议的状态修正

在修复代码前，建议先把项目状态改为：

| Phase | 建议状态 | 理由 |
|---|---|---|
| Phase 0 基础框架 | 部分完成 | schema/loader/CLI 存在，但 config schema、README、可用 CLI 不完整 |
| Phase 1 数据与 Forward | 部分完成 | adapters 和基础 forward 存在，retention/moisture pipeline 未接通 |
| Phase 2 Inverse Solver | 原型完成 | QP/LP 可运行，但约束体系、失败语义和科学模型不完整 |
| Phase 3 验证与报告 | 部分完成 | metrics/report 原型存在，但指标和区间语义有错误 |
| Phase 4 Ablation | 未完成/不可复现 | levels 冲突，配置未接 solver，缺实验产物 |
| Phase 5 Branded | adapter 原型 | 仅读取数据，未解析/映射/求解 |
| Phase 6 Pipeline | 未开始 | 无批处理 pipeline 和 nutrient expander |
| Phase 7 论文 | 不应开始定稿 | 核心 benchmark 需修复后重跑 |

## 13. 修复优先级

### 第一优先级：停止错误状态传播

1. 修正 SUMMARY/PROGRESS 的完成状态。
2. 将不可复现 benchmark 标记为 historical/unverified。
3. 把 DEVELOPMENT 标记为 target design。
4. 删除或标记所有不存在的当前 API 示例。

### 第二优先级：确定唯一设计

1. 确定 QPSolver 还是其他 solver 为主路径。
2. 确定 constraint registry 和 config schema。
3. 确定 G0–G7 唯一定义。
4. 确定 uncertainty 字段的严格语义。
5. 按 `SCIENCE_REVIEW.md` 重构 forward/label observation model。

### 第三优先级：实现和验收

1. 完成 FNDDS forward reproduction。
2. 完成 config → solver → report 端到端 pipeline。
3. 提交 benchmark manifest。
4. 完成 Branded parser/mapper 后再更新 Stage 2 文档。

## 14. 完成一致性整改的验收条件

- 每个标为 implemented 的模块都有真实文件、公开入口和测试；
- 文档中的所有示例可以运行，或明确标为伪代码；
- CLI 默认配置存在且命令成功完成真实任务；
- enabled constraint 不会被 solver 静默忽略；
- category YAML 能被实际加载、继承和执行；
- G0–G7 在代码、配置和文档中完全一致；
- benchmark 可从干净 checkout 一条命令复现；
- result manifest 包含版本、数据和失败样本；
- feasible bound、ensemble quantile 和 credible interval 不再混用；
- DEVELOPMENT、SUMMARY、PROGRESS、DATA 与当前代码无直接矛盾；
- 所有被 `SCIENCE_REVIEW.md` 判定无效的设计已删除、修正或明确标记实验性。

## 15. 最终判断

当前最大风险不是“文档少写了几个新类”，而是文档让读者相信系统已经完成了尚未接通的核心能力，并把无法从仓库复现的实验结果描述为已验证结论。

代码原型仍有继续发展的价值，但在完成一致性整改前，应把项目定位为：

> 具备若干数据适配、约束、求解和报告模块的研究原型；主 pipeline、科学观测模型、配置驱动约束、外部验证与可复现实验仍在建设中。
