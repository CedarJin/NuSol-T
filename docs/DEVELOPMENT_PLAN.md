# NuSol-T 完整开发计划

> 日期：2026-07-05  
> 分支：`refactor/yaml-solver-framework`  
> 基于：`REVIEW.md` / `SCIENCE_REVIEW.md` / `DESIGN_IMPLEMENTATION_REVIEW.md` 代码核实结果  
> 配套文档：`docs/REFACTOR_PLAN.md`（架构设计，本计划的上游参考）、`docs/FIX_PLAN.md`（现有代码 bug 修复清单）

---

## 文档关系

```
REFACTOR_PLAN.md       ← 架构设计（YAML 契约、IR 类型、约束注册表、目标目录结构）
    ↑
DEVELOPMENT_PLAN.md    ← 本文件：执行计划 + 实现细节补充 + Phase 排期
    ↑
FIX_PLAN.md            ← 问题索引；其中需要保留的修复只通过新架构落地
```

本文件不重复 REFACTOR_PLAN.md 已有的 YAML 示例、IR 类型定义和目录结构。本文件补充：

1. **具体实现细节**（Pydantic schema 结构、错误分类体系、营养名称标准化、CSV 格式规范）
2. **Phase 排期和执行顺序**（含依赖关系、里程碑、风险）
3. **迁移路线**（现有测试的处理策略、legacy 代码处置）
4. **工程规范**（提交策略、CI 门禁、测试要求）

本计划不在 `main` 上维护一套独立 bug-fix 实现。旧系统问题只作为重构验收用例，所有代码修改均在 `refactor/yaml-solver-framework` 分支通过新领域模型、编译器和 backend 解决。确需回补 `main` 的紧急修复必须单独评估，不属于本计划范围。

---

## 1. 补充实现细节

### 1.1 错误分类体系

新系统需要三层错误，每层在明确的阶段抛出：

```python
# ── config/errors.py ──

class NuSolError(Exception):
    """Base error for all NuSol-T failures."""

# Layer 1: 配置阶段 (YAML parse / schema / extends / resources)
class ConfigError(NuSolError):
    """YAML schema violation, unknown field, duplicate ID, cycle in extends, etc."""
    exit_code: int = 1

class SchemaValidationError(ConfigError):
    """Pydantic validation failure with field paths."""

class InheritanceError(ConfigError):
    """Cycle detected, parent not found, merge conflict."""

class ResourceError(ConfigError):
    """File not found, checksum mismatch, unsupported format."""

# Layer 2: 编译阶段 (domain validation / constraint → IR)
class CompileError(NuSolError):
    """Missing nutrient in observation, shape mismatch, NaN in matrix,
    enabled constraint not supported by any available backend, etc."""
    exit_code: int = 2

class MissingNutrientError(CompileError):
    """Observation references a nutrient not in composition matrix."""

class UnsupportedConstraintError(CompileError):
    """Enabled constraint type has no backend that supports it."""

# Layer 3: 求解阶段 (backend solve failure)
class SolveError(NuSolError):
    """Infeasible, unbounded, numerical failure, timeout."""
    exit_code: int = 3
```

**原则**：每一层只抛出该层定义的错误类型。不允许跨层抛异常（如 solve 阶段抛 ConfigError）。

### 1.2 Pydantic Schema 详细结构

#### SolveDocument（YAML 顶层）

```python
from pydantic import BaseModel, Field, model_validator
from typing import Annotated, Any, Literal, Optional
from enum import Enum

class SchemaVersion(str, Enum):
    V1_0_DRAFT = "1.0-draft"
    V1_0 = "1.0"

class MassBasis(str, Enum):
    INPUT_FRACTION = "input_fraction"

class NutrientBasis(str, Enum):
    PER_100G = "per_100g_finished_product"

class DeclarationGroup(str, Enum):
    MAIN = "main"
    TWO_PERCENT = "two_percent_or_less"

class ConstraintMode(str, Enum):
    HARD = "hard"
    SOFT = "soft"

class LossFunction(str, Enum):
    SQUARED_HINGE = "squared_hinge"  # max(0, violation)² — 仅惩罚超出区间
    LEAST_SQUARES = "least_squares"  # (pred - target)² — 向目标值靠拢

class BackendName(str, Enum):
    SCIPY_SLSQP = "scipy_slsqp"
    HIGHS_LP = "highs_lp"

class MissingValuePolicy(str, Enum):
    ERROR = "error"
    DROP_NUTRIENT = "drop_nutrient"
    DROP_INGREDIENT = "drop_ingredient"

class ModelType(str, Enum):
    LINEAR_MIXING = "linear_mixing"

class BasisSpec(BaseModel, extra="forbid"):
    ingredient_mass: MassBasis = MassBasis.INPUT_FRACTION
    nutrient_amount: NutrientBasis = NutrientBasis.PER_100G

class EvidenceSpec(BaseModel, extra="forbid"):
    status: Literal["validated", "experimental"]
    source: str
    version: Optional[str] = None

# ── Ingredient ──
class IngredientSpec(BaseModel, extra="forbid"):
    id: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(..., min_length=1)
    declaration_position: int = Field(..., ge=0)
    declaration_group: DeclarationGroup = DeclarationGroup.MAIN

class NutrientColumnSpec(BaseModel, extra="forbid"):
    id: str
    unit: str
    # 可选：如何从 USDA 数据找到这个 nutrient
    usda_nutrient_ids: list[int] = Field(default_factory=list)  # adapter lookup
    usda_nutrient_names: list[str] = Field(default_factory=list)  # controlled aliases only

class InlineCompositionSpec(BaseModel, extra="forbid"):
    source: Literal["inline"]
    nutrients: list[NutrientColumnSpec]
    values: dict[str, list[float | None]]

class CsvCompositionSpec(BaseModel, extra="forbid"):
    source: Literal["csv"]
    path: str
    sha256: str
    key_column: str = "ingredient_id"
    missing_value_policy: MissingValuePolicy = MissingValuePolicy.ERROR
    allow_extra_nutrients: bool = False
    nutrients: list[NutrientColumnSpec]

CompositionSpec = Annotated[
    InlineCompositionSpec | CsvCompositionSpec,
    Field(discriminator="source"),
]

# ── Observation ──
class NutrientObservation(BaseModel, extra="forbid"):
    nutrient: str
    unit: str
    basis: NutrientBasis = NutrientBasis.PER_100G
    # 互斥：三选一
    interval: Optional[tuple[float, float]] = None   # [lo, hi]
    exact: Optional[float] = None                     # == value
    less_than: Optional[float] = None                 # < threshold

    @model_validator(mode="after")
    def exactly_one_mode(self):
        modes = [self.interval, self.exact, self.less_than]
        if sum(1 for m in modes if m is not None) != 1:
            raise ValueError("Exactly one of interval/exact/less_than required")
        return self

# ── Constraints ──
class ConstraintSpec(BaseModel, extra="forbid"):
    id: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    type: str  # 由 constraint_registry 校验
    mode: ConstraintMode = ConstraintMode.HARD
    enabled: bool = True
    weight: float = Field(1.0, gt=0)
    config: dict[str, Any] = Field(default_factory=dict)
    evidence: Optional[EvidenceSpec] = None

class ModelSpec(BaseModel, extra="forbid"):
    type: Literal["linear_mixing"]
    config: dict[str, Any] = Field(default_factory=dict)

class IngredientFractionVariableSpec(BaseModel, extra="forbid"):
    lower: float = Field(0.0, ge=0.0, le=1.0)
    upper: float = Field(1.0, ge=0.0, le=1.0)

class VariableSpec(BaseModel, extra="forbid"):
    ingredient_fractions: IngredientFractionVariableSpec

class PriorSpec(BaseModel, extra="forbid"):
    id: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    type: str
    enabled: bool = True
    weight: float = Field(..., gt=0)
    config: dict[str, Any] = Field(default_factory=dict)
    evidence: EvidenceSpec

# ── Solver ──
class PointSolverSpec(BaseModel, extra="forbid"):
    backend: BackendName = BackendName.SCIPY_SLSQP
    options: dict = Field(default_factory=lambda: {
        "max_iterations": 500,
        "tolerance": 1e-8,
    })

class BoundsSolverSpec(BaseModel, extra="forbid"):
    backend: BackendName = BackendName.HIGHS_LP
    feasible_region: Literal["hard_constraints_only", "explicit_slack_budget"] = \
        "hard_constraints_only"
    slack_budgets: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_slack_budget(self):
        if self.feasible_region == "explicit_slack_budget" and not self.slack_budgets:
            raise ValueError("explicit_slack_budget requires slack_budgets")
        if self.feasible_region == "hard_constraints_only" and self.slack_budgets:
            raise ValueError("slack_budgets require explicit_slack_budget mode")
        return self

class SolverSpec(BaseModel, extra="forbid"):
    point: Optional[PointSolverSpec] = None
    bounds: Optional[BoundsSolverSpec] = None
    # 至少一个
    @model_validator(mode="after")
    def at_least_one_solver(self):
        if self.point is None and self.bounds is None:
            raise ValueError("At least one of point/bounds solver required")
        return self

# ── Output ──
class OutputSpec(BaseModel, extra="forbid"):
    path: str
    include: list[Literal[
        "point_estimate",
        "feasible_bounds",
        "constraint_diagnostics",
        "nutrient_predicted",
        "nutrient_residuals",
    ]] = Field(default_factory=lambda: [
        "point_estimate", "feasible_bounds", "constraint_diagnostics"
    ])

# ── Top-level ──
class SolveDocument(BaseModel, extra="forbid"):
    schema_version: Literal["1.0-draft", "1.0"]
    problem_id: str
    extends: list[str] = Field(default_factory=list)
    basis: BasisSpec
    ingredients: list[IngredientSpec]
    composition: CompositionSpec
    observations: list[NutrientObservation]
    model: ModelSpec
    variables: VariableSpec
    constraints: list[ConstraintSpec] = Field(default_factory=list)
    priors: list[PriorSpec] = Field(default_factory=list)
    solver: SolverSpec
    output: OutputSpec

    @model_validator(mode="after")
    def unique_ids(self):
        ing_ids = [i.id for i in self.ingredients]
        if len(ing_ids) != len(set(ing_ids)):
            raise ValueError("Duplicate ingredient id")
        c_ids = [c.id for c in self.constraints]
        if len(c_ids) != len(set(c_ids)):
            raise ValueError("Duplicate constraint id")
        p_ids = [p.id for p in self.priors]
        if len(p_ids) != len(set(p_ids)):
            raise ValueError("Duplicate prior id")
        if set(c_ids) & set(p_ids):
            raise ValueError("Constraint and prior ids must be globally unique")
        return self
```

#### 关键设计决策

1. **constraint 的 `type` 不是 Literal 枚举**，而是由 `constraint_registry` 运行时校验。这允许后续插件注册新类型而无需修改 schema。但 schema 在 load 阶段就调用 registry 做校验（在 Pydantic `@model_validator` 或独立 validation pass 中）。

2. **Composition 使用 discriminated union**：inline values 与 source 位于同一对象中；CSV 模式只允许 path/checksum 等外部资源字段，避免跨字段状态组合。

3. **`NutrientObservation` 三选一互斥**：interval / exact / less_than 确保每次观测的类型明确。

4. **constraint/prior 参数执行二次严格校验**：顶层 schema 允许插件扩展类型，但 resolver 完成后必须由 registry 中对应的 Pydantic parameter model 校验。错误路径必须定位到具体 `constraints[i].config.<field>`。

5. **首版只支持 input fractions 和 per-100g finished-product nutrients**：`finished_fraction` 与 `per_serving` 需要额外的加工/serving 语义，不进入 YAML 1.0。后续通过 versioned observation/process extension 增加，不能在缺少必要字段时提前暴露枚举值。

### 1.3 营养名称标准化策略

当前系统在不同数据库中查找 nutrient 时依赖字符串精确匹配。新系统需要标准化层：

```python
# domain/nutrient.py

# Canonical nutrient ID — 唯一的内部标识
# 不依赖 USDA nutrient ID（因为 FNDDS/SR Legacy/Foundation 之间可能不一致）
CANONICAL_NUTRIENTS = {
    # canonical_id: (preferred_name, unit, [usda_ids], [alt_names])
    "energy_kcal": (
        "Energy", "kcal",
        [1008],  # USDA nutrient IDs
        ["Energy (kcal)", "Energy (kilocalories)", "Energy (Kcal)"],
    ),
    "protein_g": (
        "Protein", "g",
        [1003],
        ["Protein, total", "Total protein"],
    ),
    "fat_g": (
        "Total lipid (fat)", "g",
        [1004],
        ["Fat", "Total Fat", "Total lipid"],
    ),
    "saturated_fat_g": (
        "Fatty acids, total saturated", "g",
        [1258],  # ← 修正后 (曾错误为 1292)
        ["Saturated Fat", "Saturated fatty acids", "Saturates"],
    ),
    "monounsaturated_fat_g": (
        "Fatty acids, total monounsaturated", "g",
        [1292],  # ← 修正后 (曾错误为 1293)
        ["Monounsaturated Fat", "Monounsaturates"],
    ),
    "polyunsaturated_fat_g": (
        "Fatty acids, total polyunsaturated", "g",
        [1293],  # ← 修正后 (曾错误为 1294)
        ["Polyunsaturated Fat", "Polyunsaturates"],
    ),
    "trans_fat_g": (
        "Fatty acids, total trans", "g",
        [1257],
        ["Trans Fat", "Trans fatty acids"],
    ),
    "carbohydrate_g": (
        "Carbohydrate, by difference", "g",
        [1005],
        ["Carbohydrate", "Total Carbohydrate", "Carbs"],
    ),
    "fiber_g": (
        "Fiber, total dietary", "g",
        [1079],
        ["Dietary Fiber", "Fiber", "Total fiber"],
    ),
    "sugars_g": (
        "Total Sugars", "g",
        [2000],
        ["Sugars", "Sugar", "Total Sugars, Total"],
    ),
    "added_sugars_g": (
        "Sugars, added", "g",
        [1063],
        ["Added Sugars", "Added Sugar"],
    ),
    "cholesterol_mg": (
        "Cholesterol", "mg",
        [1253],
        ["Total Cholesterol"],
    ),
    "sodium_mg": (
        "Sodium, Na", "mg",
        [1093],
        ["Sodium"],  # salt equivalent is not an alias; it requires an explicit conversion
    ),
    "calcium_mg": (
        "Calcium, Ca", "mg",
        [1087],
        ["Calcium"],
    ),
    "iron_mg": (
        "Iron, Fe", "mg",
        [1089],
        ["Iron"],
    ),
    "potassium_mg": (
        "Potassium, K", "mg",
        [1092],
        ["Potassium"],
    ),
    "vitamin_d_mcg": (
        "Vitamin D (D2 + D3)", "µg",
        [1112],  # µg form only; IU nutrient 1110 requires an explicit unit conversion
        ["Vitamin D", "Vit D"],
    ),
    # ... extend as needed
}
```

**标准化流程**：
1. 数据源加载时优先按受控 USDA nutrient ID 匹配；只有显式维护的 exact alias 可以按名称匹配，禁止自动 fuzzy nutrient matching
2. 匹配到 canonical_id 后，内部全部使用 canonical_id
3. 展示层映射回 `preferred_name`

**CSV/JSON composition source 中的 nutrient 列用 canonical_id**。

### 1.4 CSV Composition Source 格式规范

```csv
ingredient_id,energy_kcal,protein_g,fat_g,carbohydrate_g,fiber_g,sugars_g,...
flour,364.0,10.3,1.0,76.3,2.7,0.3,...
sugar,387.0,0.0,0.0,100.0,0.0,100.0,...
oil,884.0,0.0,100.0,0.0,0.0,0.0,...
```

规则：
- 第一列是 `key_column`（默认 `ingredient_id`），值必须匹配 YAML `ingredients[].id`
- 后续每列是 canonical nutrient ID
- 空单元格 / `NA` / `NaN` → missing（根据 `missing_value_policy` 处理）
- 数值必须是 float 或空白
- 列顺序 = YAML `composition.nutrients` 的声明顺序（schema 加载时校验）
- 额外的列（不在 YAML 声明的 nutrients 中）默认报错；只有 `allow_extra_nutrients: true` 时才允许忽略，并在 manifest 记录被忽略列

### 1.5 Manifest JSON Schema

每次 `nusol solve` 输出 manifest.json：

```json
{
  "schema_version": "1.0",
  "problem_id": "bread_minimal",
  "run_id": "20260705T143022-a1b2c3",
  "timestamps": {
    "started": "2026-07-05T14:30:22Z",
    "finished": "2026-07-05T14:30:23Z",
    "duration_seconds": 0.847
  },
  "software": {
    "nusol_version": "0.2.0",
    "python_version": "3.12.4",
    "platform": "macOS-14.5-arm64"
  },
  "git": {
    "commit": "abc123def456",
    "branch": "refactor/yaml-solver-framework",
    "dirty": false
  },
  "resolved_config": {
    "path": "output/bread_minimal_resolved.yaml",
    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  },
  "resources": {
    "composition_csv": {
      "path": "data/composition.csv",
      "sha256": "a7ffc6f8bf1ed76651c14756a061d662f580ff4de43b49fa82d80a4b80f8434a"
    }
  },
  "solver": {
    "point": {
      "backend": "scipy_slsqp",
      "success": true,
      "status": "optimal",
      "objective_value": 0.0,
      "iterations": 12,
      "solve_time_seconds": 0.023
    },
    "bounds": {
      "backend": "highs_lp",
      "success": true,
      "status": "optimal",
      "solve_time_seconds": 0.008,
      "n_lps_solved": 6,
      "n_feasible": 6
    }
  },
  "constraints": {
    "total": 3,
    "hard": 2,
    "soft": 1,
    "violated": [],
    "diagnostics": [
      {
        "constraint_id": "total_mass",
        "satisfied": true,
        "value": 1.0,
        "target": 1.0,
        "slack": 0.0
      },
      {
        "constraint_id": "decl_order",
        "satisfied": true,
        "violations": 0
      },
      {
        "constraint_id": "label_fit",
        "satisfied": true,
        "objective_contribution": 0.0
      }
    ]
  }
}
```

### 1.6 `declared_percentage` 与 `mass_balance` 的交互

声明百分比不是 ingredient 的隐含属性，而是 YAML 中显式定义的约束。框架不得自行加入默认容差：

```yaml
constraints:
  - id: declared_chicken
    type: declared_percentage
    mode: hard
    config:
      ingredient: chicken
      exact: 0.70
```

如果来源只支持范围，必须由用户明确给出：

```yaml
      interval: [0.665, 0.735]
```

`exact` 和 `interval` 互斥。`Σx_i = 1` 仍然成立。如果多个声明百分比造成冲突，问题应返回 `infeasible`，框架不能自动放宽。

在 IR 编译时，exact constraint 转化为：
```python
LinearConstraintIR(
    id="declared_chicken",
    coefficients=one_hot(i, n_vars),
    lower=0.70,
    upper=0.70,
)
```

interval constraint 则直接使用 YAML 提供的 lower/upper。

### 1.7 `linear_expression` 的 coefficient 校验

```yaml
- id: oil_not_above_meat
  type: linear
  coefficients:
    oil: 1.0
    beef: -1.0
  upper: 0.0
```

编译时校验：
1. `coefficients` 的 key 必须是 `ingredients[].id` 或 `__constant__`
2. 不能所有 coefficient 都为 0
3. `__constant__` 表示常数项（例如 `upper: -0.1` 表示 `c·x ≤ -0.1`，但一般不需要）
4. 如果 YAML 引用了不存在的 ingredient id → `ConfigError`

### 1.8 Soft constraints 与 feasible bounds

点估计可以通过 soft constraints 的 penalty 在多个候选解中选择最优点，但 soft constraint 本身不定义唯一可行域。Bounds solver 必须显式选择以下一种语义：

1. `hard_constraints_only`：只使用 hard constraints 计算数学可行边界；soft constraints 完全不进入 bounds。
2. `explicit_slack_budget`：除 hard constraints 外，将 YAML 明确给出的各 soft constraint 最大 slack/penalty budget 编译为额外硬边界。

默认使用：

```yaml
solver:
  bounds:
    backend: highs_lp
    feasible_region: hard_constraints_only
```

如果需要限定标签拟合误差：

```yaml
    feasible_region: explicit_slack_budget
    slack_budgets:
      label_fit: 0.01
```

规则：

- 不允许把 soft constraint 自动硬化；
- 不允许使用点估计的 objective value 作为未声明的隐式 budget；
- LP backend 只能接受可线性表示的 budget；
- 不可线性化的 budget 与 `highs_lp` 组合必须在编译阶段失败；
- result 和 manifest 必须记录使用的 feasible-region 定义。

### 1.9 FDA Rounding / Label Observation 模型

首版 `NutrientObservation` 支持三种模式：

```yaml
# Mode 1: interval（最常见 — 标签反演或实验室分析）
observations:
  - nutrient: energy_kcal
    interval: [410, 430]  # 真实值在 410-430 kcal/100g 之间
    unit: kcal

# Mode 2: exact（已知精确值 — FNDDS forward validation）
  - nutrient: protein_g
    exact: 5.7
    unit: g

# Mode 3: less_than（标签声明 "< 1g", "not a significant source"）
  - nutrient: trans_fat_g
    less_than: 0.5
    unit: g
```

**后续 Phase 扩展**：`observation/fda.py` 实现 `label_value → interval` 的 FDA 合规反演，但首版不要求——用户直接在 YAML 中写 interval。

### 1.10 性能目标

| 指标 | 当前 legacy | 新系统目标 |
|------|-----------|----------|
| 单 recipe point estimate | ~30ms | ≤ 50ms |
| 单 recipe feasible bounds | ~60ms (n×1ms LP) | ≤ 100ms |
| 200 recipe benchmark | ~18s | ≤ 30s |
| YAML load + resolve + compile | — | ≤ 100ms |
| CLI cold start | ~200ms | ≤ 500ms |

新系统做了更多校验（schema validation, capability check, manifest write），允许适度慢于 legacy，但不应超过 2x。

---

## 2. Phase 排期和依赖关系

### 2.1 依赖图

```text
Phase 0 (legacy 基线)
    │
Phase 1 (draft YAML schema)
    │
Phase 2 (领域模型)
    │
Phase 3 (Registry + IR)
    │
Phase 3.5 (FNDDS spike + schema review)
    │
    ├── 锁定 YAML 1.0
    │
Phase 4 (backend)
    │
Phase 5 (API + CLI)
    │
Phase 6 (custom constraint plugins)
    │
Phase 7 (adapters)
    │
Phase 8 (metrics + benchmark)
    │
Phase 9 (docs + legacy cleanup)
```

Phase 1–3 按顺序执行。YAML schema 在 FNDDS spike 之前保持 `1.0-draft`，避免领域模型和 IR 尚未验证时过早冻结公开契约。

### 2.2 时间估算

| Phase | 内容 | 预计天数 | 关键产出 |
|-------|------|---------|---------|
| **0** | 冻结 legacy 基线 | 0.5 | synthetic fixtures, 快照 |
| **1** | Draft YAML Schema + Resolver + validate CLI | 4 | SolveDocument draft, extends merge, canonical resolved YAML |
| **2** | 领域模型 + Linear Mixing | 4 | IngredientProblem, NutrientValue 四态, CompositionMatrix |
| **3** | Constraint Registry + IR Compiler | 5 | 6 类基础约束, CompiledProblem, capability model |
| **3.5** | FNDDS Spike | 2 | IR 在真实数据上的验证报告 |
| **4** | Backend 迁移 | 4 | ScipySLSQPBackend, HighsLPBackend, infeasible handling |
| **5** | Solve API + CLI | 3 | `nusol solve/validate/resolve/inspect`, manifest |
| **6** | 自定义约束插件 | 3 | plugin discovery/version/schema/capability/manifest |
| **7** | 数据适配器迁移 | 4 | FNDDS/SR/Foundation/Branded → problem builders |
| **8** | Metrics 修正 + Benchmark | 3 | MAE union, feasible-bound coverage, reproducible benchmark |
| **9** | 文档对齐 + Legacy 清理 | 3 | CURRENT_STATUS, README, DEVELOPMENT 标记 |
| | **总计** | **35.5 天 (~7–8 周)** | |

### 2.3 里程碑

| 里程碑 | 在哪个 Phase 之后 | 含义 |
|--------|------------------|------|
| M1: Draft Schema | Phase 1 | YAML draft 可 validate/resolve，允许受控修改 |
| M2: Domain Complete | Phase 2 | IngredientProblem 替代 context dict |
| M3: Schema 1.0 Stable | Phase 3.5 | Domain/IR 经 FNDDS spike 验证后锁定 YAML 1.0 |
| M4: Backend Working | Phase 4 | Legacy QP/LP 能力已在新架构中复现 |
| M5: End-to-End | Phase 5 | `nusol solve` 从干净 checkout 可运行 |
| M6: Plugin Ready | Phase 6 | 自定义约束可安全注册、校验、编译和追踪版本 |
| M7: USDA Data | Phase 7 | 4 个适配器全部升级到新接口 |
| M8: Benchmark Ready | Phase 8 | 可复现 benchmark，修正后的 metrics |
| M9: Docs Aligned | Phase 9 | 文档与代码一致，legacy 公开入口删除 |

### 2.4 Phase 6 自定义约束插件任务

Phase 6 是 YAML-only 工程要求的一部分，不是可选增强。必须完成：

- [ ] 定义 Python package entry-point group，例如 `nusol.constraints`；
- [ ] 定义 plugin manifest：name、version、parameter schema、IR types、capabilities；
- [ ] 只发现已安装且通过 entry point 注册的插件；
- [ ] 禁止 YAML 提供文件路径、module path、lambda 或 Python expression；
- [ ] 对 YAML `plugin` 和 `version` 做精确匹配；
- [ ] 用插件自带 Pydantic model 严格校验 `config`；
- [ ] 插件编译结果必须进入统一 IR，不能直接调用 backend；
- [ ] backend capability check 对插件约束同样生效；
- [ ] manifest 记录 distribution name、package version、constraint version；
- [ ] 提供一个独立 example plugin 和端到端测试；
- [ ] 未安装、版本不符、参数错误、能力不符分别返回可识别错误。

插件验收命令：

```bash
uv run nusol validate examples/plugin_constraint.yaml
uv run nusol inspect examples/plugin_constraint.yaml
uv run nusol solve examples/plugin_constraint.yaml
```

三条命令的 resolved YAML、compiled constraint ID 和 manifest plugin version 必须一致。

---

## 3. 测试迁移策略

### 3.1 现有测试分类

| 类别 | 文件 | 数量(约) | 策略 |
|------|------|---------|------|
| **A: 纯函数/无副作用** | test_numerics, test_units, test_nutrient_registry, test_schema, test_parser | ~80 | **保留** — 这些模块在新架构中几乎不变 |
| **B: 约束逻辑** | test_constraints | ~20 | **重写** — 约束改为 register → compile 链路 |
| **C: Solver 核心数学** | test_qp_solver, test_solver | ~40 | **重写为 parity tests** — 新 backend 在 synthetic fixtures 上结果与 legacy 一致 |
| **D: Adapter 集成** | test_fndds_adapter, test_foundation_adapter, test_sr_legacy_adapter | ~30 | **重写** — 新 adapter 接口变化 |
| **E: Metrics** | test_metrics | ~15 | **修正** — 修复 MAE/coverage/zero_slack 后更新期望值 |
| **F: CLI + E2E** | test_cli | ~5 | **新写** — 当前 CLI 基本无实质测试 |
| **G: 其他** | test_forward, test_labelize, test_trust, test_ablation | ~18 | **部分保留/重写** |

### 3.2 迁移时间线

```
Phase 0-2:   A 类测试在重构分支保留并逐步迁移
Phase 3-4:   B + C 类测试在 refactor 分支重写
Phase 5:     F 类新增
Phase 6:     新增插件 contract tests
Phase 7:     D 类重写
Phase 8:     E 类修正
Phase 9:     legacy 测试完成迁移或记录删除理由
```

### 3.3 Legacy 测试策略

在 Phase 9 之前，`tests/legacy/` 保存必要的原测试副本，标记为 `pytest.mark.legacy`。这些测试：
- 不要求在新代码上通过
- 作为重构前后的行为差异参考
- Phase 9 后，所有 legacy 测试要么迁移到新接口，要么显式删除（记录原因）

---

## 4. 分支和合并策略

```text
main
  │
  └── refactor/yaml-solver-framework (唯一实施分支)
        ├── Phase 0: legacy baseline
        ├── Phase 1: draft YAML schema
        ├── Phase 2: domain model
        ├── Phase 3/3.5: IR + spike + schema 1.0 freeze
        ├── Phase 4: backends
        ├── Phase 5: API + CLI
        ├── Phase 6: custom plugins
        ├── Phase 7: adapters
        ├── Phase 8: metrics + benchmark
        ├── Phase 9: docs + legacy cleanup
        │
        └── review 后合并到 main
```

不在 `main` 上并行实施 `FIX_PLAN`。其中仍适用的问题转化为新架构的测试和 DoD；会被新架构替代的旧代码不单独修补。若重构期间发现必须紧急回补生产主线的问题，应建立独立 hotfix，经明确批准后 cherry-pick，不形成长期双轨。

**不 squash merge**：保留每个 Phase 的独立 commit，方便回溯。

**合并前 checklist**：
- [ ] 全量测试通过（legacy + new）
- [ ] `nusol solve examples/bread_minimal.yaml` 从干净 checkout 可运行
- [ ] Ruff + mypy 零新增问题
- [ ] 文档状态与代码一致

---

## 5. 风险登记表

| # | 风险 | P | I | 缓解 | 触发条件 | 应急预案 |
|---|------|---|---|------|----------|----------|
| R1 | IR 设计在真实数据上不够用 | M | H | Phase 3.5 spike 提前验证 | Spike 发现 IR 无法表示某个约束 | 扩展 IR 类型，Phase 4 顺延 |
| R2 | 新 backend 结果与 legacy 不一致 | M | M | Parity tests + property tests | Parity test 失败 | 逐 case 分析差异原因；如果是 legacy bug，记录并更新快照 |
| R3 | 数据适配器迁移遗漏隐含逻辑 | M | M | 逐行对比旧代码 + contract tests | Adapter 输出的 IngredientProblem 无法正确求解 | 写对比脚本，old vs new 对同 recipe 的 matrix 逐元素 diff |
| R4 | 重构范围膨胀 | H | M | 严格按 Phase 边界执行，每个 Phase 有 DoD | 某 Phase 超过预计时间 50% | 缩减该 Phase 范围，推迟非核心功能到 Phase 9 |
| R5 | 旧测试大面积无法迁移 | L | L | Legacy adapter 桥接 | 旧测试在 legacy adapter 下也失败 | 逐 test 决定：修/跳/删 |
| R6 | YAML schema 过早稳定，后续频繁变更 | M | M | Phase 3.5 前保持 draft，完成真实数据 spike 后再锁定 1.0 | spike 发现 schema 无法表达真实问题 | 在 1.0 发布前集中修订 draft，不产生兼容承诺 |
| R7 | 科学错误在新代码中复现 | M | H | Phase 2 显式修正所有已知常量 + cross-ref FIX_PLAN | Code review 发现已知错误仍存在 | 建立 canonical constants 文件，单一来源 |

P=概率, I=影响, H/M/L=高/中/低

---

## 6. CI 质量门禁

```yaml
# .github/workflows/ci.yml (或等效)
jobs:
  quality:
    steps:
      - pytest tests/ -v                    # 全部测试
      - ruff check src/ tests/              # 零容忍
      - ruff format --check src/ tests/     # 格式一致
      - mypy src/                           # 类型检查
      - uv build                            # 包可构建
      - uv run nusol validate examples/bread_minimal.yaml  # CLI smoke
      - uv run nusol solve examples/bread_minimal.yaml --dry-run
```

---

## 7. 各 Phase 的 DoD（Definition of Done）

除 REFACTOR_PLAN.md 已有的验收标准外，每个 Phase 还需满足：

| Phase | 额外 DoD |
|-------|---------|
| 0 | 3 个 synthetic fixtures 可在 CI 运行（无需 USDA 数据） |
| 1 | draft `bread_minimal.yaml` 可被 validate 和 resolve；拼错字段报错；重复 ID 报错 |
| 2 | `NutrientValue(status="missing")` 不得在 matrix 中当 0；IU 转换修正 |
| 3 | 6 种基础约束每种有独立 YAML→IR 测试；disabled 不进 IR；enabled 100% 进 IR |
| 3.5 | FNDDS spike 完成；YAML/Domain/IR 联合 review 通过；正式锁定 schema 1.0 |
| 4 | infeasible → `success=False`；feasible bounds 正确；parity tests 通过 |
| 5 | CLI 四个命令全部可运行；exit code 正确；manifest 包含必要字段 |
| 6 | 插件发现、版本、参数 schema、capability 和 manifest 测试全部通过；YAML 不可动态导入任意路径 |
| 7 | FNDDS adapter 输出可构建有效 IngredientProblem；重复 description 不覆盖 |
| 8 | MAE 用并集；coverage 不混淆语义；任意 YAML 消融配置可执行且实际 enabled constraint 可审计 |
| 9 | CURRENT_STATUS 可被仓库验证；README 含最小示例；旧公开 `context dict` 路径删除 |

---

## 8. 附录

### A. 与 FIX_PLAN.md 的对应关系

`FIX_PLAN.md` 仅作为已知问题索引，不再代表一条独立实施轨道。下列问题只在重构分支的新模块中解决；旧模块不会为了保持双轨而单独修补。

| FIX_PLAN | 本计划 Phase | 说明 |
|----------|-------------|------|
| F0.1-F0.5 (阻塞性) | Phase 4, 8 | 求解器失败语义在 Phase 4 修复，指标在 Phase 8 修复 |
| F1.1-F1.6 (科学基础) | Phase 2, 3 | 常量和公式修正在领域模型和约束实现中落地 |
| F2.1-F2.5 (约束连通) | Phase 1, 3 | 架构级别解决：schema 强制 + registry + capability check |
| F3.1-F3.4 (端到端) | Phase 5, 7, 8 | CLI + adapter + benchmark |
| F4.1-F4.4 (数据质量) | Phase 7 | Adapter 重构 |
| F5.1-F5.4 (Trust) | Phase 8 + Deferred | feasible bounds 语义修正；Trust Grade 首版不做 |
| F6.1-F6.5 (文档) | Phase 9 | 文档对齐 |

### B. 原始 REFACTOR_PLAN.md 与本文件的分工

- **REFACTOR_PLAN.md**：为什么要重构、YAML 契约长什么样、目标目录结构、IR 类型定义。给新人看的"愿景文档"。
- **DEVELOPMENT_PLAN.md（本文件）**：怎么执行、每个 Phase 做什么、多少天、依赖什么、有什么风险。给开发者看的"执行手册"。
