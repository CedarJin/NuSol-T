# NuSol-T 技术原理与求解器设计

> 面向食物营养成分分析的约束求解框架——从营养学原理到工程实现

---

## 目录

1. [营养学基础：线性混合模型](#1-营养学基础线性混合模型)
2. [问题的数学结构](#2-问题的数学结构)
3. [约束的分层体系](#3-约束的分层体系)
4. [Slack 变量与软约束机制](#4-slack-变量与软约束机制)
5. [IngredientMapper：四级回退映射](#5-ingredientmapper四级回退映射)
6. [求解器架构总览](#6-求解器架构总览)
7. [Point Solver：Slack-based QP](#7-point-solverslack-based-qp)
8. [Bounds Solver：LP 可行域分析](#8-bounds-solverlp-可行域分析)
9. [Slack Budget 机制](#9-slack-budget-机制)
10. [FNDDS 验证方法论](#10-fndds-验证方法论)
11. [配方的可辨识性条件](#11-配方的可辨识性条件)
12. [全流程 Pipeline](#12-全流程-pipeline)

---

## 1. 营养学基础：线性混合模型

### 1.1 基本假设

加工食品本质上是一个**物理混合系统**。当配料按比例混合制成成品时，每一项营养素含量满足：

$$\text{Nutrient}_{final} = \sum_{i=1}^{n} x_i \cdot \text{Nutrient}_{i}$$

其中 $x_i$ 是第 $i$ 种配料的质量分数（$\sum x_i = 1$），$\text{Nutrient}_i$ 是该配料每 100g 的营养素含量，来自 USDA 数据库。

### 1.2 假设成立的条件

大多数加工工艺不改变化学元素的物质守恒：

| 工艺 | 蛋白质 | 脂肪 | 碳水 | 矿物质 | 维生素 |
|------|--------|------|------|--------|--------|
| 搅拌/混合 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 研磨/粉碎 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 巴氏杀菌 | ✓ | ✓ | ✓ | ✓ | 轻微损失 |
| 烘焙 | ✓ | ✓ | ✓ | ✓ | 热敏损失 |
| 发酵 | 转化 | ✓ | 消耗 | ✓ | 合成/损失 |
| 深度油炸 | 变性 | 吸收 | ✓ | ✓ | 损失 |

对于大多数加工食品，线性假设足够精确。需要修正的例外通过 retention factor 处理（Phase 3+）。

### 1.3 营养素作为化学指纹

每种配料在不同营养素维度上呈现独特的"化学指纹"：

| 配料 | 能量 | 蛋白 | 脂肪 | 碳水 | 纤维 | 糖 | 钠 |
|------|------|------|------|------|------|-----|-----|
| Water | 0 | 0 | 0 | 0 | 0 | 0 | 4 |
| Oats | 379 | 13.2 | 6.5 | 67.7 | 10.1 | 1.0 | 6 |
| Canola oil | 884 | 0 | **100** | 0 | 0 | 0 | 0 |
| Sugar | 387 | 0 | 0 | **100** | 0 | **99.8** | 1 |
| Salt | 0 | 0 | 0 | 0 | 0 | 0 | **38800** |

这种化学多样性是反推配料比例的基础——不同配料在不同的营养维度上"点亮"独特的信号。

---

## 2. 问题的数学结构

### 2.1 已知条件

| 信息来源 | 提供的内容 | 数学符号 |
|----------|-----------|----------|
| Nutrition Facts 标签 | 每 100g 成品的营养素含量 | $b_j$（第 $j$ 种营养素的标签值） |
| 配料表 | 配料名称（按含量降序排列） | 配料名 → USDA 数据库查询 |
| USDA SR Legacy | 每种配料每 100g 的营养素含量 | $A_{ij}$（配料 $i$ 中营养素 $j$ 的含量） |

### 2.2 未知变量

$$x_i \in [0, 1], \quad i = 1, \dots, n \quad \text{（每种配料的质量分数）}$$

### 2.3 线性方程组

$$\begin{cases}
A_{11}x_1 + A_{21}x_2 + \cdots + A_{n1}x_n = b_1 \quad \text{(能量)} \\
A_{12}x_1 + A_{22}x_2 + \cdots + A_{n2}x_n = b_2 \quad \text{(蛋白质)} \\
\vdots \\
A_{1m}x_1 + A_{2m}x_2 + \cdots + A_{nm}x_n = b_m \quad \text{(钾)}
\end{cases}$$

矩阵形式：**A·x = b**，其中 A 是 n×m 配料×营养素矩阵，x 是 n 维分数向量，b 是 m 维标签值向量。

### 2.4 三种求解情况

| 情况 | 条件 | 示例 | 结果 |
|------|------|------|------|
| 确定/超定 | m ≥ n-1，配料化学差异大 | Oat milk (5 配料, 10 观测) | MAE 0.24pp |
| 欠定 | 配料营养相似，有效维度不足 | Milk NFS (4 乳品, 1 有效维度) | MAE 19pp |
| 矛盾 | 标签值无法由配料数据解释 | 排除强化剂后的钙 (155mg vs max 5mg) | Infeasible |

---

## 3. 约束的分层体系

约束按优先级分为 5 级，从物理定律到统计先验：

### P0：硬约束（物理定律，必须满足）

**质量守恒**：

$$\sum_{i=1}^{n} x_i = 1.0$$

100g 成品由 100g 配料组成。这是最基本的物理约束。

### P1：法规结构约束

- `ingredient_order`：$x_i \geq x_{i+1}$（配料按含量降序排列，遵循 FDA 标签法规）
- `two_percent`：标记为 "≤2%" 的配料 $\leq 0.02$

### P2：标签拟合（软约束，允许松弛）

对每个标签声明的营养素 $j$：

$$b_j^{lo} \leq \sum_i x_i \cdot A_{ij} \leq b_j^{hi}$$

**为什么用区间而不是精确值？**

1. FDA 允许 Nutrition Facts 标签与实验室值之间存在误差（Class I: ±20%, Class II: ±20% 上限 + 不限下限）
2. USDA 数据库值是实验室测量均值，实际原料有 ±10-15% 的生物变异
3. 标签值存在 rounding 规则（如 <5 kcal → round to 0; 5-50 → nearest 5）

### P3：食品科学约束

- 脂肪酸闭合：$\sum$ 各脂肪酸 ≤ 总脂肪
- 能量闭合：4×蛋白 + 4×碳水 + 9×脂肪 ≈ 总能量
- 水分/固形物平衡

### P4：统计先验

- 同类产品配料比例的分布先验
- 特定品类配料用量范围（如面包中盐 <2%）

---

## 4. Slack 变量与软约束机制

### 4.1 为什么需要 Slack

硬约束要求"必须满足"，但现实中配料数据库和标签值都只是近似值。如果强行要求完美匹配，问题很容易变成 infeasible。

Slack 变量允许约束被"有限度地违反"，但违反产生惩罚。

### 4.2 数学形式

每个软区间约束拆成两个方向：

**lo-side**（下限）：
$$A \cdot x + s_{lo} \geq b^{lo}, \quad s_{lo} \geq 0$$

**hi-side**（上限）：
$$A \cdot x - s_{hi} \leq b^{hi}, \quad s_{hi} \geq 0$$

### 4.3 目标函数

$$\min_{x, s} \sum_{k} w_k \cdot s_k^2$$

其中 $w_k$ 是约束权重（YAML 中 `weight: 10.0`）。

**为什么是 $s^2$ 而不是 $|s|$？**

平方惩罚的边际成本递增：一个 4 单位的 slack 比两个 2 单位的 slack 代价更大（$4^2 = 16 > 2^2 + 2^2 = 8$）。这迫使求解器将偏差分散到多个营养素上，而不是让单一营养素严重偏离。营养学上合理——多种营养素的微量偏差优于单一营养素的严重偏差。

### 4.4 Slack 的营养学解释

| Slack 值 | 含义 | 可能原因 |
|----------|------|----------|
| s = 0 | 数据完美解释标签 | 配料数据与标签高度自洽 |
| s > 0 | 存在不可调和的偏差 | 数据库误差 / 生物变异 / 强化剂缺失 |
| s 很大 | 某个营养素严重不匹配 | 可能是强化营养素被排除 |

oat milk 的 objective = $2.2 \times 10^{-15}$，意味着所有 10 种营养素的 slack 全部接近零——配料数据与标签完美自洽。

---

## 5. IngredientMapper：四级回退映射

### 5.1 核心问题

Branded food 标签上的配料名是短名（"OATS"、"CANOLA OIL"），USDA 数据库中则是冗长的标准名（"Cereals, oats, regular and quick, not fortified, dry"）。Mapper 完成名称到营养成分的映射。

### 5.2 四级回退策略

```
Ingredient Code/Name
    │
    ├─ L1: code → FNDDS foodCode (confidence=1.0)
    │      同一数据源自查询。e.g. code 8120 → "Cereals, oats..."
    │
    ├─ L2: code → Foundation Foods ndbNumber (confidence=0.98)
    │      最新 USDA 数据 (2026)，比 SR Legacy 更准确
    │
    ├─ L3: code → SR Legacy ndbNumber (confidence=0.95)
    │      最全面的回退 (2018)，覆盖 7793 种食材
    │
    └─ L4: description → SR Legacy fuzzy search (confidence=score/100)
           文本匹配：exact → substring → word-overlap
```

### 5.3 Fortificant 处理

配料代码 999xxx 系列是纯营养素强化剂（无营养成分数据），在 L1 之前短路返回：

```python
FORTIFICANT_CODES = {
    "999328",  # Vitamin D
    "999301",  # Calcium
    "999303",  # Iron
    "999418",  # Vitamin B-12
    # ... 
}
# → MappingResult(method="fortificant", profile=None)
```

### 5.4 MappingResult 结构

| 字段 | 类型 | 说明 |
|------|------|------|
| `profile` | NutrientProfile \| None | 营养成分（None 表示未匹配） |
| `method` | str | "fndds_self" / "foundation_ndb" / "sr_legacy_ndb" / "fuzzy" / "fortificant" / "none" |
| `confidence` | float | 0.0-1.0 匹配置信度 |
| `food_state` | str | "as_purchased" / "estimated" / "unknown" |

---

## 6. 求解器架构总览

### 6.1 完整 Pipeline

```
YAML 文件
    │
    ▼
ConfigResolver (extends 继承, defaults 填充)
    │
    ▼
SolveDocument (Pydantic v2 严格校验, extra="forbid")
    │
    ▼
ProblemBuilder → IngredientProblem
    │              ├─ Ingredient 对象 (ID, 名称, 声明位置, 组别)
    │              ├─ CompositionMatrix (四态 missingness)
    │              └─ Observations (interval / exact / less_than)
    │
    ▼
ConstraintCompiler → CompiledProblem (Solver-Neutral IR)
    │                 ├─ VariableIR[]       (决策变量)
    │                 ├─ LinearConstraintIR[] (线性约束, mode=hard/soft)
    │                 └─ QuadraticPenaltyIR[] (二次罚项)
    │
    ├──────────────────────────┐
    ▼                          ▼
ScipySLSQPBackend         HighsLPBackend
(Point Solve)              (Bounds Solve)
    │                          │
    ▼                          ▼
fractions dict            bounds dict
{ing_id: point_est}      {ing_id: [lo, hi]}
    │                          │
    └──────────┬───────────────┘
               ▼
         Result Dict
{fractions, bounds, diagnostics, manifest}
```

### 6.2 Solver-Neutral IR

Compiler 不直接生成求解器代码，而是生成一个不依赖任何特定求解器的中间表示（IR）：

```python
@dataclass(frozen=True)
class VariableIR:
    id: str              # 配料 ID
    lower: float | None  # 变量下界
    upper: float | None  # 变量上界

@dataclass(frozen=True)
class LinearConstraintIR:
    id: str              # 约束 ID（可追溯到 YAML 声明）
    coefficients: np.ndarray   # c·x 的系数向量, shape (n_vars,)
    lower: float | None  # 下界 (None = 无下界)
    upper: float | None  # 上界 (None = 无上界)
    mode: "hard" | "soft"
    weight: float        # 软约束的二次惩罚权重
    source_id: str | None  # 追溯到 YAML 约束声明

@dataclass(frozen=True)
class CompiledProblem:
    variables: tuple[VariableIR, ...]
    linear_constraints: tuple[LinearConstraintIR, ...]
    quadratic_penalties: tuple[QuadraticPenaltyIR, ...]
    ingredient_ids: tuple[str, ...]
    nutrient_ids: tuple[str, ...]
```

**关键设计决策**：

- 所有 `frozen=True`：保证后端不能修改 IR
- `source_id` 追溯 YAML 声明：用于错误信息定位和 slack_budget 匹配
- IR 不包含 slack 变量：slack 是 Point Solver 的实现细节，不属于 IR 层

### 6.3 Capability Check

编译时 IR 聚合需求，求解时验证后端能力：

```
CompiledProblem.required_capabilities:
  {"continuous", "linear_constraints", "soft_constraints"}

ScipySLSQPBackend.capabilities:
  {"continuous", "linear_constraints", "soft_constraints"}  ✓

HighsLPBackend.capabilities:
  {"continuous", "linear_constraints"}  ✗ (no soft_constraints)
  → 用于 bounds (不需要 soft 能力)，不能用于 point solve (需要)
```

Mismatch → `UnsupportedConstraintError`（编译期错误，非运行时崩溃）。

### 6.4 两层注册表

| 注册表 | 注册对象 | 用途 | 外部插件 |
|--------|---------|------|----------|
| `ConstraintRegistry` | 约束类型 → compile 函数 | YAML `type: mass_balance` → IR | `nusol.constraints` entry points |
| `BackendRegistry` | 求解器名 → Backend 类 | YAML `backend: scipy_slsqp` → 求解 | `register_point/bounds()` API |

---

## 7. Point Solver：Slack-based QP

### 7.1 问题转化

将 YAML 中的 hard + soft 约束转化为非线性规划问题。

**分离约束**：

- Hard 约束 → 直接作为 SciPy 的等式/不等式约束
- Soft interval 约束 → 引入 slack 变量，每个方向一个

### 7.2 决策向量结构

```
x = [x₀, x₁, ..., x_{n-1}, s₀, s₁, ..., s_{m-1}]
     └── 配料分数 ──┘  └── slack 变量 ──┘
     n 维               m = 2 × |soft_constraints|
```

oat milk: n=5 配料, m=20 slack (10 营养素 × 2 方向), 总维度 = 25。

### 7.3 数学形式

**目标**：
$$\min_{x, s} \sum_{k=1}^{m} w_k \cdot s_k^2$$

**硬约束**：
$$A_{hard} \cdot x = b_{hard} \quad \text{（等式）}$$
$$A_{hard} \cdot x \geq b_{hard}^{lo} \quad \text{（不等式下界）}$$
$$A_{hard} \cdot x \leq b_{hard}^{hi} \quad \text{（不等式上界）}$$

**Slack 约束**（每个软方向一个）：
$$c \cdot x + s \geq lo \quad \text{（lo-side, 保证预测不低于下界减 slack）}$$
$$hi - c \cdot x + s \geq 0 \quad \text{（hi-side, 保证预测不高于上界加 slack）}$$
$$s \geq 0 \quad \text{（slack 非负）}$$

**变量边界**：
$$x_i \in [lower_i, upper_i] \quad \text{（来自 YAML variables.ingredient_fractions）}$$
$$s_k \in [0, 10^6] \quad \text{（slack 无实际上界）}$$

### 7.4 算法流程

```
1. 分离 hard/soft 约束
2. 可行性预检 (objective=0, 仅 hard 约束)
   → infeasible → SolveError
   → feasible → 记录可行点作为初始猜测
3. 构造初始解:
   x[:n] = 可行点
   x[n+k] = max(0, lo - predicted) 或 max(0, predicted - hi)
4. SLSQP 求解
5. 硬约束验证:
   → 满足 → 返回结果
   → 违反 → 10 次随机重启重试
```

### 7.5 为什么 SLSQP 需要 10 次重试

SLSQP 是**局部优化器**，从初始点沿梯度下降，可能停在局部最优或不可行区域。10 次随机重启通过探索不同的初始点来增加找到全局最优的概率。每次 restart 使用不同的随机种子生成 x[:n]，确保覆盖决策空间的广泛区域。

---

## 8. Bounds Solver：LP 可行域分析

### 8.1 核心思想

对每个配料 $i$ 分别求解两个独立的 LP：

$$\min / \max \quad x_i$$
$$\text{s.t.} \quad \text{所有 hard 约束}$$
$$x_j \in [lower_j, upper_j], \quad \forall j$$

n 个配料需要 2n 次 LP 求解。

### 8.2 为什么用 LP 而不用 SLSQP

| | SLSQP (Point) | HiGHS Simplex (Bounds) |
|---|---|---|
| 最优性 | 局部 | **全局** |
| 初始点 | 需要 | 不需要 |
| 目标 | 二次 | 线性 |
| 每次求解 | 1 次 | 2n 次 |

LP 通过 simplex 法保证全局最优——上下界是真正的可行极值，不是局部近似。

### 8.3 算法流程

```
1. 构造 LP 标准形式:
   Hard 约束 → A_ub·x ≤ b_ub, A_eq·x = b_eq
   软约束跳过（不进入 bounds）

2. 可行性预检:
   min 0·x  (dummy LP)
   → infeasible → SolveError("INFEASIBLE")

3. 对每个变量 i:
   下界: min c·x, c[i]=1, 其他=0 → res_lo.x[i]
   上界: min c·x, c[i]=-1, 其他=0 → res_hi.x[i]

4. 报告: {ing_id: (feasible_min, feasible_max)}
```

### 8.4 当 Bounds 全是 [0, 1]

oat milk 只有 `mass_balance` 一个 hard 约束（$\sum x_i = 1$），对单独变量无约束力——任何 $x_i$ 理论上都可以从 0 到 1。此时 bounds 反映的是"仅凭物理定律的可能范围"，而非"营养学上的合理范围"。要获得 tighter bounds，需要激活 slack budget 模式。

---

## 9. Slack Budget 机制

### 9.1 问题

默认的 `feasible_region: hard_constraints_only` 只用 hard 约束定义可行域，bounds 很宽。如何获得更紧的 bounds？

### 9.2 机制

`feasible_region: explicit_slack_budget` 将 soft 约束按 budget 收紧后纳入可行域：

```yaml
solver:
  bounds:
    backend: highs_lp
    feasible_region: explicit_slack_budget
    slack_budgets:
      label_fit: 5.0    # 约束 ID → 允许的松弛量上限
```

**数学变换**：

```
原始 soft:  A·x + s ≥ lo, s ≥ 0  (允许无限松弛)
                 ↓ budget=5.0
收紧为hard:  A·x ≥ lo - 5.0       (最多违反 5 单位)
```

### 9.3 Budget 如何选择——营养学依据

| Budget | 含义 | 适用场景 |
|--------|------|----------|
| 0 | 营养素必须严格匹配观测区间 | 高置信度数据库 + 精确标签 |
| 5-10 | 允许微量偏差 | 常规情况（数据库变异 + 标签 rounding） |
| 20+ | 允许较大偏差 | 配料 fuzzy match + 标签可能有误 |

选择依据：

1. **数据库精度**：SR Legacy 是实验室均值，实际原料有 ±10-15% 生物变异
2. **标签 rounding**：FDA rounding 规则导致标签值与真实值可能出现跳跃
3. **配料映射质量**：fuzzy match (confidence < 0.95) → 需要更大 budget

### 9.4 求解器独立性

Point Solver 和 Bounds Solver **完全独立**——两者读取同一个 CompiledProblem，但：

- Point 读取 **全部** 约束（hard + soft），运行 slack-QP
- Bounds 读取 **仅 hard** 约束（或 budget 收紧后的），运行 LP

```
CompiledProblem (同一个 IR)
      │
      ├──→ Point  → fractions {ing_id: float}
      │             objective_value (Σ w·s²)
      │
      └──→ Bounds → {ing_id: [lo, hi]}
                    每个 ingred 独立 min/max LP
```

**顺序**：代码中点估计先执行、界限后执行，但这是为了方便——两者不存在数据依赖，交换顺序不影响结果。

**独立配置**：YAML 可单独配置 point、单独配置 bounds、或两者都配置。`success` 取决于所有已配置求解器都成功。

---

## 10. FNDDS 验证方法论

### 10.1 验证逻辑

FNDDS 提供两种信息：（1）配方最终产品的营养素（模拟 Nutrition Facts 标签），（2）每种配料的真实质量分数（ground truth）。

验证只使用（1）作为输入，用（2）来评估求解精度——模拟 branded food 场景下仅凭标签信息反推配料比例。

### 10.2 模拟 Branded Food 的可见条件

| FNDDS 可用信息 | Branded Food 等效 | 是否用于求解 |
|---------------|-------------------|-------------|
| 配料描述（USDA 标准名） | 配料标签名 → IngredientMapper → USDA 标准名 | ✓ |
| 最终产品营养素 | Nutrition Facts 标签 | ✓ |
| 配料 sequence number | 标签声明顺序 | ✓ （可选，ingredient_order） |
| **配料 code** | — | ✗ branded food 没有 code |
| **配料重量/比例** | — | ✗ 这是求解目标，仅用于验证 |
| **FNDDS 内部配料→营养映射** | — | ✗ branded food 只能用 SR Legacy |

### 10.3 数据清洗步骤

1. **排除 fortificant**：代码 999xxx 或无营养成分数据的配料
2. **kJ→kcal 修正**：Atwater 4-4-9 公式检测误标的能量值
3. **排除强化营养素**：max_ingredient_value < 50% of label value → 标记为 fortified，跳过观测
4. **检查营养素完整度**：所有配料必须有该营养素的数据

### 10.4 200-recipe 验证集

- 来源：FNDDS 中随机抽样的 200 个多配料配方
- 剔除 NFS（Not Further Specified，配方本身是混合体）：3 个
- 可用：**197 个**
- 配料数分布：中位数 4，范围 2-16
- 含 fortificant：5 个（主要是 fortified cereals）

---

## 11. 配方的可辨识性条件

### 11.1 可辨识的充分条件

要唯一确定 n 种配料的分数，需要 **n 个线性独立的营养化学维度**。

oat milk（5 配料, 10 观测）→ 高度超定，MAE = 0.24pp ✓

Milk NFS（4 种乳品, 仅 1 个有效区分维度——脂肪含量）→ 欠定，MAE = 19pp ✗

### 11.2 决定辨识度的因素

| 因素 | 有利 | 不利 |
|------|------|------|
| 配料多样性 | 不同食材类别混合 | 同类食材混合（如多种乳品、多种谷物） |
| 营养素覆盖 | 脂肪、蛋白、碳水、矿物质均有差异 | 营养素含量相似 |
| 标签营养素数量 | 13-15 种 FDA label 营养素 | 仅有基础宏量营养素 |
| 数据库质量 | 精确匹配，confidence ≥ 0.95 | Fuzzy match，confidence < 0.8 |

### 11.3 方法的适用边界

| 适用 ✓ | 不适用 ✗ |
|---------|----------|
| 配方化学差异大（面包、酱料、饮料） | 配方营养相似（混合乳品、混合果汁） |
| 标签营养素 ≥ 配料数 - 1 | 极简标签 + 多种配料 |
| SR Legacy 覆盖配料 | 新型添加剂、强化剂 |
| 物理混合为主的工艺 | 深度发酵、化学改性 |

---

## 12. 全流程 Pipeline

### 12.1 输入（YAML 配置）

```yaml
schema_version: "1.0-draft"
problem_id: "oat_milk_fdc2705412"

basis:
  ingredient_mass: input_fraction       # 求解目标
  nutrient_amount: per_100g_finished_product

ingredients:                            # 配料列表（模拟标签）
  - id: water
    name: Water
    declaration_group: main
  - id: salt
    name: Salt, table
    declaration_group: two_percent_or_less

composition:                            # 每 100g 配料的营养成分
  source: inline                        # （来自 SR Legacy 查找）
  nutrients:
    - { id: energy_kcal, unit: kcal }
  values:
    water: [0.0]
    salt:  [0.0]

observations:                           # Nutrition Facts 标签
  - nutrient: energy_kcal
    unit: kcal
    interval: [40.5, 49.5]             # ±10% label value

constraints:                            # 约束声明
  - { id: mass_balance, type: mass_balance, mode: hard }
  - { id: label_fit, type: nutrient_interval, mode: soft, weight: 10.0 }

solver:                                 # 求解器配置
  point:  { backend: scipy_slsqp }
  bounds: { backend: highs_lp }
```

### 12.2 输出（Result Dict）

```json
{
  "success": true,
  "status": "optimal",
  "problem_id": "oat_milk_fdc2705412",
  "fractions": {
    "water": 0.9031,
    "oats": 0.0540,
    "canola_oil": 0.0198,
    "sugar": 0.0219,
    "salt": 0.0012
  },
  "bounds": {
    "water": [0.0, 1.0],
    "oats": [0.0, 1.0]
  },
  "diagnostics": {
    "point": {
      "objective_value": 2.2e-15,
      "status": "optimal",
      "solve_time_s": 0.17
    }
  },
  "manifest": {
    "resolved_config": { "sha256": "..." },
    "resources": [...],
    "git": { "commit": "..." }
  }
}
```

### 12.3 CLI 接口

```bash
nusol validate problem.yaml   # 验证 YAML 格式
nusol resolve problem.yaml    # 展开 extends 继承链
nusol inspect problem.yaml    # 显示问题结构（不求解）
nusol solve problem.yaml      # 完整求解
nusol solve --dry-run problem.yaml  # 编译但不求解（查看 IR 结构）
nusol solve -o result.json problem.yaml  # 输出 JSON
```

---

## 附录 A：关键术语表

| 术语 | 英文 | 说明 |
|------|------|------|
| 线性混合模型 | Linear Mixing Model | $\text{Nutrient}_{final} = \sum x_i \cdot \text{Nutrient}_i$ |
| 松弛变量 | Slack Variable | 允许约束被有限违反的辅助变量 |
| 二次惩罚 | Quadratic Penalty | $\min \sum w \cdot s^2$，边际成本递增 |
| 可行域 | Feasible Region | 所有满足约束的解的集合 |
| 点估计 | Point Estimate | 最优单点解 |
| 界限分析 | Bounds Analysis | 每个变量的可行 [min, max] |
| 强化剂 | Fortificant | 纯营养素添加剂（如 Vitamin D as ingredient） |
| 中间表示 | IR (Intermediate Representation) | 求解器无关的约束描述 |
| 配料指纹 | Ingredient Fingerprint | 配料在多维营养空间中的特征向量 |

## 附录 B：参考文献

- USDA FoodData Central: https://fdc.nal.usda.gov/
- FDA Nutrition Facts Label (21 CFR 101.9)
- FDA Nutrition Facts Label Compliance (FDA Food Labeling Guide)
- Atwater General Factors (4-4-9 kcal/g for protein, carbohydrate, fat)
- SciPy SLSQP: https://docs.scipy.org/doc/scipy/reference/optimize.minimize-slsqp.html
- HiGHS LP Solver: https://highs.dev/
