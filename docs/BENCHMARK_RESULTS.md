# FNDDS Benchmark 实验结果

> 2026-07-15 | 分支: `refactor/yaml-solver-framework` | 259 tests passing

---

## 一、全量测试 (3,734 配方)

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

### Export 失败 (33, 0.9%)

全部因为**配料无法在 SR Legacy 中匹配**：

| 类别 | 数量 | 示例 |
|------|------|------|
| Fortified cereals | 3 | Cereal O's flavored, chocolate puffs — 含 Fiber/Iron/Folic Acid/Vitamin C/D/Calcium "as ingredient" (纯 fortificant, 无营养成分数据) |
| "As ingredient" 伪配料 | ~25 | "Mushrooms, cooked, as ingredient"、"Breakfast meat as ingredient in omelet" — FNDDS 特有描述，SR Legacy 无对应条目 |
| 其他 | ~5 | 小众食材 |

**修复方向**: 建立 fortificant→营养素对照表，并对 "as ingredient" 类配料使用 code-based 映射（已在四级 mapper 中支持，但部分 code 在 SR Legacy 中无对应）。

### Solve 失败 (159, 4.3%)

全部为 SLSQP 收敛失败 (`Positive directional derivative for linesearch`)。

| 类别 | 数量 | 占比 | 原因 |
|------|------|------|------|
| Fish/Seafood | 66 | 41% | 鱼+油+盐是最常见简单配方，营养差异小，优化平面平坦 |
| Bean dishes | 15 | 9% | 豆+油组合，同上 |
| Soup/Stew | 7 | 4% | 汤汁中多种配料营养同质 |
| Vegetable | 5 | 3% | 蔬菜+油脂组合 |
| Other | 60 | 38% | 散落在各类低辨识度配方 |

**共同特征**: 配料数少 (2-3) + 营养特征相似 → 优化梯度接近零 → SLSQP 无法收敛。

**修复方向**: 备选 point solver (IPOPT)；或对低辨识度配方自动放宽 soft constraint weight。

---

## 三、Ablation Study (约束消融)

在 197 样本上测试约束逐层叠加的效果：

```
Level           约束                   成功率   MAE Mean   MAE Median
─────────────────────────────────────────────────────────────────────
G0 mass_only    mass_balance            95.9%     3.04 pp     2.53 pp
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
| Fortificant | 正则识别 + max_ing_val < 50% label 自动跳过 |

---

## 五、关键结论

1. **方法在 FNDDS 上有效且稳定**：全量 3,734 配方的 MAE 中位 1.74pp，197 样本的 1.96pp 与之一致
2. **最大瓶颈是 SR Legacy 覆盖率**（export 失败 0.9%），其次为 SLSQP 收敛（solve 失败 4.3%）
3. **结构约束（ingredient_order、two_percent）有明确收益**，合计降低 MAE 中位 23%
4. **Prior 在当前条件下边际贡献有限**：高辨识度配方不需要，低辨识度配方无法纠偏。在 Branded Food 阶段标签信息更稀疏时价值更大
5. **方法适用条件**：配料化学差异大 → 精确；配料营养同质 → 不可辨识（这是线性模型的数学极限，非工程问题）
