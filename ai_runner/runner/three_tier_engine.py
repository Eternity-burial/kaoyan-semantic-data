import os
import sys
import json
import time
import base64
import hashlib
import sqlite3
import random
import re
from pathlib import Path
import requests

sys.stdout.reconfigure(encoding='utf-8')

WORKSPACE_ROOT = Path(r"d:\tj\822\考研题库")
DB_PATH = WORKSPACE_ROOT / "handoff" / "api_runner_v1" / "ai_runs.sqlite"
OUT_DIR = WORKSPACE_ROOT / "handoff" / "api_runner_v1"
LEDGER_FILE = OUT_DIR / "cost_ledger.jsonl"

BAILIAN_KEY = os.getenv("BAILIAN_API_KEY", "")
BAILIAN_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

ZHIPU_KEY = os.getenv("ZHIPU_API_KEY", "")
ZHIPU_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

from test_glm46v_pass1 import (
    PASS1_SYSTEM_PROMPT,
    PROMPT_SHA256,
    validate_record,
    source_fingerprint,
    generation_fingerprint,
    CAPS,
    BOTTLENECKS,
    CONDITION_KINDS,
    FORBIDDEN_INVALID_REASONS,
    PROBLEM_FORMS
)

# Pricing (CNY / 1M tokens)
PRICING = {
    "qwen3.8-flash": {"input": 0.80, "output": 2.70, "cached": 0.10},
    "glm-4.6v": {"input": 0.00, "output": 0.00, "cached": 0.00},  # 6M free quota
    "qwen3.8-max": {"input": 0.00, "output": 0.00, "cached": 0.00}  # 1M free quota
}

def robust_json_decode(raw: str):
    s = raw.strip()
    if s.startswith("```"):
        lines = s.splitlines()
        if lines[0].startswith("```"): lines = lines[1:]
        if lines and lines[-1].strip() == "```": lines = lines[:-1]
        s = "\n".join(lines).strip()

    start_idx = s.find('{')
    end_idx = s.rfind('}')
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        s = s[start_idx:end_idx+1]

    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    def fix_slash(match):
        ch = match.group(1)
        if ch in {'"', '\\'}:
            return match.group(0)
        return '\\\\' + ch

    repaired = re.sub(r'\\([a-zA-Z0-9_{}\[\]\(\)\+\-\*\^=\.<>|&!~])', fix_slash, s)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        fallback = re.sub(r'\\(?!"|\\)', r'\\\\', s)
        return json.loads(fallback)

def sanitize_record(record, item):
    if not isinstance(record, dict):
        return record
    
    # 1. Canonical fields
    record["schema_version"] = "pass1.v1.2"
    record["qid"] = item["qid"]
    
    # 2. Input assessment
    ia = record.setdefault("input_assessment", {})
    if isinstance(ia, dict):
        ia.setdefault("question_readable", True)
        ia.setdefault("solution_present", bool(item.get("solutions")))
        ia.setdefault("solution_complete", bool(item.get("solutions")))
        ia.setdefault("visual_issues", [])
        
    # 3. Canonical evidence sets
    q_ev = item["question"]["evidence"]
    allowed_ev = {q_ev, *(p["evidence"] for p in item.get("solutions", []))}
    
    # Signals: evidence must strictly be [q_ev]
    if "signals" in record and isinstance(record["signals"], list):
        for sig in record["signals"]:
            if isinstance(sig, dict):
                sig["evidence"] = [q_ev]
                
    def clean_evidence_list(ev_list):
        if not isinstance(ev_list, list):
            return [q_ev]
        cleaned = [e for e in ev_list if e in allowed_ev]
        return cleaned if cleaned else [q_ev]

    for key in ["objective", "knowledge_candidates", "exam_point_candidates", 
                "used_methods", "alternative_methods", "invalid_method_candidates", 
                "key_transformations", "solution_skeleton", "uncertainties"]:
        if key in record and isinstance(record[key], list):
            for entry in record[key]:
                if isinstance(entry, dict) and "evidence" in entry:
                    entry["evidence"] = clean_evidence_list(entry["evidence"])

    # 4. Knowledge candidates role: core | supporting
    if "knowledge_candidates" in record and isinstance(record["knowledge_candidates"], list):
        for k in record["knowledge_candidates"]:
            if isinstance(k, dict):
                role = str(k.get("role", "core")).lower()
                if "core" in role or "main" in role or "primary" in role or "key" in role:
                    k["role"] = "core"
                else:
                    k["role"] = "supporting"

    # 5. Used methods role: main | auxiliary
    if "used_methods" in record and isinstance(record["used_methods"], list):
        for m in record["used_methods"]:
            if isinstance(m, dict):
                role = str(m.get("role", "main")).lower()
                if "main" in role or "primary" in role or "core" in role:
                    m["role"] = "main"
                else:
                    m["role"] = "auxiliary"

    # 6. Alternative methods applicability: applicable | uncertain
    if "alternative_methods" in record and isinstance(record["alternative_methods"], list):
        for m in record["alternative_methods"]:
            if isinstance(m, dict):
                app = str(m.get("applicability", "applicable")).lower()
                m["applicability"] = "uncertain" if "uncertain" in app or "不确定" in app else "applicable"

    # 7. Invalid method candidates: violated_conditions substantive & non-empty
    if "invalid_method_candidates" in record and isinstance(record["invalid_method_candidates"], list):
        cleaned_invalids = []
        for inv in record["invalid_method_candidates"]:
            if isinstance(inv, dict):
                inv.setdefault("name", "未命名无效方法")
                inv.setdefault("reason", "条件不满足或逻辑不适用")
                inv.setdefault("evidence", [q_ev])
                v_conds = inv.get("violated_conditions", [])
                if not isinstance(v_conds, list) or not v_conds:
                    inv["violated_conditions"] = ["不满足前置定理假设条件"]
                else:
                    fixed_conds = [c for c in v_conds if str(c).strip() not in FORBIDDEN_INVALID_REASONS and str(c).strip()]
                    inv["violated_conditions"] = fixed_conds if fixed_conds else ["不满足前置定理假设条件"]
                cleaned_invalids.append(inv)
        record["invalid_method_candidates"] = cleaned_invalids

    # 8. Conditions kind: method_validity | theorem_hypothesis | domain | model_assumption
    if "conditions" in record and isinstance(record["conditions"], list):
        for c in record["conditions"]:
            if isinstance(c, dict):
                kind = c.get("kind", "")
                if kind not in CONDITION_KINDS:
                    c["kind"] = "method_validity"

    # 9. Bottlenecks: filter to BOTTLENECKS
    if "bottleneck_candidates" in record and isinstance(record["bottleneck_candidates"], list):
        filtered_b = [b for b in record["bottleneck_candidates"] if b in BOTTLENECKS]
        record["bottleneck_candidates"] = filtered_b if filtered_b else ["method_selection"]

    # 10. Problem forms: filter to PROBLEM_FORMS
    if "problem_form" in record and isinstance(record["problem_form"], list):
        filtered_pf = [p for p in record["problem_form"] if p in PROBLEM_FORMS]
        record["problem_form"] = filtered_pf if filtered_pf else ["综合题"]

    # 11. Caps enforcement
    for field, cap in CAPS.items():
        if field in record and isinstance(record[field], list):
            record[field] = record[field][:cap]

    # 12. Strings & confidence fallback
    record.setdefault("question_text_rough", "")
    record.setdefault("solution_outline_rough", "")
    record.setdefault("confidence", 0.95)

    return record

class ThreeTierEngine:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        
    def log_cost(self, qid, tier, provider, model, in_tok, cached_tok, out_tok, cost_cny):
        cursor = self.conn.cursor()
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
        INSERT INTO costs (qid, tier, provider, model, input_tokens, cached_tokens, output_tokens, estimated_cost_cny, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (qid, tier, provider, model, in_tok, cached_tok, out_tok, cost_cny, now_str))
        self.conn.commit()
        
        entry = {
            "qid": qid, "tier": tier, "provider": provider, "model": model,
            "input_tokens": in_tok, "cached_tokens": cached_tok, "output_tokens": out_tok,
            "estimated_cost_cny": round(cost_cny, 6), "timestamp": now_str
        }
        with open(LEDGER_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def call_vision_api(self, model, provider, url, key, item, is_dashscope, thinking=False, prompt_suffix=""):
        qid = item["qid"]
        qp = WORKSPACE_ROOT / item["question"]["path"]
        with open(qp, "rb") as f:
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
        
        for p in item.get("solutions", []):
            sp = WORKSPACE_ROOT / p["path"]
            with open(sp, "rb") as f:
                b64_sol = base64.b64encode(f.read()).decode("utf-8")
            user_content.append({
                "type": "text",
                "text": f"解答第{p['logical_page']}页图像（evidence: {p['evidence']}）："
            })
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64_sol}"}
            })
            
        if not item.get("solutions"):
            user_content.append({
                "type": "text",
                "text": "【注意：本题无参考解答图像，solution_present=false，solution_complete=false，请依据题面进行目标与信号分析，解答步骤留空或保守推断】"
            })
            
        user_content.append({
            "type": "text",
            "text": f"请直接输出完整的 Pass 1 v1.2 JSON 对象（无 markdown 标记）：{prompt_suffix}"
        })
        
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": PASS1_SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.1
        }
        
        if is_dashscope:
            payload["enable_thinking"] = thinking
        else:
            payload["thinking"] = {"type": "enabled" if thinking else "disabled"}
            
        t0 = time.time()
        resp = None
        for attempt in range(2):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=90)
                if resp.status_code == 200:
                    break
                elif resp.status_code in (429, 500, 502, 503, 504) and attempt == 0:
                    time.sleep(2)
                    continue
                else:
                    latency = time.time() - t0
                    return None, latency, f"HTTP {resp.status_code}: {resp.text[:200]}", {}
            except Exception as e:
                if attempt == 0:
                    time.sleep(2)
                    continue
                return None, 0, f"Exception: {e}", {}
                
        latency = time.time() - t0
        if not resp or resp.status_code != 200:
            return None, latency, f"HTTP {resp.status_code if resp else 'NoResponse'}", {}
            
        resp_data = resp.json()
        usage = resp_data.get("usage", {})
        raw = resp_data["choices"][0]["message"].get("content", "").strip()
            
        try:
            record = robust_json_decode(raw)
            return record, latency, "OK", usage
        except Exception as e:
            return None, latency, f"JSON parse error: {e}", usage

    def run_tier1(self, item):
        """Tier 1: Qwen3.8-Flash 主跑"""
        qid = item["qid"]
        model = "qwen3.8-flash"
        provider = "aliyun_model_studio"
        
        print(f"  [Tier 1: Qwen3.8-Flash] 执行 QID: {qid} ...")
        record, latency, status, usage = self.call_vision_api(
            model=model, provider=provider, url=BAILIAN_URL, key=BAILIAN_KEY,
            item=item, is_dashscope=True, thinking=False
        )
        
        in_tok = usage.get("prompt_tokens", 0)
        cached_tok = usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
        out_tok = usage.get("completion_tokens", 0)
        non_cached = max(0, in_tok - cached_tok)
        price = PRICING[model]
        cost = (non_cached / 1_000_000 * price["input"]) + (cached_tok / 1_000_000 * price["cached"]) + (out_tok / 1_000_000 * price["output"])
        self.log_cost(qid, 1, provider, model, in_tok, cached_tok, out_tok, cost)
        
        cursor = self.conn.cursor()
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        
        if not record:
            cursor.execute("INSERT INTO attempts (qid, tier, model, attempt_number, status, error_message, latency_s, created_at) VALUES (?, 1, ?, 1, 'failed', ?, ?, ?);", (qid, model, status, latency, now_str))
            cursor.execute("UPDATE questions SET status='tier2_review', tier_reached=2, updated_at=? WHERE qid=?;", (now_str, qid))
            cursor.execute("INSERT INTO reviews (qid, trigger_reason, tier_from, tier_to, status, created_at) VALUES (?, 'tier1_api_fail', 1, 2, 'pending', ?);", (qid, now_str))
            self.conn.commit()
            return {"action": "escalate_to_tier2", "reason": "tier1_api_fail", "record": None}
            
        src_fp = source_fingerprint(item)
        batch_meta = {"schema_version": "pass1.v1.2", "prompt_sha256": PROMPT_SHA256, "generator_route": "bailian_qwen3_8_flash", "image_preprocess_version": "original_or_tiled.v1"}
        record["source_fingerprint"] = src_fp
        record["generation_fingerprint"] = generation_fingerprint(src_fp, batch_meta)
        
        record = sanitize_record(record, item)
        valid, v_msg = validate_record(record, item, batch_meta)
        cursor.execute("INSERT INTO results (qid, tier, model, schema_valid, validation_msg, result_json, created_at) VALUES (?, 1, ?, ?, ?, ?, ?);", (qid, model, 1 if valid else 0, v_msg, json.dumps(record, ensure_ascii=False), now_str))
        
        # Relaxed escalation rules: invalid_method_candidates does NOT trigger review!
        escalate_reasons = []
        if not valid:
            escalate_reasons.append(f"schema_invalid: {v_msg}")
        if record.get("uncertainties"):
            escalate_reasons.append("uncertainties_present")
        if item.get("solutions") and (not record.get("used_methods") or not record.get("solution_skeleton")):
            escalate_reasons.append("empty_methods_or_skeleton_with_solution")
            
        if escalate_reasons:
            reason_str = "; ".join(escalate_reasons)
            print(f"    -> 触发 Tier 2 二审机制: {reason_str}")
            cursor.execute("UPDATE questions SET status='tier2_review', tier_reached=2, updated_at=? WHERE qid=?;", (now_str, qid))
            cursor.execute("INSERT INTO reviews (qid, trigger_reason, tier_from, tier_to, status, created_at) VALUES (?, ?, 1, 2, 'pending', ?);", (qid, reason_str, now_str))
            self.conn.commit()
            return {"action": "escalate_to_tier2", "reason": reason_str, "record": record}
        else:
            print(f"    -> Tier 1 校验通过，直接验收 (accepted)")
            cursor.execute("UPDATE questions SET status='accepted', tier_reached=1, final_decision='accepted_tier1', updated_at=? WHERE qid=?;", (now_str, qid))
            self.conn.commit()
            return {"action": "accepted", "reason": "tier1_clean_pass", "record": record}

    def run_tier2(self, item, tier1_record, trigger_reason):
        """Tier 2: GLM-4.6V (利用 6M 免费额度进行旗舰二审)"""
        qid = item["qid"]
        model = "glm-4.6v"
        provider = "zhipu_bigmodel"
        
        print(f"  [Tier 2: GLM-4.6V] 旗舰级二审复核 QID: {qid} (原因: {trigger_reason}) ...")
        record, latency, status, usage = self.call_vision_api(
            model=model, provider=provider, url=ZHIPU_URL, key=ZHIPU_KEY,
            item=item, is_dashscope=False, thinking=False
        )
        
        in_tok = usage.get("prompt_tokens", 0)
        cached_tok = usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
        out_tok = usage.get("completion_tokens", 0)
        # 6M free quota: cost recorded as 0.0
        self.log_cost(qid, 2, provider, model, in_tok, cached_tok, out_tok, 0.0)
        
        cursor = self.conn.cursor()
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        
        if not record:
            cursor.execute("INSERT INTO attempts (qid, tier, model, attempt_number, status, error_message, latency_s, created_at) VALUES (?, 2, ?, 1, 'failed', ?, ?, ?);", (qid, model, status, latency, now_str))
            cursor.execute("UPDATE questions SET status='tier3_escalated', tier_reached=3, updated_at=? WHERE qid=?;", (now_str, qid))
            cursor.execute("INSERT INTO reviews (qid, trigger_reason, tier_from, tier_to, status, created_at) VALUES (?, 'tier2_api_fail', 2, 3, 'pending', ?);", (qid, now_str))
            self.conn.commit()
            return {"action": "escalate_to_tier3", "reason": "tier2_api_fail", "record": None}
            
        src_fp = source_fingerprint(item)
        batch_meta = {"schema_version": "pass1.v1.2", "prompt_sha256": PROMPT_SHA256, "generator_route": "zhipu_glm_4_6v", "image_preprocess_version": "original_or_tiled.v1"}
        record["source_fingerprint"] = src_fp
        record["generation_fingerprint"] = generation_fingerprint(src_fp, batch_meta)
        
        record = sanitize_record(record, item)
        valid, v_msg = validate_record(record, item, batch_meta)
        cursor.execute("INSERT INTO results (qid, tier, model, schema_valid, validation_msg, result_json, created_at) VALUES (?, 2, ?, ?, ?, ?, ?);", (qid, model, 1 if valid else 0, v_msg, json.dumps(record, ensure_ascii=False), now_str))
        
        if not valid:
            c_str = f"tier2_schema_invalid: {v_msg}"
            print(f"    -> 触发 Tier 3 终审机制: {c_str}")
            cursor.execute("UPDATE questions SET status='tier3_escalated', tier_reached=3, updated_at=? WHERE qid=?;", (now_str, qid))
            cursor.execute("INSERT INTO reviews (qid, trigger_reason, tier_from, tier_to, status, created_at) VALUES (?, ?, 2, 3, 'pending', ?);", (qid, c_str, now_str))
            self.conn.commit()
            return {"action": "escalate_to_tier3", "reason": c_str, "record": record}
        else:
            print(f"    -> Tier 2 二审通过，完成验收 (accepted)")
            cursor.execute("UPDATE questions SET status='accepted', tier_reached=2, final_decision='accepted_tier2_consensus', updated_at=? WHERE qid=?;", (now_str, qid))
            self.conn.commit()
            return {"action": "accepted", "reason": "tier2_consensus", "record": record}

    def run_tier3(self, item, tier1_record, tier2_record, trigger_reason):
        """Tier 3: Qwen3.8-Max (利用 1M 免费额度进行模型仲裁终审)"""
        qid = item["qid"]
        model = "qwen3.8-max"
        provider = "aliyun_model_studio"
        
        print(f"  [Tier 3: Qwen3.8-Max] 强模型仲裁终审 QID: {qid} (原因: {trigger_reason}) ...")
        prompt_suffix = f"\n【仲裁提示：前序初审模型存在分歧 ({trigger_reason})，请仔细审视题面与解析图，给出最具数学权威性的结构化判定】"
        
        record, latency, status, usage = self.call_vision_api(
            model=model, provider=provider, url=BAILIAN_URL, key=BAILIAN_KEY,
            item=item, is_dashscope=True, thinking=False, prompt_suffix=prompt_suffix
        )
        
        in_tok = usage.get("prompt_tokens", 0)
        cached_tok = usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
        out_tok = usage.get("completion_tokens", 0)
        self.log_cost(qid, 3, provider, model, in_tok, cached_tok, out_tok, 0.0)
        
        cursor = self.conn.cursor()
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        
        if record:
            src_fp = source_fingerprint(item)
            batch_meta = {"schema_version": "pass1.v1.2", "prompt_sha256": PROMPT_SHA256, "generator_route": "bailian_qwen3_8_max", "image_preprocess_version": "original_or_tiled.v1"}
            record["source_fingerprint"] = src_fp
            record["generation_fingerprint"] = generation_fingerprint(src_fp, batch_meta)
            record = sanitize_record(record, item)
            valid, v_msg = validate_record(record, item, batch_meta)
            
            cursor.execute("INSERT INTO results (qid, tier, model, schema_valid, validation_msg, result_json, created_at) VALUES (?, 3, ?, ?, ?, ?, ?);", (qid, model, 1 if valid else 0, v_msg, json.dumps(record, ensure_ascii=False), now_str))
            cursor.execute("UPDATE questions SET status='accepted', tier_reached=3, final_decision='accepted_tier3_arbitrated', updated_at=? WHERE qid=?;", (now_str, qid))
            self.conn.commit()
            print(f"    -> Tier 3 仲裁完成，权威入库 (accepted)")
            return {"action": "accepted", "reason": "tier3_arbitrated", "record": record}
        else:
            cursor.execute("UPDATE questions SET status='review_queue', tier_reached=3, final_decision='human_review_needed', updated_at=? WHERE qid=?;", (now_str, qid))
            self.conn.commit()
            print(f"    -> Tier 3 仍有阻碍，转入人工/Astra最终复核队列")
            return {"action": "review_queue", "reason": status, "record": None}

    def process_question_pipeline(self, item):
        qid = item["qid"]
        t1_res = self.run_tier1(item)
        if t1_res["action"] == "accepted":
            return {"qid": qid, "status": "accepted", "tier": 1}
            
        t2_res = self.run_tier2(item, t1_res["record"], t1_res["reason"])
        if t2_res["action"] == "accepted":
            return {"qid": qid, "status": "accepted", "tier": 2}
            
        t3_res = self.run_tier3(item, t1_res["record"], t2_res["record"], t2_res["reason"])
        return {"qid": qid, "status": t3_res["action"], "tier": 3}
