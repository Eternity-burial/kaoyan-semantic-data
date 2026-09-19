# Direct-Vision Pass 1 语义资产汇总目录 (semantic_inventory)

本项目录存放由 `scripts/generate_semantic_inventory.py` 确定性构建的考研数学 5 本图书（共 4,575 题）全量多模态 Pass 1 原始语义候选词典、共现关系网、反向索引与审计报告。

---

## 目录结构导航

```text
semantic_inventory/
├── README.md                           # 本导航说明文档
├── inventory_manifest.json             # 完备性审计凭证与全文件 SHA256 签名
├── global_stats.json                   # 机器可读的全局统计与多维分布数据
├── summary_report.md                   # 核心问题直接解答与全景统计报告
│
├── candidates/                         # 10 大语义类型候选清单 (JSONL)
│   ├── knowledge.jsonl                 # 知识点候选词典 (含出现频次、学科/来源分布、QID列表)
│   ├── exam_points.jsonl               # 考查角度/考点候选词典
│   ├── used_methods.jsonl              # 实际使用解题方法候选词典
│   ├── alternative_methods.jsonl       # 备选解法候选词典
│   ├── invalid_methods.jsonl           # 失效/违规解法候选词典 (含被违反条件)
│   ├── signals.jsonl                   # 题面解题信号候选词典 (含suggests提示)
│   ├── conditions.jsonl                # 定理假设与适用条件词典 (按 kind 严格隔离)
│   ├── pitfalls.jsonl                  # 常见易错点与避坑策略词典
│   ├── transformations.jsonl           # 关键代数变形/等式转换词典
│   └── bottlenecks.jsonl               # 思维卡点/解题瓶颈词典
│
├── indexes/                            # 高性能双向检索索引 (JSONL)
│   ├── candidate_to_qids.jsonl         # 候选词 -> 题目 QID 列表正向索引
│   ├── qid_to_candidates.jsonl         # 题目 QID -> 全部候选词反向索引
│   └── raw_variant_index.jsonl         # 规范化词 -> 原始自然语言变体索引
│
├── relations/                          # 拓扑共现与角色交叉分析 (JSONL)
│   ├── cooccurrence.jsonl              # 11 种二元语义共现网络对及共现频次
│   ├── cross_type_collisions.jsonl     # 跨语义类型碰撞词典 (如既是知识又是方法)
│   └── method_role_collisions.jsonl    # 方法角色交叉碰撞 (同一方法充当 used/alt/inv)
│
├── context/                            # 语义上下文束 (JSONL)
│   └── candidate_context.jsonl         # 每个候选词的代表性真题情境采样 (最多5题)
│
└── audit/                              # 审计基线与审阅建议 (JSONL / MD)
    ├── anomalies.jsonl                 # 自动化探测的潜在异常与线索提示
    ├── possible_merge_candidates.jsonl # 词法相似/包含建议合并候选 (仅供审阅)
    └── aggregation_report.md           # 深度技术审计报告与后续本体构建路线图
```

---

## 复现与验证指令

```powershell
python scripts/generate_semantic_inventory.py
```

*生成环境：Python 3.11+ · 纯文本确定性算法 · 零外部 API 消耗*
