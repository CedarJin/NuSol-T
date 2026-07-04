# NuSol-T 开发文档

> 面向食物营养成分分析的可扩展统一计算框架

---

## 1. 技术栈

| 层级 | 选型 | 说明 |
|------|------|------|
| 语言 | Python 3.12+ | 科学计算生态成熟 |
| 数据处理 | Pandas, NumPy | 表格数据和矩阵运算 |
| 优化求解 | SciPy.optimize | `trust-constr`, `SLSQP`, `linprog` |
| 符号计算 | SymPy | YAML constraint 解析为符号表达式 |
| 配置管理 | PyYAML / OmegaConf | YAML 驱动配置 |
| CLI | Typer (基于 click) | 现代化 CLI，type-hint 驱动 |
| 数据结构 | Pydantic v2 | Schema 定义、数据校验、序列化 |
| 报告输出 | Jinja2, Plotly | HTML 报告、图表 |
| 测试 | pytest, pytest-cov | 单元测试、覆盖率 |
| 代码质量 | ruff, mypy, pre-commit | Lint、类型检查 |
| 依赖管理 | uv (astral-sh) | 快速、可复现的 Python 包管理 |

---

## 2. 项目目录结构

```
NuSol-T/
├── pyproject.toml                 # 项目元信息、依赖、配置
├── README.md                      # 项目说明
├── LICENSE                        # 开源协议
│
├── docs/                          # 文档
│   ├── NuSol-T.md                 # 总体规划书
│   ├── DEVELOPMENT.md             # 开发文档（本文件）
│   ├── API.md                     # API 文档
│   └── DATA.md                    # 数据字典
│
├── config/                        # YAML 配置文件
│   ├── fndds_forward.yaml         # FNDDS forward calculation 配置
│   ├── fndds_inverse.yaml         # FNDDS inverse reconstruction 配置
│   ├── fndds_labelized.yaml       # FNDDS labelized simulation 配置
│   ├── branded_inverse.yaml       # Branded Food 应用配置
│   └── ablation/                  # Ablation study 配置
│       ├── g0_mass_balance.yaml
│       ├── g1_plus_order.yaml
│       └── ...
│
├── nusol/                         # 核心 Python 包
│   ├── __init__.py
│   │
│   ├── core/                      # 核心 schema 和基类
│   │   ├── __init__.py
│   │   ├── schema.py              # 核心 Pydantic schemas
│   │   ├── nutrient_registry.py   # Canonical Nutrition Model
│   │   ├── units.py               # 单位系统
│   │   └── enums.py               # 枚举定义
│   │
│   ├── data/                      # Data Adapter Layer
│   │   ├── __init__.py
│   │   ├── base.py                # 基类 DataAdapter
│   │   ├── fndds.py               # FNDDS 数据适配器
│   │   ├── branded.py             # Branded Food 数据适配器
│   │   ├── sr_legacy.py           # SR Legacy 数据适配器
│   │   └── foundation.py          # Foundation Foods 数据适配器
│   │
│   ├── ingredient/                # Ingredient Parsing & Mapping
│   │   ├── __init__.py
│   │   ├── parser.py              # 配料表解析 → IngredientTree
│   │   ├── parser_utils.py        # 解析辅助函数
│   │   ├── mapper.py              # 配料 → 数据库映射
│   │   └── compound.py            # 复合配料处理
│   │
│   ├── nutrition/                 # Forward Nutrition Calculation
│   │   ├── __init__.py
│   │   ├── forward.py             # ForwardNutritionModel
│   │   ├── retention.py           # Retention factors
│   │   ├── moisture.py            # Moisture/yield adjustment
│   │   └── labelize.py            # 精确值 → 模拟标签值
│   │
│   ├── constraints/               # Constraint & Prior Layer
│   │   ├── __init__.py
│   │   ├── base.py                # Constraint 基类
│   │   ├── mass_balance.py        # P0: 质量守恒
│   │   ├── ingredient_order.py    # P1: 配料顺序
│   │   ├── two_percent.py         # P1: 2% rule
│   │   ├── label_interval.py      # P2: 标签区间拟合
│   │   ├── energy_closure.py      # P3: 能量闭合
│   │   ├── water_solid.py         # P3: 水-固平衡
│   │   ├── sodium_balance.py      # P3: 钠源平衡
│   │   ├── sugar_balance.py       # P3: 添加糖平衡
│   │   ├── fatty_acid.py          # P3: 脂肪酸闭合
│   │   └── category_prior.py      # P4: 类别先验
│   │
│   ├── solver/                    # Inverse Solver Layer
│   │   ├── __init__.py
│   │   ├── base.py                # Solver 基类
│   │   ├── point_solver.py        # PointSolver
│   │   ├── bound_solver.py        # BoundSolver
│   │   ├── ensemble_solver.py     # EnsembleSolver
│   │   ├── objective.py           # 目标函数构造
│   │   └── initializer.py         # 多初值策略
│   │
│   ├── validation/                # Validation Layer
│   │   ├── __init__.py
│   │   ├── metrics.py             # 评价指标计算
│   │   ├── compare.py             # 结果比较
│   │   └── ablation.py            # Ablation study 运行器
│   │
│   ├── report/                    # Trust & Reporting Layer
│   │   ├── __init__.py
│   │   ├── trust.py               # TrustReport 生成
│   │   ├── trust_grade.py         # 可信等级计算
│   │   ├── html_report.py         # HTML 报告模板
│   │   └── provenance.py          # 数据溯源追踪
│   │
│   ├── config/                    # 配置解析
│   │   ├── __init__.py
│   │   ├── loader.py              # YAML 配置加载
│   │   └── config_schema.py       # 配置 schema 校验
│   │
│   └── utils/                     # 通用工具
│       ├── __init__.py
│       ├── logging.py             # 日志
│       ├── numerics.py            # 数值工具（四舍五入、区间）
│       └── parallel.py            # 并行处理
│
├── scripts/                       # 执行脚本
│   ├── run_fndds_forward.py       # FNDDS forward 验证
│   ├── run_fndds_inverse.py       # FNDDS inverse 重构
│   ├── run_fndds_labelized.py     # FNDDS labelized simulation
│   ├── run_branded.py             # Branded Food 应用
│   └── run_ablation.py            # Ablation study
│
├── notebooks/                     # Jupyter notebooks (探索用)
│   ├── 01_data_exploration.ipynb
│   ├── 02_fndds_forward.ipynb
│   └── ...
│
├── tests/                         # 测试
│   ├── __init__.py
│   ├── conftest.py                # fixtures
│   ├── test_core/
│   ├── test_data/
│   ├── test_ingredient/
│   ├── test_nutrition/
│   ├── test_constraints/
│   ├── test_solver/
│   └── test_report/
│
├── output/                        # 运行输出 (gitignore)
│   ├── fndds_forward/
│   ├── fndds_inverse/
│   ├── fndds_labelized/
│   ├── branded/
│   └── ablation/
│
└── data/                          # 本地缓存/处理后数据 (gitignore, symlink to ../db)
```

---

## 3. 核心 Schema 设计

### 3.1 NutrientRecord

```python
from pydantic import BaseModel, Field
from typing import Optional

class NutrientRecord(BaseModel):
    """统一营养素记录"""
    nutrient_id: int           # USDA nutrient ID
    nutrient_number: str       # USDA nutrient number (e.g. "208")
    name: str                  # 标准名称 (e.g. "Energy")
    amount: float              # 数值
    unit: str                  # 单位 (e.g. "kcal", "g", "mg")
    rank: Optional[int] = None # USDA 排序号

class NutrientProfile(BaseModel):
    """食品/配料的营养素画像"""
    fdc_id: Optional[int] = None
    description: str
    nutrients: list[NutrientRecord]
    basis: str = "per_100g"    # 基准
```

### 3.2 IngredientTree

```python
class IngredientNode(BaseModel):
    """配料树节点"""
    name: str                           # 原始名称
    normalized_name: str                # 标准化名称
    position: int                       # 顺序（0-based）
    is_compound: bool = False           # 是否为复合配料
    is_sub_ingredient: bool = False     # 是否为子配料
    is_low_impact: bool = False         # 是否为 ≤2% 组
    parenthetical_text: Optional[str]   # 括号内子配料文本
    children: list["IngredientNode"]    # 子配料

    # 映射结果（解析后填充）
    mapping_candidates: list["MappingCandidate"] = []

class IngredientTree(BaseModel):
    """配料解析树"""
    raw_text: str
    root_ingredients: list[IngredientNode]
    two_percent_group: list[IngredientNode]

class MappingCandidate(BaseModel):
    """配料映射候选"""
    fdc_id: int
    description: str
    source: str                 # "SR_LEGACY" | "FNDDS" | "FOUNDATION"
    confidence: float           # 0-1
    nutrient_profile: NutrientProfile
    match_method: str           # "exact" | "fuzzy" | "synonym" | "manual"
```

### 3.3 ProductObservation

```python
class ProductObservation(BaseModel):
    """产品观测（求解器输入）"""
    fdc_id: int
    description: str
    source: str                 # "FNDDS" | "BRANDED"

    # 标签营养素
    label_nutrients: list[NutrientRecord]
    serving_size_g: float       # serving size in grams

    # 配料
    ingredient_tree: IngredientTree

    # 元信息
    brand_owner: Optional[str] = None
    branded_category: Optional[str] = None
    gtin_upc: Optional[str] = None

    # 仅 FNDDS 验证阶段可用（gold standard）
    true_ingredient_fractions: Optional[dict[str, float]] = None
    true_nutrient_profile: Optional[NutrientProfile] = None
```

### 3.4 TrustReport

```python
class TrustReport(BaseModel):
    """可信报告"""
    fdc_id: int
    description: str

    # 估计结果
    ingredient_estimates: list[IngredientEstimate]
    expanded_nutrients: list[NutrientEstimate]

    # 质量指标
    nutrient_residuals: dict[str, float]       # nutrient_name → residual
    constraint_slacks: dict[str, float]        # constraint_name → slack
    constraint_conflicts: list[str]

    # 不确定性
    identifiability_report: IdentifiabilityReport

    # 溯源
    mapping_provenance: list[MappingProvenance]
    data_source_version: dict[str, str]

    # 结论
    warnings: list[str]
    trust_grade: str            # "A" | "B" | "C" | "D"
    trust_score: float          # 0-100

class IngredientEstimate(BaseModel):
    ingredient_name: str
    point_estimate: float       # 点估计 (质量比例, 0-1)
    lower_bound: float          # 下界
    upper_bound: float          # 上界
    interval_80: tuple[float, float]
    interval_95: tuple[float, float]
    mapping_confidence: float

class NutrientEstimate(BaseModel):
    nutrient_name: str
    unit: str
    median: float
    p5: float
    p95: float
    label_value: Optional[float] = None
    source_coverage: float      # 配料中该营养素的数据覆盖率 0-1

class IdentifiabilityReport(BaseModel):
    n_ingredients: int
    n_label_nutrients: int
    degrees_of_freedom: int
    identifiable_ingredients: list[str]
    poorly_identified_ingredients: list[str]
    interval_width_median: float
```

### 3.5 SolverResult

```python
class SolverResult(BaseModel):
    """求解器输出"""
    success: bool
    message: str

    # 点估计
    x_point: dict[str, float]              # ingredient_name → fraction
    moisture_change: Optional[float]       # 水分变化参数
    objective_value: float

    # 区间估计
    x_lower: dict[str, float]
    x_upper: dict[str, float]

    # 拟合质量
    nutrient_predicted: dict[str, float]   # 预测营养素值
    nutrient_residuals: dict[str, float]
    constraint_values: dict[str, float]
    constraint_slacks: dict[str, float]
    active_constraints: list[str]

    # 求解元信息
    solver_name: str
    n_iterations: int
    n_func_evals: int
    solve_time_s: float
```

---

## 4. 数据流设计

### 4.1 FNDDS Forward Validation 数据流

```
FNDDS JSON
    │
    ▼
FNDDSDataAdapter.read_recipe(fdc_id)
    │ 提取: inputFoods, ingredient weights, retention codes, moisture adjustment
    │
    ├──→ ingredient_weights → ForwardNutritionModel
    │         │
    │         ├── ingredient_fdc_ids → SRLegacyDataAdapter / FNDDSDataAdapter
    │         │       │ 查询 ingredient nutrient profiles (per 100g)
    │         │       ▼
    │         │   NutrientMatrix (ingredients × nutrients)
    │         │
    │         ├── compute predicted_nutrients = Σ x_i × A_ij
    │         ├── apply retention factors
    │         ├── apply moisture / yield adjustment
    │         ▼
    │     PredictedFinalNutrients
    │
    └──→ FNDDSNutVal (true final nutrients)
              │
              ▼
          Comparison: MAE, relative error, nutrient-specific residuals
              │
              ▼
          ForwardValidationReport
```

### 4.2 FNDDS Inverse Reconstruction 数据流

```
FNDDS JSON
    │
    ▼
FNDDSDataAdapter.read_recipe(fdc_id)
    │
    ├──→ IngredientTree (from inputFoods, with order)
    ├──→ NutrientProfile (from FNDDSNutVal)
    ├──→ IngredientNutrientMatrix (from IngredNutVal)
    │
    ▼
ProductObservation (without true fractions)

    │
    ▼
NuSol Inverse Pipeline:
    │
    ├── 1. ConstraintBuilder.build(product_obs, config)
    │       ├── MassBalanceConstraint
    │       ├── IngredientOrderConstraint
    │       ├── LabelIntervalFitConstraint
    │       └── ...
    │
    ├── 2. PointSolver.solve(variables, constraints, objective)
    │       └── SciPy trust-constr / SLSQP
    │
    ├── 3. BoundSolver.solve(variables, constraints)
    │       └── For each ingredient: min/max subject to all constraints
    │
    ├── 4. EnsembleSolver.solve(variables, constraints, config)
    │       ├── Multi-start (n=50)
    │       ├── Label bootstrap (n=100)
    │       ├── Mapping perturbation
    │       └── Aggregate → intervals
    │
    ▼
SolverResult
    │
    ▼
TrustReportBuilder.build(solver_result, product_obs)
    │
    ▼
TrustReport
    │
    ▼
Compare estimated fractions vs FNDDS true fractions
    │
    ▼
InverseValidationReport
```

### 4.3 Branded Food Application 数据流

```
USDA Branded Food JSON
    │
    ▼
BrandedDataAdapter.read_product(fdc_id)
    │
    ├──→ ingredients_string → IngredientParser → IngredientTree
    ├──→ labelNutrients / foodNutrients → LabelNutrientConverter → TargetIntervals
    ├──→ servingSize → per_100g conversion
    │
    ▼
ProductObservation

    │
    ▼
IngredientMapper.map(ingredient_tree)
    │ 对每个 ingredient node:
    │   ├── 精确匹配 SR Legacy
    │   ├── 模糊匹配（TF-IDF / fuzzy string matching）
    │   ├── 同义词/别名映射
    │   ├── 返回 top-k candidates + confidence
    │   ▼
    │ IngredientTree with mapping_candidates
    │
    ▼
ConstraintBuilder + Solver (同 FNDDS 流程)
    │
    ▼
NutrientExpander.expand(ingredient_estimates, nutrient_matrix)
    │ 用 ingredient fraction intervals × ingredient nutrient profiles
    │ → 计算扩展营养素（标签之外的营养素）
    │
    ▼
TrustReport
```

---

## 5. 约束系统实现细节

### 5.1 约束优先级和罚函数

```python
from enum import IntEnum

class ConstraintPriority(IntEnum):
    P0 = 0    # 不可放松（硬约束）
    P1 = 1    # 法规结构（尽量硬，可小量 slack）
    P2 = 2    # 标签拟合（软约束，目标函数项）
    P3 = 3    # 食品科学（软约束，低权重）
    P4 = 4    # 统计先验（软约束，最低权重）

class ConstraintBase:
    priority: ConstraintPriority
    name: str
    enabled: bool = True
    slack_allowed: bool = False
    slack_max: float = 0.0        # 最大允许 slack
    weight: float = 1.0           # 软约束在目标函数中的权重

    def evaluate(self, x: np.ndarray, context: dict) -> ConstraintEval:
        """返回 constraint value, slack, violation flag"""
        ...

    def to_scipy_constraint(self) -> dict:
        """转为 SciPy 约束格式"""
        ...
```

### 5.2 P0: 质量守恒

```python
class MassBalanceConstraint(ConstraintBase):
    """
    Σ_i x_i = 1
    x_i ≥ 0
    复合配料: parent.x = Σ child.x
    """
    priority = P0
    slack_allowed = False

    def evaluate(self, x, context):
        total = np.sum(x)
        return ConstraintEval(
            value=total,
            target=1.0,
            violation=abs(total - 1.0),
            slack=0.0,
            satisfied=abs(total - 1.0) < 1e-6
        )
```

### 5.3 P1: 配料比例排序

```python
class IngredientOrderConstraint(ConstraintBase):
    """
    对于不在 ≤2% 组的主配料:
      x_i ≥ x_{i+1} (按顺序排列)
    
    对于 ≤2% 组的配料:
      x_i ≤ 0.02
    """
    priority = P1
    slack_allowed = True
    slack_max = 0.005  # 允许 0.5% 的 slack

    def evaluate(self, x, context):
        violations = []
        main_ingredients = context['main_ingredient_indices']
        two_pct_indices = context['two_percent_indices']

        for i in range(len(main_ingredients) - 1):
            if x[main_ingredients[i]] < x[main_ingredients[i+1]]:
                violations.append(x[main_ingredients[i+1]] - x[main_ingredients[i]])

        for idx in two_pct_indices:
            if x[idx] > 0.02:
                violations.append(x[idx] - 0.02)

        return ConstraintEval(...)
```

### 5.4 P2: 标签营养素区间

```python
class LabelIntervalFitConstraint(ConstraintBase):
    """
    将标签值转换为法规感知区间，计算拟合残差。

    转换逻辑（FDA rounding rules）：
      - < 0.5g → [0, 0.5)
      - < 1g → [0.5, 1)
      - ≥ 1g → round to nearest 1g
      - ... (更多规则)

    残差计算：
      如果 predicted 在区间内 → 0
      否则 → 超出区间的距离
    """
    priority = P2
    slack_allowed = True

    def build_target_intervals(self, label_nutrients: list) -> dict:
        """根据 FDA 四舍五入规则计算每个营养素的 target interval"""
        intervals = {}
        for nut in label_nutrients:
            intervals[nut.name] = self._fda_rounding_interval(
                nut.amount, nut.unit
            )
        return intervals

    def _fda_rounding_interval(self, value: float, unit: str) -> tuple[float, float]:
        """返回 (lower, upper) interval"""
        # Implementation of FDA 21 CFR 101.9 rounding rules
        ...
```

---

## 6. Solver 实现策略

### 6.1 优化问题形式

```
minimize    Σ_j w_j × slack_j² + Σ_k w_k × prior_violation_k²
            (P2 label fit + P3 science + P4 prior 的加权罚项)

subject to  Σ_i x_i = 1                        (P0 硬约束)
            x_i ≥ 0, ∀i                        (P0 硬约束)
            x_i ≥ x_{i+1} + slack              (P1 软/硬约束)
            predicted_nutrient_j ∈ interval_j   (P2 目标函数项)
```

决策变量：`x = [x_0, x_1, ..., x_n]`（n 个配料的质量比例），可选 `θ`（加工参数）

### 6.2 PointSolver

```python
class PointSolver:
    """
    使用 SciPy.optimize.minimize 寻找最优点估计。

    策略：
      1. 用均匀分布或 category prior 生成初始点
      2. 使用 trust-constr (优先) 或 SLSQP
      3. P0 为等式/不等式约束 (scipy constraints)
      4. P1 尽量硬，允许微量 slack
      5. P2-P4 合并进目标函数作为罚项
    """
    def solve(self, variables, constraints, config) -> SolverResult:
        # 1. 构造初始点
        x0 = self._initial_guess(variables, constraints)

        # 2. 构造 SciPy 约束
        scipy_constraints = [
            c.to_scipy_constraint()
            for c in constraints if c.priority <= P1
        ]

        # 3. 构造目标函数
        def objective(x):
            return self._penalty(x, constraints, config)

        # 4. 求解
        result = minimize(
            objective, x0,
            method='trust-constr',
            constraints=scipy_constraints,
            bounds=Bounds(0, 1),
            options={'maxiter': 1000, 'xtol': 1e-8}
        )

        return SolverResult(...)
```

### 6.3 BoundSolver

```python
class BoundSolver:
    """
    对每个配料分别求解可行最小值/最大值。

    策略：
      For each ingredient i:
        minimize x_i  subject to all constraints → lower bound
        maximize x_i  subject to all constraints → upper bound

    对于不稳定的 bound，可以在 EnsembleSolver 中通过
    采样进一步验证。
    """
    def solve(self, variables, constraints, point_result=None) -> SolverResult:
        lower = {}
        upper = {}
        for i, name in enumerate(variables.ingredient_names):
            # Minimize x_i
            res_min = minimize(
                lambda x: x[i], x0,
                constraints=all_scipy_constraints,
                bounds=Bounds(0, 1)
            )
            lower[name] = res_min.x[i] if res_min.success else 0.0

            # Maximize x_i
            res_max = minimize(
                lambda x: -x[i], x0,
                constraints=all_scipy_constraints,
                bounds=Bounds(0, 1)
            )
            upper[name] = res_max.x[i] if res_max.success else 1.0

        return SolverResult(x_lower=lower, x_upper=upper, ...)
```

### 6.4 EnsembleSolver

```python
class EnsembleSolver:
    """
    通过多重采样产生不确定性区间。

    扰动源：
      1. 多初值 (n=50): 不同起点 → 可能收敛到不同局部最优
      2. 标签 bootstrap (n=100): 在 target interval 内重新采样标签值
      3. 映射扰动: 随机选择 top-3 映射候选中非首选候选
      4. 数据库值扰动: 在 ingredient nutrient value 上添加高斯噪声

    输出:
      - Percentile intervals (5%, 25%, 50%, 75%, 95%)
      - Kernel density estimate
    """
    def solve(self, variables, constraints, config) -> SolverResult:
        results = []

        # 多初值
        for seed in range(config.multi_start):
            x0 = self._random_initial(variables, seed)
            res = self._point_solve(x0, variables, constraints)
            if res.success:
                results.append(res)

        # 标签 bootstrap
        for boot in range(config.n_bootstrap):
            perturbed_constraints = self._bootstrap_labels(constraints, boot)
            x0 = self._random_initial(variables, boot + 10000)
            res = self._point_solve(x0, variables, perturbed_constraints)
            if res.success:
                results.append(res)

        # 聚合
        return self._aggregate(results, variables)
```

---

## 7. 法规感知标签区间

### 7.1 FDA 四舍五入规则 (21 CFR 101.9)

```python
# 部分关键规则
FDA_ROUNDING_RULES = {
    "Energy": {
        "unit": "kcal",
        "rules": [
            ("< 5", "round_nearest_5"),        # < 5 cal → 0
            ("≤ 50", "round_nearest_5"),       # 5-50 → nearest 5
            ("> 50", "round_nearest_10"),      # > 50 → nearest 10
        ]
    },
    "Total lipid (fat)": {
        "unit": "g",
        "rules": [
            ("< 0.5", "express_as_0"),
            ("< 5", "round_nearest_0.5"),
            ("≥ 5", "round_nearest_1"),
        ]
    },
    "Sodium, Na": {
        "unit": "mg",
        "rules": [
            ("< 5", "express_as_0"),
            ("≤ 140", "round_nearest_5"),
            ("> 140", "round_nearest_10"),
        ]
    },
    # ... 更多规则
}

def label_value_to_interval(
    label_value: float, unit: str, nutrient_name: str
) -> tuple[float, float]:
    """
    将 Nutrition Facts 标签值转换为法规感知的可能真值区间。

    例:
      label: "Total Fat 5g"  → interval: [4.75, 5.25)
      label: "Sodium 120mg"   → interval: [117.5, 122.5)
      label: "Calories 250"   → interval: [245, 255)
    """
    ...
```

### 7.2 Per Serving → Per 100g 转换

```python
def normalize_to_per_100g(
    nutrients: list[NutrientRecord],
    serving_size_g: float
) -> list[NutrientRecord]:
    """
    将 per serving 的营养值转换到 per 100g 基准。

    四舍五入传播：
      由于 serving → 100g 的乘数放大了标签四舍五入区间，
      需要传播 uncertainty。
    """
    multiplier = 100.0 / serving_size_g
    result = []
    for nut in nutrients:
        lower, upper = label_value_to_interval(nut.amount, nut.unit, nut.name)
        result.append(NutrientRecord(
            name=nut.name,
            amount=nut.amount * multiplier,  # nominal
            lower_bound=lower * multiplier,
            upper_bound=upper * multiplier,
            unit=f"{nut.unit}_per_100g"
        ))
    return result
```

---

## 8. 配料解析 (Ingredient Parser)

### 8.1 解析规则

配料表是一段自然语言文本，按特定格式编写。需要处理的结构：

| 结构 | 示例 | 处理方式 |
|------|------|----------|
| 主配料序列 | `OATS, SUGAR, OIL, SALT` | 按逗号分割 |
| 括号子配料 | `COCOA (PROCESSED WITH ALKALI)` | 递归解析括号内容 |
| `CONTAINS 2% OR LESS` | `CONTAINS 2% OR LESS OF: X, Y, Z` | 后面的配料标记为 ≤2% 组 |
| `AND/OR` | `SOYBEAN AND/OR CANOLA OIL` | 标记为替代配料组 |
| 句点终止 | `SALT.` → 配料 = `SALT` | 去除标点 |
| 复合配料声明 | `CHOCOLATE (SUGAR, COCOA BUTTER, ...)` | 创建 compound ingredient 节点 |

### 8.2 解析状态机

```python
class IngredientParser:
    """
    将配料 string 解析为 IngredientTree。

    处理流程:
      1. 预处理：统一大小写、去除多余空格
      2. 识别 CONTAINS ... 2% OR LESS 标记
      3. 识别 AND/OR 组
      4. 按逗号分割主体
      5. 递归处理括号内的子配料
      6. 清理标点、数字标记(*, †, etc.)
      7. 标准化配料名称（stemming, lemmatization）
    """
    def parse(self, text: str) -> IngredientTree:
        ...

    def _preprocess(self, text: str) -> str:
        """统一大小写、去 HTML、去多余空格"""
        ...

    def _split_ingredients(self, text: str) -> list[str]:
        """按逗号分割，但保护括号内的逗号"""
        ...

    def _extract_parenthetical(self, text: str) -> tuple[str, Optional[str]]:
        """提取括号内容"""
        ...
```

### 8.3 配料映射 (Ingredient Mapper)

```python
class IngredientMapper:
    """
    将 parsed ingredient 映射到食品成分数据库。

    多层映射策略:
      1. 精确匹配: ingredient name == DB description
      2. 标准化匹配: 去除品牌名、处理常见别名
      3. 模糊匹配: fuzzywuzzy / rapidfuzz (threshold > 85)
      4. 手动映射表: 常见 ingredient → FDC ID 映射

    输出: top-k candidates with confidence scores
    """
    def __init__(self, sr_legacy_db, fndds_db, foundation_db):
        self.databases = {
            'SR_LEGACY': sr_legacy_db,
            'FNDDS': fndds_db,
            'FOUNDATION': foundation_db,
        }
        self.synonym_map = self._load_synonym_map()

    def map(self, ingredient_name: str) -> list[MappingCandidate]:
        candidates = []
        for source, db in self.databases.items():
            # 精确匹配
            exact = db.search_exact(ingredient_name)
            if exact:
                candidates.append(MappingCandidate(
                    confidence=1.0, source=source, ...
                ))
                continue

            # 模糊匹配
            fuzzy = db.search_fuzzy(ingredient_name, threshold=85)
            for match in fuzzy:
                candidates.append(MappingCandidate(
                    confidence=match.score / 100, ...
                ))

        # 按 confidence 排序，保留 top-k
        candidates.sort(key=lambda c: c.confidence, reverse=True)
        return candidates[:5]
```

---

## 9. Forward Nutrition Calculation

```python
class ForwardNutritionModel:
    """
    基础模型:
      predicted_j = (100 / Y) × Σ_i x_i × A_ij × r_ij

    其中:
      x_i = ingredient i 的质量比例 (0-1)
      A_ij = ingredient i 每 100g 中 nutrient j 的含量
      r_ij = retention factor for nutrient j in ingredient i
      Y = final yield (accounting for moisture change)
    """
    def __init__(self, config):
        self.basis = config.get('basis', 'per_100g')
        self.retention_enabled = config.get('retention', {}).get('enabled', False)
        self.moisture_enabled = config.get('moisture', {}).get('enabled', False)

    def compute(
        self,
        ingredient_fractions: np.ndarray,
        nutrient_matrix: np.ndarray,
        retention_factors: Optional[np.ndarray] = None,
        moisture_change: float = 0.0,
    ) -> np.ndarray:
        """
        Returns: predicted nutrient values (per 100g finished product)

        nutrient_matrix: shape (n_ingredients, n_nutrients)
        ingredient_fractions: shape (n_ingredients,)
        """
        # 基本预测
        predicted = ingredient_fractions @ nutrient_matrix  # (n_nutrients,)

        # Yield 调整
        if self.moisture_enabled:
            yield_factor = 100.0 / (100.0 - moisture_change)
            predicted *= yield_factor

        return predicted
```

---

## 10. FNDDS 验证阶段详解

### 10.1 FNDDS 数据适配器

```python
class FNDDSDataAdapter(DataAdapterBase):
    """
    读取 FNDDS JSON，抽取 Recipe 结构。

    FNDDS JSON 中的关键字段：
      - foodNutrients: 最终产品营养素 (FNDDSNutVal)
      - inputFoods[]:
          - ingredientCode
          - ingredientDescription
          - ingredientWeight (g per 100g finished product)
          - retentionCode
          - amount
          - sequenceNumber (配料顺序)
      - foodPortions[]: serving size 信息
      - foodAttributes[]: WWEIA 分类
      - moistureAdjust (if applicable)
    """
    def read_recipe(self, fdc_id: int) -> dict:
        """返回一个 FNDDS recipe 的完整信息"""
        ...

    def get_ingredient_nutrients(self, ingredient_code: int) -> NutrientProfile:
        """从 IngredNutVal 获取配料营养素"""
        ...
```

### 10.2 Labelized Simulation

```python
def labelize_simulation(
    true_nutrients: list[NutrientRecord],
    serving_size_g: float,
    rounding_rules: str = "FDA",
) -> list[NutrientRecord]:
    """
    模拟真实标签不精确性：
      1. exact per 100g → per serving (multiply by serving/100)
      2. per serving → apply FDA rounding
      3. rounded label → convert to target intervals
      4. → NuSol inverse solver

    这样可以在已知 ground truth 的情况下，
    评估 rounding 和 interval 化对 reconstruction 的影响。
    """
    # Step 1: Convert to per serving
    per_serving = [
        NutrientRecord(
            name=n.name,
            amount=n.amount * serving_size_g / 100,
            unit=n.unit
        )
        for n in true_nutrients
    ]

    # Step 2: Apply rounding
    rounded = [
        NutrientRecord(
            name=n.name,
            amount=apply_fda_rounding(n.amount, n.unit, n.name),
            unit=n.unit
        )
        for n in per_serving
    ]

    # Step 3: Build target intervals
    intervals = {
        n.name: label_value_to_interval(n.amount, n.unit, n.name)
        for n in rounded
    }

    return rounded, intervals
```

---

## 11. 分阶段开发计划

### Phase 0: 基础框架搭建 (预计 3-5 天)

- [ ] 初始化 Python 项目 (`pyproject.toml`, `poetry init`)
- [ ] 搭建目录结构
- [ ] 实现核心 Schema (`nusol/core/schema.py`)
- [ ] 定义 NutrientRegistry (`nusol/core/nutrient_registry.py`)
- [ ] 实现单位系统 (`nusol/core/units.py`)
- [ ] 实现 YAML 配置加载 (`nusol/config/loader.py`)
- [ ] 实现配置 Schema 校验 (`nusol/config/config_schema.py`)
- [ ] 编写 Phase 0 单元测试
- [ ] 创建示例配置文件

### Phase 1: FNDDS 数据适配与 Forward Calculation (预计 5-7 天)

- [ ] 实现 `DataAdapterBase` 基类
- [ ] 实现 `FNDDSDataAdapter`: 读取 FNDDS JSON
  - 解析 `foodNutrients` (FNDDSNutVal)
  - 解析 `inputFoods` (FNDDSIngred)
  - 解析 IngredNutVal
  - 处理 moisture adjustment
- [ ] 实现 `SRLegacyDataAdapter`: 读取 SR Legacy JSON
- [ ] 实现 `ForwardNutritionModel`
  - 基础矩阵计算
  - Retention factor 支持
  - Moisture/yield adjustment
- [ ] 实现 FNDDS forward validation pipeline
- [ ] 实现评价指标 (`nusol/validation/metrics.py`)
- [ ] 编写 Phase 1 单元测试和集成测试

### Phase 2: Inverse Solver (预计 7-10 天)

- [ ] 实现约束基类 (`nusol/constraints/base.py`)
- [ ] 实现 P0 约束: MassBalance
- [ ] 实现 P1 约束: IngredientOrder, TwoPercentRule
- [ ] 实现 P2 约束: LabelIntervalFit (含 FDA rounding rules)
- [ ] 实现 P4 约束: CategoryPrior (第一版)
- [ ] 实现目标函数构造 (`nusol/solver/objective.py`)
- [ ] 实现多初值策略 (`nusol/solver/initializer.py`)
- [ ] 实现 `PointSolver`
- [ ] 实现 `BoundSolver`
- [ ] 实现基本版 `EnsembleSolver` (多初值部分)
- [ ] 编写 Phase 2 单元测试

### Phase 3: FNDDS Inverse Validation (预计 7-10 天)

- [ ] 实现 FNDDS inverse pipeline
  - 隐藏 true fractions
  - 使用 FNDDSNutVal 作为 target nutrients
  - 使用 inputFoods order 作为配料顺序
- [ ] 实现 Labelized Simulation
  - FDA rounding 规则完整实现
  - Serving size ↔ per 100g 转换
  - Rounding uncertainty propagation
- [ ] 实现 IngredientParser 基本版（不需要 Branded Food 的复杂解析）
- [ ] 实现 IngredientMapper 基本版
- [ ] 实现 TrustReport 生成
- [ ] 实现 TrustGrade 计算
- [ ] 运行 FNDDS benchmark
  - Forward reconstruction accuracy
  - Inverse reconstruction accuracy
  - Labelized simulation robustness
- [ ] 编写 Phase 3 测试

### Phase 4: Ablation Study (预计 3-5 天)

- [ ] 设计 ablation 配置（G0-G7）
- [ ] 实现 ablation 运行器 (`nusol/validation/ablation.py`)
- [ ] 实现评价指标汇总和可视化
- [ ] 运行并收集结果
- [ ] 约束权重调优
- [ ] Trust grade 校准

### Phase 5: Branded Food Adapter (预计 5-7 天)

- [ ] 实现 `BrandedDataAdapter`
  - 解析 Branded Food JSON
  - 提取 labelNutrients, foodNutrients
  - 提取 ingredients 字符串
  - 提取 servingSize, category, metadata
- [ ] 实现完整的 `IngredientParser`
  - 括号子配料处理
  - CONTAINS 2% OR LESS 识别
  - AND/OR 处理
  - 复合配料解析
- [ ] 实现完整的 `IngredientMapper`
  - 精确/模糊匹配
  - 同义词典
  - 手动映射表
  - Top-k candidates + confidence
- [ ] 实现 `LabelNutrientConverter`
  - per serving → per 100g
  - FDA rounding → target intervals
  - Compliance-aware intervals
- [ ] 编写 Phase 5 测试

### Phase 6: Branded Food Application (预计 7-10 天)

- [ ] 实现产品筛选逻辑
- [ ] 实现批量处理 pipeline
  - 遍历 Branded Food 产品
  - Ingredient parsing
  - Ingredient mapping
  - Constraint building
  - Solving (Point + Bound + Ensemble)
  - TrustReport generation
- [ ] 实现 `NutrientExpander`
  - 用 ingredient fraction intervals × nutrient matrix
  - 计算扩展营养素
  - 输出区间估计 (median, p5, p95)
- [ ] 实现批量报告
  - Category-level 统计
  - Solve rate, trust grade distribution
  - Constraint conflict frequency
- [ ] 输出 JSON/CSV/HTML 报告
- [ ] Failure mode taxonomy

### Phase 7: 文档、测试完善、论文准备（持续）

- [ ] API 文档
- [ ] 使用示例
- [ ] 完整测试覆盖
- [ ] 性能优化（并行处理、缓存）
- [ ] 论文图表生成

---

## 12. 关键接口设计

### 12.1 主 Pipeline 接口

```python
# scripts/run_fndds_forward.py

from nusol.config import load_config
from nusol.data import FNDDSDataAdapter
from nusol.nutrition import ForwardNutritionModel
from nusol.validation import ForwardValidator

def main():
    config = load_config("config/fndds_forward.yaml")

    # Load data
    adapter = FNDDSDataAdapter(config.data)
    recipes = adapter.load_recipes()

    # Run forward model
    model = ForwardNutritionModel(config.forward_model)
    results = []
    for recipe in recipes:
        predicted = model.compute(
            ingredient_fractions=recipe.fractions,
            nutrient_matrix=recipe.nutrient_matrix,
        )
        results.append(recipe.compare(predicted))

    # Validate
    validator = ForwardValidator(config)
    report = validator.evaluate(results)
    validator.save_report(report, config.reporting.output_dir)
```

### 12.2 Inverse Pipeline 接口

```python
# scripts/run_fndds_inverse.py

from nusol.config import load_config
from nusol.data import FNDDSDataAdapter
from nusol.constraints import ConstraintBuilder
from nusol.solver import PointSolver, BoundSolver, EnsembleSolver
from nusol.report import TrustReportBuilder

def main():
    config = load_config("config/fndds_inverse.yaml")
    adapter = FNDDSDataAdapter(config.data)

    for recipe in adapter.load_recipes():
        # Build ProductObservation (hide true fractions)
        obs = adapter.to_product_observation(recipe)

        # Build constraints
        builder = ConstraintBuilder(config.inverse_solver)
        constraints = builder.build(obs)

        # Solve
        point = PointSolver().solve(obs, constraints, config)
        bounds = BoundSolver().solve(obs, constraints, point)
        ensemble = EnsembleSolver().solve(obs, constraints, config)

        # Report
        report = TrustReportBuilder().build(
            obs, point, bounds, ensemble, config.reporting
        )

        # Validate against ground truth
        compare(report, recipe.true_fractions)
```

---

## 13. 配置文件设计

### 13.1 主配置文件结构

```yaml
# config/fndds_inverse.yaml
run_id: fndds_inverse_v1
description: "FNDDS inverse reconstruction with full constraint set"

data:
  fndds:
    path: "../db/FoodData_Central_survey_food_json_2024-10-31/surveyDownload.json"
    version: "2021-2023"
  ingredient_nutrients:
    path: "../db/FoodData_Central_sr_legacy_food_json_2018-04/FoodData_Central_sr_legacy_food_json_2018-04.json"
    version: "2018"

forward_model:
  basis: per_100g
  retention:
    enabled: true
    source: fndds  # 从 FNDDS retention code 读取
  moisture:
    enabled: true
    estimate: true  # 将 moisture change 作为优化变量
    default_bounds: [-0.30, 0.30]

inverse_solver:
  variables:
    ingredient_fractions: true
    moisture_change: true
  constraints:
    mass_balance:
      enabled: true
      priority: P0
    ingredient_order:
      enabled: true
      priority: P1
      slack: true
      penalty_weight: 1000.0
    label_interval_fit:
      enabled: true
      priority: P2
      default_weight: 10.0
      rounding_standard: FDA_21CFR_101_9
    energy_closure:
      enabled: true
      priority: P3
      weight: 0.2
  solver:
    point_solver: scipy_trust_constr
    multi_start: 50
    max_iter: 1000
    tolerance: 1e-8
    bound_solver:
      enabled: true
    ensemble:
      enabled: true
      n_bootstrap: 100
      n_multi_start: 50

reporting:
  output_dir: "./output/fndds_inverse_v1"
  formats: [json, csv, html]
  include_provenance: true
  include_uncertainty: true
  include_warnings: true
  include_trust_grade: true
```

### 13.2 Ablation 配置生成

```python
def generate_ablation_configs(base_config: dict) -> list[dict]:
    """生成 G0-G7 的消融配置"""
    ablation_levels = {
        'G0': ['mass_balance'],
        'G1': ['mass_balance', 'ingredient_order'],
        'G2': ['mass_balance', 'ingredient_order', 'label_interval_fit'],
        'G3': ['mass_balance', 'ingredient_order', 'label_interval_fit', 'energy_closure'],
        'G4': ['mass_balance', 'ingredient_order', 'label_interval_fit',
               'energy_closure', 'moisture'],
        'G5': ['mass_balance', 'ingredient_order', 'label_interval_fit',
               'energy_closure', 'moisture', 'sodium_balance'],
        'G6': ['mass_balance', 'ingredient_order', 'label_interval_fit',
               'energy_closure', 'moisture', 'sodium_balance', 'category_prior'],
        'G7': ['mass_balance', 'ingredient_order', 'label_interval_fit',
               'energy_closure', 'moisture', 'sodium_balance', 'category_prior',
               'added_sugar_balance', 'fatty_acid_closure'],
    }
    configs = []
    for level, enabled in ablation_levels.items():
        cfg = copy.deepcopy(base_config)
        for c_name in cfg['inverse_solver']['constraints']:
            cfg['inverse_solver']['constraints'][c_name]['enabled'] = \
                c_name in enabled
        configs.append((level, cfg))
    return configs
```

---

## 14. 数值处理规范

### 14.1 四舍五入处理

所有 label value → interval 转换必须使用 tolerance-aware 比较：

```python
# 不应该用:
if predicted == label_value: ...

# 应该用:
def within_interval(predicted: float, interval: tuple[float, float]) -> bool:
    return interval[0] <= predicted <= interval[1]

def interval_overlap(a: tuple, b: tuple) -> bool:
    return a[0] <= b[1] and b[0] <= a[1]
```

### 14.2 零值处理

Label 上标注为 0 的营养素不一定真的是 0：
- 实际值 < 0.5g 可能被 label 为 0g
- 需要建立 "expressed as zero" → [0, threshold) 的映射

### 14.3 不确定性传播

当 nutrient value 带有 uncertainty interval 时，forward calculation 应传播 uncertainty：

```python
# Interval arithmetic for forward model
predicted_lower = Σ_i x_i_lower × A_ij_lower
predicted_upper = Σ_i x_i_upper × A_ij_upper
```

---

## 15. 测试策略

### 15.1 测试层级

| 层级 | 工具 | 覆盖目标 |
|------|------|----------|
| 单元测试 | pytest | 每个模块 ≥ 90% |
| 集成测试 | pytest | 数据流、pipeline 端到端 |
| 回归测试 | pytest + fixtures | 已知 FNDDS recipe 的精确输出 |
| 性能测试 | pytest-benchmark | 大型 product 的求解时间 |

### 15.2 关键测试用例

- FNDDS forward: 使用 5-10 个已知 recipe，验证 nutrient calculation 精确重现
- Mass balance: Σx = 1, x ≥ 0 在所有求解结果中成立
- Ingredient order: 主配料的估计顺序与声明顺序一致
- Label interval: 预测营养素在 target interval 内（或 slack 可控）
- Bound solver: lower ≤ point ≤ upper

### 15.3 Test Fixtures

```python
# tests/conftest.py
@pytest.fixture
def sample_fndds_recipe():
    """一个简单的 FNDDS recipe fixture"""
    return {
        'fdc_id': 2705384,
        'description': 'Milk, NFS',
        'inputFoods': [...],
        'foodNutrients': [...],
    }

@pytest.fixture
def sample_branded_product():
    """一个 Branded Food product fixture"""
    return {
        'fdc_id': 1106281,
        'description': 'GRANOLA',
        'ingredients': 'ORGANIC ROLLED OATS, ...',
        'foodNutrients': [...],
    }
```

### 15.4 CI/CD 建议

- pre-commit: ruff format + ruff check + mypy
- GitHub Actions: pytest on push
- Coverage report via pytest-cov (target > 80%)

---

## 16. 编码规范

- **命名**: snake_case for functions/variables, PascalCase for classes
- **类型注解**: 所有 public 函数必须有完整类型注解
- **Docstring**: Google style, 含 Args, Returns, Raises, Examples
- **Imports**: stdlib → third-party → local, 按字母序
- **行长**: 100 字符上限
- **数值**: 用 `float` 不用 `int` for nutrient amounts; 显式处理 NaN

---

## 17. 依赖

使用 **uv** 管理依赖。初始化项目：

```bash
uv init --lib nusol-t
uv add numpy scipy pandas pydantic pyyaml omegaconf typer jinja2 plotly tqdm
uv add --dev pytest pytest-cov pytest-benchmark ruff mypy pre-commit
```

```toml
# pyproject.toml (核心依赖)
[project]
name = "nusol-t"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "numpy>=1.26",
    "scipy>=1.12",
    "pandas>=2.1",
    "pydantic>=2.5",
    "pyyaml>=6.0",
    "omegaconf>=2.3",
    "typer>=0.12",
    "jinja2>=3.1",
    "plotly>=5.18",
    "tqdm>=4.66",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.1",
    "pytest-benchmark>=4.0",
    "ruff>=0.3",
    "mypy>=1.8",
    "pre-commit>=3.6",
]

[tool.uv]
dev-dependencies = [
    "pytest>=8.0",
    "pytest-cov>=4.1",
    "pytest-benchmark>=4.0",
    "ruff>=0.3",
    "mypy>=1.8",
    "pre-commit>=3.6",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

---

## 18. 参考文献概要

### 文献 1 (经典方法 — 线性规划估计配料比例)
- **核心方法**: 使用线性规划从配料和营养标签估计食品营养组成
- **关键技术**: 配料映射、线性规划约束求解、processing water 虚拟成分
- **在 NuSol 中的应用**: inverse solver 的基础方法论

### 文献 2 (较新方法 — ML 预测标签营养素)
- **核心方法**: 使用 USDA Branded Food 数据库训练 ML 模型预测营养素
- **数据**: USDA Global Branded Food Products Database
- **在 NuSol 中的应用**: baseline comparison、Branded Food 处理实践参考

---

> **文档版本**: v0.1.0  
> **最后更新**: 2026-07-04  
> **维护者**: Yanshan Jin
