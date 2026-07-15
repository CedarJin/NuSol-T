# NuSol-T 营养学与食品科学有效性 Review

> Review 日期：2026-07-05  
> 范围：营养素定义、食品成分数据库、标签法规、配方质量守恒、加工与保留率、科学约束、验证设计、不确定性和结果解释  
> 说明：本文聚焦科学有效性，不重复 `docs/REVIEW.md` 中的一般工程质量问题。法规和数据库结论以 FDA、USDA、NIH 等原始资料为依据。
>
> **状态说明（2026-07-15）**：本文是历史科学审查记录。当前工程进度以 `docs/CURRENT_STATUS.md` 和 `docs/PROGRESS.md` 为准；食品科学先验、校准可信度、Bayesian/分层模型和真实 Branded Food 外部验证仍属于后续扩展。

## 1. 总体科学结论

NuSol-T 的研究问题具有价值：利用 Nutrition Facts、配料表和食品成分数据库，对包装食品配料比例与扩展营养成分进行约束推断。但当前实现尚不足以支持“科学上可信的配料组成范围”这一强结论。

最核心的问题不是优化器精度，而是观测模型和数据生成过程尚未正确建模：

1. 标签值不仅经过舍入，还受合规容差、检测误差、配方批次差异和数据库换算影响。
2. 配料表顺序描述的是投料时按重量的相对顺序，不等价于成品中的质量分数。
3. 烹调损失、吸水、脱水、脂肪增减和营养素保留会改变配料质量与成品营养密度。
4. FNDDS recipe ingredients 是用于生成代表性营养画像的计算配方，不是商业产品的真实 label ingredients。
5. 不同 FoodData Central 数据类型的营养值具有不同来源、时间、食物状态和不确定性，不能无误差地互换。
6. 当前若干营养素代码、FDA 舍入规则、能量公式和营养闭合约束本身存在科学错误。

因此，现阶段更合适的定位是：

> 在简化配方模型和选定食品成分记录下，生成满足部分标签与顺序约束的候选配料比例。

在修复本文高优先级问题并完成外部验证前，不宜把输出称为真实配方、可信区间、credible interval，或用 Trust Grade 表达经过校准的科学可信度。

## 2. 关键科学问题汇总

| 优先级 | 问题 | 主要后果 |
|---|---|---|
| 严重 | 脂肪酸营养素 ID 错位 | 饱和、单不饱和、多不饱和脂肪可能被错误识别 |
| 严重 | 标签区间只反演舍入，不包含合规与测量不确定性 | 可行域过窄，产生伪精确和错误冲突 |
| 严重 | 加工前配料重量与成品质量分数混用 | 质量守恒与营养浓缩模型基础不成立 |
| 严重 | 缺失营养值被当成零 | 系统性低估营养贡献并扭曲配料比例 |
| 严重 | FNDDS recipe 被过度解释为真实配方验证 | benchmark 不能外推到商业包装食品 |
| 高 | FDA 舍入规则和反演区间实现不完整 | 标签模拟与 inverse target 错误 |
| 高 | retention code/moisture adjustment 未真正接入 | forward 模型不能复现 FNDDS 计算过程 |
| 高 | Energy 和 water-solid closure 定义错误 | 科学先验会把解推离真实值 |
| 高 | 跨数据库映射没有状态与不确定性模型 | 数据库差异被错误归因于配料比例 |
| 高 | 强化剂被跳过且未补回营养贡献 | 微量营养素推断严重偏低 |
| 中 | Added sugar、sodium、fatty-acid 等启发式约束依据不足 | 约束看似食品科学，实际可能无效或有偏 |
| 中 | 不确定性只覆盖优化可行域 | 远低于总科学不确定性 |

## 3. 严重问题

### 3.1 脂肪酸营养素 ID 与名称错位

位置：`src/nusol/core/nutrient_registry.py:23-27`

当前注册表定义：

```text
1292 -> Fatty acids, total saturated
1293 -> Fatty acids, total monounsaturated
1294 -> Fatty acids, total polyunsaturated
```

USDA FNDDS 资料中的正确主要 ID 是：

```text
1258 -> Fatty acids, total saturated
1292 -> Fatty acids, total monounsaturated
1293 -> Fatty acids, total polyunsaturated
```

USDA 的 FNDDS 文档明确列出 saturated fat 为 1258、monounsaturated fat 为 1292。[USDA FNDDS 文档](https://www.ars.usda.gov/ARSUserFiles/80400530/pdf/fndds/2017_2018_FNDDS_Doc.pdf)

影响：

- 按 ID 标准化时会把脂肪酸类别错配；
- fatty-acid closure 和标签营养素映射可能使用错误列；
- 跨 FNDDS、SR Legacy、Foundation 的统一模型不再可信；
- 即使名称路径暂时正确，注册表作为 canonical layer 仍会向后续功能传播错误。

建议：从当前 FoodData Central nutrient 表自动生成 registry，不要手工维护 ID。增加 ID、number、name、unit 四元组的一致性测试，并对每次 USDA 数据版本升级执行差异检查。

### 3.2 标签真实值区间不能只由舍入规则反演

位置：

- `src/nusol/utils/numerics.py:7-184`
- `src/nusol/nutrition/labelize.py:56-94`

项目当前假设：标签值的真实区间等于“所有会舍入到该标签值的数值集合”。这只描述显示舍入，不是完整的标签观测模型。

FDA 对营养标签合规采用 Class I、Class II 和另一组营养素的不同判定标准。例如某些添加的 Class I 营养素要求分析值至少达到申报值；部分 Class II 营养素通常允许分析值不低于申报值的 80%；某些限制性营养素则关注分析值不超过申报值的 120%。这些容差是非对称的，且与营养素类别、是否添加和检测分析相关。[FDA nutrition-labeling database guidance](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/guidance-industry-guide-developing-and-using-data-bases-nutrition-labeling) [FDA 2016 label revision guidance](https://www.fda.gov/media/134505/download?attachment=)

此外还存在：

- 实验室分析误差；
- 生产批次和原料季节差异；
- serving weight 误差；
- 标签数据库由 %DV 反算的误差；
- 小 serving 经舍入后放大到每 100 g 的误差。

USDA 明确提醒，GBFPD 中的标签舍入会导致 100 g/100 mL 数值额外变异，缺失值也不表示零。[USDA GBFPD documentation](https://fdc.nal.usda.gov/GBFPD_Documentation/)

影响：当前 inverse interval 通常过窄，把正常标签/分析差异误判为配方冲突，并产生伪精确的配料区间。

建议建立分层观测模型：

```text
真实成品营养浓度
  -> 批次/分析误差
  -> 每份换算
  -> 法规合规申报
  -> 显示舍入或“<1 g”等文本
  -> FoodData Central 标准化回每100g
```

至少应区分 rounding interval、regulatory compliance interval 和 database-derived uncertainty，不能合并为一个无来源的区间。

### 3.3 配料质量守恒使用了错误的质量基准

位置：

- `src/nusol/data/fndds.py:113-116, 129-145`
- `src/nusol/constraints/mass_balance.py:13-44`
- `src/nusol/nutrition/forward.py:33-67`

FNDDS 文档说明，recipe ingredient weight 是应用 moisture loss 前的重量；moisture adjustment 在 recipe level 处理，代表烹调过程的吸水或失水。[USDA FNDDS 2021–2023 documentation, pp. 17–18](https://www.ars.usda.gov/ARSUserFiles/80400530/pdf/fndds/2021_2023_FNDDS_Doc.pdf)

当前代码却把 ingredient weights 归一化为和为 1，并将其直接解释为成品质量分数，同时再次对营养浓度应用 moisture factor。这混合了两个不同基准：

- 投料配方质量分数；
- 成品中各来源物质的质量贡献。

例如烘焙面包、脱水零食、煮熟谷物和浓缩酱料中，投料总重与成品总重明显不同。配料表的顺序通常基于制造时加入的重量，而营养标签是成品每份或每 100 g 的浓度。

建议明确变量：

```text
w_i = 第 i 个配料投料质量
M_in = Σw_i
M_out = 成品质量
Y = M_out / M_in
x_i = w_i / M_in
```

营养素质量应先按投料量和 retention 计算，再除以成品质量。若使用成品来源质量分数，则配料表顺序约束未必仍能直接施加。

### 3.4 缺失营养值被系统性当成零

位置：

- `src/nusol/data/fndds.py:63-70, 288-295`
- `src/nusol/data/sr_legacy.py:229-246`
- `src/nusol/data/foundation.py:78-95`
- `src/nusol/data/branded.py:37-59`

代码使用 `amount=fn.get("amount", 0.0)`，且 profile 没有某营养素时在 matrix 中写 0。这在食品成分科学上通常不成立：

- 缺失可能表示未分析、未提交或不适用；
- 零可能表示低于检出限、低于定量限、标签舍入为零，或真正为零；
- 这些状态对应完全不同的不确定性。

USDA Foundation Foods 明确指出，一些营养素尚未分析；LOQ 信息与 component value 分开保存。GBFPD 也明确指出 missing 和 “not a significant source” 都不表示零。[USDA Foundation Foods documentation](https://fdc.nal.usda.gov/Foundation_Foods_Documentation/) [USDA GBFPD documentation](https://fdc.nal.usda.gov/GBFPD_Documentation/)

影响：

- 未分析的微量营养素被当成无贡献；
- 求解器可能增加其他配料比例来补偿不存在的“零”；
- unique-source 判断产生假阳性；
- 扩展营养画像系统性低估缺失较多的营养素。

建议使用四态或更多状态：measured、calculated/imputed、below-LOQ、missing。Matrix 不应只存 float，应同时携带 value、uncertainty、derivation、LOQ 和 missingness。

### 3.5 FNDDS 不能作为商业配料比例的直接 gold standard

位置：

- `src/nusol/data/fndds.py:129-145, 299-342`
- `docs/NuSol-T.md`
- `docs/PROGRESS.md`

FNDDS 文档明确说明：recipe ingredients 是为了生成某一 food/beverage code 的代表性营养画像而选择，不一定代表具体产品中的实际配料；它们也不是产品标签上的 label ingredients；对营养贡献很小的成分通常不会纳入。[USDA FNDDS 2021–2023 documentation, p. 17](https://www.ars.usda.gov/ARSUserFiles/80400530/pdf/fndds/2021_2023_FNDDS_Doc.pdf)

此外，salt 或 fat 可能只是为形成代表性 nutrient profile 而加入计算配方，并不意味着实际产品一定以该形式使用。

因此，FNDDS 验证能回答的是：

> 在 FNDDS 自身的 recipe-calculation 表示下，是否可以恢复其计算配方？

它不能直接回答：

> 是否能从商业包装标签恢复制造商真实配方？

如果 ingredient profiles 又优先从 FNDDS self lookup 获取，验证还具有同源循环性：目标营养值和解释矩阵来自同一体系，误差会显著低于跨数据库和真实商业应用。

建议把验证拆成：

1. 内部数值复现：严格复现 FNDDS recipe calculation；
2. 跨数据库鲁棒性：只使用真实应用时可获得的数据源；
3. 外部配方验证：使用公开标准化配方、厂家提供配方或受控实验配方；
4. 商业食品应用：只报告可行候选与敏感性，不宣称真实比例准确率。

## 4. 高优先级问题

### 4.1 FDA 舍入表存在多项科学和法规错误

位置：`src/nusol/utils/numerics.py:10-184`

主要问题：

1. `0.5–1 g` carbohydrate、fiber、sugars、added sugars 被模拟为数值 `0.5 g`；FDA 标签在多种情形下使用“less than 1 g”文本或允许相应声明，并非统一显示 0.5 g。
2. cholesterol 2–5 mg 应表示为“less than 5 mg”，当前用 5 mg increment 数值舍入，2 mg 甚至可能被算成 0。
3. calcium、iron、potassium 共用一套自定义阈值，但新版标签实际 quantitative amount 的精度不同，例如 calcium 通常到 10 mg、iron 到 0.1 mg、vitamin D 到 0.1 mcg。[FDA quantitative amount Q&A](https://www.fda.gov/media/117402/download?attachment=) [FDA educational rounding table](https://www.fda.gov/media/95613/download)
4. 未知营养素默认 `<1 -> 0、其余取整` 没有通用法规依据。
5. 反演逻辑无法表示文本声明、“not a significant source”、省略字段和 dual-column label。

FDA Food Labeling Guide 的 Appendix H 对 calories、fat、cholesterol、sodium、carbohydrate 等采用营养素特异规则，并明确 cholesterol 2–5 mg 和低于 1 g 的文本表达。[FDA Food Labeling Guide](https://www.fda.gov/media/81606/download)

建议把 label representation 建模为结构化类型，而不是强制 float：

```text
ExactNumeric(value)
RoundedNumeric(value)
LessThan(threshold)
ZeroDeclared(threshold)
NotSignificantSource
MissingOrOmitted
```

### 4.2 Retention factor 与 moisture adjustment 没有复现 USDA 过程

位置：

- `src/nusol/nutrition/forward.py:27-67`
- `src/nusol/data/fndds.py:101-127`

FNDDS adapter 读取 retention code，但没有把四位 code 映射到各营养素 retention factor。Forward model 只在调用方已经提供完整 retention matrix 时简单相乘，当前 pipeline 并未构造该矩阵。

USDA retention factors 是按食物组、加工方法和营养素定义的，覆盖特定维生素、矿物质和 alcohol，并非所有营养素统一乘同一比例。True retention 的定义还涉及加工前后食品重量。[USDA Table of Nutrient Retention Factors](https://www.ars.usda.gov/arsuserfiles/80400530/pdf/retn06.pdf)

建议：

- 加载 USDA retention-code 表；
- 按 ingredient × nutrient 映射 factor；
- 未提供 factor 的营养素使用 1 还是 missing 必须有明确规则；
- retention 和 yield/moisture 分开建模；
- 用 FNDDS 已知 recipe 做逐营养素 forward reproduction test。

### 4.3 Energy closure 不是可靠的统一 4/9/4 公式

位置：

- `src/nusol/constraints/energy_closure.py:13-83`
- `src/nusol/nutrition/forward.py:99-122`

当前使用：

```text
4 × protein + 9 × fat + 4 × carbohydrate + 2 × fiber + 7 × alcohol
```

问题包括：

- `Carbohydrate, by difference` 已包含 dietary fiber，再额外加 `2 × fiber` 会重复计能；
- 若想对 fiber 使用 2 kcal/g，应从 4 kcal/g carbohydrate 部分扣除 fiber；
- USDA 同时存在 Atwater general factor 和 food-specific factor 能量，二者不一定相同；
- sugar alcohol、organic acids 和不同 fiber fermentation energy 未纳入；
- 标签 energy 可能由法规允许的方法计算，而非当前公式。

USDA 明确指出 carbohydrate by difference 包含 fiber，并区分 Atwater general 与 specific factors。[USDA Foundation Foods documentation](https://fdc.nal.usda.gov/Foundation_Foods_Documentation/)

建议把 energy closure 作为带方法 provenance 的弱校验，而不是普遍科学硬先验。只有当 carbohydrate 定义、fiber 处理和 energy derivation 已知时才启用。

### 4.4 Water-solid closure 重复计数且忽略分析误差

位置：`src/nusol/constraints/water_solid.py:17-88`

当前总和为：

```text
water + protein + fat + carbohydrate by difference + fiber + ash + alcohol
```

carbohydrate by difference 本身定义为 100 减去 water、protein、fat、ash 和 alcohol，且包含 fiber。因此当前公式重复加入 fiber，理论上会系统性超过 100。

即使改正重复计数，独立分析得到的 sugars、fiber、starch 等也具有分析变异，子组分之和可能不等于 carbohydrate by difference。USDA 对此有明确说明。[USDA Foundation Foods documentation](https://fdc.nal.usda.gov/Foundation_Foods_Documentation/)

建议：

- 若使用 carbohydrate by difference，closure 只使用其定义中的互斥 proximate components；
- 若使用独立 carbohydrate fractions，则需要残余项和分析不确定性；
- 不要同时使用两套定义做质量闭合。

### 4.5 跨数据库映射没有科学可比性控制

位置：`src/nusol/data/fndds.py:159-297`

当前映射优先依据 code 或文本相似度，但没有系统比较：

- raw、cooked、drained、dry matter 等状态；
- edible portion 与 as-purchased basis；
- cultivar、脂肪等级、加工程度和强化状态；
- moisture、品牌配方与年代；
- analytical、calculated、imputed derivation；
- sample number 和成分变异。

Foundation Foods、SR Legacy、FNDDS 和 Branded Foods 是不同目的、不同获取方式的数据类型。USDA 也强调各数据类型具有独特用途，Foundation Foods 中部分食物甚至以 0% moisture basis 表示。[USDA FoodData Central overview](https://fdc.nal.usda.gov/) [USDA Foundation Foods documentation](https://fdc.nal.usda.gov/Foundation_Foods_Documentation/)

文本 fuzzy score 不是营养组成相似度，也不是科学 uncertainty。

建议建立 eligibility filter：食物状态、处理方式、moisture basis 和强化状态不兼容时不得直接匹配。匹配后的 composition uncertainty 应进入求解和敏感性分析。

### 4.6 强化剂被移除但没有补回营养贡献

位置：`src/nusol/data/fndds.py:147-157, 185-187, 253-295`

FNDDS 的 `999xxx` code 是单一或复合营养素，在 recipe calculation 中用于提供 vitamin D、calcium、iron、vitamin C、folate、B12 或 fiber。USDA 文档明确列出这些 code。[USDA FNDDS 2021–2023 documentation, p. 19](https://www.ars.usda.gov/ARSUserFiles/80400530/pdf/fndds/2021_2023_FNDDS_Doc.pdf)

当前代码将其映射为 `None`，小重量时直接过滤，保留时又创建空 nutrient profile，最终营养贡献为 0。文档声称“作为对应标签营养素的直接来源处理”，但代码没有该过程。

影响：强化食品中的 vitamin D、iron、calcium、folate 等会被严重低估，求解器可能错误提高其他天然来源配料比例。

建议：把 fortificant 建模为低质量、高浓度的 nutrient addition term，既保留其非零质量，也保留精确营养贡献；若 FNDDS 提供直接 addition value，应按其 recipe-calculation 规则使用。

### 4.7 Branded Foods 的 100-unit basis 和介质没有正确处理

位置：`src/nusol/data/branded.py:62-74, 76-121`

USDA 会把提供的 per-serving label values 标准化为每 100 g 或每 100 mL，具体取决于数据提供方；derivation code 记录换算来源。[USDA GBFPD documentation](https://fdc.nal.usda.gov/GBFPD_Documentation/)

当前代码只要存在 serving size 就把 profile 标为 `per_serving`，并把 serving size 数值直接当克，忽略 mL 等单位。这会造成：

- 已经是 per 100 g 的值被再次当作 per serving；
- 饮料等 per 100 mL 数据被当作 per 100 g；
- 缺乏密度时进行无依据的体积—质量换算。

建议保留 basis quantity、basis unit、serving quantity、serving unit 和 derivation method。没有密度时不得把 mL 当作 g。

### 4.8 IU 转换对 vitamin E 和 vitamin A 不成立

位置：`src/nusol/core/units.py:22-69`

当前表把 vitamin E 的 `0.67` 注释为 IU→mg，但 `convert_iu(..., to_unit="mg")` 又乘 `0.001`，使 1 IU 变成 0.00067 mg，误差 1000 倍。

此外：

- vitamin E 自然型约 0.67 mg/IU，合成型约 0.45 mg/IU，不能只用一个 factor；
- vitamin A 的 IU→µg RAE 取决于 retinol、supplemental beta-carotene 或 dietary beta-carotene，分别可为 0.3、0.3、0.05 µg RAE/IU；
- 缺少化学形式时转换本身不可识别。

这些差异可见 NIH ODS 的 [Vitamin E fact sheet](https://ods.od.nih.gov/factsheets/VitaminE-HealthProfessional/) 和 [Vitamin A conversion说明](https://ods.od.nih.gov/factsheets/Pregnancy-HealthProfessional/)。Vitamin D 的 0.025 µg/IU 则有 FDA 明确换算依据。[FDA unit conversion guidance](https://www.fda.gov/media/129863/download)

建议把 nutrient form 作为转换必需参数；未知形式时返回不可转换状态，而不是猜测。

## 5. 科学约束的有效性问题

### 5.1 Fatty-acid closure 不应被视为精确化学等式

位置：`src/nusol/constraints/fatty_acid_closure.py:13-73`

总脂肪的标签/数据库定义可能是脂肪酸按 triglyceride equivalents 表示，而 fatty-acid classes 来自气相色谱测定。USDA 明确指出 fatty acids 之和在逻辑上不一定等于 total lipid。[USDA Foundation Foods documentation](https://fdc.nal.usda.gov/Foundation_Foods_Documentation/)

此外，未测或未列出的脂肪酸、甘油部分和分析误差都会产生差异。因此 `sat + mono + poly + trans <= total fat` 只能作为带方法依赖的宽松诊断，不能作为普遍配方约束。

### 5.2 Sodium source balance 的生理/食品化学依据不足

位置：`src/nusol/constraints/sodium_balance.py:13-62`

钠来源不限于食盐。MSG、sodium bicarbonate、sodium nitrite、sodium benzoate、磷酸盐等都可贡献钠，FDA 也明确列举了这些来源。[FDA sodium guidance](https://www.fda.gov/food/nutrition-education-resources-materials/sodium-your-diet)

当前约束只按 ingredient nutrient density 是否低于 50 mg/100 g 判断，不识别含钠添加剂，也没有对“高钠来源应解释多少标签钠”建立质量守恒。因此它不是有效的 sodium-source 模型。

建议基于含钠化合物的化学计量、配料映射和不确定区间建模；无法识别来源时不要施加方向性惩罚。

### 5.3 Added sugar 不能由普通成分表直接可靠分解

位置：`src/nusol/constraints/added_sugar_balance.py:13-82`

Added sugars 是配方与法规分类属性，不是所有基础食物成分记录都具有的固有分析值。SR Legacy/Foundation 的很多配料没有可靠 added-sugar 字段；缺失被填 0 后，模型会错误认为天然或添加糖贡献已知。

蜂蜜、糖浆、浓缩果汁等是否及如何计入 added sugars 还取决于标签法规和具体用途。仅靠关键词不能确定其全部糖是否应归为 added sugar。

建议把 added sugar 建模为 sugar-source ingredient 的投料糖质量与法规分类问题，并对 ambiguous ingredient 使用区间或类别变量，而不是依赖稀疏的 `Sugars, added` matrix 列。

### 5.4 Category prior 缺少经验数据支持

位置：`src/nusol/constraints/category_prior.py:13-49`

“多配料食品中单个配料超过 80% 不常见”不是普遍食品学规律。饮料、果泥、乳制品、肉制品、简单谷物和单一主料食品都可能由一个主要配料占绝大部分。

建议 category prior 必须来自独立训练集并按食品类别、配料位置和制造过程校准；报告 prior source、样本量和外部验证。未经校准的阈值不能被称为食品科学先验。

### 5.5 Compound ingredients 和 alternatives 未形成合法质量模型

位置：

- `src/nusol/ingredient/parser.py`
- `src/nusol/core/schema.py:79-129`

复合配料的 parent mass 应等于其 sub-ingredients 的质量和；如果 parent 与 children 同时进入营养矩阵，会重复计数；如果只使用 parent，则无法利用子配料顺序。`and/or` 表示替代配方或供应变化，不能简单改写成普通 “or” 文本后当作同时存在的连续变量。

建议为 compound ingredient 建立层级质量守恒，为 alternatives 建立离散情景或 mixture model，并分别输出情景不确定性。

## 6. 验证与不确定性解释问题

### 6.1 当前 benchmark 混合了算法误差和数据同源优势

使用 FNDDS final nutrients 作为 target，同时从 FNDDS self 获取 ingredient profiles，相当于在相同计算生态内反演。该结果适合验证优化器能否恢复一个内部生成过程，但不能等同于真实世界配料推断性能。

应分别报告：

- same-source closed-loop；
- cross-source composition；
- labelized FNDDS；
- external recipe；
- real branded food。

不同设置不能合并成单一 MAE 结论。

### 6.2 配料顺序只提供偏序信息，不提供比例间距

FDA 要求配料通常按加入时重量优势降序排列；明确使用 “contains 2% or less” 时，这组配料可以不再按优势顺序排列，但每个都不得超过声明阈值。[FDA ingredient overview](https://www.fda.gov/food/food-additives-and-gras-ingredients-information-consumers/types-food-ingredients) [21 CFR 101.4](https://www.govinfo.gov/content/pkg/CFR-2025-title21-vol2/pdf/CFR-2025-title21-vol2-part101.pdf)

因此顺序只能说明 `w_i >= w_{i+1}`，不能说明差距大小。相邻配料可能几乎相等，供应或批次变化也可能改变顺序。科学输出应强调这是一种弱偏序约束。

### 6.3 Feasible bounds 不等于概率或可信区间

LP 得到的最小/最大值只回答：在固定 matrix、固定标签区间和固定约束下，该变量能取到什么范围。它没有整合：

- ingredient mapping uncertainty；
- composition variability；
- processing uncertainty；
- label compliance and measurement uncertainty；
- alternative formulation；
- model misspecification。

因此不能解释为 80%、95% credible interval，也不能直接支持统计 coverage 声明。

建议采用分层 Monte Carlo/Bayesian 或 scenario ensemble：每次抽取 mapping、composition、retention、yield 和 label observation，再在条件情景内求解。最终区间必须说明是概率区间还是最坏情况可行域。

### 6.4 Trust Grade 没有科学校准

当前 Trust Grade 是基于 solver success、冲突数、绝对残差和区间宽度的人工计分。不同营养素单位未归一化，也没有与真实错误概率、外部验证或决策风险建立对应关系。

科学上更稳妥的做法是把它称为 diagnostic score，直到完成：

- calibration curve；
- grade-wise empirical error/coverage；
- external validation；
- category-stratified performance；
- failure-mode sensitivity。

只有当 A/B/C/D 与可观测的误差风险稳定对应时，才适合称为 trust grade。

## 7. 建议的科学模型重构

### 7.1 数据层

每个 nutrient value 至少保存：

```text
value
unit
basis_amount
basis_unit
food_state
derivation_method
analytical_method
sample_count
missingness_status
LOQ
uncertainty
source_version
```

### 7.2 Forward model

推荐使用质量基模型：

```text
NutrientMass_j = Σ_i w_i × A_ij × R_ij + Addition_j - Loss_j
FinishedConcentration_j = NutrientMass_j / M_out
M_out = Σ_i w_i + water_gain - water_loss + other_mass_change
```

其中脂肪 gain/loss、draining 和 processing water 应按类别建模，不能全部压缩进单一 moisture scalar。

### 7.3 Label observation model

分别处理：

```text
finished concentration
-> serving conversion
-> analytical/formulation variability
-> compliance declaration
-> display rounding/text representation
-> FoodData Central 100-unit derivation
```

### 7.4 Inverse model

把不确定性源显式分层：

- formulation uncertainty；
- ingredient identity uncertainty；
- food composition uncertainty；
- processing uncertainty；
- label observation uncertainty。

不要把所有不确定性都表示为 nutrient slack。

## 8. 建议的科学验证路线

### 阶段 A：基础定义验证

1. 对照 USDA nutrient dictionary 修复所有 canonical IDs、numbers 和 units。
2. 用 FDA 官方示例逐项验证 rounding 和 inverse interval。
3. 用 USDA retention 示例验证 true-retention 计算。
4. 验证 carbohydrate、fiber、energy、fatty-acid 的定义一致性。

### 阶段 B：FNDDS forward reproduction

1. 使用 FNDDS 原始 ingredient weight，不提前归一化。
2. 应用 retention code 和 moisture adjustment。
3. 按营养素报告 reproduction error。
4. 将无法复现的误差按 derivation、ingredient mapping 和 processing 分类。

### 阶段 C：受控 inverse validation

1. 使用研究团队自建的已知配方食品。
2. 记录投料质量、成品 yield、加工步骤和实验室营养分析。
3. 生成符合 FDA 表示的模拟标签。
4. 盲法恢复配方并评估 bias、coverage 和 failure rate。

### 阶段 D：外部商业验证

1. 寻找公开 percentage ingredient declarations 或厂家配方范围。
2. 按类别、加工方式、配料数、serving size 和 mapping quality 分层。
3. 单独评估点估计、feasible bounds 和概率区间。
4. 对 Trust Grade 做经验校准。

## 9. 发布或论文使用前的最低科学门槛

在使用现有结果支持论文或营养暴露研究前，建议至少满足：

- canonical nutrient IDs 和单位全部通过 USDA 对照测试；
- missing、zero、below-LOQ 和 omitted 不再混用；
- FDA label observation 不再只由简单舍入反演；
- FNDDS retention 与 moisture calculation 可被逐营养素复现；
- 投料质量和成品质量基准明确分离；
- energy、water-solid 和 fatty-acid closure 使用一致定义；
- FNDDS 内部验证与外部商业有效性明确区分；
- 强化剂营养贡献被正确保留；
- composition/mapping/processing uncertainty 进入最终区间；
- feasible bounds 不再称为 credible intervals；
- Trust Grade 经过外部误差校准。

## 10. 主要权威资料

- [USDA FNDDS 2021–2023 Documentation](https://www.ars.usda.gov/ARSUserFiles/80400530/pdf/fndds/2021_2023_FNDDS_Doc.pdf)
- [USDA Table of Nutrient Retention Factors, Release 6](https://www.ars.usda.gov/arsuserfiles/80400530/pdf/retn06.pdf)
- [USDA Foundation Foods Documentation](https://fdc.nal.usda.gov/Foundation_Foods_Documentation/)
- [USDA Global Branded Food Products Database Documentation](https://fdc.nal.usda.gov/GBFPD_Documentation/)
- [FDA Food Labeling Guide](https://www.fda.gov/media/81606/download)
- [FDA Guide for Developing and Using Databases for Nutrition Labeling](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/guidance-industry-guide-developing-and-using-data-bases-nutrition-labeling)
- [FDA Nutrition Facts Label Revision Guidance](https://www.fda.gov/media/134505/download?attachment=)
- [FDA Vitamin and Mineral Quantitative Amount Q&A](https://www.fda.gov/media/117402/download?attachment=)
- [FDA Unit Conversion Guidance for Vitamins A, D and E](https://www.fda.gov/media/129863/download)
- [NIH ODS Vitamin E Fact Sheet](https://ods.od.nih.gov/factsheets/VitaminE-HealthProfessional/)
