import os
import sys
import json
import time
import base64
import hashlib
import sqlite3
import threading
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)

WORKSPACE_ROOT = Path(r"d:\tj\822\考研题库")
OUT_DIR = WORKSPACE_ROOT / "handoff" / "api_runner_v1"
DB_PATH = OUT_DIR / "ai_runs.sqlite"
MANIFEST_PATH = OUT_DIR / "master_structural_manifest.jsonl"
SEMANTIC_RAW_PATH = OUT_DIR / "semantic_raw.jsonl"
LEDGER_FILE = OUT_DIR / "cost_ledger.jsonl"

sys.path.insert(0, str(WORKSPACE_ROOT / "scratch"))
sys.path.insert(0, str(OUT_DIR / "ai_runner" / "runner"))

from three_tier_engine import (
    BAILIAN_KEY, BAILIAN_URL,
    ZHIPU_KEY, ZHIPU_URL,
    PASS1_SYSTEM_PROMPT, PROMPT_SHA256,
    validate_record, source_fingerprint, generation_fingerprint,
    PRICING, robust_json_decode, sanitize_record
)

import requests

class ThreadLocalDB:
    _local = threading.local()

    @classmethod
    def get_conn(cls):
        if not hasattr(cls._local, "conn") or cls._local.conn is None:
            cls._local.conn = sqlite3.connect(DB_PATH, timeout=60.0)
            cls._local.conn.execute("PRAGMA journal_mode=WAL;")
            cls._local.conn.execute("PRAGMA busy_timeout=30000;")
        return cls._local.conn

def call_vision_api(model, provider, url, key, item, is_dashscope, thinking=False, prompt_suffix=""):
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

FILE_LOCK = threading.Lock()

def log_cost(conn, qid, tier, provider, model, in_tok, cached_tok, out_tok, cost_cny):
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO costs (qid, tier, provider, model, input_tokens, cached_tokens, output_tokens, estimated_cost_cny, timestamp)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (qid, tier, provider, model, in_tok, cached_tok, out_tok, cost_cny, now_str))
    conn.commit()
    
    entry = {
        "qid": qid, "tier": tier, "provider": provider, "model": model,
        "input_tokens": in_tok, "cached_tokens": cached_tok, "output_tokens": out_tok,
        "estimated_cost_cny": round(cost_cny, 6), "timestamp": now_str
    }
    with FILE_LOCK:
        with open(LEDGER_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def append_accepted_record(record):
    with FILE_LOCK:
        with open(SEMANTIC_RAW_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

def process_question_pipeline(item, attempt=1):
    qid = item["qid"]
    conn = ThreadLocalDB.get_conn()
    cursor = conn.cursor()
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    
    # --- TIER 1: Qwen3.8-Flash ---
    t1_model = "qwen3.8-flash"
    t1_provider = "aliyun_model_studio"
    t1_rec, t1_lat, t1_status, t1_usage = call_vision_api(
        model=t1_model, provider=t1_provider, url=BAILIAN_URL, key=BAILIAN_KEY,
        item=item, is_dashscope=True, thinking=False
    )
    
    in_tok = t1_usage.get("prompt_tokens", 0)
    cached_tok = t1_usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
    out_tok = t1_usage.get("completion_tokens", 0)
    non_cached = max(0, in_tok - cached_tok)
    t1_price = PRICING[t1_model]
    t1_cost = (non_cached / 1_000_000 * t1_price["input"]) + (cached_tok / 1_000_000 * t1_price["cached"]) + (out_tok / 1_000_000 * t1_price["output"])
    log_cost(conn, qid, 1, t1_provider, t1_model, in_tok, cached_tok, out_tok, t1_cost)
    
    escalate_to_t2 = False
    escalate_reason = ""
    accepted_record = None
    final_tier = 1
    
    if not t1_rec:
        escalate_to_t2 = True
        escalate_reason = f"t1_api_fail: {t1_status}"
    else:
        src_fp = source_fingerprint(item)
        batch_meta = {"schema_version": "pass1.v1.2", "prompt_sha256": PROMPT_SHA256, "generator_route": "bailian_qwen3_8_flash", "image_preprocess_version": "original_or_tiled.v1"}
        t1_rec["source_fingerprint"] = src_fp
        t1_rec["generation_fingerprint"] = generation_fingerprint(src_fp, batch_meta)
        t1_rec = sanitize_record(t1_rec, item)
        valid, v_msg = validate_record(t1_rec, item, batch_meta)
        
        cursor.execute("INSERT INTO results (qid, tier, model, schema_valid, validation_msg, result_json, created_at) VALUES (?, 1, ?, ?, ?, ?, ?);",
                       (qid, t1_model, 1 if valid else 0, v_msg, json.dumps(t1_rec, ensure_ascii=False), now_str))
        conn.commit()
        
        reasons = []
        if not valid: reasons.append(f"schema_invalid: {v_msg}")
        if t1_rec.get("uncertainties"): reasons.append("uncertainties_present")
        if item.get("solutions") and (not t1_rec.get("used_methods") or not t1_rec.get("solution_skeleton")):
            reasons.append("empty_methods_or_skeleton_with_solution")
            
        if reasons:
            escalate_to_t2 = True
            escalate_reason = "; ".join(reasons)
        else:
            accepted_record = t1_rec
            cursor.execute("UPDATE questions SET status='accepted', tier_reached=1, final_decision='accepted_tier1', updated_at=? WHERE qid=?;", (now_str, qid))
            conn.commit()
            append_accepted_record(accepted_record)
            return {"qid": qid, "status": "accepted", "tier": 1, "latency": t1_lat, "cost": t1_cost}
            
    # --- TIER 2: GLM-4.6V (6M Free Quota) ---
    final_tier = 2
    cursor.execute("UPDATE questions SET status='tier2_review', tier_reached=2, updated_at=? WHERE qid=?;", (now_str, qid))
    cursor.execute("INSERT INTO reviews (qid, trigger_reason, tier_from, tier_to, status, created_at) VALUES (?, ?, 1, 2, 'pending', ?);", (qid, escalate_reason, now_str))
    conn.commit()
    
    t2_model = "glm-4.6v"
    t2_provider = "zhipu_bigmodel"
    t2_rec, t2_lat, t2_status, t2_usage = call_vision_api(
        model=t2_model, provider=t2_provider, url=ZHIPU_URL, key=ZHIPU_KEY,
        item=item, is_dashscope=False, thinking=False
    )
    
    in_tok2 = t2_usage.get("prompt_tokens", 0)
    out_tok2 = t2_usage.get("completion_tokens", 0)
    log_cost(conn, qid, 2, t2_provider, t2_model, in_tok2, 0, out_tok2, 0.0)
    
    escalate_to_t3 = False
    conflict_reason = ""
    
    if not t2_rec:
        escalate_to_t3 = True
        conflict_reason = f"t2_api_fail: {t2_status}"
    else:
        src_fp = source_fingerprint(item)
        batch_meta2 = {"schema_version": "pass1.v1.2", "prompt_sha256": PROMPT_SHA256, "generator_route": "zhipu_glm_4_6v", "image_preprocess_version": "original_or_tiled.v1"}
        t2_rec["source_fingerprint"] = src_fp
        t2_rec["generation_fingerprint"] = generation_fingerprint(src_fp, batch_meta2)
        t2_rec = sanitize_record(t2_rec, item)
        valid2, v_msg2 = validate_record(t2_rec, item, batch_meta2)
        cursor.execute("INSERT INTO results (qid, tier, model, schema_valid, validation_msg, result_json, created_at) VALUES (?, 2, ?, ?, ?, ?, ?);",
                       (qid, t2_model, 1 if valid2 else 0, v_msg2, json.dumps(t2_rec, ensure_ascii=False), now_str))
        conn.commit()
        
        if not valid2:
            escalate_to_t3 = True
            conflict_reason = f"tier2_schema_invalid: {v_msg2}"
        else:
            accepted_record = t2_rec
            cursor.execute("UPDATE questions SET status='accepted', tier_reached=2, final_decision='accepted_tier2_consensus', updated_at=? WHERE qid=?;", (now_str, qid))
            conn.commit()
            append_accepted_record(accepted_record)
            return {"qid": qid, "status": "accepted", "tier": 2, "latency": t1_lat + t2_lat, "cost": t1_cost}
            
    # --- TIER 3: Qwen3.8-Max (1M Free Quota) ---
    final_tier = 3
    cursor.execute("UPDATE questions SET status='tier3_escalated', tier_reached=3, updated_at=? WHERE qid=?;", (now_str, qid))
    cursor.execute("INSERT INTO reviews (qid, trigger_reason, tier_from, tier_to, status, created_at) VALUES (?, ?, 2, 3, 'pending', ?);", (qid, conflict_reason, now_str))
    conn.commit()
    
    t3_model = "qwen3.8-max"
    t3_provider = "aliyun_model_studio"
    t3_rec, t3_lat, t3_status, t3_usage = call_vision_api(
        model=t3_model, provider=t3_provider, url=BAILIAN_URL, key=BAILIAN_KEY,
        item=item, is_dashscope=True, thinking=False,
        prompt_suffix=f"\n【仲裁提示：前序初审模型存在分歧 ({conflict_reason})，请仔细审视题面与解析，给出最具数学权威性的结构化判定】"
    )
    
    in_tok3 = t3_usage.get("prompt_tokens", 0)
    cached_tok3 = t3_usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
    out_tok3 = t3_usage.get("completion_tokens", 0)
    log_cost(conn, qid, 3, t3_provider, t3_model, in_tok3, cached_tok3, out_tok3, 0.0)
    
    if t3_rec:
        src_fp = source_fingerprint(item)
        batch_meta3 = {"schema_version": "pass1.v1.2", "prompt_sha256": PROMPT_SHA256, "generator_route": "bailian_qwen3_8_max", "image_preprocess_version": "original_or_tiled.v1"}
        t3_rec["source_fingerprint"] = src_fp
        t3_rec["generation_fingerprint"] = generation_fingerprint(src_fp, batch_meta3)
        t3_rec = sanitize_record(t3_rec, item)
        valid3, v_msg3 = validate_record(t3_rec, item, batch_meta3)
        cursor.execute("INSERT INTO results (qid, tier, model, schema_valid, validation_msg, result_json, created_at) VALUES (?, 3, ?, ?, ?, ?, ?);",
                       (qid, t3_model, 1 if valid3 else 0, v_msg3, json.dumps(t3_rec, ensure_ascii=False), now_str))
        cursor.execute("UPDATE questions SET status='accepted', tier_reached=3, final_decision='accepted_tier3_arbitrated', updated_at=? WHERE qid=?;", (now_str, qid))
        conn.commit()
        append_accepted_record(t3_rec)
        return {"qid": qid, "status": "accepted", "tier": 3, "latency": t1_lat + t2_lat + t3_lat, "cost": t1_cost}
    else:
        cursor.execute("UPDATE questions SET status='review_queue', tier_reached=3, final_decision='human_review_needed', updated_at=? WHERE qid=?;", (now_str, qid))
        conn.commit()
        return {"qid": qid, "status": "review_queue", "tier": 3, "latency": t1_lat + t2_lat + t3_lat, "cost": t1_cost}

def run_production_loop(max_workers=5):
    print("=" * 70)
    print("=== Direct-Vision Pass 1 生产流水线 (高容错/极简流转版) 已启动 ===")
    print(f"并发线程: {max_workers} | 数据库: {DB_PATH}")
    print(f"三级架构: Tier 1 (Qwen3.8-Flash 主跑) -> Tier 2 (GLM-4.6V 6M免费额度二审) -> Tier 3 (Qwen3.8-Max 1M免费额度终审)")
    print("优化特性: LaTeX 反斜杠自动清洗已激活 | 无效方法放宽直出 | 极低流转损耗")
    print("=" * 70)
    
    # 1. Load pending items
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT qid FROM questions WHERE status='pending';")
    pending_qids = {r[0] for r in cursor.fetchall()}
    conn.close()
    
    print(f"当前待处理题目总数: {len(pending_qids)} 题")
    if not pending_qids:
        print("所有题目均已处理完成！")
        return
        
    # Match with manifest
    manifest_items = {}
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            it = json.loads(line)
            if it["qid"] in pending_qids:
                manifest_items[it["qid"]] = it
                
    queue = list(manifest_items.values())
    total_in_queue = len(queue)
    print(f"成功装载 {total_in_queue} 道待执行任务。开始并发调度...\n")
    
    start_time = time.time()
    completed = 0
    tier_counts = {1: 0, 2: 0, 3: 0}
    total_cost = 0.0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_question_pipeline, item): item["qid"] for item in queue}
        for fut in as_completed(futures):
            qid = futures[fut]
            completed += 1
            try:
                res = fut.result()
                t = res["tier"]
                tier_counts[t] += 1
                c = res["cost"]
                total_cost += c
                st = res["status"]
                lat = res["latency"]
                print(f"[{completed}/{total_in_queue}] [Tier {t} -> {st}] ({lat:.1f}s, ¥{c:.5f}) {qid}")
            except Exception as exc:
                print(f"[{completed}/{total_in_queue}] [CRITICAL_ERROR] {qid}: {exc}")
                
            # Print milestone summary every 50 questions
            if completed % 50 == 0 or completed == total_in_queue:
                elapsed = time.time() - start_time
                speed = completed / (elapsed / 60) if elapsed > 0 else 0
                remaining = total_in_queue - completed
                eta_min = remaining / speed if speed > 0 else 0
                print("\n" + "-" * 50)
                print(f"【进度报告】已处理: {completed}/{total_in_queue} ({completed/total_in_queue*100:.1f}%)")
                print(f"【层级分布】Tier 1直接验收: {tier_counts[1]} | Tier 2二审验收: {tier_counts[2]} | Tier 3仲裁: {tier_counts[3]}")
                print(f"【累计开销】预估累计费用: ¥{total_cost:.4f} 元")
                print(f"【处理速度】{speed:.1f} 题/分钟 | 预计剩余耗时: {eta_min:.1f} 分钟 ({eta_min/60:.1f} 小时)")
                print("-" * 50 + "\n")
                
    print("\n" + "=" * 70)
    print("=== 全量生产任务已完成！ ===")

if __name__ == "__main__":
    workers = 5
    if len(sys.argv) > 1:
        try:
            workers = int(sys.argv[1])
        except ValueError:
            pass
    run_production_loop(max_workers=workers)
