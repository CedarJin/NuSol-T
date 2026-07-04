# NuSol-T Project Instructions

## 项目概述

NuSol-T 是一个面向食物营养成分分析的可扩展统一计算框架。从包装食品的 Nutrition Facts 标签和配料表出发，结合 USDA FoodData Central 数据库，通过约束求解推断配料组成范围，并扩展估计完整的营养成分。

## 开发原则

### TDD 测试驱动开发

- **所有代码必须先写测试，再写实现。**
- 每个 Phase 开始时：
  1. 在 `tests/` 下创建测试文件，写出所有测试用例（红灯）
  2. 实现代码，让测试逐步通过（绿灯）
  3. 跑全量回归，确保不破坏已有功能
- 项目天然适合 TDD：
  - 数学计算可验证（forward nutrition calculation 有 FNDDS ground truth）
  - 约束求解行为可预测（确定输入 → 确定输出）
  - 数据解析是纯函数（配料 string → IngredientTree）
  - FNDDS 是天然黄金标准，适合 regression tests

### 测试分层

| 层级 | 工具 | 覆盖目标 |
|------|------|----------|
| 单元测试 | pytest | 每个模块 ≥ 90% |
| 集成测试 | pytest | 数据流、pipeline 端到端 |
| 回归测试 | pytest + fixtures | 已知 FNDDS recipe 的精确输出 |

### 文档策略

- **不需要每个 Phase 单独写开发文档** — `docs/DEVELOPMENT.md` 已包含完整的分 Phase 任务清单、接口设计和代码示例
- 仅当某个模块逻辑特别复杂时（如 Solver 算法、IngredientParser 状态机），在该 Phase 开始前写简短 spec 确定算法细节
- 总体规划在 `docs/NuSol-T.md`，开发细节在 `docs/DEVELOPMENT.md`

## 项目结构

```
NuSol-T/
├── CLAUDE.md
├── pyproject.toml
├── .gitignore
├── docs/
│   ├── NuSol-T.md         # 总体规划书
│   ├── DEVELOPMENT.md     # 开发文档
│   └── DATA.md            # 数据字典 & 配料映射策略
├── src/
│   └── nusol/             # 核心 Python 包 (src layout)
│       ├── py.typed       # PEP 561 marker
│       ├── __init__.py
│       ├── cli.py         # Typer CLI
│       ├── core/          # Schema, NutrientRegistry, Units, Enums
│       ├── data/          # Data Adapters (FNDDS, Branded, SR Legacy)
│       ├── ingredient/    # Parser, Mapper
│       ├── nutrition/     # Forward Model, Labelize
│       ├── constraints/   # P0-P4 约束系统
│       ├── solver/        # PointSolver, BoundSolver, EnsembleSolver
│       ├── validation/    # Metrics, Ablation
│       ├── report/        # TrustReport, TrustGrade
│       ├── config/        # YAML Loader
│       └── utils/         # Numerics, Logging
├── tests/                 # 测试（镜像 src/nusol/ 结构）
├── config/                # YAML 配置文件
├── scripts/               # 执行脚本
├── notebooks/             # Jupyter 探索
└── output/                # 运行输出 (gitignore)
```

## 数据路径

数据库位于上级目录 `../db/`：

| 文件 | 用途 |
|------|------|
| `../db/FoodData_Central_survey_food_json_2024-10-31/surveyDownload.json` | FNDDS (Survey Food) |
| `../db/FoodData_Central_branded_food_json_2026-04-30/FoodData_Central_branded_food_json_2026-04-30.json` | USDA Branded Food |
| `../db/FoodData_Central_sr_legacy_food_json_2018-04/FoodData_Central_sr_legacy_food_json_2018-04.json` | SR Legacy |
| `../db/FoodData_Central_foundation_food_json_2026-04-30/FoodData_Central_foundation_food_json_2026-04-30.json` | Foundation Foods |

文献：`../paper/`

## 分阶段开发计划

| Phase | 内容 | 预计 |
|-------|------|------|
| **Phase 0** | 基础框架搭建：项目初始化、Schema、NutrientRegistry、YAML 配置 | 3-5 天 |
| **Phase 1** | FNDDS 数据适配 + Forward Calculation：读取数据、复现 recipe calculation | 5-7 天 |
| **Phase 2** | Inverse Solver：约束系统(P0-P4)、Point/Bound/Ensemble Solver | 7-10 天 |
| **Phase 3** | FNDDS Inverse Validation：隐藏真实配方→反推、Labelized Simulation、TrustReport | 7-10 天 |
| **Phase 4** | Ablation Study：G0-G7 消融实验、约束权重校准 | 3-5 天 |
| **Phase 5** | Branded Food Adapter：配料解析器、映射器、标签转换 | 5-7 天 |
| **Phase 6** | Branded Food Application：批量 pipeline、NutrientExpander、报告 | 7-10 天 |
| **Phase 7** | 文档、测试完善、论文准备 | 持续 |

Phase 0-4 = Stage 1 (FNDDS 验证), Phase 5-6 = Stage 2 (Branded Food 应用)

## 技术栈

- **Python 3.12+**, 包管理用 **uv** (https://docs.astral.sh/uv/)
- Pydantic v2 (Schema), SciPy (optimization), Pandas/NumPy
- **Typer** (CLI, 基于 click), PyYAML / OmegaConf (配置)
- pytest (测试), ruff + mypy (代码质量)

### uv 常用命令

```bash
uv sync                    # 安装依赖（根据 pyproject.toml 和 uv.lock）
uv sync --dev              # 含 dev 依赖
uv add <package>           # 添加依赖
uv add --dev <package>     # 添加开发依赖
uv run pytest              # 在项目环境中运行命令
uv run python scripts/xxx.py
uv lock                    # 更新 lock 文件
```

## 编码规范

- **命名**: `snake_case` for functions/variables, `PascalCase` for classes
- **类型注解**: 所有 public 函数必须有完整类型注解
- **Docstring**: Google style (Args, Returns, Raises, Examples)
- **Imports**: stdlib → third-party → local, 按字母序
- **行长**: 100 字符上限
- **数值**: 显式处理 NaN，用 `float` 不用 `int` for nutrient amounts

## 关键设计决策

- **YAML 配置驱动**：保证实验可复现，方便 ablation study
- **三种求解器**：PointSolver（点估计）、BoundSolver（可行区间）、EnsembleSolver（不确定性分布）
- **5 级约束优先级**：P0(硬约束) → P1(法规结构) → P2(标签拟合) → P3(食品科学) → P4(统计先验)
- **TrustReport 而非单纯配料表**：包含 uncertainty、provenance、constraint conflicts、trust grade (A/B/C/D)
- **数据溯源**：所有 nutrient value 记录来源数据库和版本
