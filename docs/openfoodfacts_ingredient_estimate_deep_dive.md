# Open Food Facts Ingredient Amount Estimate 深度技术调研

## ——与 NuSol-T Framework 的对比分析

---

## 执行摘要

Open Food Facts (OFF) 确实已经实现了配料比例估算功能，但其技术路线、设计目标和精度水平与您的 **NuSol-T** framework 存在**本质差异**。OFF 采用两套并行模型：一套是运行在其后端 **Product Opener** 中的简单启发式模型（仅基于配料顺序做 min/max 范围估计），另一套是实验性的 **Recipe Estimator**（基于 CIQUAL 营养数据的线性优化）。根据 OFF 自有的 metrics 框架，Recipe Estimator 在 1,000 个测试产品上的平均绝对差约为 **23.7 个百分点**（all-CIQUAL 子集约 12.3 pp），而 NuSol-T 在 3,734 个 FNDDS 食谱上的中位 MAE 仅为 **1.74 pp**——两者相差约 **一个数量级**。OFF 的估算主要服务于 **Nutri-Score 水果/蔬菜/坚果百分比计算**和粗略的配料可视化，而 NuSol-T 是为**高精度配方逆向工程**设计的学术级方法。

---

## 1. Open Food Facts 的两套配料估算模型

OFF 在配料比例估算上采用了**双轨策略**：一套是已在生产环境运行多年的简单模型，另一套是正在开发中的基于营养优化的模型。

### 1.1 Product Opener Model（生产环境默认模型）

这是当前所有 OFF 产品页面上显示的 `percent_estimate` 字段的来源。该模型运行在 **Product Opener**（OFF 的 Perl 后端）中，其算法被官方文档描述为 **"simplistic"**（过于简化的）。[^135^] 具体而言，它仅基于配料标签上的**顺序信息**和**已知百分比**来计算每个配料的可行范围：

**核心逻辑**：对于配料列表中的每一项，根据其排序位置和已知信息推导 min/max 边界。例如，若某产品有 4 个配料且无已知百分比，则第一个配料的范围是 (25%, 100%)，第二个是 (0%, 50%)，第三个是 (0%, 33%)，第四个是 (0%, 25%)——基于"前面所有配料之和不能超过 100%"的朴素推理。然后模型**取第一个配料范围的中点**，再从剩余量中依次向下分配。[^135^]

该模型**完全不使用营养成分数据**，仅依赖标签法规中的顺序规则。它的设计目的不是精确估算配方，而是为 Nutri-Score 计算提供水果/蔬菜/坚果的粗略百分比，以及在产品页面上给用户一个大致的配料占比概念。

### 1.2 Recipe Estimator（实验性营养优化模型）

这是 OFF 社区在 2023-2026 年间开发的**新模型**，目前作为独立服务部署在 `recipe-estimator.openfoodfacts.org`，尚未完全替代 Product Opener Model。[^153^] 该模型才是与 NuSol-T 真正可比的技术方案。

**Recipe Estimator 的工作流程**（基于其开源代码和文档）[^195^][^198^]：

**Step 1 — 获取配料营养数据**：每个配料通过其 `ciqual_food_code`（法国 CIQUAL 数据库的食物编码）获取营养谱。若配料无 CIQUAL 编码，则尝试通过 OFF 的 `ingredients.json` 分类体系查找代理编码。营养数据仅使用带有 `_100g` 后缀的"主要"营养素。[^195^]

**Step 2 — 确定可用营养素**：只有**所有配料都含有**的营养素才能参与计算。Energy 被排除（因为它是组合值）。[^195^]

**Step 3 — 营养素加权**：可为特定营养素设置权重。若未设置，默认权重为 1。[^195^]

**Step 4 — 优化求解**：系统支持**四种求解器**：

| 求解器 | 类型 | 特点 |
|--------|------|------|
| **CVXPY** (默认) | 凸优化 | 最新添加，支持复杂约束，代码 308 行 [^198^] |
| **GLOP** | 线性规划 (LP) | Google OR-Tools 的 LP 求解器 [^195^] |
| **SciPy** | 非线性优化 | 使用 SciPy 的优化模块 [^195^] |
| **NNLS** | 非负最小二乘 | 快速但约束能力有限 [^197^] |

**Step 5 — 返回结果**：为每个配料添加 `percent_estimate`（估算百分比）和 `quantity_estimate`（制作 100g 产品所需量），并估算 `evaporation`（加工中的水分损失）。[^195^]

---

## 2. Recipe Estimator (CVXPY) 的核心算法拆解

以最新的 CVXPY 求解器为例，其核心代码 reveals 了以下关键技术细节：[^198^]

### 2.1 约束系统

Recipe Estimator 的约束构建是一个**递归过程**，处理嵌套的配料结构（复合配料）：

**约束 1：已知百分比的范围约束**

若某配料在标签上标注了百分比（如 "tomatoes 41%"），则根据四舍五入规则建立范围：
- 若百分比为整数（如 41%），假设标准四舍五入，范围为 **(40.5%, 41.5%)**
- 若百分比含小数（如 41.5%），假设精确到 0.5%，范围为 **(41.25%, 41.75%)**

这通过 `get_ingredient_range()` 函数实现。[^198^]

**约束 2：配料顺序约束**

```
sum(previous_ingredient_mixing_bowl_weight) >= sum(my_mixing_bowl_weight)
```

即前一个配料的混合碗重量（考虑水分损失后）必须大于等于后一个配料的。[^198^]

**约束 3：复合配料的水分损失约束**

对于复合配料（如 "chocolate 24.9% (sugar, cocoa paste, cocoa butter...)"），模型引入**预混合碗水分损失变量** `pre_mixing_bowl_water_loss`，并约束其不超过子配料总含水量：

```
pre_mixing_bowl_water_loss <= sum(child_ingredient_quantity × water_proportion)
```

**约束 4：总量约束**

```
sum(ingredient_quantities) - (ingredient_quantities @ water_proportions) <= 100
```

即所有配料的总量减去最大可能水分损失不能超过 100g。[^198^]

### 2.2 目标函数

Recipe Estimator 的优化目标是一个**组合目标函数**，按优先级依次为：

**主目标：营养匹配**

```python
residual = ingredients_nutrients @ ingredient_quantities - product_nutrients
nutrient_variance = sum(weightings @ square(residual))
```

最小化加权营养残差的平方和——这与 NuSol-T 的 slack-variable QP 在数学形式上是同类的，但 OFF 使用**纯二次惩罚**（无 hard/soft 约束分层），且营养素权重由系统预设而非统一处理。[^198^]

**备选目标：简单幂级数估计（Fallback）**

当太多配料缺少 CIQUAL 营养数据时（`percent_unknown >= 10%`），系统放弃营养匹配，转而使用基于**逆幂级数**的简单估计：

```python
# estimate_percentages 函数
estimate = a * (n + 1.0) ** POWER  # POWER = -1.7
```

其中 `a` 通过使所有估计值之和为 100% 来归一化。这个幂律分布旨在模拟真实配方中配料比例随排名递减的模式。[^198^]

**蒸发惩罚项**

```python
evaporation_cost = 0.01 * square(sum(ingredient_quantities) - 100)
```

轻微惩罚总配料量偏离 100g 的情况，将过量解释为水分蒸发。[^198^]

### 2.3 求解策略

Recipe Estimator 的求解流程如下：[^198^]

1. **首先尝试营养匹配法**：构建以营养方差最小化为目标的凸优化问题，用 CVXPY 求解
2. **检查最优性**：若 `status == OPTIMAL` 且 `nutrient_variance < 2500`，接受结果
3. **Fallback 到简单估计**：若营养法失败或方差过大，改用幂级数估计作为目标函数重新求解
4. **设置百分比**：根据求解结果，为每个配料计算 `percent_estimate`（考虑水分损失后）和 `quantity_estimate`（原始量）

---

## 3. OFF Recipe Estimator vs NuSol-T：全维度对比

### 3.1 技术架构对比

| 维度 | OFF Recipe Estimator | NuSol-T Framework |
|------|---------------------|-------------------|
| **核心求解方法** | CVXPY 凸优化 / GLOP LP / SciPy 非线性 | Slack-Variable QP (SLSQP) + LP Bounds (HiGHS) |
| **约束分层** | 无明确分层，所有约束为 hard | P0 硬约束 (质量平衡) + P1 硬约束 (顺序+2%规则) + P2 软约束 (营养区间) |
| **营养数据源** | CIQUAL (法国, 3,484 食物, 67 成分) | USDA SR Legacy + Foundation Foods (300K+ 食物, 50-100+ 营养素) |
| **观察营养素** | 未明确列出，"main nutrients" | **13 种 FDA 标签营养素** (Energy, Protein, Fat, Sat.Fat, Carb, Fiber, Sugars, Cholesterol, Sodium, Calcium, Iron, Potassium, VitD) |
| **Fallback 策略** | 营养法失败 → 幂级数估计 | 无 fallback，通过迭代调参 (max_iter, fortificant filtering, yield factor) 达到 99.5% 成功率 |
| **水分/蒸发处理** | 显式建模 pre-mixing bowl water loss | Yield factor via energy conservation (raw→cooked) |
| **多求解器支持** | CVXPY, GLOP, SciPy, NNLS, Simple | SLSQP (QP) + HiGHS (LP) |
| **随机重启** | 无 | **10 次随机重启**避免局部最优 |

### 3.2 验证结果对比

这是最关键的差异维度：

| 指标 | OFF Recipe Estimator | NuSol-T |
|------|---------------------|---------|
| **验证数据集** | ~1,000 个有已知百分比的包装食品 [^135^] | 3,734 个 FNDDS 食谱（已知 ground truth） |
| **成功率** | 未明确报告（需所有配料匹配 CIQUAL） | **94.9%** (auto) / **99.5%** (post-hoc recovery) |
| **平均绝对差** | 1000 产品集：**23.71 pp**；all-CIQUAL 子集 (128 产品)：**12.33 pp** [^135^] | 中位 MAE：**1.74 pp** (auto) / **0.9 pp** (recovery) |
| **74.3% 食谱 MAE** | 未报告 | **< 3 pp** |
| **90.0% 食谱 MAE** | 未报告 | **< 5 pp** |

**数量级差距**：OFF Recipe Estimator 的 all-CIQUAL 平均差 (12.33 pp) 是 NuSol-T 中位 MAE (1.74 pp) 的 **7 倍**。即使考虑到 OFF 处理的是更嘈杂的真实包装食品数据（vs FNDDS 的清洁调查数据），这个差距仍然显著。

### 3.3 设计目标与应用场景差异

| 维度 | OFF Recipe Estimator | NuSol-T |
|------|---------------------|---------|
| **首要设计目标** | 为 Nutri-Score 提供水果/蔬菜/坚果百分比 [^143^]；产品页面配料可视化 | 从营养标签精确逆向推导配料质量分数 |
| **处理对象** | 真实包装食品（OCR 噪声、配料解析错误、缺失数据） | 标准化的调查食谱（FNDDS） |
| **输出精度要求** | 粗略估计（用于评分和可视化） | 高精度（用于营养扩展、环境评估、配方逆向） |
| **嵌套配料支持** | 完整支持（递归处理复合配料） | 当前仅处理扁平配料列表 |
| **已知百分比利用** | 充分利用标签上标注的百分比作为强约束 | FNDDS 无已知百分比，纯从营养推断 |

---

## 4. 为什么 OFF 已经有了 estimate，但 NuSol-T 仍有独特价值

### 4.1 精度水平的根本差异

OFF Recipe Estimator 的 **12-24 pp 平均差**意味着对于中位产品，其配料比例估计可能偏离真实值达 12-24 克/100 克产品。这个精度对于 Nutri-Score 的水果/蔬菜/坚果百分比计算（只需要区分 <40%、40-60%、>60% 几个档位）是足够的，但对于以下应用远远不够：

- **营养扩展**（从 13 种标签营养素扩展到 150+ 种完整营养素）需要更高精度的配料比例
- **环境足迹计算**（碳排放、水足迹对配料比例误差敏感）
- **竞品配方逆向工程**（食品工业需要更精确的估算）

NuSol-T 的 **1.74 pp 中位 MAE** 比 OFF 精确约 **7-14 倍**，使其能够支撑上述高精度应用场景。

### 4.2 技术路线的互补性

两套系统在技术路线上形成**互补**而非替代关系：

| OFF Recipe Estimator 的优势 | NuSol-T 的优势 |
|---------------------------|---------------|
| 处理**真实世界噪声**（OCR 错误、配料解析失败、缺失营养数据） | 处理**标准化数据**时达到学术级精度 |
| 支持**嵌套配料**（复合配料递归展开） | 更**完整的约束系统**（硬/软约束分层 + 2% 规则） |
| 利用标签上**已知的百分比**作为强先验 | 更多**观察营养素维度**（13 种 vs "main nutrients"） |
| 覆盖**全球 300 万+产品**的广泛适用性 | **99.5% 成功率**的可靠性 |
| **多求解器**灵活切换（CVXPY/GLOP/SciPy/NNLS） | **Yield factor 校正**（raw→cooked energy conservation） |

### 4.3 实际集成建议

对于您的 NuSol-T framework，可以从 OFF Recipe Estimator 中借鉴以下技术点：

**可借鉴的技术点**：

1. **已知百分比的利用**：当处理真实包装食品时（而非 FNDDS），标签上常有 "tomatoes 41%" 这类已知百分比。NuSol-T 当前未利用这一强先验信息。可参考 OFF 的 `get_ingredient_range()` 逻辑，将已知百分比转化为 ±0.5% 或 ±0.25% 的 hard 约束。

2. **嵌套配料的递归处理**：OFF 的 `add_ingredient_constraints()` 递归函数展示了如何处理复合配料（如 "chocolate (sugar, cocoa, cocoa butter)"）。这对将 NuSol-T 扩展到真实包装食品至关重要。

3. **水分蒸发的显式建模**：OFF 的 `pre_mixing_bowl_water_loss` 变量和蒸发惩罚项提供了一种替代 NuSol-T yield factor 的水分处理方法。两种方法可以对比测试。

4. **多求解器策略**：OFF 的 CVXPY/GLOP/SciPy/NNLS 多求解器设计可以作为 NuSol-T 求解器选择的参考。特别是 CVXPY 作为 convex optimization DSL，可能比直接调用 SLSQP 更具可扩展性。

**NuSol-T 相对于 OFF 的核心优势应继续保持**：

- 13 种营养素的完整观察维度
- Hard/soft 约束的明确分层
- 10 次随机重启避免局部最优
- Yield factor 的能量守恒校正
- 3,734 食谱的大规模验证

---

## 5. 关键数据与指标汇总

### 5.1 Open Food Facts Recipe Estimator 技术指标

| 指标 | 值 | 来源 |
|------|-----|------|
| GitHub Stars | 12 | [^153^] |
| 主要求解器 | CVXPY (默认), GLOP, SciPy, NNLS | [^195^] |
| 营养数据库 | CIQUAL 2025 (3,484 食物, 67 成分) | [^178^][^148^] |
| 代码语言 | Python 87.6%, TypeScript 10.3% | [^153^] |
| CVXPY solver 代码行数 | 308 行 (258 loc) | [^198^] |
| 生产部署 | recipe-estimator.openfoodfacts.org | [^153^] |

### 5.2 验证数据对比

| 来源 | 测试集大小 | 平均差 (pp) | 备注 |
|------|----------|------------|------|
| OFF Recipe Estimator (全部 1000 产品) | 1,000 | **23.71** | 含未匹配 CIQUAL 的配料 [^135^] |
| OFF Recipe Estimator (all-CIQUAL 子集) | 128 | **12.33** | 所有配料均匹配 CIQUAL [^135^] |
| OFF Product Opener (基准模型) | 1,000 | 未报告 | 简单启发式 [^135^] |
| **NuSol-T (auto pipeline)** | **3,734** | **1.74 (中位)** | 74.3% < 3pp, 90.0% < 5pp |
| **NuSol-T (recovery)** | **3,734** | **0.9 (中位)** | 99.5% 成功率 |

---

## 6. 结论

Open Food Facts 的 ingredient amount estimate 系统是一个**面向实际应用的、容忍噪声的粗略估算工具**，其 Recipe Estimator 在最佳情况下（all-CIQUAL 子集）的平均误差约为 **12 个百分点**。这一精度对于 Nutri-Score 评分和产品页面可视化是足够的，但无法满足高精度配方逆向工程的需求。

您的 **NuSol-T framework** 在以下维度上显著超越 OFF Recipe Estimator：

- **精度**：中位 MAE 1.74 pp vs 12-24 pp（**7-14 倍提升**）
- **约束系统**：完整的三层约束层级 vs 无分层约束
- **观察维度**：13 种 FDA 标签营养素 vs 未明确数量的"main nutrients"
- **验证规模**：3,734 食谱 vs ~1,000 产品
- **成功率**：99.5% vs 未报告（依赖所有配料匹配 CIQUAL）

两者是**互补关系**：OFF 擅长处理真实世界的噪声和嵌套配料结构，NuSol-T 擅长在标准化数据上实现学术级精度。将 OFF 的已知百分比利用、嵌套配料递归处理和多求解器策略融入 NuSol-T，是下一步值得探索的融合方向。
