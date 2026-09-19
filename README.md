# 考研数学题库 - DirectVision Pass 1 语义标注与题元结构化数据集

[![Schema: pass1.v1.2](https://img.shields.io/badge/Schema-pass1.v1.2-blue.svg)](schemas/pass1.v1.2.schema.json)
[![Coverage: 100%](https://img.shields.io/badge/Coverage-4575%2F4575%20(100%25)-brightgreen.svg)](audit/audit_report.md)
[![Total Cost: ¥27.23](https://img.shields.io/badge/Total%20Cost-%C2%A527.23-orange.svg)](data/cost_ledger.jsonl)

本项目为考研数学题库系统的核心底层认知语义资产，包含 5 部考研数学经典权威图书（《张宇考研数学1000题》、《张宇考研数学基础30讲》、《张宇考研数学强化36讲》、《李范复习全书》、《老姚高数基础强化》）全量 **4,575 道大题与小问** 的多模态视觉理解、题元识别与解题逻辑建模结果。

---

## 目录索引

- [一、 数据集结构与规格](#一-数据集结构与规格)
- [二、 题库覆盖与验收矩阵](#二-题库覆盖与验收矩阵)
- [三、 目录文件组织](#三-目录文件组织)
- [四、 核心 Schema 规范 (pass1.v1.2)](#四-核心-schema-规范-pass1v12)
- [五、 快速使用与查询指南](#五-快速使用与查询指南)
- [六、 生产与复现说明](#六-生产与复现说明)

---

## 一、 数据集结构与规格

| 指标 | 详情 |
| :--- | :--- |
| **标准版本** | Pass 1 v1.2 (Direct-Vision Semantic Extraction Specification) |
| **涵盖图书** | 5 本（基础30讲、强化36讲、1000题、李范全书、老姚高数） |
| **有效题量** | **4,575 题** (唯一 QID，100% 覆盖率，0 缺失，0 重复) |
| **多模态特征** | 包含题面目标、解题信号 (Signals)、核心考点、主选方法、次选/无效方法、关键代数变形、条件约束、避坑指南、解答骨架等 22 项严谨结构化特征 |
| **证据链完备性** | 所有语义特征严格绑定原图证据锚点 (`question`, `solution:1`, `solution:2` 等) |
| **双向密码学指纹**| 每道题目携带 `source_fingerprint` 与 `generation_fingerprint`，防篡改并实现确定性溯源 |

---

## 二、 题库覆盖与验收矩阵

本数据集由 **三级渐进式多模态推理流水线** 执行产出：
1. **Tier 1 (Qwen3.8-Flash)**: 全量主跑，高并发前缀缓存加速；
2. **Tier 2 (GLM-4.6V)**: 旗舰级视觉大模型复核疑难题；
3. **Tier 3 (Qwen3.8-Max)**: 权威仲裁模型分歧。

| 图书名称 | 总题量 | 验收通过数 | 覆盖率 | Tier 1 直出 | Tier 2 二审 | Tier 3 终审 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **《1000题》** | 1,213 题 | 1,213 题 | 100.0% | 967 | 28 | 218 |
| **《基础30讲》** | 888 题 | 888 题 | 100.0% | 583 | 149 | 156 |
| **《强化36讲》** | 464 题 | 464 题 | 100.0% | 289 | 115 | 60 |
| **《李范全书》** | 840 题 | 840 题 | 100.0% | 788 | 52 | 0 |
| **《老姚高数》** | 1,170 题 | 1,170 题 | 100.0% | 1,029 | 141 | 0 |
| **全量总计** | **4,575 题** | **4,575 题** | **100.00%** | **3,656 (79.9%)** | **485 (10.6%)** | **434 (9.5%)** |

---

## 三、 目录文件组织

```text
kaoyan-semantic-data/
├── README.md                           # 本说明文档
├── .gitignore                          # Git 忽略配置
├── data/
│   ├── semantic_raw.jsonl              # [核心交付物] 4,575 题全量 Pass 1 语义特征数据 (20.5 MB)
│   ├── master_structural_manifest.jsonl# [SSOT 清单] 4,575 题全局统一结构清单与物理图像哈希索引 (4.1 MB)
│   └── cost_ledger.jsonl               # [财务账本] 13,743 次多模态 API 调用 Token 与费用审计流水 (3.5 MB)
├── database/
│   └── ai_runs.sqlite                  # [控制状态机] 完整题目流转生命周期与判定数据库 (33.6 MB)
├── schemas/
│   └── pass1.v1.2.schema.json          # Pass 1 v1.2 严格 JSON Schema 定义
├── prompts/
│   └── pass1.v1.2.api.md               # Pass 1 v1.2 视觉语义抽取系统 Prompt 及标准 Few-shot
├── ai_runner/                          # 完整三层渐进式执行引擎源码
│   ├── .env.example                    # API 环境变量配置模板
│   ├── runner/
│   │   ├── three_tier_engine.py        # 三层流转调度核心引擎
│   │   └── production_runner.py        # 多线程生产并发流水线
│   └── validation/
│       └── validator.py                # Schema 校验与指纹生成器
└── audit/
    ├── verify_final.py                 # 全量数据严谨性校验审查脚本
    └── audit_report.md                 # 完工验收审计报告
```

---

## 四、 核心 Schema 规范 (pass1.v1.2)

每条题目记录均遵循严格的 JSON 格式，关键字段定义如下：

```json
{
  "schema_version": "pass1.v1.2",
  "qid": "math::强化36讲::高数::lec01::ex_1-1",
  "input_assessment": {
    "question_readable": true,
    "solution_present": true,
    "solution_complete": true,
    "visual_issues": []
  },
  "objective": [
    { "text": "求函数极限 \lim_{x \to 0} ...", "evidence": ["question"] }
  ],
  "signals": [
    {
      "text": "题面含未定型 \frac{0}{0} 且分子含三角差函数",
      "suggests": "优先考虑等价无穷小代换或泰勒展开",
      "evidence": ["question"]
    }
  ],
  "knowledge_candidates": [
    { "name": "等价无穷小代换", "role": "core", "evidence": ["solution:1"] }
  ],
  "used_methods": [
    { "name": "泰勒展开法", "role": "main", "why_selected": "展开至 x^3 项直接抵消", "evidence": ["solution:1"] }
  ],
  "alternative_methods": [
    { "name": "洛必达法则", "applicability": "applicable", "reason": "连续求导计算量偏大", "evidence": ["solution:1"] }
  ],
  "invalid_method_candidates": [
    { "name": "直接代入法", "reason": "分母为零", "violated_conditions": ["分母极限不能为0"], "evidence": ["question"] }
  ],
  "solution_skeleton": [
    { "step": "将 sin x 展开为 x - x^3/6 + o(x^3)", "purpose": "消除分子低阶无穷小", "evidence": ["solution:1"] }
  ],
  "bottleneck_candidates": ["method_selection", "computation"],
  "problem_form": ["计算题"],
  "source_fingerprint": "...",
  "generation_fingerprint": "..."
}
```

---

## 五、 快速使用与查询指南

### 1. 读取并遍历所有题目
```python
import json

with open("data/semantic_raw.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        item = json.loads(line)
        qid = item["qid"]
        methods = [m["name"] for m in item.get("used_methods", [])]
        print(f"[{qid}] 方法: {', '.join(methods)}")
```

### 2. 运行完整性自检脚本
```powershell
python audit/verify_final.py
```

---

## 六、 生产与复现说明

- **模型配置**:
  - `BAILIAN_API_KEY`: 阿里云百炼平台凭证（用于 Qwen3.8-Flash 与 Qwen3.8-Max）
  - `ZHIPU_API_KEY`: 智谱开放平台凭证（用于 GLM-4.6V）
- **运行命令**:
  ```powershell
  python ai_runner/runner/production_runner.py 5
  ```
- **财务审计**: 全量生产总成本为 **¥27.23 元**，明细详见 [`data/cost_ledger.jsonl`](data/cost_ledger.jsonl)。

---

*考研数学题库研发团队 · 2026年9月*
