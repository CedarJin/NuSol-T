# NuSol-T 项目进展报告

> 2026-07-06

## 一、总体进度

**Phase 0-4（FNDDS 验证框架）已完成，Phase 5-7 待开发。**

| Phase | 状态 | 交付物 |
|-------|------|--------|
| Phase 0 — 基础框架 | ✅ | Pydantic Schema、NutrientRegistry、YAML 配置、Typer CLI |
| Phase 1 — 数据适配 | ✅ | FNDDS/SR Legacy/Foundation Foods 适配器、Forward Model |
| Phase 2 — Inverse Solver | ✅ | QPSolver (凸QP)、BoundSolver (LP)、Bohn2022Solver |
| Phase 3 — 验证体系 | ✅ | TrustReport、TrustGrade、Validation Metrics、Ablation |
| Phase 4 — 消融实验 | ✅ | G0-G7 消融配置 + YAML 约束配置体系 |
| Phase 5 — Branded Food | ⏳ | 待开发 |
| Phase 6 — 批量 Pipeline | ⏳ | 待开发 |
| Phase 7 — 论文文档 | ⏳ | 待开发 |

## 二、代码规模

| 指标 | 数量 |
|------|------|
| Python 源文件 | 46 |
| 测试文件 | 21 |
| 测试用例 | 208 (100% 通过) |
| YAML 配置文件 | 6 (default + 4 品类 + all_categories) |
| 文档 | 6 (NuSol-T / DEVELOPMENT / DATA / SUMMARY / PROGRESS / CLAUDE) |

## 三、求解器演进

```
Phase 2 初始:  trust-constr + 15 multi-starts  → 6s/recipe,  MAE≈0.08
Phase 2 优化:  + 正确配料顺序 + 硬约束          → 精度改善
Phase 2 优化:  + fortificant 过滤               → MAE 大幅降低
Phase 3 重构:  凸QP + SLSQP (单次求解)         → 30ms/recipe, 200x faster
Phase 3 重构:  LP BoundSolver (HiGHS)           → 1ms/bound, 800x faster
Phase 3 最终:  QPSolver + LP BoundSolver        → 200 recipes / 18秒
```

## 四、200 Recipe Benchmark 结果

| 指标 | 13 nutrients | Big7 only |
|------|-------------|-----------|
| MAE mean | 0.0731 | 0.0840 |
| MAE median | 0.0523 | 0.0815 |
| Coverage (true在区间内) | 99.5% | — |
| 运行时间 | 18 秒 | — |
| Trust A | 25% | — |
| Trust A+B | 46.5% | — |

## 五、与 Bohn et al. (2022) 对比

| 维度 | Bohn 2022 | NuSol-T |
|------|-----------|---------|
| 营养素 | Big7 (7个) | 全部 label nutrients (13) |
| 优化方法 | 约束最小二乘 (R limSolve) | 凸QP + slack + LP bounds |
| 配料映射 | Levenshtein + 人工矫正 | 4级 fallback (ndb→FNDDS→Foundation→fuzzy) |
| 200 recipe MAE (Big7) | 0.1059 | **0.0840** (好 26%) |
| 200 recipe MAE (Full) | — | **0.0731** (好 45%) |
| 不确定性 | ❌ 仅点估计 | ✅ 上下界 + TrustReport |
| 验证 | 无 ground truth | FNDDS 200 recipe 已知配方 |

### MAE 差异分解 (Big7: 0.1059 vs 0.0840)

```
总差距 = 0.0219
  ├── 33% 来自营养素数量 (13 vs 7, 同为 QP)
  └── 67% 来自优化方法 (QP+slack vs 约束 LS)
```

## 六、关键发现

### 1. 配料映射源是 MAE 的主要瓶颈

| 映射源 | 纯源 recipe 数 | Big7 MAE |
|--------|---------------|----------|
| FNDDS self (L1, 同源闭环) | 13 | **0.0198** |
| Foundation Foods (L2, 2026) | 5 | **0.0347** |
| SR Legacy (L3, 2018 冻结) | 14 | 0.1549 |

数据同源时 Big7 近乎完美 (MAE=0.02)。跨数据库映射时误差放大 5-7x。

### 2. P3/P4 软约束在 FNDDS 上无效

所有在外部配料数据上施加的食品科学先验 (能量闭合、水固平衡、钠源、糖源) 在 FNDDS 验证中均增加 MAE。根因：SR Legacy 配料营养值 ≠ FNDDS 内部使用的值 → 先验基于"错误"数据 → 推开真解。

### 3. 硬约束 (unique-source lower bound) 有效

当某个营养素只有唯一配料来源时 (例如果冻中糖 100% 来自水果)，可以从标签下界直接推出该配料的最小比例。这是唯一在 FNDDS 上既有效又不引入误差的 P3 约束。

改善案例：Gelatin dessert MAE 0.112 → 0.011 (10x)。

### 4.SR Legacy MAE 的三个来源

```
30%: 数据不匹配 (SR Legacy 营养值 ≠ FNDDS 内部值)
40%: 欠定 (多个解满足所有约束, solver 无偏好)
30%: 配料不可区分 (两种配料 nutrient profile 几乎相同)
```

## 七、约束配置体系

建立了 YAML 驱动的约束配置体系，支持品类特定约束:

```
config/constraints/
├── default.yaml           # 通用 P0-P4 约束
├── baked_goods.yaml       # 烘焙 (面粉主料先验)
├── dairy_desserts.yaml    # 乳制品/甜点 (相似配料防极端)
├── meat_seafood.yaml      # 肉类/海鲜 (油不超过肉)
├── soups_stews.yaml       # 汤/炖菜 (水为主成分)
└── all_categories.yaml    # 品类汇总
```

## 八、下一步

1. **实现 YAML 约束解析器** — 将约束配置连接到 solver
2. **Phase 5** — Branded Food 适配器完善 + 真实包装食品配料解析
3. **Phase 6** — Branded Food 批量 pipeline + 扩展营养成分估计
4. **FNDDS 端到端验证** — 在 200 recipe 上跑完整 forward→inverse→TrustReport
5. **论文图表** — 方法对比图、消融结果、品类分析
