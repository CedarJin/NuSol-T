# NuSol-T 数据字典

## 数据源

| 数据源 | 文件 | 大小 | 用途 |
|--------|------|------|------|
| FNDDS (Survey Food) | `FoodData_Central_survey_food_json_2024-10-31/surveyDownload.json` | ~250MB | 验证数据：已知配料配方 + 最终营养素 |
| SR Legacy | `FoodData_Central_sr_legacy_food_json_2018-04/FoodData_Central_sr_legacy_food_json_2018-04.json` | ~50MB | 配料营养成分映射库 |
| Branded Food | `FoodData_Central_branded_food_json_2026-04-30/FoodData_Central_branded_food_json_2026-04-30.json` | ~2GB | 真实包装食品标签（Stage 2） |
| Foundation Foods | `FoodData_Central_foundation_food_json_2026-04-30/FoodData_Central_foundation_food_json_2026-04-30.json` | ~80MB | 补充成分数据 |

## FNDDS 数据结构

### SurveyFoods 记录

```json
{
  "fdcId": 2705384,
  "foodCode": "11100000",
  "description": "Milk, NFS",
  "foodNutrients": [
    {
      "nutrient": {"id": 1003, "number": "203", "name": "Protein", "unitName": "g"},
      "amount": 3.33
    }
  ],
  "inputFoods": [
    {
      "ingredientCode": 1077,
      "ingredientDescription": "Milk, whole, 3.25% milkfat, with added vitamin D",
      "ingredientWeight": 40,
      "retentionCode": 0,
      "amount": 40,
      "sequenceNumber": 1
    }
  ]
}
```

### 关键字段

| 字段 | 说明 |
|------|------|
| `fdcId` | FDC 唯一标识 |
| `foodCode` | FNDDS 8 位 food code |
| `foodNutrients[].nutrient.id` | USDA nutrient ID (e.g. 1008=Energy) |
| `foodNutrients[].amount` | 最终食品每 100g 的营养素含量 |
| `inputFoods[].ingredientCode` | 配料编码（NDB 号段或 FNDDS 号段） |
| `inputFoods[].ingredientWeight` | 配料克重 (per 100g 成品) |
| `inputFoods[].retentionCode` | 营养素保留因子代码 |
| `inputFoods[].sequenceNumber` | 配料顺序 |

### FNDDS 验证数据集规模

| 条件 | 可用数量 |
|------|----------|
| 总食品数 | 5,432 |
| 有配料 + 营养素 | 5,431 |
| ≥ 2 配料 | 3,829 |
| ≥ 3 配料 | 2,790 |
| ≥ 5 配料 | 1,379 |
| ≥ 10 配料 | 247 |
| 每食品营养素数 | 65 (统一) |

## SR Legacy 数据结构

### SRLegacyFoods 记录

```json
{
  "fdcId": 167512,
  "ndbNumber": "18634",
  "description": "Butter, salted",
  "foodNutrients": [
    {
      "nutrient": {"id": 1003, "number": "203", "name": "Protein", "unitName": "g"},
      "amount": 0.85
    }
  ]
}
```

### 关键字段

| 字段 | 说明 |
|------|------|
| `fdcId` | FDC 唯一标识 |
| `ndbNumber` | USDA NDB 编号（经典编号体系） |
| `description` | 食品描述 |
| `foodNutrients[].amount` | 每 100g 的营养素含量 |

## 配料映射策略

### 编码体系

FNDDS 的 `ingredientCode` 使用两种编码体系：

| 号段 | 体系 | 示例 | 映射目标 |
|------|------|------|----------|
| 1001-9999 | **NDB 号段** | 1001=黄油, 2003=香料 | SR Legacy `ndbNumber` |
| 100000-99999999 | **FNDDS 号段** | 63200100=Berries NFS | FNDDS `foodCode` |
| 999xxx | **强化营养素** | 999328=Vit D as ingredient | 跳过映射，标记为 fortificant |

### 三级 Fallback 策略

```
FNDDS ingredientCode
    │
    ├── Level 1: 查 SR Legacy.ndbNumber
    │   匹配 (71.7% unique codes)
    │
    ├── Level 2: 查 FNDDS.foodCode  
    │   匹配 (93.8% cumulative)
    │
    └── Level 3: ingredientDescription → SR Legacy 模糊匹配
         ├── 子串匹配 (如 "Onions, red, raw" ⊃ "Onions, raw")
         ├── 词重叠匹配 (如 "REDUCED SODIUM: Ham" → "Ham")
         ├── 手动映射表 (4 codes)
         └── (99.8% cumulative)
```

### 强化营养素处理 (8 codes)

| Code | 描述 | 处理方式 |
|------|------|----------|
| 999328 | Vitamin D as ingredient | 不查 ingredient profile，直接作为对应 nutrient 的源 |
| 999301 | Calcium as ingredient | 同上 |
| 999303 | Iron as ingredient | 同上 |
| 999401 | Vitamin C as ingredient | 同上 |
| 999431 | Folic acid as ingredient | 同上 |
| 999418 | Vitamin B-12 as ingredient | 同上 |
| 999001 | Vitamin B composite in cereals | 同上 |
| 999291 | Fiber, total dietary, as ingredient | 同上 |

这些"配料"是纯营养素强化剂。在 solver 中标记为 `is_fortificant=True`，它们不贡献 mass balance，而是作为对应标签营养素的直接来源处理。

### 手动映射表 (4 codes)

| Code | 描述 | 映射到 |
|------|------|--------|
| 100260 | Spinach, baby | Spinach, raw (ndb=11457) |
| 100261 | Tomato, roma | Tomatoes, red, ripe, raw (ndb=11529) |
| 100299 | Cheese, oaxaca, solid | Cheese, queso fresco (ndb=1267) |
| 11966 | Ketchup, restaurant | Catsup/Ketchup (ndb=11935) |

## Branded Food 数据结构

### BrandedFoods 记录

```json
{
  "fdcId": 1106281,
  "description": "GRANOLA",
  "brandOwner": "MICHELE'S",
  "ingredients": "ORGANIC ROLLED OATS, ORGANIC BROWN SUGAR...",
  "servingSize": 28,
  "servingSizeUnit": "g",
  "foodNutrients": [...],
  "brandedFoodCategory": "Cereal"
}
```

## 营养素编号对照

### USDA Label Nutrients (Big 7 +)

| USDA ID | NDB # | 名称 | 单位 |
|---------|-------|------|------|
| 1008 | 208 | Energy | kcal |
| 1003 | 203 | Protein | g |
| 1004 | 204 | Total lipid (fat) | g |
| 1005 | 205 | Carbohydrate, by difference | g |
| 1079 | 291 | Fiber, total dietary | g |
| 2000 | 269 | Total Sugars | g |
| 1063 | 269.3 | Sugars, added | g |
| 1257 | 605 | Fatty acids, total trans | g |
| 1292 | 606 | Fatty acids, total saturated | g |
| 1253 | 601 | Cholesterol | mg |
| 1093 | 307 | Sodium, Na | mg |
| 1087 | 301 | Calcium, Ca | mg |
| 1089 | 303 | Iron, Fe | mg |
| 1092 | 306 | Potassium, K | mg |
| 1112 | 328 | Vitamin D (D2 + D3) | µg |
