# FNDDS Benchmark 实验结果

> 2026-07-15 | 分支: `refactor/yaml-solver-framework` | 266 tests passing

本文记录 FNDDS workflow 的扩展 benchmark 结果。需要和 `docs/CURRENT_STATUS.md` 区分：

- `CURRENT_STATUS.md` 当前主口径仍是 197-sample benchmark；
- 本文记录的是 3,734 个 FNDDS 多配料配方的 extended/full-run 结果；
- 99.2% 是 post-hoc assisted recovery 后的成功率，不是默认自动 pipeline 的原始成功率；
- 本次 benchmark 未启用 prior，因此不能用于判断 prior 的边际贡献。

---

## 一、扩展全量测试 (3,734 配方)

### 总体结果

```
FNDDS 多配料配方 (2+ inputFoods, 排除 95 个 NFS)
────────────────────────────────────────────────
  Export 成功: 3,701 (99.1%)
  Solve 成功:  3,542 (94.9%)
  Export 失败:    33 ( 0.9%)
  Solve 失败:    159 ( 4.3%)
────────────────────────────────────────────────
  MAE mean:   2.48 pp
  MAE median: 1.74 pp
  MAE best:   0.00 pp
  MAE worst: 50.00 pp
────────────────────────────────────────────────
  耗时: 250s (4 分 10 秒)
```

### Post-hoc assisted recovery 结果

针对 33 个 export 失败和 159 个 solve 失败，做了两类事后辅助处理：

| 类别 | 原始失败 | 修复成功 | 仍失败 | 修复方法 |
|------|---------|----------|--------|----------|
| Export | 33 | **16** (48%) | 17 | 手动过滤 fortificant 配料，保留真实食材 |
| Solve | 159 | **147** (92.5%) | 12 | `max_iterations`: 500 → 2000 |
| **合计** | 192 | **163** (85%) | 29 | |

辅助恢复后总体成功率：

```
post-hoc assisted: 3,542 + 147 + 16 = 3,705 / 3,734 = 99.2%
```

这个数字说明失败案例中有大量可恢复样本，但不应表述为默认 workflow 的自动成功率。

修复后 Solve MAE：均值 4.8pp，中位 3.2pp。
修复后 Export MAE：均值 5.9pp，中位 6.1pp（fortified cereal 本身配料复杂，精度低于平均水平）。

### 仍无法修复的 29 个

**Export (17)**：
- 4 yogurt + 1 orange juice：去 fortificant（Vitamin D、Calcium）后只剩 1 个配料，无法求解
- 1 banana、1 tomato、1 onion：3 个品种/成熟度间营养几乎相同，2 配料配方退化为不可辨识
- 1 shredded wheat plain：去 fortificant 后只剩 flour，无法求解
- 8 fortified cereal：fortificant 占比过大，去掉后剩余食材营养过于相似 → SLSQP 不收敛

**Solve (12)**：Venison jerky、Tongue pot roast、Hog maws、Calamari 等复杂肉制品/器官肉类或低辨识度组合——即使 2000 次迭代也无法收敛。需要区分三类原因：营养空间不可辨识、当前 composition profile 不适用、以及 SLSQP 数值收敛问题。

### MAE 分布

```
<1 pp    : 1048 (29.6%) ████████████████████████████████
1-3 pp   : 1584 (44.7%) ████████████████████████████████████████████
3-5 pp   :  557 (15.7%) ████████████████
5-10 pp  :  255 ( 7.2%) ██████
10-20 pp :   71 ( 2.0%) █
>20 pp   :   27 ( 0.8%)
```

**74.3% 的配方 MAE < 3pp，90.0% < 5pp。**

---

## 二、失败分析

### 原始失败

```
Export 失败: 33 (0.9%) — 配料无法在 SR Legacy 中匹配
Solve 失败: 159 (4.3%) — SLSQP 收敛失败
```

### 手工修复

| 修复策略 | 修复数 | 成功率 |
|----------|--------|--------|
| Export: 手动 YAML，过滤 fortificant 配料 | 16/33 (48%) | MAE 均值 5.9pp / 中位 6.1pp |
| Solve: `max_iterations` 500→2000 | 147/159 (92.5%) | MAE 均值 4.8pp / 中位 3.2pp |
| **合计修复** | **163/192 (85%)** | |

辅助恢复后总体成功率：**3,705/3,734 = 99.2%**

### 剩余 29 个无法修复的案例

#### 类别 1：去 fortificant 后只剩 1 个配料 (6 个)

| FDC | 产品 | 配方真相 |
|-----|------|----------|
| 2705418 | Yogurt, whole milk, plain | Yogurt 100g + VitD 0.004g |
| 2705419 | Yogurt, low fat milk, plain | Yogurt 100g + VitD 0.012g |
| 2705420 | Yogurt, nonfat milk, plain | Yogurt 100g + VitD 0.01g |
| 2705464 | Baby Toddler yogurt, plain | Yogurt 100g + VitD 0.004g |
| 2708479 | Cereal, shredded wheat, plain | Flour 99g + Fiber fortificant 1g |
| 2709189 | Orange juice, 100%, with Ca | OJ 100g + Ca 0.013g + VitD 0.01g |

**失败原因**：FNDDS 把 fortificant 单独列为 ingredient，使得这些更接近 **single-base-food + fortification** 的食品被计为多配料。它们不应该和一般多原料配方混在一起评估；在真实 branded food 场景中，应由 ingredient parser / fortificant handler 把 base food 和 fortificant 分开处理，而不是强行作为普通多配料比例反推任务。

#### 类别 2：同一食材的不同品种/成熟度 (3 个)

| FDC | 产品 | 配料 | 原因 |
|-----|------|------|------|
| 2709224 | Banana, raw | 90% ripe + 10% overripe | 成熟度差异，营养参数几乎完全一样 |
| 2709719 | Tomatoes, raw | 60% red + 30% roma + 10% grape | 品种差异，营养参数几乎完全一样 |
| 2709795 | Onions, raw | 60% yellow + 30% white + 10% red | 品种差异，营养参数几乎完全一样 |

**失败原因**：品种/成熟度间**营养参数化学上不可区分**（同样的蔬菜，只是颜色/大小不同），线性模型中这些配料在营养空间中完全共线 → 任意权重组合都产生相同的营养预测 → 不可辨识。真实标签通常也不会把这些品种/成熟度拆成多个 ingredient，因此这类案例更适合在 export 阶段合并为一个 canonical ingredient。

#### 类别 3：Fortified cereal — 去掉 fortificant 后 SLSQP 不收敛 (8 个)

| FDC | 产品 | 真实食材 | Fortificant 数 |
|-----|------|---------|---------------|
| 2708446 | O's, flavored | Oats 66g + Sugar 32g + Oil + Salt | 7 |
| 2708448 | O's, plain | Oats 95g + Sugar 4g + Salt | 7 |
| 2708450 | Cinnamon toast | Flour 35g + Sugar 30g + Rice flour 25g + Oil 9g | 7 |
| 2708452 | Corn squares | Cornmeal 85g + Sugar 9g + Soy + Oil | 7 |
| 2708454 | Corn puffs | Cornmeal 85g + Sugar 11g + Soy + Oil | 7 |
| 2708463 | Corn squares, flavored | Cornmeal 60g + Sugar 25g + Flour 11g + Oil | 7 |
| 2708464 | O's, honey nut | Oats 66g + Sugar 32g + Oil + Salt | 7 |
| 2708485 | Peanut butter cereal | Cornmeal 45g + Sugar 30g + Oats 10g + PB 5g + Oil 7g | 7 |

**失败原因**：这些 cereal 配方的**真实营养差异主要来自 fortificant**（不同 cereal 变体之间，基础谷物+糖+油的组合几乎一样，差异在于维生素和矿物质的强化配方不同）。去掉 7 个 fortificant 后，剩余 3-7 个真实食材的营养特征高度相似（都是谷物+糖+油+盐组合），SLSQP 无法在近乎平坦的优化平面上收敛。

#### 类别 4：器官肉 / 低辨识度组合 (12 个)

下表列出当前记录中的主要案例；完整 failure artifact 应补齐第 12 个 FDC，避免文档和原始结果不一致。

| FDC | 产品 | 配料结构 | 失败原因 |
|-----|------|----------|----------|
| 2705915 | Venison/deer jerky | Deer meat + Lard + Sugar + Salt (4 配料) | 腌制肉干，脂肪和瘦肉比例不稳定 |
| 2706161 | Tongue pot roast | Beef tongue + Water + spices (5 配料) | 舌头器官肉，营养数据特殊 |
| 2706164 | Hog maws | Pork stomach + Salt (2 配料) | 猪胃器官，营养数据可能不准确 |
| 2706333 | Calamari, cooked | Squid + Oil + Salt (3 配料) | 鱿鱼+油+盐，低辨识度 |
| 2708717 | Bacalaitos fritos | Cod + Flour + Water + Oil (5 配料) | 炸鱼饼，加工后营养模型失准 |
| 2709138 | Jelly sandwich | Bread + Jelly (2 配料) | 面包+果酱，营养重叠严重 |
| 2705557 | Infant formula premature | 2 种早产配方奶各 50% | 两种配方奶营养几乎一样 |
| 2705788 | Vegetable pizza topping | 5 种蔬菜+奶酪+酱料 | 配料间营养重叠 |
| 2708835 | Pasta+veg ready-to-heat | Pasta + Sauce + Oil + Salt | 意面和酱料营养重叠 |
| 2708845 | Pasta+poultry ready-to-heat | Pasta + Poultry sauce + Oil + Salt | 同上 |
| 2710681 | Alcoholic coffee drink | Coffee + Liquor + Cream + Sugar | 酒精+咖啡+奶油，营养模型不适用 |

**失败原因**：器官肉类（舌头、胃、鱿鱼）的 SR Legacy 营养数据精度不足；意面/酱料/面包/果酱等配料在营养空间中重叠严重；低辨识度 2-3 配料组合的优化平面过平坦。

### 失败根因总结

| 根因 | 数量 | 是否可修 | 说明 |
|------|------|----------|------|
| Fortificant 作为唯一区分特征 | 6 | 应重分类 | single-base-food + fortification，不适合按普通多配料任务评估 |
| 品种/成熟度营养不可区分 | 3 | 应合并 | 同一 canonical ingredient 的变体，线性模型无法区分 |
| Fortificant 移除后谷物组合过相似 | 8 | 可改进 | 需要 fortificant→营养素对照表和 cereal category prior |
| 器官肉 / 低辨识度组合 | 12 | 可部分改进 | 需要更稳健 solver、better profile、category-specific metadata |

**核心洞察**：剩余失败主要暴露了当前 workflow 的边界：fortificant metadata 不完整、同类 ingredient 变体不可辨识、部分 food category 的 composition profile 不够适配、以及 SLSQP 在平坦目标面上的收敛不足。其中一部分是线性逆问题的固有限制，另一部分仍属于 export、metadata 和 solver 层可以继续改进的问题。

---

## 三、Ablation Study (约束消融)

在 197 样本上测试约束逐层叠加的效果。这里的 `G0 baseline` 不是只使用 mass balance；nutrient observations 仍作为 soft label-fit objective 编译进入求解。G0 的含义是移除额外 structural constraints 后的 baseline。

```
Level           约束                   成功率   MAE Mean   MAE Median
─────────────────────────────────────────────────────────────────────
G0 baseline     mass_balance            95.9%     3.04 pp     2.53 pp
G1 +order       + ingredient_order      95.4%     2.71 pp     2.10 pp
G2 +two_pct     + two_percent           94.9%     2.62 pp     1.96 pp
G3 full         + label_fit (marker)    94.9%     2.62 pp     1.96 pp
```

### 每个约束的边际贡献

| 约束 | MAE 中位改善 | 机制 |
|------|-------------|------|
| ingredient_order | 2.53 → 2.10 pp (**−17%**) | 配料排序信息有效缩小解空间 |
| two_percent | 2.10 → 1.96 pp (**−7%**) | ≤2% 配料上限约束排除极端解 |
| label_fit (marker) | 无额外变化 | 默认 soft/weight=10 与自动生成行为一致 |

G3 = G2 因为 `label_fit` 只是配置标记：nutrient observations 的编译独立于此约束声明，默认就是 soft mode + weight=10。

本 ablation 没有启用 Level 2 priors，因此不能得出 prior 边际贡献有限或有效的结论。prior 的作用需要单独做 no-prior / single-prior / combined-prior ablation，并报告 prior contribution、MAE 变化和失败案例恢复情况。

---

## 四、实验配置

| 配置项 | 值 |
|--------|-----|
| Benchmark mode | `fndds_workflow_code_assisted` |
| Mapping mode | `code_assisted` (FNDDS 4-level mapper: L1 FNDDS→L2 Foundation→L3 SR Legacy ndb→L4 fuzzy) |
| Observation mode | `fndds_final_nutrients_pm10pct` (FNDDS 最终产品营养素 ±10%) |
| 约束 | mass_balance (hard) + ingredient_order (hard, main group) + two_percent (hard, declaration_group) + nutrient_interval (soft, w=10) |
| Prior | **未启用** |
| Point solver | ScipySLSQP (slack-based QP, 10x retry) |
| Bounds solver | HiGHS LP (hard constraints only) |
| kJ→kcal | Atwater 4-4-9 自动检测修正 |
| Fortificant | code/name 规则识别；从普通 ingredient fraction 求解中分离；输出 `fortification` diagnostics；受 fortification 主导的 nutrient 结构化记录为 skipped |

---

## 五、针对失败案例的提升办法

### 5.1 Export 失败改进

| 失败类型 | 当前表现 | 建议提升办法 | 验收指标 |
|----------|----------|--------------|----------|
| Fortificant 导致 pseudo multi-ingredient | Yogurt、orange juice、shredded wheat 等去 fortificant 后只剩一个 base food | 已增加 `single_base_with_fortification` 分类；fortificant 进入 `fortification` diagnostics，不进入普通 ingredient fraction 求解 | 这 6 类可被单独统计；仍需重跑 full benchmark 验证 |
| Fortified cereal | 强化营养素解释了主要标签差异，删除 fortificant 后信息不足 | 已完成 fortificant 分离和 skipped nutrient diagnostics；下一步建立 fortificant→nutrient contribution 表，把 calcium、vitamin D、iron、B vitamins 等作为可解释 additive profile | cereal export 成功率提升需等 additive profile 接入后验证 |
| 同一食材品种/成熟度 | Banana/tomato/onion 变体营养共线 | 在 FNDDS export 阶段做 canonical ingredient collapse，把同一 base ingredient 的品种/成熟度合并 | 变体案例不再进入不可辨识多变量求解 |
| SR Legacy 匹配失败 | 部分 ingredient 找不到 profile 或 profile 不合适 | 增加 mapper failure taxonomy：missing profile、ambiguous profile、low-confidence fuzzy match、fortificant-only；优先接 Foundation/FNDDS code profile | export failure 可解释率达到 100%，并能按类别回归 |
| 手工修复不可复现 | 当前 16 个 export 恢复来自人工过滤 | 把人工规则沉淀成 YAML export policy 和 regression fixture，而不是只保留结果数字 | 16 个恢复样本可由脚本自动复现 |

建议新增 export 输出字段：

```yaml
export_diagnostics:
  export_mode: fndds_workflow_code_assisted
  failure_category: single_base_with_fortification | canonical_variant_collapse | missing_profile | low_confidence_mapping
  fortificant_ingredients: [...]
  collapsed_ingredients: [...]
  skipped_nutrients:
    - nutrient: iron
      reason: fortification_dominated
```

### 5.2 Solve 失败改进

| 失败类型 | 当前表现 | 建议提升办法 | 验收指标 |
|----------|----------|--------------|----------|
| SLSQP 迭代不足 | 147/159 通过 `max_iterations=2000` 恢复 | 已实现基础 adaptive retry：先用 YAML `max_iterations`，失败后可用 `retry_max_iterations=2000` 自动重试，并输出 `retry_trace`；后续还需接 benchmark failure taxonomy | 默认自动 pipeline 应能恢复部分原需人工改参数的样本，需重跑全量 benchmark 验证 |
| 平坦目标面 / 低辨识度 | 面包+果酱、意面+酱、谷物+糖+油等组合营养重叠 | 增加 condition diagnostics：composition matrix rank、condition number、ingredient cosine similarity、active constraint count | failure report 能区分“不可辨识”和“优化失败” |
| 器官肉 / 特殊肉类 | SR Legacy profile 可能不适配实际加工状态 | 增加 category-specific profile selection；对 cured/dried/fried/cooked organ meat 使用更接近的 profile 或 yield/moisture metadata | 器官肉案例 residual 降低，或明确报告 profile mismatch |
| 油/盐/糖小比例变量不稳定 | 小比例 ingredient 对少数 nutrient 高敏感 | 对 salt/oil/sugar 添加经过 calibration 的弱 prior 或 declared upper bound；但必须可 ablation | 小比例 ingredient 极端解减少，prior contribution 可解释 |
| Alcoholic food | 酒精饮品 energy closure 可能不适用 | 对 alcoholic food 增加 alcohol metadata 和 7 kcal/g energy factor；若无 alcohol observation，报告 low-identifiability | alcoholic coffee drink 不再被普通 Atwater 4-4-9 错误解释 |
| Solver 单一 | 当前主要依赖 SLSQP | 增加 HiGHS/QP-compatible convex fallback 或 IPOPT adapter；至少实现多起点 + projected feasible initialization | 剩余 12 个 solve failure 中可明确区分数值失败和科学不可辨识 |

建议新增 solve diagnostics：

```json
{
  "identifiability": {
    "matrix_rank": 4,
    "condition_number": 120000.0,
    "near_collinear_ingredient_pairs": [
      ["tomato_red", "tomato_roma"]
    ]
  },
  "retry_trace": [
    {"solver": "scipy_slsqp", "max_iterations": 500, "success": false},
    {"solver": "scipy_slsqp", "max_iterations": 2000, "success": true}
  ],
  "failure_category": "ill_conditioned | solver_convergence | profile_mismatch | unsupported_food_model"
}
```

### 5.3 优先级建议

1. **先做 failure taxonomy 和 diagnostics**：不要只追求成功率，先让每个失败有稳定分类。
2. **把 post-hoc 修复变成自动 policy**：`max_iterations=2000` retry 和 fortificant 分离/diagnostics 已有基础版。
3. **再做 fortificant contribution metadata**：这是 cereal 和 fortified food 的主要瓶颈。
4. **最后引入 calibrated weak priors**：prior 只能作为可解释的软偏好，不能用来掩盖 profile mismatch 或不可辨识。

---

## 六、关键结论

1. **方法在 FNDDS extended benchmark 上表现有潜力**：默认自动结果为 3,542/3,734 solve 成功，MAE 中位 1.74pp；post-hoc assisted recovery 后达到 3,705/3,734。
2. **最大可恢复瓶颈很清楚**：export 失败主要来自 fortificant 和 ingredient variant handling；solve 失败中大量样本可通过 adaptive retry 恢复。
3. **结构约束（ingredient_order、two_percent）有明确收益**，合计降低 MAE 中位 23%
4. **本次实验不能评价 prior**：实验配置明确为 `Prior: 未启用`。prior 的作用需要后续单独做 prior ablation 和 sensitivity。
5. **方法适用条件需要显式报告**：配料营养差异大时可精确；配料营养同质、profile mismatch、fortification 主导或 alcohol/yield metadata 缺失时，需要输出低辨识度或模型不适用诊断。
