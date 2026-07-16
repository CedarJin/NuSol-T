# NuSol-T 深度 Review 与修改建议

> 日期：2026-07-15  
> 分支：`refactor/yaml-solver-framework`  
> 状态：建议文档，不代表已实现功能  
> 最新项目状态参考：`docs/CURRENT_STATUS.md`

## 0. 当前执行状态

> 更新口径：本文最初是 detailed improvement plan。后续代码已经完成其中一部分 Phase A 工作；未完成项继续作为后续任务跟踪。

已完成：

- `ingredient_order` 支持 declaration group；
- `two_percent` 支持从 `declaration_group` 自动生成；
- FNDDS export 重新启用 declaration-aware order 和 two-percent rule；
- bounds output 区分 `hard_feasible_bounds` 与 `slack_budget_bounds`；
- benchmark summary 记录 `benchmark_mode`、`mapping_mode` 和 `observation_mode`；
- observation schema 支持 `source` 字段；
- `nusol.solver` 已标记为 legacy；
- legacy constraint profile YAML 已标记为非 solve document；
- Level 2 prior registry / compiler 已实现第一版机制；
- SLSQP backend 已支持 quadratic prior objective；
- `solve()` result 已输出 `prior_contributions`；
- typed `SolveResult` / `BoundsResult` 已加入并用于校验公开结果；
- prior ablation document variant generator 已加入。

部分完成：

- `constraint_diagnostics` 已输出第一版，但 objective contribution reconciliation 仍需继续用于回归测试和 benchmark 诊断；
- legacy isolation 已开始，但 report、ablation 和旧 constraint profile YAML 尚未完全隔离。

未完成：

- targeted scientific checks；
- prior calibration / sensitivity；当前 prior 参数仍是 YAML 显式声明，不是从 FNDDS 自动学习或科学标定得到；
- prior ablation 接入完整 benchmark runner。

## 1. 本文目的

本文从营养学、食品科学和 computation 三个角度，对当前 NuSol-T 项目进行一次深度 review，并提出后续修改建议。

本文不否定当前工作。当前 YAML solver framework 已经完成关键工程重构，可以支撑在 FNDDS 上验证 workflow 可行性。本文关注的是：

1. 当前实现和项目 objective 之间还有哪些差距；
2. 哪些问题会影响科学解释；
3. 哪些问题会影响代码长期可维护性；
4. 哪些改进应该优先做，哪些可以保留为后续观察项；
5. 如何在不过度复杂化系统的前提下继续提升项目质量。

## 2. 当前项目定位

当前项目的近期 focus 是：

> 在 FNDDS 上测试 NuSol-T workflow 的可行性，验证 YAML 驱动的原料比例逆向求解框架是否能稳定完成从配置、数据、约束、求解到 benchmark 的基本闭环。

Branded Food 是后续应用方向，但不是当前最主要 focus。更稳妥的阶段划分是：

1. **当前阶段：FNDDS workflow validation**
   - 验证 solver framework；
   - 验证 YAML 输入契约；
   - 验证 composition matrix、observations、constraints 和 backend 是否能稳定连接；
   - 识别欠定、冲突和不可行问题；
   - 形成可复现 benchmark workflow。

2. **下一阶段：FNDDS workflow refinement**
   - 完善 constraint semantics；
   - 引入基础 Level 2 priors；
   - 增强 diagnostics；
   - 做 ablation 和 sensitivity；
   - 检查特殊食品类别，例如高纤维食品、酒精食品、强化食品。

3. **后续阶段：Branded Food application**
   - 真实标签 parser；
   - 标签短名到 USDA ingredient profile 的 mapper；
   - mapping uncertainty；
   - external validation 或 case-study validation；
   - TrustReport。

因此，本文对 benchmark 的建议重点不是要求立即达到真实 Branded Food 条件，而是要求文档和代码明确当前 benchmark 的科学边界。

## 3. 总体结论

当前 NuSol-T 的工程主链路已经基本成立：

```text
YAML
  → resolved config
  → IngredientProblem
  → solver-neutral IR
  → SLSQP point solve / HiGHS bounds solve
  → result + manifest
```

这条链路已经可以支撑 FNDDS workflow feasibility testing。

但从项目长期 objective 看，还有三个核心缺口：

1. **Prior 机制已完成第一版，但仍需校准和消融**
   - 项目核心科学目标是用有证据的先验解决欠定逆问题；
   - 当前已支持 Level 2 deterministic / MAP-style priors；
   - 目前 prior 的数值参数来自 YAML 显式声明；
   - 仓库测试和示例中的 prior 参数只用于机制验证，不应解释为科学结论；
   - calibrated priors 和 prior sensitivity 仍是后续任务。

2. **Diagnostics 不够细**
   - 当前 point solver 主要返回总 objective 和 fractions；
   - 当前已有 per-constraint slack 和 per-prior contribution；
   - 仍缺少更直接的 per-observation residual view；
   - 这会限制科学解释、错误定位和后续 TrustReport。

3. **新旧模块仍并存**
   - YAML solver framework 是当前主链路；
   - legacy solver、report、ablation 和旧 constraint YAML 仍存在；
   - 如果不明确隔离，会持续造成文档、代码和用户理解之间的漂移。

## 4. 优先级总览

| 优先级 | 方向 | 问题 | 建议 |
|---|---|---|---|
| P0 | Constraint semantics | `ingredient_order` 不理解 `two_percent_or_less` | 优先修 |
| P0 | Result diagnostics | 缺少 constraint / observation 级别诊断 | 优先修 |
| P0 | Prior objective | Level 2 prior compiler/backend 已有第一版 | 下一步做校准、消融和 sensitivity |
| P1 | Benchmark interpretation | 当前 FNDDS benchmark 应明确是 workflow feasibility / code-assisted mapping 条件 | 文档修正，不必立即重做全部 |
| P1 | Legacy isolation | 旧 solver/report/config 仍可能被误用 | 标记 legacy 或迁移 |
| P1 | Bounds semantics | hard feasible bounds 与 slack-budget bounds 需要明确区分 | 输出字段和文档修正 |
| P2 | Label observation | 当前可先保留简单区间策略 | 后续做 sensitivity，不急于复杂化 |
| P2 | Energy closure | 当前可保留 heuristic | 后续专门检查 fiber/alcoholic food performance |
| P2 | Ruff / scripts quality | scripts 和部分核心路径仍有 lint 债务 | 分阶段清理 |

## 5. 详细问题与修改建议

### 5.1 `ingredient_order` 需要支持声明分组

#### 当前问题

当前 builtin `ingredient_order` 对所有相邻 ingredient 强制：

```text
x_i >= x_{i+1}
```

这对普通 main ingredient list 成立，但对 `contains 2% or less of` group 不一定成立。真实标签里，≤2% group 之后的成分通常可以不按严格投料顺序解释，且不应简单把 main group 和 ≤2% group 作为一条连续降序链。

#### 科学影响

配料顺序是最强的 Level 1 structural prior 之一。如果这个 prior 的语义错误，求解器会把错误的法规结构当成 hard constraint，导致：

- 可行域被错误缩小；
- 某些真实可行解被排除；
- benchmark 中不得不跳过 order constraint；
- 后续 Branded Food 阶段会遇到大量真实标签问题。

#### Proposed fix

将 `ingredient_order` 从“全列表相邻降序”改为 declaration-aware constraint。

建议规则：

1. `main` group 内部按 declaration_position 强制降序；
2. `two_percent_or_less` group 不默认强制内部降序；
3. `two_percent_or_less` group 中每个 ingredient 自动生成 `x_i <= 0.02`；
4. main group 和 two-percent group 之间的连接关系需要显式配置，默认不强制；
5. 如果 YAML 显式要求 two-percent group 内部排序，才启用。

建议 YAML：

```yaml
constraints:
  - id: declaration_order
    type: ingredient_order
    mode: hard
    config:
      groups: ["main"]
      include_two_percent_group_order: false
      link_main_to_two_percent: false

  - id: two_percent_rule
    type: two_percent
    mode: hard
    config:
      source: declaration_group
```

#### 验收条件

- main-only 配料表保持现有行为；
- main + two-percent 配料表只对 main group 强制降序；
- two-percent group 自动生成 `x_i <= 0.02`；
- benchmark export 不再需要因为 two-percent issue 跳过 ingredient_order；
- 有单元测试覆盖：
  - main-only；
  - main + two-percent；
  - two-percent internal order disabled；
  - explicit internal order enabled。

### 5.2 Point solver 需要输出可解释 diagnostics

#### 当前问题

当前 point solver 返回：

- fractions；
- success/status；
- objective_value；
- iterations；
- solve_time。

但缺少以下关键诊断：

- 每个 observation 的 predicted value；
- 每个 observation interval 的 residual；
- 每个 soft constraint 的 slack；
- 每个 constraint 对 objective 的 contribution；
- hard constraint violation check；
- constraint source_id。

#### 科学影响

没有这些 diagnostics，结果很难解释：

- 不知道是哪一个 nutrient 驱动了解；
- 不知道哪个标签值无法满足；
- 不知道 soft label fit 是否大幅违反；
- 无法比较 prior 和 observation 的冲突；
- 无法构建可信 TrustReport。

#### Proposed fix

在 backend 或 result assembly 阶段生成 `constraint_diagnostics`。

建议结构：

```json
{
  "constraint_diagnostics": [
    {
      "source_id": "label_fit",
      "ir_id": "nu_hi_energy_kcal",
      "type": "linear_constraint",
      "mode": "soft",
      "weight": 10.0,
      "value": 430.2,
      "lower": null,
      "upper": 420.0,
      "raw_violation": 10.2,
      "slack": 10.2,
      "weighted_penalty": 1040.4
    }
  ]
}
```

#### 验收条件

- `solve()` result 包含 observation-level diagnostics；
- 每个 enabled constraint 都可追溯到 YAML `id`；
- objective_value 等于各 soft contribution 之和，允许数值容差；
- hard constraint violation 不为 0 时必须导致 failure 或 explicit warning；
- diagnostics 可被后续 report 模块直接消费。

### 5.3 Level 2 Prior 应成为下一阶段核心

#### 当前问题

当前 YAML schema 已有 `PriorSpec`。第一版实现支持 `fraction_interval_prior`、`group_total_prior`、`recipe_center_prior`、`anti_extreme_prior` 和 `ratio_prior`，并将 prior contribution 输出到结果中。

但项目 objective 是：

> 通过先验知识解决方程欠定问题。

因此，prior 层已经从“接口预留”进入“可运行初版”。后续重点不是继续堆更多 prior 类型，而是做 calibration、ablation 和 sensitivity。

需要明确一个科学边界：当前实现完成的是 prior 的表达、校验、编译、求解和诊断机制；不是已经完成的科学先验库。当前 prior 参数由 YAML 作者显式给出，测试和示例中的数值主要用于证明机制可运行，不应被当作经过 FNDDS 或食品学实证标定的参数。后续所有用于正式推断的 prior 都必须带有可追溯 `evidence`，并说明来源、样本范围、统计口径、适用 food category 和版本。

#### Proposed fix

已先实现 Level 2 deterministic / MAP priors，不直接跳到 Bayesian。

首批建议实现：

1. `fraction_interval_prior`
   - 单个 ingredient 的合理比例区间；
   - 例如 salt 通常不超过某阈值。

2. `group_total_prior`
   - 一组 ingredient 的总比例区间；
   - 例如 flour-like ingredients 总量。

3. `recipe_center_prior`
   - 相对某类食品中心配方的二次距离；
   - 适合 FNDDS category-level calibration。

4. `anti_extreme_prior`
   - 抑制无证据的极端边界解；
   - 只能作为弱 prior，必须可关闭。

5. `ratio_prior`
   - 两个 ingredient 或 ingredient group 之间的比例关系；
   - 例如 oil 不应大幅超过 meat group。

建议 YAML：

```yaml
priors:
  - id: salt_fraction_prior
    type: fraction_interval_prior
    enabled: true
    weight: 0.2
    evidence:
      status: experimental
      source: fndds_training_split
      version: "2026-07-15"
    config:
      ingredient: salt
      interval: [0.0, 0.02]
      loss: squared_hinge
```

上面的数值只能作为格式示例。正式 prior 不应靠个人经验或代码作者直觉固化；推荐来源顺序是：

1. FNDDS category-level calibration statistics；
2. 独立 benchmark / held-out split；
3. 明确记录的专家规则或法规规则；
4. 仅用于 debug 的 hand-written example prior。

每个正式 prior 至少应记录：

- `evidence.status`：`example` / `experimental` / `calibrated` / `deprecated`；
- 数据来源和版本；
- food category 或适用条件；
- 统计口径，例如 p10-p90、median/IQR、empirical center；
- 样本量或覆盖范围；
- 生成脚本或 calibration artifact。

#### 工程设计建议

已新增：

```text
src/nusol/priors/
  base.py
  registry.py
  builtin/
    fraction_interval.py
    group_total.py
    recipe_center.py
    anti_extreme.py
    ratio.py
```

并在 compiler 中明确区分：

```text
ConstraintSpec → feasible-region IR
PriorSpec      → objective/prior IR
```

不要把 prior 继续塞进 constraint plugin 里，否则 hard feasibility 和 soft preference 会混乱。

#### 已完成验收条件

- enabled prior 未注册时失败；
- registered prior 能产生 objective contribution；
- weight 进入 objective；
- result 输出 prior contribution；
- prior 不改变 hard feasible bounds，除非 YAML 明确声明 slack/probabilistic bounds；

#### 仍未完成

- prior 参数的 FNDDS category-level calibration；
- no-prior / single-prior / combined-prior ablation 接入完整 benchmark runner；
- prior weight sensitivity；
- 将 hand-written example prior 与 calibrated prior 在文档和输出中明确区分。

### 5.4 Bounds 语义需要更明确

#### 当前问题

HiGHS bounds 默认只使用 hard constraints。soft label intervals 不进入 bounds，除非使用 explicit slack budget。

这是合理的数学设计，但容易被误读。

#### Proposed fix

结果字段不要只叫 `bounds`，建议拆成：

```json
{
  "bounds": {
    "type": "hard_feasible_bounds",
    "values": {
      "flour": [0.2, 0.8]
    }
  }
}
```

或更明确：

```json
{
  "hard_feasible_bounds": {},
  "slack_budget_bounds": {},
  "posterior_intervals": null
}
```

#### 验收条件

- 用户能从 result 直接知道 bounds 是否包含 label slack；
- docs 明确 feasible bounds 不是 credible interval；
- TrustReport 不把 feasible bounds 命名为 Bayesian interval。

### 5.5 Benchmark 解释需要更精确

#### 当前问题

当前 FNDDS benchmark 对 workflow 很有价值，但应避免表述为已经模拟真实 Branded Food 条件。脚本当前会使用 FNDDS ingredient code 进行 code-assisted mapping。

#### 用户补充口径

当前阶段的重点是在 FNDDS 上评估 workflow 可行性；Branded Food 是后续方向，不是当前主要 focus。

这个口径合理。建议不是立即重做 benchmark，而是把 benchmark 类型标清楚。

#### Proposed fix

将 benchmark 分层命名：

1. `fndds_workflow_code_assisted`
   - 当前 benchmark；
   - 允许使用 FNDDS ingredient code；
   - 目标是验证 workflow 和 solver。

2. `fndds_workflow_name_only`
   - 后续 benchmark；
   - 禁止使用 FNDDS ingredient code；
   - 目标是提前模拟 mapping difficulty。

3. `fndds_labelized_name_only`
   - 更后续；
   - 加入 labelized observation；
   - 目标是接近 Branded Food 条件。

#### 文档建议

当前 `CURRENT_STATUS.md` 中可以把 benchmark 解释为：

> FNDDS workflow feasibility benchmark under code-assisted ingredient-profile mapping.

而不是：

> fully branded-food-like benchmark.

### 5.6 Label observation 暂时可以保留简化策略

#### 当前讨论

标签观测如果过度自定义，会导致解释困难和 reproduce 困难。当前阶段使用清晰、简单、统一的 interval strategy 是合理的。

#### 建议

短期不建议大幅扩展 label observation metadata。

当前可以保留：

- YAML 中显式 interval；
- 简单可解释；
- 可复现；
- 不隐含复杂法规逻辑。

但建议加两个最小保护：

1. 每个 observation interval 记录来源：

```yaml
observations:
  - nutrient: energy_kcal
    unit: kcal
    interval: [90, 110]
    source: fndds_workflow_interval
```

如果暂时不改 schema，也至少在 benchmark summary 中记录 interval construction method。

2. 后续单独做 sensitivity：

```text
±5%
±10%
±20%
FDA labelized interval
```

看 solver performance 是否对 interval construction 敏感。

#### 触发升级条件

只有当下面情况出现时，再考虑更复杂 label model：

- 同一类食品在 ±10% 下表现好，但真实 labelized simulation 明显变差；
- 某些 nutrient 系统性造成 infeasible；
- low-value nutrients，例如 sodium、cholesterol、saturated fat，出现大量边界误差；
- Branded Food 阶段无法解释 label mismatch。

### 5.7 Energy closure 先作为观察项，不急于复杂化

#### 当前讨论

Energy closure 如果需要太多 metadata，会增加系统复杂度。是否值得引入，需要看 fiber-rich food 和 alcoholic food 上的 prediction error。

这个判断合理。

#### 建议

短期：

- 不把 energy closure 作为 hard universal constraint；
- 不引入复杂 metadata；
- 保留当前 heuristic；
- 在 diagnostics 中记录 energy-related residual。

中期：

增加 targeted evaluation：

1. high-fiber foods；
2. alcoholic foods；
3. sugar-alcohol / low-carb products；
4. fortified cereals；
5. products with organic acids or polyols, if data exists。

#### 决策规则

如果当前 simple energy approach 在上述类别中误差小，继续保留。

如果出现系统性偏差，再考虑加 metadata：

```yaml
model:
  type: linear_mixing
  config:
    energy:
      method: atwater_general
      carbohydrate_definition: by_difference_includes_fiber
      alcohol_mode: explicit_if_present
```

注意：这类 metadata 只有在实证证明必要时才加入，不应预先复杂化。

### 5.8 Forward model 的 yield / moisture 语义需要锁定

#### 当前问题

`ForwardNutritionModel.compute()` 的 `moisture_change` 注释说 fraction，例如 `0.05 = 5%`，但公式按百分数使用：

```text
yield_factor = 100 / (100 - moisture_change)
```

如果传入 `0.05`，实际只表示 0.05%，不是 5%。

#### Proposed fix

短期：

- 修改参数名或文档，明确单位；
- 推荐使用 `yield_factor` 或 `finished_yield_ratio`，避免 ambiguity。

中期：

把 yield 作为 explicit model parameter：

```yaml
model:
  type: linear_mixing
  config:
    yield:
      enabled: false
      basis: finished_mass_per_input_mass
      value: 1.0
```

#### 验收条件

- 单元测试覆盖 10% moisture loss；
- docstring 和公式一致；
- YAML 中不允许 ambiguous moisture fraction。

### 5.9 Fortificant 不应长期只靠 skip

#### 当前问题

当前 FNDDS export 已经能识别 fortificant，并把它们从普通 ingredient fraction 求解中分离，输出 `fortification` diagnostics。对于 calcium、iron、fiber 等质量换算明确的 fortificant，export 会先估计 fortificant contribution 并从 label observation 中扣除；可能由 fortification 主导但无法定量的 nutrients 会被结构化记录为 skipped/suspected nutrients。这比原先只靠 skip 更可复现，但还没有处理 vitamin D、B vitamins、folic acid premix 等 potency 依赖营养素，因此仍不能完整解释 fortified cereal 的全部强化维生素/矿物质。

#### Proposed fix

短期：

- 保留普通 ingredient solve 与 fortificant layer 分离的策略；✅
- 在 benchmark summary 中明确记录 skipped fortificant 和 skipped nutrient；✅
- 对 calcium/iron/fiber 等可量化 fortificant contribution 做 observation adjustment；✅
- 不把相关 nutrient 纳入 MAE 解释。

中期：

加入 pseudo-ingredient：

```yaml
ingredients:
  - id: vitamin_d_fortificant
    name: Vitamin D fortificant
    declaration_group: fortificant
```

或者作为 additive component：

```yaml
model:
  additives:
    - nutrient: vitamin_d_mcg
      source: fortification
      variable: true
```

这可以放到 Branded Food 之前，但不必作为当前最高优先级。

### 5.10 Parser / Mapper 不是当前 focus，但接口应提前避免返工

#### 当前状态

`IngredientParser` 已经有基础实现，但尚不足以处理真实包装食品复杂 ingredient list。当前 focus 是 FNDDS workflow，所以这不是 P0。

#### 建议

短期不需要把 parser 做完整，但应提前定义 interface：

```text
raw_label_text
  → IngredientTree
  → IngredientCandidate[]
  → mapped ingredient profile
  → mapping provenance
```

每个 mapping candidate 至少包括：

- query；
- matched description；
- source database；
- confidence；
- match method；
- nutrient coverage；
- warnings。

这样后续 Branded Food 接入时不会破坏 solver 主链路。

### 5.11 Legacy 模块需要隔离

#### 当前问题

仓库仍有旧体系模块：

- `src/nusol/solver/*`
- `src/nusol/report/trust.py`
- `src/nusol/report/trust_grade.py`
- `src/nusol/validation/ablation.py`
- `config/constraints/*.yaml`

这些模块可以作为历史参考，但不应与 YAML solver framework 混在同一“当前能力”叙述中。

#### Proposed fix

选择一种策略：

1. 移动到 `src/nusol/legacy/`；
2. 保留原路径但加 runtime deprecation warning；
3. docs 明确标记 legacy；
4. tests 中将 legacy tests 单独 marker：`@pytest.mark.legacy`。

建议最小改法：

- 在 legacy module docstring 顶部加：

```python
"""Legacy module. Current public solve path is nusol.solve(yaml_path)."""
```

- 在 `docs/PROGRESS.md` 中列出 legacy isolation 是 Phase 9 task。

### 5.12 Constraint profile YAML 需要重新定位

#### 当前问题

`config/constraints/*.yaml` 不是当前 solve YAML schema，但文件名和位置容易让人误以为可以直接用于 solver。

这些 YAML 包含很多尚未实现或旧命名的 constraints，例如：

- `unique_source_lower_bound`
- `similarity_anti_extreme`
- `water_solid_balance`
- `category_prior`

#### Proposed fix

短期：

- 移动到 `docs/legacy_constraint_profiles/`；
或者：
- 改名为 `config/legacy_constraint_profiles/`；
或者：
- 在每个文件顶部加明确 warning：

```yaml
# WARNING:
# This is a legacy design profile, not a NuSol YAML 1.0 solve document.
# It is not consumed by nusol.solve().
```

中期：

把其中仍有价值的 prior 转成新的 `PriorSpec` examples。

## 6. 建议实施路线

### Phase A：语义收敛，低风险高收益

1. 修复 `ingredient_order` group semantics；
2. 自动支持 `two_percent` from declaration_group；
3. 修改 benchmark 文档口径，标明 current benchmark 是 FNDDS workflow feasibility；
4. result 中区分 hard feasible bounds 和 slack-budget bounds；
5. 给 legacy modules / legacy constraint profiles 加 warning。

预期收益：

- 当前 workflow 科学解释更稳；
- 减少文档和代码漂移；
- benchmark 可以重新启用 ingredient_order；
- 为后续 Branded Food 减少返工。

### Phase B：Diagnostics 和 result schema

1. 新增 typed `SolveResult`；✅
2. 输出 observation residuals；✅ 当前输出 `observation_diagnostics`；
3. 输出 constraint diagnostics；✅
4. 输出 objective contribution；✅
5. manifest 记录 benchmark mode、interval construction method、mapping mode；部分完成，benchmark summary 已记录。

预期收益：

- 结果可解释；
- debug 效率提升；
- 为 TrustReport 打基础；
- 可以开始做 ablation 和 sensitivity。

### Phase C：Level 2 Prior

1. 新增 `src/nusol/priors/`；✅
2. 实现 `fraction_interval_prior`；✅
3. 实现 `group_total_prior`；✅
4. 实现 `anti_extreme_prior`；✅
5. 实现 prior contribution diagnostics；✅
6. 做 no-prior / single-prior / combined-prior ablation。部分完成：已支持 document variant generation，待接入 benchmark runner。

预期收益：

- 项目开始真正解决欠定问题；
- prior 的科学作用可被量化；
- 后续 Bayesian 层有稳定接口。

### Phase D：Targeted scientific checks

不急于复杂化 observation 或 energy metadata。先做 targeted checks：

1. high-fiber food；
2. alcoholic food；
3. fortified food；
4. high-sodium soup；
5. oil-rich meat/seafood；
6. dairy dessert with similar ingredients。

根据 empirical error 决定是否引入更复杂 metadata。

## 7. 不建议现在做的事

1. 不建议立即上 Bayesian / hierarchical model。
   - Prior 初版和 diagnostics 已可运行，但 calibration、sensitivity 和报告语义还没稳；
   - 先做 deterministic MAP 更可解释。

2. 不建议立即复杂化 label observation schema。
   - 当前目标是 FNDDS workflow；
   - 过度自定义会降低 reproducibility。

3. 不建议把 TrustGrade 作为当前成果。
   - 还没有 calibrated prior；
   - 还没有 external validation；
   - 当前可以保留 diagnostic score，但不要叫 calibrated trust。

4. 不建议把 Branded Food 大规模 pipeline 作为下一步最高优先级。
   - 先把 FNDDS workflow 的 semantics、diagnostics 和 prior 层做扎实。

## 8. 建议新增测试

### Constraint tests

- declaration-aware ingredient order；
- two-percent group auto bound；
- hard/soft bounds distinction；
- unknown prior failure；
- registered prior objective contribution。

### Benchmark tests

- benchmark mode metadata 存在；
- code-assisted mapping mode 明确记录；
- interval construction method 明确记录；
- skipped fortificant nutrients 被记录。

### Diagnostics tests

- objective equals sum of weighted penalties；
- hard constraints satisfied；
- each observation produces predicted/residual；
- each prior produces contribution。

### Scientific regression fixtures

- high-fiber food；
- alcoholic food；
- fortified cereal；
- soup with salt；
- oil-heavy meat dish；
- similar dairy dessert ingredients。

## 9. 修改后的能力表述建议

推荐当前项目表述：

> NuSol-T 当前已完成 YAML-driven inverse solver framework，并在 FNDDS workflow feasibility benchmark 中验证了从配置、数据映射、约束求解到 MAE 统计的闭环可行性。当前结果证明 solver framework 有实用潜力，但还不等价于真实 Branded Food 外部验证，也不代表 calibrated prior-driven inference 已完成。

避免当前阶段使用：

- “恢复真实商业配方”；
- “credible interval”；
- “calibrated TrustGrade”；
- “fully branded-food-like benchmark”；
- “食品科学先验已完成”。

## 10. 最推荐的下一组改动

如果下一轮直接动代码，建议按下面顺序：

1. `ingredient_order` 支持 declaration group；
2. `two_percent` 从 declaration group 自动生成；
3. `solve()` result 增加 constraint / observation diagnostics；
4. benchmark summary 写入 `benchmark_mode` 和 `mapping_mode`；
5. legacy constraint profiles 加 warning；
6. 实现第一个 Level 2 prior：`fraction_interval_prior`。✅

这组改动的收益最大，因为它们同时改善：

- 科学语义；
- 工程一致性；
- 后续 prior 框架；
- FNDDS workflow 可解释性；
- Branded Food 未来扩展路径。
