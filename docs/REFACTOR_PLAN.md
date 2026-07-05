# NuSol-T YAML 求解框架重构计划

> 分支：`refactor/yaml-solver-framework`  
> 计划日期：2026-07-05  
> 状态：待实施  
> 目标：将 NuSol-T 重构为以 YAML 为唯一公开求解输入、支持自定义约束、可替换求解器和食品科学扩展的原料比例计算框架。

## 1. 重构目标

框架只解决一个稳定的核心问题：

> 给定原料、原料营养组成、成品营养观测、配料声明信息、约束和先验，估计原料投料质量比例及其数学可行范围。

公开入口统一为：

```bash
nusol validate problem.yaml
nusol resolve problem.yaml --output resolved.yaml
nusol inspect problem.yaml
nusol solve problem.yaml
```

Python 公开接口同样只接受 YAML：

```python
result = nusol.solve("problem.yaml")
```

内部实现流程：

```text
YAML
  → Parse
  → Resolve inheritance/defaults
  → Strict schema validation
  → Resource loading and checksum validation
  → IngredientProblem
  → Constraint/Prior compilation
  → Solver-neutral IR
  → Backend capability validation
  → LP/QP/NLP/MILP backend
  → Typed result and diagnostics
```

## 2. 非目标

本次重构首版不实现：

- Bayesian 或分层人群模型；
- 完整食品加工化学模型；
- 自动猜测产品密度；
- 未经校准的类别先验；
- 概率意义上的 credible interval；
- Branded Food 大规模生产 pipeline；
- 自动执行 YAML 中的 Python 代码。

这些能力只预留扩展接口。

## 3. 不可违反的工程原则

1. YAML 是唯一公开求解输入。
2. 所有求解输入、数据资源、约束、先验、模型、solver 和输出要求必须由 YAML 声明。
3. YAML 只能声明配置，不得嵌入任意可执行代码。
4. 未知字段、未知约束、未知参数必须报错。
5. backend 不支持 enabled constraint 时必须报错，不能静默忽略。
6. 所有默认值必须出现在 resolved YAML 中。
7. 每次运行必须保存 resolved YAML、资源 checksum、软件版本和 solver diagnostics。
8. 配料内部使用稳定 ID，不使用 description 作为唯一键。
9. feasible bounds、ensemble quantiles 和 posterior intervals 必须使用不同字段。
10. 新旧系统迁移期间，legacy 结果只能作为回归参考，不能作为科学正确性标准。

## 4. 目标架构

```text
src/nusol/
├── api.py                         # solve(yaml_path) 唯一公开 API
├── cli.py                         # validate/resolve/inspect/solve
│
├── config/
│   ├── schema.py                  # YAML Pydantic schema
│   ├── loader.py                  # YAML parsing
│   ├── resolver.py                # extends/defaults/overrides
│   ├── resources.py               # 外部资源加载和 checksum
│   └── errors.py
│
├── problem/
│   ├── schema.py                  # IngredientProblem 领域模型
│   ├── builder.py                 # ResolvedConfig → IngredientProblem
│   └── validation.py              # 单位、shape、ID、interval 校验
│
├── composition/
│   ├── schema.py                  # NutrientValue/CompositionMatrix
│   ├── loaders.py                 # inline/csv/FDC adapter
│   └── missingness.py
│
├── observation/
│   ├── base.py
│   ├── interval.py                # 首版区间观测
│   └── fda.py                     # 后续扩展
│
├── models/
│   ├── base.py                    # ForwardModel protocol
│   └── linear_mixing.py           # 首版模型
│
├── constraints/
│   ├── base.py
│   ├── registry.py
│   ├── mass_balance.py
│   ├── ingredient_order.py
│   ├── two_percent.py
│   ├── nutrient_interval.py
│   ├── declared_percentage.py
│   └── linear_expression.py
│
├── priors/
│   ├── base.py
│   └── registry.py
│
├── compiler/
│   ├── ir.py                      # solver-neutral IR
│   ├── compiler.py
│   └── capability.py
│
├── backends/
│   ├── base.py
│   ├── registry.py
│   ├── scipy_qp.py
│   └── highs_lp.py
│
├── plugins/
│   ├── discovery.py
│   └── manifest.py
│
├── results/
│   ├── schema.py
│   ├── diagnostics.py
│   └── writer.py
│
├── validation/
│   └── metrics.py
│
└── legacy/
    └── context_adapter.py         # 临时迁移层，最终删除
```

## 5. YAML 1.0 契约

### 5.1 最小完整示例

```yaml
schema_version: "1.0"
problem_id: bread_example

basis:
  ingredient_mass: input_fraction
  nutrient_amount: per_100g_finished_product

ingredients:
  - id: flour
    name: Wheat flour
    declaration_position: 0
    declaration_group: main

  - id: sugar
    name: Sugar
    declaration_position: 1
    declaration_group: main

  - id: oil
    name: Vegetable oil
    declaration_position: 2
    declaration_group: main

composition:
  source:
    type: inline
  nutrients:
    - id: energy
      unit: kcal
    - id: protein
      unit: g
    - id: fat
      unit: g
  values:
    flour: [364.0, 10.3, 1.0]
    sugar: [387.0, 0.0, 0.0]
    oil: [884.0, 0.0, 100.0]

observations:
  - nutrient: energy
    interval: [410.0, 430.0]
    unit: kcal
    basis: per_100g_finished_product

  - nutrient: protein
    interval: [5.0, 6.0]
    unit: g
    basis: per_100g_finished_product

model:
  type: linear_mixing

variables:
  ingredient_fractions:
    lower: 0.0
    upper: 1.0

constraints:
  - id: total_mass
    type: mass_balance
    mode: hard
    target: 1.0

  - id: declaration_order
    type: ingredient_order
    mode: hard
    ingredients: [flour, sugar, oil]

  - id: label_fit
    type: nutrient_interval
    mode: soft
    loss: squared_hinge
    weight: 10.0

solver:
  point:
    backend: scipy_slsqp
    options:
      max_iterations: 500
      tolerance: 1.0e-8
  bounds:
    backend: highs_lp

output:
  path: output/bread_example.json
  include:
    - point_estimate
    - feasible_bounds
    - constraint_diagnostics
```

### 5.2 外部资源

大型 composition matrix 不要求内嵌，但必须由 YAML 完整声明：

```yaml
composition:
  source:
    type: csv
    path: data/composition.csv
    sha256: "<required-checksum>"
    key_column: ingredient_id
    missing_value_policy: error
```

首版支持：

- `inline`
- `csv`
- `json`

FoodData Central adapter 在基础契约稳定后接入。

### 5.3 配置继承

```yaml
schema_version: "1.0"
extends:
  - templates/base_linear_inverse.yaml

problem_id: bread_001

constraints:
  - id: category_prior
    enabled: false
```

规则：

- mapping 递归合并；
- ingredients 按 `id` 合并；
- constraints/priors 按 `id` 合并；
- 普通列表默认替换，不做隐式拼接；
- 检测循环继承；
- resolve 后生成完全展开且无 `extends` 的 YAML；
- solver 只接收 resolved config。

## 6. 自定义约束设计

### 6.1 内置声明式约束

首版内置：

```text
mass_balance
ingredient_order
two_percent
nutrient_interval
declared_percentage
linear
```

通用线性约束示例：

```yaml
constraints:
  - id: oil_not_above_meat
    type: linear
    mode: hard
    coefficients:
      oil: 1.0
      beef: -1.0
      chicken: -1.0
    upper: 0.0
```

软范围约束：

```yaml
  - id: flour_preference
    type: linear
    mode: soft
    coefficients:
      flour: 1.0
    lower: 0.30
    upper: 0.75
    loss: squared_hinge
    weight: 0.1
    evidence:
      status: experimental
      source: controlled_bread_recipes_v1
```

### 6.2 插件约束

复杂约束通过预安装插件注册：

```yaml
constraints:
  - id: custom_texture_prior
    type: plugin
    plugin: my_lab_constraints.texture_prior
    version: "1.2"
    mode: soft
    weight: 0.4
    parameters:
      threshold: 0.75
```

插件要求：

```python
@constraint_registry.register(
    name="my_lab_constraints.texture_prior",
    version="1.2",
    capabilities={"continuous", "nonlinear"},
)
class TexturePrior(CustomConstraint):
    parameter_model = TexturePriorParameters

    def compile(self, problem, parameters):
        ...
```

约束插件必须声明：

- 唯一名称；
- semantic version；
- 参数 Pydantic model；
- 所需 problem features；
- 所需 backend capabilities；
- 编译结果类型；
- provenance。

YAML 不允许指定模块文件路径或 Python expression，只能引用已注册插件名称。

## 7. Solver-neutral IR

### 7.1 IR 类型

```python
@dataclass(frozen=True)
class VariableIR:
    id: str
    lower: float | None
    upper: float | None
    kind: Literal["continuous", "integer", "binary"]

@dataclass(frozen=True)
class LinearConstraintIR:
    id: str
    coefficients: NDArray[np.float64]
    lower: float | None
    upper: float | None

@dataclass(frozen=True)
class QuadraticPenaltyIR:
    id: str
    quadratic: NDArray[np.float64]
    linear: NDArray[np.float64]
    constant: float
    weight: float

@dataclass(frozen=True)
class NonlinearConstraintIR:
    id: str
    evaluator: Callable
    lower: float | None
    upper: float | None

@dataclass(frozen=True)
class CompiledProblem:
    variables: tuple[VariableIR, ...]
    linear_constraints: tuple[LinearConstraintIR, ...]
    quadratic_penalties: tuple[QuadraticPenaltyIR, ...]
    nonlinear_constraints: tuple[NonlinearConstraintIR, ...]
    required_capabilities: frozenset[str]
```

### 7.2 Backend capabilities

```text
highs_lp:
  continuous
  linear_objective
  linear_constraints

scipy_slsqp:
  continuous
  quadratic_objective
  nonlinear_objective
  linear_constraints
  nonlinear_constraints
```

编译后、求解前执行 capability check。缺失能力直接产生配置错误。

## 8. 领域模型

### 8.1 IngredientProblem

```python
class IngredientProblem(BaseModel):
    schema_version: str
    problem_id: str
    basis: ProblemBasis
    ingredients: tuple[Ingredient, ...]
    composition: CompositionMatrix
    observations: tuple[NutrientObservation, ...]
    model: ForwardModelSpec
    variables: VariableSpec
    constraints: tuple[ConstraintSpec, ...]
    priors: tuple[PriorSpec, ...]
    provenance: ProblemProvenance
```

### 8.2 NutrientValue

```python
class NutrientValue(BaseModel):
    value: float | None
    unit: str
    basis: str
    status: Literal[
        "measured",
        "calculated",
        "imputed",
        "below_loq",
        "missing",
    ]
    lower: float | None = None
    upper: float | None = None
    provenance: dict[str, str] = {}
```

首版 linear solver 规则：

- `measured/calculated/imputed` 且 value 有限：可进入 matrix；
- `below_loq`：只有在策略明确时转换为 interval；
- `missing`：不得自动转换为 0；
- matrix 对用于 observation constraint 的缺失营养素默认报错；
- 可通过 YAML 显式选择 `drop_nutrient`，但 resolved YAML 必须记录决策。

## 9. 结果模型

```python
class IngredientResult(BaseModel):
    ingredient_id: str
    point_estimate: float | None
    feasible_lower: float | None
    feasible_upper: float | None

class SolveDiagnostics(BaseModel):
    success: bool
    status: str
    message: str
    backend: str
    objective_value: float | None
    constraint_evaluations: list[ConstraintDiagnostic]
    unsupported_features: list[str]
    iterations: int | None
    solve_time_seconds: float

class SolveResult(BaseModel):
    schema_version: str
    problem_id: str
    ingredients: list[IngredientResult]
    diagnostics: SolveDiagnostics
    resolved_config_path: str
    resource_checksums: dict[str, str]
    software_version: str
```

首版不再提供 `interval_80`、`interval_95` 或 `trust_grade`。

## 10. 分阶段迁移计划

### Phase 0：冻结 legacy 基线

目标：保留当前行为，防止重构过程中无法判断变化来源。

任务：

- [ ] 记录当前 commit、测试结果和已知失败；
- [ ] 保存三个小型 synthetic fixtures；
- [ ] 保存一个可行、一个不可行、一个欠定问题；
- [ ] 将当前 QPSolver/BoundSolver 标记 legacy；
- [ ] 不把当前 benchmark 数字作为正确性验收标准。

验收：

- legacy tests 可单独运行；
- fixtures 不依赖外部 USDA 大文件。

### Phase 1：YAML schema、resolver 和 validate CLI

任务：

- [ ] 实现 `SolveDocument` Pydantic schema；
- [ ] `extra="forbid"`；
- [ ] 实现 YAML loader；
- [ ] 实现 `extends` 和按 ID merge；
- [ ] 实现循环继承检测；
- [ ] 实现 resolved YAML 输出；
- [ ] 实现 resource checksum；
- [ ] 实现 `nusol validate`；
- [ ] 实现 `nusol resolve`。

验收：

- 一个最小 YAML 可 validate 和 resolve；
- 拼错字段、重复 ingredient ID、重复 constraint ID 必须失败；
- 相同输入产生字节稳定的 canonical resolved YAML；
- 默认值全部可见。

### Phase 2：领域模型和 Linear Mixing Model

任务：

- [ ] 实现 IngredientProblem；
- [ ] 实现稳定 ingredient ID；
- [ ] 实现 CompositionMatrix；
- [ ] 实现 NutrientValue missingness；
- [ ] 实现 basis/unit/shape validation；
- [ ] 实现 inline/csv/json composition loader；
- [ ] 实现 LinearMixingModel。

验收：

- `x @ A` 的维度、ID 和单位严格校验；
- missing 不会被自动填 0；
- observation 和 matrix nutrient ID 必须一一匹配；
- 非法 interval、NaN、Inf 必须失败。

### Phase 3：Constraint registry 和 IR compiler

任务：

- [ ] 实现 constraint registry；
- [ ] 实现 parameter schema 注册；
- [ ] 实现 `mass_balance`；
- [ ] 实现 `ingredient_order`；
- [ ] 实现 `two_percent`；
- [ ] 实现 `nutrient_interval`；
- [ ] 实现 `declared_percentage`；
- [ ] 实现通用 `linear`；
- [ ] 实现 solver-neutral IR；
- [ ] 实现 capability aggregation；
- [ ] 未知/不支持约束严格失败。

验收：

- 每个约束都有 YAML→schema→IR 单元测试；
- IR 不依赖 SciPy；
- constraint ID 可追踪到 diagnostics；
- disabled constraint 不进入 IR；
- enabled constraint 不可能被静默丢弃。

### Phase 4：迁移 QP/LP backend

任务：

- [ ] 将现有 QP 数学核心迁移为 `ScipySLSQPBackend`；
- [ ] 将现有 BoundSolver 迁移为 `HighsLPBackend`；
- [ ] 实现 backend registry；
- [ ] 实现 capability check；
- [ ] 修复 infeasible/unbounded/numerical status；
- [ ] 实现 point estimate；
- [ ] 实现 feasible bounds；
- [ ] 禁止 fallback uniform 或 `[0,1]` 冒充成功结果。

验收：

- 可行问题成功；
- 不可行问题明确失败；
- 欠定问题返回宽 feasible bounds；
- two-percent 和自定义 linear constraint 确实改变结果；
- backend 不支持的 IR 在调用前失败。

### Phase 5：唯一 solve API 和 CLI

任务：

- [ ] 实现 `nusol.solve(yaml_path)`；
- [ ] 实现 `nusol inspect`；
- [ ] 实现 `nusol solve`；
- [ ] 实现 dry-run：只编译不求解；
- [ ] 输出 resolved YAML 和 JSON result；
- [ ] 生成运行 manifest；
- [ ] CLI 使用非零 exit code 表示 validate/compile/solve failure。

验收：

```bash
uv run nusol validate examples/basic.yaml
uv run nusol solve examples/basic.yaml
```

能够从干净 checkout 完成，不需要额外 Python glue code。

### Phase 6：自定义插件约束

任务：

- [ ] 定义 plugin manifest；
- [ ] 实现 entry-point discovery；
- [ ] 实现名称和版本匹配；
- [ ] 实现参数 schema 校验；
- [ ] 实现 capability 声明；
- [ ] 输出记录插件 package/version；
- [ ] 编写 example plugin；
- [ ] 禁止 YAML 动态导入任意路径。

验收：

- 未安装插件给出明确错误；
- 版本不匹配失败；
- 参数错误在求解前失败；
- plugin constraint 出现在 compiled IR 和 diagnostics；
- manifest 能复现实验使用的插件版本。

### Phase 7：迁移现有数据适配器

任务：

- [ ] FNDDS adapter 输出 IngredientProblem builder input；
- [ ] 使用稳定 ingredient ID；
- [ ] 区分 missing 和 zero；
- [ ] 修正 canonical nutrient IDs；
- [ ] Branded basis/unit 保真；
- [ ] 不做隐式 mL→g；
- [ ] adapter 选择和数据版本全部由 YAML 声明。

验收：

- adapter 不再返回供 solver 直接读取的松散 context；
- 所有数据变换进入 provenance；
- 相同数据 checksum 和 YAML 产生相同 IngredientProblem。

### Phase 8：修复 metrics 与实验复现

任务：

- [ ] MAE 使用 ingredient ID 并集；
- [ ] 增加 mapping coverage；
- [ ] feasible-bound coverage 单独命名；
- [ ] 移除伪 80/95 coverage；
- [ ] 修复 zero-slack 指标；
- [ ] 建立实验 manifest；
- [ ] 重跑 synthetic benchmark；
- [ ] 科学模型完善前，FNDDS benchmark 标记 internal closed-loop。

验收：

- 每个 aggregate metric 可追溯到 per-item 结果；
- failure/skip 不会被当成功样本；
- benchmark 可从 YAML 一条命令重跑。

### Phase 9：食品科学扩展接口

基础框架稳定后再增加：

- [ ] ProcessModel protocol；
- [ ] moisture/yield model；
- [ ] nutrient retention model；
- [ ] fortification additions；
- [ ] compound ingredient hierarchy；
- [ ] alternative ingredient groups；
- [ ] observation model plugin；
- [ ] calibrated priors。

每个扩展必须：

- 由 YAML 声明；
- 声明变量、单位和 basis；
- 编译为明确 IR；
- 声明 backend capability；
- 有独立科学验证数据；
- 不改变未启用该扩展的基础模型行为。

## 11. 兼容迁移策略

### 11.1 Legacy adapter

短期提供内部适配：

```python
LegacyContextAdapter.to_problem(context: dict) -> IngredientProblem
```

限制：

- 只用于旧测试迁移；
- 不作为公开 API；
- 遇到无法推断的 basis/missingness 必须报错；
- Phase 8 后删除。

### 11.2 文件迁移原则

- 先新增目标模块，不立即移动旧文件；
- 新 backend 通过 parity tests 后再替换导出；
- 每个阶段保持主分支测试可运行；
- 不在同一提交中同时改 schema、数学模型和 benchmark；
- 每次行为变化附带 changelog 和迁移说明。

## 12. 测试策略

### 12.1 Contract tests

- YAML schema valid/invalid fixtures；
- inheritance and override；
- canonical resolved YAML；
- plugin registration/version；
- backend capability errors。

### 12.2 Mathematical tests

- 单配料唯一解；
- 多配料可识别解；
- 欠定解；
- infeasible；
- active bound；
- hard vs soft constraint；
- two-percent；
- custom linear constraint。

### 12.3 Property tests

- 所有比例非负；
- 成功解满足所有 hard constraints；
- feasible lower ≤ point ≤ feasible upper；
- 增加 hard constraint 不会扩大 feasible region；
- ingredient ID 顺序变化不改变按 ID 对齐的结果。

### 12.4 End-to-end tests

- inline YAML → JSON result；
- CSV resource YAML → JSON result；
- extends YAML → resolved snapshot；
- plugin YAML → compiled and solved result；
- CLI failure exit codes。

## 13. 每阶段提交策略

建议提交序列：

```text
refactor: add strict solve document schema
refactor: add yaml resolver and canonical output
refactor: add ingredient problem domain model
refactor: add solver-neutral constraint ir
refactor: compile built-in constraints to ir
refactor: migrate slsqp point backend
refactor: migrate highs feasible-bound backend
feat: expose yaml-only solve api and cli
feat: add registered custom constraint plugins
refactor: migrate fndds adapter to problem builder
fix: correct validation metrics semantics
docs: publish yaml 1.0 specification and migration guide
```

每个提交要求：

- 单一职责；
- 新增或更新测试；
- 不提交生成数据和大型数据库；
- 不混入无关格式化；
- 行为变化写入 commit message。

## 14. 风险和控制

| 风险 | 控制措施 |
|---|---|
| YAML schema 过早复杂化 | 1.0 只支持线性基础模型和六类约束 |
| 插件破坏可复现性 | 记录 package/version，禁止动态路径导入 |
| 旧测试绑死 context | legacy adapter 逐步迁移，不扩大公开面 |
| QP/LP 结果变化 | synthetic parity tests + hard-constraint checks |
| 配置继承难以理解 | resolved YAML 是唯一实际执行配置 |
| solver 静默忽略能力 | compile-time capability error |
| missing 值再次变成零 | domain validator 禁止隐式填充 |
| 文档再次漂移 | YAML schema 和 registry 自动生成参考表 |

## 15. Definition of Done

重构第一阶段完成必须同时满足：

- [ ] 唯一公开求解入口只接受 YAML；
- [ ] YAML schema versioned 且严格禁止未知字段；
- [ ] resolved YAML 包含全部默认值；
- [ ] inline 和外部 composition resource 均可用；
- [ ] 六类内置约束可从 YAML 编译；
- [ ] 自定义注册插件约束可从 YAML 引用；
- [ ] QP point estimate 和 LP feasible bounds 使用统一 IR；
- [ ] 不支持约束不能被静默忽略；
- [ ] infeasible 问题不能返回成功；
- [ ] missing nutrient 不能隐式变成零；
- [ ] 结果严格区分 point estimate 和 feasible bounds；
- [ ] CLI 可以从干净 checkout 运行最小示例；
- [ ] 每次运行输出 resolved YAML、checksums 和 manifest；
- [ ] 文档示例由端到端测试覆盖；
- [ ] 旧 `context dict` 不再出现在公开 API。

## 16. 重构完成后的能力边界

框架能够可靠声明：

> 在 YAML 明确指定的原料、composition、观测、模型、约束和先验条件下，计算原料投料比例的点估计与数学可行边界，并完整报告所有求解条件和诊断。

框架暂不声明：

- 结果是真实商业配方；
- feasible bounds 是概率可信区间；
- 未校准食品科学先验具有普遍有效性；
- 基础 linear mixing model 已覆盖全部加工效应。

后续高级模块必须在不破坏 YAML 1.0 基础契约的前提下扩展。
