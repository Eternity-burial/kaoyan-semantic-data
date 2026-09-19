import os
import sys
import json
import time
import base64
import hashlib
from pathlib import Path
from collections import Counter
import requests

sys.stdout.reconfigure(encoding='utf-8')

API_KEY = "4d89ce9096fa4286970af9ccaf008d19.cqCQqbLIcEnVxd4r"
API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
MODEL_NAME = "glm-4.6v-flashx"

WORKSPACE_ROOT = Path(r"d:\tj\822\考研题库")

# Pricing: GLM-4.6V-FlashX (CNY / 1M tokens)
PRICE_INPUT_PER_M = 0.15
PRICE_OUTPUT_PER_M = 1.50

# --- PASS 1 v1.2 SPECIFICATIONS & VALIDATOR ---
REQUIRED = {
    "schema_version", "qid", "input_assessment", "objective", "signals",
    "knowledge_candidates", "exam_point_candidates", "used_methods",
    "alternative_methods", "invalid_method_candidates", "key_transformations",
    "conditions", "pitfalls", "solution_skeleton", "bottleneck_candidates",
    "problem_form", "question_text_rough", "solution_outline_rough",
    "uncertainties", "confidence", "source_fingerprint", "generation_fingerprint",
}
CAPS = {
    "objective": 3, "signals": 8, "knowledge_candidates": 8,
    "exam_point_candidates": 6, "used_methods": 5,
    "alternative_methods": 4, "invalid_method_candidates": 4,
    "key_transformations": 8, "conditions": 8, "pitfalls": 8,
    "solution_skeleton": 10, "uncertainties": 6, "problem_form": 4,
}
PROBLEM_FORMS = {"选择题", "填空题", "计算题", "证明题", "应用题", "综合题"}
BOTTLENECKS = {"signal_recognition", "knowledge_recall", "method_selection", "validity_check", "key_transformation", "computation", "detail_check"}
CONDITION_KINDS = {"method_validity", "theorem_hypothesis", "domain", "model_assumption"}
FORBIDDEN_INVALID_REASONS = {"无", "只是方法选择不经济", "只是计算复杂", "不够简洁"}

def source_fingerprint(item):
    parts = [item["qid"], item["question"]["sha256"] or ""]
    for page in item["solutions"]:
        parts.extend([str(page["logical_page"]), page["sha256"] or ""])
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()

def generation_fingerprint(source, meta):
    text = "\n".join([source, meta["schema_version"], meta["prompt_sha256"], meta["generator_route"], meta["image_preprocess_version"]])
    return hashlib.sha256(text.encode()).hexdigest()

def walk_evidence(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "evidence":
                if not isinstance(child, list):
                    raise ValueError("evidence must be array")
                yield from child
            else:
                yield from walk_evidence(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_evidence(child)

def validate_record(record, item, meta):
    missing = REQUIRED - set(record)
    if missing:
        return False, f"missing fields: {sorted(missing)}"
    if record["schema_version"] != "pass1.v1.2":
        return False, "schema_version must be pass1.v1.2"
    if record["qid"] != item["qid"]:
        return False, f"qid mismatch: {record['qid']} != {item['qid']}"
    
    ia = record.get("input_assessment", {})
    if not isinstance(ia, dict):
        return False, "input_assessment must be dict"
    for key in ("question_readable", "solution_present", "solution_complete"):
        if not isinstance(ia.get(key), bool):
            return False, f"input_assessment.{key} must be bool"
    if not isinstance(ia.get("visual_issues"), list):
        return False, "input_assessment.visual_issues must be list"
        
    specs = {
        "objective": {"text": str, "evidence": list},
        "signals": {"text": str, "suggests": str, "evidence": list},
        "knowledge_candidates": {"name": str, "role": str, "evidence": list},
        "exam_point_candidates": {"name": str, "description": str, "evidence": list},
        "used_methods": {"name": str, "role": str, "why_selected": str, "evidence": list},
        "alternative_methods": {"name": str, "applicability": str, "reason": str, "evidence": list},
        "invalid_method_candidates": {"name": str, "reason": str, "violated_conditions": list, "evidence": list},
        "key_transformations": {"text": str, "purpose": str, "evidence": list},
        "conditions": {"kind": str, "text": str, "applies_to": str},
        "pitfalls": {"text": str, "failure_mode": str, "prevention": str},
        "solution_skeleton": {"step": str, "purpose": str, "evidence": list},
        "uncertainties": {"text": str, "evidence": list},
    }
    
    for field, shape in specs.items():
        val = record.get(field)
        if not isinstance(val, list):
            return False, f"{field} must be list"
        if len(val) > CAPS[field]:
            return False, f"{field} exceeds cap {CAPS[field]} (has {len(val)})"
        for index, child in enumerate(val):
            if not isinstance(child, dict):
                return False, f"{field}[{index}] must be dict"
            missing_keys = set(shape) - set(child)
            if missing_keys:
                return False, f"{field}[{index}] missing keys: {missing_keys}"
            for key, typ in shape.items():
                if not isinstance(child[key], typ):
                    return False, f"{field}[{index}].{key} wrong type (expected {typ}, got {type(child[key])})"
                    
    if not isinstance(record.get("bottleneck_candidates"), list):
        return False, "bottleneck_candidates must be list"
    if not isinstance(record.get("problem_form"), list):
        return False, "problem_form must be list"
    if any(x not in BOTTLENECKS for x in record["bottleneck_candidates"]):
        return False, f"invalid bottleneck: {[x for x in record['bottleneck_candidates'] if x not in BOTTLENECKS]}"
    if any(x not in PROBLEM_FORMS for x in record["problem_form"]):
        return False, f"invalid problem_form: {[x for x in record['problem_form'] if x not in PROBLEM_FORMS]}"
    if any(x["role"] not in {"core", "supporting"} for x in record["knowledge_candidates"]):
        return False, "invalid knowledge role (must be core|supporting)"
    if any(x["role"] not in {"main", "auxiliary"} for x in record["used_methods"]):
        return False, "invalid used_methods role (must be main|auxiliary)"
    if any(x["applicability"] not in {"applicable", "uncertain"} for x in record["alternative_methods"]):
        return False, "invalid alternative applicability (must be applicable|uncertain)"
        
    for x in record["invalid_method_candidates"]:
        if not x["violated_conditions"] or any(str(c).strip() in FORBIDDEN_INVALID_REASONS for c in x["violated_conditions"]):
            return False, "invalid_method violated_conditions must be substantive and non-empty"
            
    if any(x["kind"] not in CONDITION_KINDS for x in record["conditions"]):
        return False, f"invalid condition kind: {[x['kind'] for x in record['conditions'] if x['kind'] not in CONDITION_KINDS]}"
        
    allowed_ev = {item["question"]["evidence"], *(p["evidence"] for p in item["solutions"])}
    for ev in walk_evidence(record):
        if ev not in allowed_ev:
            return False, f"evidence {ev!r} not in allowed {allowed_ev}"
            
    if not any("question" in x["evidence"] for x in record["objective"]):
        return False, "objective lacks question evidence"
        
    for signal in record["signals"]:
        if signal["evidence"] != ["question"]:
            return False, f"signal evidence must strictly be ['question'], got {signal['evidence']}"
            
    conf = record.get("confidence", {})
    if not isinstance(conf, dict) or any(not isinstance(v, (int, float)) or not 0 <= v <= 1 for v in conf.values()):
        return False, "invalid confidence dict"
        
    return True, "OK"

# --- FIXED PASS 1 SYSTEM PROMPT ---
PASS1_SYSTEM_PROMPT = """你是一个考研数学多模态语义分析专家。你的任务是对输入的考研数学题目及解答进行 Pass 1 语义理解与结构化建模。

你必须严格输出且仅输出一个纯 JSON 对象，不得包含任何 Markdown 代码块（如 ```json），不得输出任何解释文本。

### 1. 核心原则与字段规则
1. **objective** (<= 3): 题面最终求值或证明的目标。每项包含 text 和 evidence，evidence 必须包含 "question"。
2. **signals** (<= 8): 【最严格规则】学生在没有看到解析之前，仅凭题面即可直接观察到的结构、措辞、公式形态、图形或条件组合，以及它提示（suggests）的思路。
   - **硬性约束**：所有 signals 的 evidence 必须严格且仅仅为 `["question"]`！绝对禁止出现 solution 步骤或解析推导结果（例如辅助函数构造、变量替换等均属于解法步骤，不是 Signal）。
3. **knowledge_candidates** (<= 8): 涉及的高等数学/线性代数/概率论稳定数学知识点。
   - 字段：name, role ("core" | "supporting"), evidence。
4. **exam_point_candidates** (<= 6): 知识点在考研真题中的具体考查方式。
   - 字段：name, description, evidence。
5. **used_methods** (<= 5): 解析中实际使用的方法。
   - 字段：name, role ("main" | "auxiliary"), why_selected, evidence (通常来自 solution:1 等)。
6. **alternative_methods** (<= 4): 数学上可行但本题解析未采用的其他合理路径。
   - 字段：name, applicability ("applicable" | "uncertain"), reason, evidence。
7. **invalid_method_candidates** (<= 4): 表面貌似可用、但因违反明确必要条件而无法使用的数学方法/定理。
   - 字段：name, reason, violated_conditions (必须包含具体违反条件的非空数组，禁止填写"无"或"计算复杂"), evidence。若无明显无效方法请置为空数组 []。
8. **key_transformations** (<= 8): 解题中的关键代数变形/关键等式转换。
   - 字段：text, purpose, evidence。
9. **conditions** (<= 8): 解题中涉及的数学条件或定理适用前提。
   - 字段：kind, text, applies_to。kind 必须严格属于以下四种之一：
     - "method_validity": 方法/公式适用条件（如洛必达条件、分部积分可导性）
     - "theorem_hypothesis": 数学定理假设（如中值定理闭区间连续开区间可导）
     - "domain": 定义域/取值约束
     - "model_assumption": 概率模型假设（如独立同分布）
10. **pitfalls** (<= 8): 常见易错点、误区及规避方式。
    - 字段：text, failure_mode, prevention。
11. **solution_skeleton** (<= 10): 解答的主干步骤纲要。
    - 字段：step, purpose, evidence。
12. **bottleneck_candidates**: 思维卡点/瓶颈，取自集合：
    ["signal_recognition", "knowledge_recall", "method_selection", "validity_check", "key_transformation", "computation", "detail_check"]
13. **problem_form**: 题型，数组元素只能来自：
    ["选择题", "填空题", "计算题", "证明题", "应用题", "综合题"]
14. **question_text_rough**: 粗略识别的题面文本内容。
15. **solution_outline_rough**: 粗略的解析全貌概括。
16. **uncertainties** (<= 6): 题面或解析存在的真正模糊点（通常为空数组 []）。每项为 {"text": "...", "evidence": [...]}。
17. **confidence**: {"vision": 0.95, "semantic": 0.95, "overall": 0.95}。
18. **input_assessment**:
    {"question_readable": true, "solution_present": true, "solution_complete": true, "visual_issues": []}

### 2. 参考示例 (Few-Shot)
【示例 1 - 概率论】
QID: math::强化36讲::概率论::lec01::ex_1-5
输出片段：
{
  "schema_version": "pass1.v1.2",
  "qid": "math::强化36讲::概率论::lec01::ex_1-5",
  "input_assessment": {"question_readable": true, "solution_present": true, "solution_complete": true, "visual_issues": []},
  "objective": [{"text": "证明三个事件交集概率之和的两个不等式", "evidence": ["question"]}],
  "signals": [
    {"text": "题面给出任意事件A、B、C，并比较P(AB)、P(AC)、P(BC)与单事件概率", "suggests": "先观察事件包含关系和容斥展开", "evidence": ["question"]},
    {"text": "第二问额外给出P(ABC)=1/2", "suggests": "使用三事件容斥式把已知三重交集带入", "evidence": ["question"]}
  ],
  "knowledge_candidates": [
    {"name": "概率单调性", "role": "core", "evidence": ["solution:1"]},
    {"name": "三事件容斥公式", "role": "core", "evidence": ["solution:2"]}
  ],
  "exam_point_candidates": [
    {"name": "事件包含与容斥不等式", "description": "用AB⊆B等包含关系证明第一问，再用并集概率不超过1处理第二问", "evidence": ["solution:1", "solution:2"]}
  ],
  "used_methods": [
    {"name": "概率单调性", "role": "main", "why_selected": "每个二重交集都包含于相应单事件", "evidence": ["solution:1"]},
    {"name": "容斥展开", "role": "main", "why_selected": "第二问需要保留三重交集项", "evidence": ["solution:2"]}
  ],
  "alternative_methods": [],
  "invalid_method_candidates": [
    {"name": "独立事件乘法公式", "reason": "题目只说任意事件，没有给出A、B、C之间的独立性", "violated_conditions": ["P(A∩B)=P(A)P(B)需要相应事件独立"], "evidence": ["question"]}
  ],
  "key_transformations": [
    {"text": "AB⊆B、AC⊆A、BC⊆C", "purpose": "逐项比较概率", "evidence": ["solution:1"]}
  ],
  "conditions": [
    {"kind": "model_assumption", "text": "A、B、C为同一概率空间中的事件", "applies_to": "概率单调性与容斥"}
  ],
  "pitfalls": [
    {"text": "把交集写成并集", "failure_mode": "包含关系方向反转", "prevention": "先写AB⊆B等集合关系"}
  ],
  "solution_skeleton": [
    {"step": "逐项使用事件包含和概率单调性", "purpose": "证明第一问", "evidence": ["solution:1"]},
    {"step": "展开三事件并集并利用其概率不超过1", "purpose": "证明第二问", "evidence": ["solution:2"]}
  ],
  "bottleneck_candidates": ["signal_recognition", "validity_check"],
  "problem_form": ["证明题"],
  "question_text_rough": "任意事件A、B、C，证明交集概率和的上界及给定三重交集时的下界",
  "solution_outline_rough": "第一问由交集包含关系得出；第二问用容斥公式和P(A∪B∪C)≤1移项",
  "uncertainties": [],
  "confidence": {"vision": 0.99, "semantic": 0.95, "overall": 0.96}
}
"""

PROMPT_SHA256 = hashlib.sha256(PASS1_SYSTEM_PROMPT.encode("utf-8")).hexdigest()

BATCH_META = {
    "schema_version": "pass1.v1.2",
    "prompt_sha256": PROMPT_SHA256,
    "generator_route": "zhipu_glm_4_6v_flashx",
    "image_preprocess_version": "original_or_tiled.v1"
}

def load_calibration_manifest():
    import tarfile
    tar_path = Path(r"C:\Users\Zhangwh\Downloads\astra_pass1_v1_2_calibration.tar.gz")
    tf = tarfile.open(tar_path)
    f = tf.extractfile("handoff/pass1_v1_2_calibration/calibration_input_manifest.jsonl")
    items = [json.loads(line) for line in f]
    return {item["qid"]: item for item in items}

def run_test():
    manifest_by_qid = load_calibration_manifest()
    
    # Select 3 test questions: 1 高数, 1 线代, 1 概率论
    test_qids = [
        "math::强化36讲::高数::lec01::ex_1-6",
        "math::强化36讲::线代::lec05::ex_5-1",
        "math::强化36讲::概率论::lec01::ex_1-5"
    ]
    
    results = []
    
    print(f"=== 开始测试 智谱 {MODEL_NAME} 在 3 道考研题目上的 Pass 1 表现 ===")
    print(f"Prompt SHA256: {PROMPT_SHA256}")
    print("=" * 70)
    
    for idx, qid in enumerate(test_qids, 1):
        item = manifest_by_qid[qid]
        print(f"\n[{idx}/3] 测试 QID: {qid}")
        print(f"学科: {item['discipline']}, 章节: {item['chapter_name']}, 标签: {item['display_label']}")
        print(f"解析页数: {len(item['solutions'])} 页")
        
        # Build user message with images
        q_path = WORKSPACE_ROOT / item["question"]["path"]
        with open(q_path, "rb") as f:
            b64_q = base64.b64encode(f.read()).decode("utf-8")
            
        user_content = [
            {
                "type": "text",
                "text": f"请针对题目 QID: {qid} 进行 Pass 1 语义分析。\n学科: {item['discipline']}\n章节: {item['chapter_name']}\n题目图像（evidence: question）："
            },
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64_q}"}
            }
        ]
        
        for p in item["solutions"]:
            sol_path = WORKSPACE_ROOT / p["path"]
            with open(sol_path, "rb") as f:
                b64_sol = base64.b64encode(f.read()).decode("utf-8")
            user_content.append({
                "type": "text",
                "text": f"解答第{p['logical_page']}页图像（evidence: {p['evidence']}）："
            })
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64_sol}"}
            })
            
        user_content.append({
            "type": "text",
            "text": "请直接输出完整的 Pass 1 v1.2 JSON 对象（无 markdown 标记）："
        })
        
        # Test Mode: Thinking disabled (Tier 1 fast direct mode)
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": PASS1_SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            "thinking": {"type": "disabled"},
            "temperature": 0.1
        }
        
        t0 = time.time()
        try:
            resp = requests.post(API_URL, headers=headers, json=payload, timeout=90)
            latency = time.time() - t0
        except Exception as e:
            print(f"API 请求异常: {e}")
            continue
            
        if resp.status_code != 200:
            print(f"API 返回错误状态码: {resp.status_code}, 内容: {resp.text}")
            continue
            
        resp_json = resp.json()
        usage = resp_json.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        cached_tokens = usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
        
        # Calculate cost in CNY
        cost_cny = (prompt_tokens / 1_000_000 * PRICE_INPUT_PER_M) + (completion_tokens / 1_000_000 * PRICE_OUTPUT_PER_M)
        
        print(f"  HTTP 状态: 200, 耗时: {latency:.2f}s")
        print(f"  Token 消耗: 输入 {prompt_tokens} (缓存命中 {cached_tokens}), 输出 {completion_tokens}, 合计 {prompt_tokens + completion_tokens}")
        print(f"  预估费用: ¥{cost_cny:.5f}")
        
        raw_content = resp_json["choices"][0]["message"].get("content", "").strip()
        
        # Strip code block if present
        if raw_content.startswith("```"):
            lines = raw_content.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            raw_content = "\n".join(lines).strip()
            
        try:
            parsed_record = json.loads(raw_content)
        except Exception as e:
            print(f"  [FAIL] JSON 解析失败: {e}")
            print(f"  原始返回片段: {raw_content[:300]}")
            continue
            
        # Attach fingerprints
        src_fp = source_fingerprint(item)
        gen_fp = generation_fingerprint(src_fp, BATCH_META)
        parsed_record["source_fingerprint"] = src_fp
        parsed_record["generation_fingerprint"] = gen_fp
        
        # Run validator
        ok, msg = validate_record(parsed_record, item, BATCH_META)
        
        print(f"  Schema 校验结果: {'[PASSED]' if ok else '[FAILED]'} -> {msg}")
        
        # Detailed semantic inspect
        print("  --- 关键语义质量检查 ---")
        print(f"  1. 题面目标 (objective): {[o['text'] for o in parsed_record.get('objective', [])]}")
        signals = parsed_record.get('signals', [])
        print(f"  2. 题面信号 (signals 数量: {len(signals)}):")
        for s in signals:
            ev = s.get('evidence')
            leak = " [LEAK!]" if ev != ["question"] else " [OK]"
            print(f"     - {s.get('text')} -> 提示: {s.get('suggests')} (evidence: {ev}){leak}")
            
        used_m = parsed_record.get('used_methods', [])
        print(f"  3. 采用方法 (used_methods): {[m.get('name') for m in used_m]}")
        alt_m = parsed_record.get('alternative_methods', [])
        print(f"  4. 备选方法 (alternative_methods): {[m.get('name') for m in alt_m]}")
        inv_m = parsed_record.get('invalid_method_candidates', [])
        print(f"  5. 无效方法 (invalid_method_candidates): {[m.get('name') for m in inv_m]}")
        conds = parsed_record.get('conditions', [])
        print(f"  6. 条件类型 (conditions): {[c.get('kind') + ': ' + c.get('text') for c in conds]}")
        skel = parsed_record.get('solution_skeleton', [])
        print(f"  7. 解题步骤 (solution_skeleton 步数: {len(skel)}):")
        for s in skel[:3]:
            print(f"     - 步骤: {s.get('step')} | 目的: {s.get('purpose')} | evidence: {s.get('evidence')}")
        if len(skel) > 3:
            print(f"     - ... (共 {len(skel)} 步)")
            
        print(f"  8. 题型: {parsed_record.get('problem_form')}, 瓶颈: {parsed_record.get('bottleneck_candidates')}")
        
        results.append({
            "qid": qid,
            "discipline": item["discipline"],
            "latency": latency,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cached_tokens": cached_tokens,
            "cost_cny": cost_cny,
            "valid": ok,
            "validation_msg": msg,
            "record": parsed_record
        })
        
    print("\n" + "=" * 70)
    print("=== 测试总结 ===")
    total_cost = sum(r["cost_cny"] for r in results)
    avg_latency = sum(r["latency"] for r in results) / len(results) if results else 0
    passed_count = sum(1 for r in results if r["valid"])
    print(f"总计测试题目: {len(results)}, 校验通过: {passed_count}/{len(results)}")
    print(f"平均耗时: {avg_latency:.2f}s")
    print(f"总计预估费用: ¥{total_cost:.5f} (平均每题 ¥{total_cost/len(results):.5f})")

if __name__ == "__main__":
    run_test()
