# NuSol-T 项目总体规划书  
## 面向食物营养成分分析的可扩展统一计算框架

## 1. 项目名称

**NuSol-T: An Extensible Unified Computational Framework for Food Nutrient Composition Analysis**

中文名称：  
**NuSol-T：面向食物营养成分分析的可扩展统一计算框架**

## 2. 项目背景

饮食是影响人类健康的重要可调节因素。准确评估个体或人群的饮食暴露，对于理解慢性疾病风险、肠道微生物组组成、代谢状态以及个体对膳食干预的反应具有重要意义。然而，当前的膳食评估方法仍然主要依赖食物代码、标准营养素汇总或人工整理的膳食记录，难以充分反映实际摄入食物的配料组成、加工特征和更细粒度的营养暴露。

这一问题在包装食品和高度加工食品中尤其突出。商业包装食品通常含有复杂的配料组合，包括精制谷物、植物油、添加糖、膳食纤维来源、乳化剂、稳定剂、香精、色素、甜味剂和其他添加成分。很多与健康相关的饮食暴露，例如不同来源的纤维、植物性配料、糖类、脂肪酸、矿物质、食品添加剂、加工相关成分以及未来可能扩展的多酚、糖类组分和其他 bioactives，往往更适合在配料层面进行估计，而不是只在 broad food category 或单一 food code 层面进行分析。

在美国，包装食品标签通常提供两类重要信息：Nutrition Facts panel 和 ingredient list。Nutrition Facts panel 提供能量、脂肪、碳水化合物、糖、蛋白质、钠等标签营养素；ingredient list 则按照配料重量优势从高到低列出配料。配料顺序为推断配料组成提供了重要的结构性约束。然而，包装食品标签通常不提供每个配料的真实克重或百分比。与此同时，Nutrition Facts 上的数值经过 serving size 换算、四舍五入和法规允许的合规容差处理，不能被视为精确真值。因此，从营养标签和配料表推断配料组成与完整营养成分，本质上是一个欠定、带不确定性、且依赖数据库映射和约束设定的计算问题。

现有研究已经尝试使用线性规划或机器学习方法从配料和营养标签估计食品营养组成或配料比例。例如，已有方法将配料表中的配料映射到 food composition table，并通过线性规划估计与包装标签 Big7 营养素最接近的配料比例；该类方法也指出，配料匹配质量、加工造成的水分变化、约束冲突和营养素容差会显著影响可行性和准确性。相关研究还提出使用 processing water 作为虚拟成分，以处理干燥、烹饪、冷冻等加工过程造成的配料营养组成变化。 另有基于 USDA Global Branded Food Products Database 的机器学习研究尝试根据 ingredient information 预测标签营养素，但这类方法往往更偏向预测模型，难以直接解释配料比例、约束来源和推断不确定性。

因此，本项目拟开发 **NuSol-T**，一个面向食物营养成分分析的可扩展统一计算框架。NuSol-T 不仅用于估计配料组成，还用于将有限的营养标签信息扩展为更完整的营养成分画像。该框架将整合食品成分数据库、配料表解析、配料映射、法规感知标签区间、forward recipe nutrient calculation、inverse constrained solving、uncertainty estimation 和 trust reporting，形成一个可验证、可解释、可复现、可扩展的计算体系。

## 3. 项目总体目标

本项目的总体目标是开发并验证 NuSol-T，一个面向食物营养成分分析的可扩展统一计算框架。该框架将首先在 FNDDS 上进行验证，以评估可信约束求解系统是否能够在已知 recipe calculation 逻辑下恢复合理的配料组成范围和营养计算结果；随后将该框架应用于 USDA Branded Food Database，基于真实包装食品的营养标签和配料表，推断配料组成范围，并进一步估计扩展的完整营养成分。

项目的核心目标可以概括为：

1. 建立一个统一的食物营养计算框架，用于连接包装食品标签、配料表、食品成分数据库和营养推断模型。
2. 建立一个可信约束求解系统，将质量守恒、配料顺序、标签营养区间、食品科学约束和数据库先验整合到同一优化框架中。
3. 使用 FNDDS 作为受控验证体系，验证 NuSol-T 的 forward calculation、inverse reconstruction 和 labelized simulation 能力。
4. 将通过验证的 NuSol-T 框架应用于 USDA Branded Food Database，对真实包装食品进行配料组成推断和完整营养成分扩展估计。
5. 输出不仅包括点估计，还包括不确定性区间、数据 provenance、约束冲突、模型警告和可信等级。

## 4. NuSol-T 的框架定位

NuSol-T 应被定义为：

> 一个面向食物营养成分分析的可扩展统一计算框架，用于在食品标签、配料表、食品成分数据库、法规规则和食品科学约束的基础上，进行配料组成推断、营养成分计算、完整营养画像扩展和可信报告生成。

NuSol-T 不是单纯的配料比例优化器，也不是一个简单的机器学习预测模型。它的核心是将 **forward nutrition calculation** 与 **inverse ingredient inference** 统一在一个可配置、可扩展、可解释的系统中。

具体而言：

```text id="i5qdzs"
Forward model:
给定配料比例、配料营养组成和加工参数，
计算最终食品的营养成分。

Inverse model:
给定营养标签、配料表、食品成分数据库和约束条件，
推断可行的配料组成范围和可能的加工参数。

Trust reporting:
报告估计结果、不确定性、数据来源、约束冲突和可信等级。
```

因此，NuSol-T 的核心不是声称恢复真实商业配方，而是：

> 在给定标签、配料、数据库和约束条件下，估计一组可信的配料组成范围，并用该范围推断更完整的营养成分，同时明确说明结果的证据来源、适用范围和不确定性。

### 4.1 核心数学问题：用先验约束欠定逆问题

NuSol-T 要解决的核心问题不是单纯求解一组营养方程，而是在欠定的配料可行空间中，利用有证据的食品学先验选择合理解，并量化仍然无法消除的不确定性。

基础线性观测模型为：

\[
y \approx A^\top x
\]

其中，\(x\) 是待估计的原料质量比例，\(A\) 是原料—营养组成矩阵，\(y\) 是成品营养观测。实际场景中，原料变量通常多于独立营养观测；不同原料还可能具有相似的营养组成。因此，即使质量守恒和标签区间都成立，满足观测的 \(x\) 通常仍不唯一。

先验知识在系统中承担三种不同职责：

1. **硬约束排除不可能解**：质量守恒、非负性、配料声明顺序、2% rule、已声明百分比和必须成立的法规或质量闭合关系。
2. **软约束在可行解中排序**：典型类别比例、原料组总量、配方中心距离、共现结构、来源平衡和 anti-extreme 等食品学知识。
3. **概率先验表达剩余不确定性**：食品类别条件分布、原料存在概率、品牌或人群差异、数据库值误差和加工参数不确定性。

确定性或 MAP 阶段可统一写为：

\[
\hat{x}=\arg\min_x\left[
L_{obs}(A^\top x,y)+\sum_k\lambda_k P_k(x)
\right]
\]

其中 \(P_k\) 是具有明确食品学含义的先验 penalty，\(\lambda_k\) 表示经过校准的证据强度。Bayesian 阶段则写为：

\[
p(x\mid y,A,c)\propto p(y\mid x,A)\,p(x\mid c)
\]

其中 \(c\) 表示食品类别、加工方式、品牌或其他分层条件。

先验的目标不是人为制造一个唯一解。每个先验必须具有：

- 明确的数学定义、适用范围和失效条件；
- 可追溯的证据来源、版本和证据等级；
- 可校准的参数与权重；
- 可单独关闭、替换并参与消融实验的实现；
- 与观测冲突时可报告的 residual、slack 或 posterior conflict；
- 不得将食品学假设伪装成由数据唯一确定的事实。

因此，系统输出必须区分：

- hard constraints 定义的数学可行边界；
- soft priors 选择的点估计或 MAP 解；
- ensemble quantile 或 Bayesian credible interval；
- 先验敏感性、可辨识性和仍然存在的多解结构。

先验能力按以下层级演进：

| 层级 | 能力 | 典型实现 |
|---|---|---|
| Level 1 | 确定性结构先验 | 质量守恒、声明顺序、2% rule、变量边界、线性关系 |
| Level 2 | 正则化先验 | 目标区间、类别总量、配方中心距离、平滑或 anti-extreme penalty |
| Level 3 | 经验分布先验 | Beta/Logit-normal 原料比例、Dirichlet 原料组、共现与存在概率 |
| Level 4 | Bayesian/分层模型 | 类别、品牌、地区共享信息，数据库和加工参数不确定性，posterior sampling |

Level 1-2 应优先通过统一 linear/quadratic IR 和 MAP backend 实现；Level 3 需要经验数据学习与校准；Level 4 使用独立 probabilistic backend，但继续复用 YAML、领域模型、forward model、provenance 和结果协议。

## 5. 科学意义与创新性

本项目的科学意义主要体现在以下几个方面。

第一，NuSol-T 可以推动膳食评估从 food-code level 向 ingredient-informed nutrient analysis 发展。传统营养数据库通常将多配料食品作为单一食品条目处理，而 NuSol-T 试图将其拆解到配料层面，从而更好地估计食品来源、加工成分和更细粒度的营养暴露。

第二，NuSol-T 将营养标签值视为不确定观测值，而不是精确真值。Nutrition Facts panel 上的数值经过四舍五入和合规规则处理，不能简单作为等式约束。NuSol-T 将标签值转化为法规感知的目标区间，并在优化过程中使用 interval fit 和 slack 机制，从而避免伪精确推断。

第三，NuSol-T 将 FNDDS 用作受控验证体系，而不是将其误认为商业配方 gold standard。FNDDS 包含 FNDDS nutrient values、moisture adjustment、ingredients、ingredient weights、retention code 和 ingredient nutrient values 等字段，可用于验证 forward recipe calculation 和 inverse reconstruction。FNDDS 数据集中，FNDDSNutVal 提供每 100g edible portion 的能量和 64 个营养素，MoistAdjust 提供 moisture change，FNDDSIngred 提供 ingredient code、retention code 和 ingredient weight，IngredNutVal 提供 ingredient nutrient values 及其来源和 derivation code。 这些结构使 FNDDS 非常适合作为 NuSol-T 的内部验证资源。

第四，NuSol-T 将 USDA Branded Food Database 定位为真实包装食品应用场景，而不是 ground-truth formulation source。已有项目设计也指出，USDA Branded Foods 含有品牌食品记录、营养值和配料表，适合作为真实包装食品标签来源；但它通常不提供真实配料用量，因此不适合作为配料比例准确性的 gold standard。

第五，NuSol-T 强调可解释性和可信输出。最终输出不仅是 ingredient percentage table，而是包含配料范围、营养估计区间、约束 slack、数据来源、mapping confidence 和 trust grade 的 TrustReport。这比黑箱机器学习预测或单点优化结果更适合科学研究和营养信息学应用。

## 6. 总体研究设计

本项目分为两个主要研究阶段：

```text id="4jthtw"
Stage 1: FNDDS validation
使用 FNDDS 验证 NuSol-T 的可信约束求解系统。

Stage 2: USDA Branded Food application
将经过验证的 NuSol-T 应用于 USDA Branded Food Database，
估计真实包装食品的配料组成范围和扩展完整营养成分。
```

两个阶段的逻辑关系如下：

```text id="xo52sv"
FNDDS controlled validation
        ↓
验证 forward nutrition calculation
验证 inverse ingredient reconstruction
验证 labelized simulation 和 uncertainty reporting
        ↓
Calibrated NuSol-T framework
        ↓
USDA Branded Food Database application
        ↓
真实包装食品配料组成推断
扩展完整营养成分估计
TrustReport 生成
```

## 7. NuSol-T 系统架构

NuSol-T 采用模块化、配置驱动的系统架构。核心模块包括：

```text id="nftes7"
1. Data Adapter Layer
2. Canonical Nutrition Model Layer
3. Ingredient Parsing and Mapping Layer
4. Forward Nutrition Calculation Layer
5. Constraint and Prior Layer
6. Inverse Solver Layer
7. Validation Layer
8. Trust and Reporting Layer
9. Application Interface Layer
```

### 7.1 Data Adapter Layer

该层负责读取和标准化不同数据源，包括：

```text id="vfchde"
FNDDS
USDA Branded Food Database
SR Legacy
Foundation Foods
custom ingredient composition tables
external validation datasets
```

在 FNDDS 阶段，Data Adapter 读取 recipe ingredient weights、moisture adjustment、retention codes、ingredient nutrient values 和 final nutrient values。

在 Branded Food 阶段，Data Adapter 读取 product description、brand information、serving size、Nutrition Facts values、ingredient list、branded category、FDC ID、UPC/GTIN 和 publication / modified metadata。

### 7.2 Canonical Nutrition Model Layer

该层建立统一营养素代码和单位体系。例如：

```text id="qkf47m"
energy_kcal
total_fat_g
saturated_fat_g
carbohydrate_g
dietary_fiber_g
total_sugars_g
added_sugars_g
protein_g
sodium_mg
cholesterol_mg
water_g
ash_g
calcium_mg
iron_mg
potassium_mg
fatty_acid_profile
vitamins
```

该层负责：

```text id="r5nbci"
营养素名称标准化
单位转换
per serving 到 per 100g 转换
标签营养素到内部 nutrient code 映射
缺失值处理
nutrient provenance 保留
```

### 7.3 Ingredient Parsing and Mapping Layer

该层将原始配料表解析为结构化 IngredientTree。

需要处理：

```text id="i20s1f"
配料顺序
compound ingredients
parenthetical sub-ingredients
contains 2% or less
and/or oils
seasoning blends
natural flavor
spices
colors
preservatives
processing aids
```

解析后的配料需要映射到食品成分数据库中的 candidate records。已有研究设计指出，配料解析和配料映射是 ingredient-level dietary analysis 中的两个关键任务，因为 branded-food ingredient lists 经常包含复杂的括号结构、复合配料、替代名称和加工助剂；错误映射会传播到后续营养重构和配料比例估计中。

### 7.4 Forward Nutrition Calculation Layer

Forward model 是 NuSol-T 的核心。它定义在给定配料比例和食品成分矩阵时，如何计算最终食品的营养成分。

基础模型为：

```text id="vvdnzu"
predicted_nutrient_j = Σ_i x_i × A_ij
```

其中：

```text id="87wrbj"
x_i = 第 i 个配料的质量比例
A_ij = 第 i 个配料每 100g 中第 j 个营养素含量
```

加工增强模型为：

```text id="b2yzmu"
predicted_nutrient_j =
100 / Y(x, θ) × [Σ_i x_i × A_ij × r_ij(θ) + q_j(θ)]
```

其中：

```text id="u4589f"
Y(x, θ) = final product yield
r_ij(θ) = retention factor
q_j(θ) = processing-induced addition or loss
θ = processing parameters
```

FNDDS 中已有 moisture adjustment、retention code、ingredient weight 和 ingredient nutrient values，因此可用于验证 NuSol-T 的 forward calculation engine。

### 7.5 Constraint and Prior Layer

NuSol-T 将约束分为五个层级：

```text id="w9oxxu"
P0: 不可放松数学约束
P1: 法规结构约束
P2: 标签营养区间拟合约束
P3: 食品科学软约束
P4: 统计或类别先验
```

P0 包括：

```text id="c3h9ja"
x_i ≥ 0
Σ_i x_i = 1
compound ingredient parent-child mass balance
```

P1 包括：

```text id="hc0kpz"
main ingredient descending order
2% or less upper bound
declared percentage constraints
```

P2 包括：

```text id="6xe6nm"
label nutrient interval fit
rounding-aware target intervals
compliance-aware target intervals
```

P3 包括：

```text id="e8r2le"
energy closure
water-solid balance
sodium source balance
added sugar balance
fatty acid closure
processing water or yield adjustment
```

P4 包括：

```text id="5nlxki"
category prior
ingredient position prior
ingredient co-occurrence prior
mapping confidence prior
```

### 7.6 Inverse Solver Layer

Inverse Solver 根据 ForwardNutritionModel 和约束系统，估计配料组成范围。

NuSol-T 包括三类求解器：

```text id="b9ithj"
PointSolver:
输出一个最优点估计。

BoundSolver:
对每个配料分别求可行最小值和最大值。

EnsembleSolver:
通过多初值、标签区间 bootstrap、候选映射扰动和数据库值扰动，输出不确定性分布。
```

该设计避免只依赖单点估计，因为配料组成推断通常是欠定问题。已有研究也指出，ingredient amount estimation 依赖 ingredient mapping 和 constraint setting，且问题常因多个配料组合可以产生相似的标签营养值而欠定。

### 7.7 Trust and Reporting Layer

NuSol-T 的输出是 TrustReport，而不是单纯的配料比例表。

TrustReport 包括：

```text id="w81ddg"
product metadata
data source and version
regulation profile
ingredient estimates
ingredient uncertainty intervals
expanded nutrient profile
nutrient uncertainty intervals
nutrient residuals
constraint slacks
mapping provenance
processing parameters
identifiability report
warnings
trust grade
```

可信等级可分为：

```text id="a1t15d"
A: 标签区间拟合良好，主要配料映射清晰，区间较窄，无关键冲突。
B: 大部分标签区间拟合，少量软约束冲突，主要配料估计较稳定。
C: 可提供方向性估计，但多个配料区间较宽，存在明显映射或标签不确定性。
D: 不建议解释为配方估计，仅适合作为冲突诊断。
```

## 8. YAML 配置驱动设计

NuSol-T 应采用 YAML 配置驱动。YAML 文件用于指定数据源、营养素目标、法规 profile、forward model、约束条件、solver 策略和报告格式。

配置文件建议分为三部分：

```text id="6o73tr"
forward_model
inverse_solver
reporting
```

示例：

```yaml id="89st4v"
run_id: branded_food_us_fda_v1

data:
  product_observation_source:
    type: USDA_BRANDED
    mode: download_snapshot
    version: "fixed_snapshot"
  ingredient_composition_source:
    type: SR_LEGACY
    version: "2018"
  validation_source:
    type: FNDDS
    version: "2021-2023"

forward_model:
  basis: per_100g
  nutrient_registry: usda_core_extended
  edible_weight_adjustment: true
  retention:
    enabled: false
    mode: none
  moisture:
    enabled: true
    estimate: true
    default_bounds: [-0.30, 0.30]
  normalization: finished_weight

inverse_solver:
  variables:
    ingredient_fractions: true
    moisture_change: true
  constraints:
    mass_balance:
      enabled: true
      priority: P0
      slack: false
    ingredient_order:
      enabled: true
      priority: P1
      slack: true
      weight: 1000
    two_percent_rule:
      enabled: true
      priority: P1
      slack: true
      weight: 1000
    label_interval_fit:
      enabled: true
      priority: P2
      default_weight: 10
    energy_closure:
      enabled: true
      priority: P3
      weight: 0.2
    sodium_source_balance:
      enabled: true
      priority: P3
      weight: 0.5
    category_prior:
      enabled: true
      priority: P4
      weight: 0.1
  solver:
    point_solver: scipy_trust_constr
    multi_start: 50
    compute_bounds: true
    ensemble:
      enabled: true
      n_bootstrap: 100

reporting:
  output_formats:
    - json
    - csv
    - html
  include_provenance: true
  include_constraint_slacks: true
  include_uncertainty: true
  include_warnings: true
  include_trust_grade: true
```

YAML 驱动的优势是：

```text id="y37t4b"
保证实验可复现
方便比较不同约束组合
方便进行 ablation study
方便在 FNDDS 验证和 Branded Food 应用之间切换配置
方便未来扩展法规 profile、营养素数据库和食品科学约束
```

## 9. 研究阶段一：FNDDS 验证

### 9.1 阶段目标

第一阶段使用 FNDDS 作为受控验证体系，评估 NuSol-T 的可信约束求解系统是否能够：

```text id="e89v5i"
复现 FNDDS-style forward nutrient calculation
在已知 recipe 条件下恢复合理的配料组成范围
在模拟标签不确定性下维持合理的估计性能
输出可靠的 uncertainty interval、constraint conflict report 和 trust grade
```

FNDDS 的优势在于，它同时包含最终食品营养值、配料组成、配料重量、moisture adjustment、retention code 和 ingredient nutrient values。这使其可以支持 forward calculation replication 和 inverse reconstruction。

### 9.2 FNDDS 验证子任务 1：Forward calculation replication

输入：

```text id="p8nvgo"
FNDDS ingredient weights
FNDDS ingredient nutrient values
retention codes
moisture adjustment
```

输出：

```text id="t5yl6i"
NuSol-T calculated final nutrient values
```

比较对象：

```text id="gd82lr"
FNDDSNutVal final nutrient values
```

目的：

```text id="pwjgd4"
验证 NuSol-T 的 ForwardNutritionModel 是否能复现 USDA-style recipe nutrient calculation。
```

评价指标：

```text id="et0f80"
nutrient reconstruction error
mean absolute error
median absolute error
relative error
nutrient-specific residual
food-category-specific residual
```

### 9.3 FNDDS 验证子任务 2：Inverse recipe reconstruction

输入：

```text id="3l6etu"
FNDDS final nutrient profile
FNDDS ingredient list
ingredient composition matrix
ingredient order or recipe structure
```

隐藏：

```text id="kz2uzm"
FNDDS ingredient weights
```

NuSol-T 任务：

```text id="n0bfj9"
推断 ingredient fractions
```

比较对象：

```text id="4oac6k"
FNDDS ingredient weights converted to proportions
```

目的：

```text id="ljxkwd"
评估 NuSol-T 是否能在标准化 recipe 条件下恢复合理的配料组成。
```

评价指标：

```text id="kqi1uq"
ingredient proportion MAE
top ingredient MAE
rank correlation
coverage of true ingredient proportions by estimated intervals
average interval width
solve rate
zero-slack rate
constraint conflict frequency
```

### 9.4 FNDDS 验证子任务 3：Labelized simulation

FNDDS 的 final nutrient values 是精确数据库值，而真实 Branded Food 中的 Nutrition Facts 是标签值。因此需要构建 labelized simulation。

流程：

```text id="z6ptdk"
FNDDS exact nutrient values
→ convert to serving basis
→ apply FDA-style rounding
→ create simulated Nutrition Facts label
→ convert label values back to target intervals
→ run NuSol-T inverse solver
→ compare estimated ingredient fractions with FNDDS recipe proportions
```

目的：

```text id="w0t9z5"
模拟真实包装食品标签不精确的情况，评估 NuSol-T 在 label uncertainty 下的稳健性。
```

评价指标：

```text id="7t349c"
ingredient MAE
coverage
interval width
calibration curve
nutrient residual
trust grade calibration
frequency and type of constraint slacks
```

### 9.5 FNDDS 验证子任务 4：Ablation study

为了评估不同约束的贡献，进行消融实验：

```text id="r2rab6"
G0: mass balance only
G1: G0 + ingredient order
G2: G1 + label interval fit
G3: G2 + energy closure
G4: G3 + moisture/yield adjustment
G5: G4 + sodium source balance
G6: G5 + category prior
G7: full NuSol-T model
```

评价：

```text id="kehu63"
每增加一类约束后，是否提高 ingredient reconstruction accuracy
是否降低 nutrient residual
是否提高 solve rate
是否缩小 uncertainty interval
是否改善 trust grade calibration
```

### 9.6 FNDDS 阶段预期产出

第一阶段预期产出包括：

```text id="nbsuaa"
1. FNDDS-compatible data adapter
2. ForwardNutritionModel validation results
3. Inverse reconstruction benchmark results
4. Labelized simulation benchmark results
5. Constraint ablation results
6. TrustReport calibration rules
7. 经验证的 NuSol-T 求解配置
```

## 10. 研究阶段二：USDA Branded Food Database 应用

### 10.1 阶段目标

第二阶段将经过 FNDDS 验证和校准的 NuSol-T 框架应用于 USDA Branded Food Database。

USDA Branded Foods 适合作为真实包装食品标签数据源，因为它包含品牌食品记录、品牌信息、营养值和配料表；但它不包含真实配料比例，因此不应用作配料组成 ground truth。

本阶段目标是：

```text id="m7ytai"
基于真实包装食品的 Nutrition Facts 和 ingredient list，
推断配料组成范围，
并进一步估计标签之外的扩展完整营养成分。
```

### 10.2 Branded Food 输入数据

对每个 branded food product，NuSol-T 读取：

```text id="egk6cu"
FDC ID
product description
brand owner / brand name
UPC / GTIN
serving size
serving size unit
household serving text
Nutrition Facts nutrient values
ingredient list
branded food category
publication date
modified date
```

这些信息被转换为 NuSol-T 的 `ProductObservation` 对象。

### 10.3 Branded Food 数据处理流程

#### Step 1：产品筛选

根据研究目标选择食品类别，例如：

```text id="j3q7on"
cookies and crackers
breakfast cereals
snack foods
beverages
sauces and dressings
yogurts and dairy products
plant-based products
frozen meals
processed meats
```

筛选标准包括：

```text id="y7laq3"
具有 ingredient list
具有 serving size
具有核心 Nutrition Facts nutrients
配料数量在可处理范围内
排除明显缺失或异常记录
固定 FoodData Central snapshot 以保证可复现
```

#### Step 2：配料表解析

将 ingredient string 解析为 IngredientTree：

```text id="byi5t1"
main ingredients
compound ingredients
sub-ingredients
2% or less group
and/or alternatives
low-impact ingredients
```

对于自然香精、spices、colors、processing aids 等低营养贡献或难以映射的成分，可设置 low-impact group，并在报告中标记低可信度。

#### Step 3：配料映射

将每个 parsed ingredient 映射到 ingredient composition source，例如 SR Legacy、Foundation Foods、FNDDS ingredient records 或 custom table。

输出：

```text id="kjq7fv"
selected candidate
alternative candidates
mapping confidence
nutrient-profile similarity
mapping provenance
```

已有方案指出，USDA SR Legacy 可作为 ingredient nutrient profiles 的映射目标，而 Branded Foods 可作为真实包装食品 ingredient lists 和 Nutrition Facts 的来源；FNDDS 和实验室食品则适合作为 reference formulation 或 case studies。

#### Step 4：标签营养值转换

将 Branded Food 中的 label nutrients 转换为 NuSol-T 的 target intervals：

```text id="lvsrhv"
per serving nutrient
→ per 100g nutrient
→ label rounding interval
→ compliance-aware interval
→ target interval
```

#### Step 5：可信约束求解

使用 FNDDS 阶段校准后的 NuSol-T 配置，进行：

```text id="jlsp8c"
PointSolver
BoundSolver
EnsembleSolver
```

输出：

```text id="0wt2xl"
ingredient point estimate
ingredient feasible range
ingredient uncertainty interval
constraint slacks
nutrient residuals
trust grade
```

#### Step 6：扩展完整营养成分估计

利用推断出的配料组成范围和配料营养组成矩阵，计算标签上未完整提供的营养素。

可扩展估计包括：

```text id="n32pf9"
water
ash
starch
individual fatty acids
cholesterol
minerals
vitamins
selected fiber-related components
future-linked polyphenols or glycans if external databases are available
```

输出不应只有单点，而应包括：

```text id="u7fcgf"
median estimate
5–95% interval
source coverage
confidence level
```

### 10.4 Branded Food 阶段输出

对每个产品生成 TrustReport：

```text id="hp7x6r"
1. 产品基本信息
2. 原始标签营养值
3. 解析后的配料结构
4. 配料映射结果
5. 估计配料组成范围
6. 扩展完整营养成分估计
7. 营养估计不确定性区间
8. 约束冲突和 slack
9. 数据来源和版本
10. warnings
11. trust grade
```

批量层面输出：

```text id="m3n145"
food-category-level solve rate
food-category-level trust grade distribution
common constraint conflicts
common mapping failure types
nutrient expansion coverage
uncertainty distribution by category
```

## 11. 预期结果

本项目预期得到以下结果。

在 FNDDS 阶段：

```text id="bqfqn2"
NuSol-T 能够较好复现 FNDDS forward nutrient calculation。
NuSol-T 能够在标准化 recipe 条件下恢复合理的主配料组成范围。
Labelized simulation 会显示标签四舍五入和区间化处理对结果可信度的重要性。
BoundSolver 和 EnsembleSolver 能够揭示单点估计的不唯一性。
TrustReport 能够有效标记高可信、低可信和约束冲突案例。
```

在 Branded Food 阶段：

```text id="s3oy8w"
NuSol-T 能够处理大规模真实包装食品记录。
NuSol-T 能够为不同食品类别生成配料组成范围。
NuSol-T 能够基于标签约束和配料数据库扩展完整营养成分画像。
复杂加工食品、含 vague ingredients 的食品和配料映射困难食品会显示较低 trust grade。
不同食品类别会有不同的 solve rate、constraint conflict pattern 和 nutrient expansion coverage。
```

## 12. 评价指标

### 12.1 FNDDS 验证指标

```text id="dtclek"
Forward nutrient reconstruction MAE
Forward nutrient reconstruction relative error
Ingredient proportion MAE
Top ingredient MAE
Rank correlation
80% / 90% interval coverage
Average interval width
Solve rate
Zero-slack rate
Constraint slack frequency
Trust grade calibration
```

### 12.2 Branded Food 应用指标

```text id="6b5yug"
Product processing success rate
Ingredient parsing success rate
Ingredient mapping coverage
Solve rate
Trust grade distribution
Nutrient label fit residual
Expanded nutrient coverage
Uncertainty interval width
Constraint conflict frequency
Category-specific failure modes
```

### 12.3 Error taxonomy

错误和失败模式包括：

```text id="w57ln1"
missing serving size
incomplete nutrient label
unparseable ingredient list
compound ingredient ambiguity
no suitable composition database match
vague ingredients such as natural flavor or seasoning
infeasible nutrient constraints
large moisture/yield adjustment required
highly non-identifiable ingredient proportions
```

## 13. 项目实施路线图

### Phase 0：基础框架搭建

```text id="5gz7b2"
建立 NuSol-T repository
定义核心 schema
建立 nutrient registry
建立 YAML config parser
建立 basic TrustReport schema
```

### Phase 1：FNDDS adapter 与 forward calculation

```text id="brn4h3"
读取 FNDDSNutVal、FNDDSIngred、IngredNutVal、MoistAdjust
实现 ForwardNutritionModel
复现 FNDDS-style nutrient calculation
输出 forward reconstruction metrics
```

### Phase 2：可信约束 inverse solver

```text id="efq6n9"
实现 MassBalanceConstraint
实现 IngredientOrderConstraint
实现 LabelIntervalFitConstraint
实现 PointSolver
实现 BoundSolver
实现 basic EnsembleSolver
在 FNDDS 上进行 inverse reconstruction
```

### Phase 3：Labelized simulation 与约束校准

```text id="xqmh6k"
构建 simulated Nutrition Facts labels
实现 label interval construction
进行 constraint ablation
校准 constraint weights 和 trust grade rules
```

### Phase 4：Branded Food adapter 与真实应用

```text id="odxhox"
读取 USDA Branded Food Database
解析 Nutrition Facts 和 ingredient list
构建 ProductObservation
进行真实包装食品求解
输出 product-level 和 category-level TrustReport
```

### Phase 5：扩展完整营养成分估计

```text id="wnllqj"
扩大 nutrient registry
根据配料组成范围估计完整营养画像
输出 expanded nutrient profile with uncertainty
评估不同类别的 nutrient expansion coverage
```

## 14. 项目产出

最终项目产出包括：

```text id="p4lbrn"
1. NuSol-T Python framework
2. YAML-driven nutrition inference pipeline
3. FNDDS validation benchmark
4. Branded Food application pipeline
5. TrustReport JSON / CSV / HTML 输出系统
6. FNDDS validation results
7. Branded Food category-level analysis results
8. Error taxonomy and failure mode report
9. Manuscript-ready methods and results
10. Future extension interface for polyphenols, glycans, additives, and bioactive components
```

## 15. 项目风险与解决方案

### 风险 1：配料组成推断欠定

解决方案：

```text id="ozf94x"
不只输出点估计
使用 BoundSolver 和 EnsembleSolver
输出区间和 identifiability report
```

### 风险 2：Branded Food 没有真实配方 ground truth

解决方案：

```text id="s9vdwi"
不使用 Branded Food 评估 ingredient accuracy
使用 FNDDS 和 selected known-formulation products 验证准确性
Branded Food 用于真实应用和可行性评估
```

### 风险 3：配料映射误差传播

解决方案：

```text id="9tzw29"
保留 top-k candidate mappings
记录 mapping confidence
进行 candidate ensemble
对低可信配料降低 trust grade
```

### 风险 4：加工过程造成营养偏差

解决方案：

```text id="v0n5y7"
引入 moisture/yield adjustment
在 FNDDS 中验证 processing parameters
对需要极端 processing adjustment 的产品标记 warning
```

### 风险 5：复杂食品无法稳定求解

解决方案：

```text id="ptf9xa"
按食品类别分层分析
建立 failure taxonomy
对低可信产品输出 conflict diagnostics，而不是强行解释为准确配方
```

## 16. 项目总结

NuSol-T 是一个面向食物营养成分分析的可扩展统一计算框架。它的目标不是恢复不可见的真实商业配方，而是在标签、配料表、食品成分数据库和可信约束条件下，推断可解释的配料组成范围，并进一步估计更完整的营养成分画像。

本项目采用两阶段研究设计。第一阶段使用 FNDDS 作为受控验证体系，验证 NuSol-T 的 forward nutrition calculation、inverse ingredient reconstruction、labelized simulation 和 trust reporting。第二阶段将经过验证的 NuSol-T 应用于 USDA Branded Food Database，利用真实包装食品的 Nutrition Facts 和 ingredient list 推断配料组成范围，并扩展估计标签之外的完整营养成分。

最终，NuSol-T 将为包装食品营养分析、ingredient-level dietary assessment、高分辨率膳食暴露估计以及未来与多酚、glycans、食品添加剂和其他 bioactive 数据库的整合提供一个透明、可复现、可扩展的计算基础。
