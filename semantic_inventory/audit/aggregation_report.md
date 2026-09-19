# Direct-Vision Pass 1 语义汇总深度审计报告 (Aggregation Report)

- **报告版本**: 1.0.0 (Audit Baseline)
- **输入数据 SHA256**: `03ac449d19ef70ec87aead6e90d23a522dcf46ba40bada42a4f179b0860acbba`
- **生成时间**: 2026-09-19 19:11:31

---

## 一、 输入数据完备性与可信度审计

1. **题目覆盖完整性**: 
   - 原始清单 4,575 题全部具有对应的有效 Pass 1 JSON 对象，无任何空缺题目；
   - 唯一 QID 数严格等于 4,575，重复 QID 数量为 0，格式畸变记录为 0；
   - 涵盖 5 本目标全书，高数 3,257 题、线代 712 题、概率论 606 题。

2. **模型与置信度审计**:
   - 平均视觉置信度: **0.9822**
   - 平均语义置信度: **0.9768**
   - 平均总体置信度: **0.9778**
   - 解答完整度分布: 完整解答图占比 **92.0%**，无解答题目仅占极少数。

---

## 二、 方法角色交叉碰撞深度审计 (Method Role Collision)

在考研数学的真实做题语境中，“同一种数学方法”在不同题目中充当了截然不同的认知角色：
- 共计 **463 个方法表面词** 在全库中跨越了 2 个或 3 个不同角色；
- **跨 3 个角色 (used & alternative & invalid) 的典型方法**:
  - **`洛必达法则`**: 在 89 题为主解法，在 150 题为备选解法，在 78 题为失效违规解法 (如 QID `math::1000题::基础篇-高数::ch01::pb_1-23`)
  - **`分部积分法`**: 在 134 题为主解法，在 54 题为备选解法，在 9 题为失效违规解法 (如 QID `math::强化36讲::高数::lec11::ex_11-19`)
  - **`极坐标变换`**: 在 83 题为主解法，在 31 题为备选解法，在 6 题为失效违规解法 (如 QID `math::1000题::强化篇-高数::ch14::pb_14-6`)
  - **`拉格朗日中值定理`**: 在 45 题为主解法，在 54 题为备选解法，在 12 题为失效违规解法 (如 QID `math::1000题::强化篇-高数::ch05::pb_5-14`)
  - **`等价无穷小替换`**: 在 61 题为主解法，在 25 题为备选解法，在 7 题为失效违规解法 (如 QID `math::基础30讲::高数::lec02::ex_2-9`)
  - **`待定系数法`**: 在 59 题为主解法，在 31 题为备选解法，在 1 题为失效违规解法 (如 QID `math::老姚高数::高数::ch12::pb_12-58`)
  - **`参数方程法`**: 在 13 题为主解法，在 62 题为备选解法，在 1 题为失效违规解法 (如 QID `math::1000题::强化篇-高数::ch18::pb_18-14`)
  - **`直接代入法`**: 在 20 题为主解法，在 5 题为备选解法，在 45 题为失效违规解法 (如 QID `math::1000题::基础篇-高数::ch01::pb_1-6`)

> **审计指导建议**：在下一阶段 Canonical Ontology 中，不能简单把“方法”当做单一维度的标签，必须建立 `(Method, Role, Question)` 的关系建模。

---

## 三、 跨类型表面碰撞审计 (Cross-Type Collision)

- 检出 **1325 个表面词** 跨越了多个不同的语义维度。
- **高频跨类型碰撞表面 Top 10**:
  - **`等价无穷小替换`** (跨 5 类: alternative_method, exam_point, invalid_method, knowledge, used_method) | 总频次: 253 次
  - **`极坐标变换`** (跨 5 类: alternative_method, invalid_method, knowledge, transformation, used_method) | 总频次: 143 次
  - **`比值判别法`** (跨 5 类: alternative_method, exam_point, invalid_method, knowledge, used_method) | 总频次: 63 次
  - **`交换积分次序`** (跨 5 类: alternative_method, exam_point, knowledge, transformation, used_method) | 总频次: 55 次
  - **`一阶线性微分方程通解公式`** (跨 5 类: alternative_method, exam_point, invalid_method, knowledge, used_method) | 总频次: 52 次
  - **`正项级数比较判别法`** (跨 5 类: alternative_method, exam_point, invalid_method, knowledge, used_method) | 总频次: 43 次
  - **`洛必达法则`** (跨 4 类: alternative_method, invalid_method, knowledge, used_method) | 总频次: 450 次
  - **`分部积分法`** (跨 4 类: alternative_method, invalid_method, knowledge, used_method) | 总频次: 315 次
  - **`拉格朗日中值定理`** (跨 4 类: alternative_method, invalid_method, knowledge, used_method) | 总频次: 177 次
  - **`待定系数法`** (跨 4 类: alternative_method, invalid_method, knowledge, used_method) | 总频次: 103 次

> **分析**：诸如“泰勒公式”、“拉格朗日中值定理”、“等价无穷小代换”等既被模型识别为知识点（Knowledge），也被识别为主方法（Used Method），甚至在题面被识别为信号（Signal）。这表明大模型对名词性概念和动词性解题动作存在自然语言边界模糊，在构建 Canonical Ontology 时必须严格拆解为 `[Knowledge: 泰勒公式] --(应用于)--> [Method: 泰勒展开法]`。

---

## 四、 潜在异常与审计线索分类统计

审计模块共检出 **15819 条候选异常提示**：

| 异常类型 | 数量 | 严重级别 | 典型特征与处置建议 |
| :--- | :---: | :---: | :--- |
| **超长文本标签 (length_exceeded)** | 6595 | 中 | 文本 > 40 字符，多为整句解析或题面推导泄漏，后续需进行句法截断与核心词提取 |
| **超长单例孤立词 (long_singleton)** | 9075 | 低 | 仅出现 1 次且超长，属于高度题设相关的长尾描述，不宜作为核心本体节点 |
| **极度泛化表面 (generic_surface)** | 0 | 高 | “方法”、“计算”等纯通用词，后续应打标为黑名单停用词或转入顶层抽象范畴 |
| **广泛跨章节弥散 (chapter_diffusion)** | 74 | 低 | 横跨 15+ 章节，多为通用数学手段（如待定系数法、换元法），属于跨模块通用方法 |
| **高频原始变体 (high_raw_variant_count)** | 0 | 中 | 归一化后聚合了 4+ 种原始写法，后续作为词法同义映射规则的坚实来源 |
| **高频失效方法 (high_frequency_invalid_method)** | 10 | 中 | 频繁在多题被判断为无效的方法，是考研数学命题中极具价值的“经典陷阱模型” |
| **极度跨类型混杂 (heavy_cross_type_collision)** | 65 | 高 | 同时在 4+ 个语义字段出现的词汇，需要人工干预明确其本质语义归属 |

---

## 五、 向 Canonical Ontology 推进的实施建议

1. **绝对保留 Raw Surface 溯源性**: 任何规范化映射表必须保留指向原始 QID 与 raw variant 的链条；
2. **知识与方法严格分层**: 将高频重合概念解耦为实体（Concept/Knowledge）与操作（Method/Procedure）；
3. **长尾长句字段采用模式抽取**: 对 Signal, Pitfall, Transformation, Condition 引入微语法（Micro-syntax）抽取，而非简单扁平分类；
4. **人工参与 Possible Merge 审阅**: 基于 `audit/possible_merge_candidates.jsonl`，结合考研考纲与数学规范词表进行同义对齐。
