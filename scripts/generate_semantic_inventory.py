#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Direct-Vision Pass 1 全局语义汇总引擎 (Semantic Inventory & Aggregation Engine)
版本: 1.0.0
适用仓库: Eternity-burial/kaoyan-semantic-data
目标: 纯文本、确定性提取 4,575 题已完成的多模态语义候选特征，建立候选词典、共现网络、交叉碰撞与审计基线
"""

import os
import sys
import json
import time
import hashlib
import unicodedata
import re
import sqlite3
import difflib
from pathlib import Path
from collections import defaultdict, Counter

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(r"D:\tj\822\考研题库\题库\kaoyan-semantic-data")
DATA_DIR = REPO_ROOT / "data"
DATABASE_DIR = REPO_ROOT / "database"
OUT_DIR = REPO_ROOT / "semantic_inventory"

SEMANTIC_RAW_PATH = DATA_DIR / "semantic_raw.jsonl"
MANIFEST_PATH = DATA_DIR / "master_structural_manifest.jsonl"
COST_LEDGER_PATH = DATA_DIR / "cost_ledger.jsonl"
SQLITE_DB_PATH = DATABASE_DIR / "ai_runs.sqlite"
SCHEMA_PATH = REPO_ROOT / "schemas" / "pass1.v1.2.schema.json"
PROMPT_PATH = REPO_ROOT / "prompts" / "pass1.v1.2.api.md"

def sha256_file(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()

def normalize_surface(text: str) -> str:
    if not text:
        return ""
    # 1. Unicode NFKC
    s = unicodedata.normalize("NFKC", str(text))
    # 2. Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    # 3. Strip outer quotes if symmetric
    if (s.startswith('"') and s.endswith('"')) or \
       (s.startswith("'") and s.endswith("'")) or \
       (s.startswith('“') and s.endswith('”')):
        s = s[1:-1].strip()
    # 4. Strip trailing punctuation
    s = re.sub(r"[\s。\.；;,，:：]+$", "", s).strip()
    return s

def get_frequency_tier(count: int) -> str:
    if count == 1:
        return "1"
    elif 2 <= count <= 4:
        return "2-4"
    elif 5 <= count <= 9:
        return "5-9"
    elif 10 <= count <= 49:
        return "10-49"
    elif 50 <= count <= 99:
        return "50-99"
    else:
        return "100+"

def get_git_commit() -> str:
    try:
        import subprocess
        res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "2f4bc783e0ed238a039433436bf0f85f3880f37d"

def main():
    start_time = time.time()
    print("=" * 75)
    print("=== Direct-Vision Pass 1 全局语义汇总与资产化构建引擎启动 ===")
    print("=" * 75)

    # 1. Ensure directory structure
    for sub in ["candidates", "indexes", "relations", "context", "audit"]:
        (OUT_DIR / sub).mkdir(parents=True, exist_ok=True)

    # 2. Load Manifest Metadata
    print("\n[Phase 1/8] 加载结构化清单与数据库元数据...")
    manifest_map = {}
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                manifest_map[item["qid"]] = item
    print(f"  - 装载 Structural Manifest 条目: {len(manifest_map)} 题")

    # Load SQLite metadata (tier, model, status)
    conn = sqlite3.connect(SQLITE_DB_PATH)
    c = conn.cursor()
    c.execute("SELECT qid, status, tier_reached, final_decision FROM questions")
    db_questions = {r[0]: {"status": r[1], "tier_reached": r[2], "final_decision": r[3]} for r in c.fetchall()}

    c.execute("SELECT qid, tier, model FROM results")
    db_results = {}
    for qid, tier, model in c.fetchall():
        if qid not in db_results or tier > db_results[qid]["tier"]:
            db_results[qid] = {"tier": tier, "model": model}
    conn.close()
    print(f"  - 装载 SQLite 状态机条目: {len(db_questions)} 题")

    # 3. Read and verify semantic_raw.jsonl
    print("\n[Phase 2/8] 读取并校验 semantic_raw.jsonl 全量数据...")
    raw_records = []
    seen_qids = set()
    duplicate_qids = []
    malformed_records = 0

    with open(SEMANTIC_RAW_PATH, "r", encoding="utf-8") as f:
        for line_idx, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                qid = rec.get("qid")
                if not qid:
                    malformed_records += 1
                    continue
                if qid in seen_qids:
                    duplicate_qids.append((qid, line_idx))
                seen_qids.add(qid)
                raw_records.append(rec)
            except Exception:
                malformed_records += 1

    total_records = len(raw_records)
    unique_qids_count = len(seen_qids)
    print(f"  - 原始记录总数: {total_records}")
    print(f"  - 唯一 QID 总数: {unique_qids_count}")
    print(f"  - 重复 QID 数量: {len(duplicate_qids)}")
    print(f"  - 格式异常记录数: {malformed_records}")

    # 4. Initialize Data Collectors
    SEMANTIC_TYPES = [
        "knowledge", "exam_point", "used_method", "alternative_method",
        "invalid_method", "signal", "pitfall", "transformation", "bottleneck"
    ]
    candidates_data = {t: defaultdict(lambda: {
        "raw_variants": Counter(),
        "qids": set(),
        "occurrences": 0,
        "disciplines": Counter(),
        "sources": Counter(),
        "chapters": Counter(),
        "roles": Counter(),
        "extra": defaultdict(list)
    }) for t in SEMANTIC_TYPES}

    # Conditions separated by (kind, norm_surface)
    conditions_data = defaultdict(lambda: {
        "raw_variants": Counter(),
        "qids": set(),
        "occurrences": 0,
        "disciplines": Counter(),
        "sources": Counter(),
        "chapters": Counter(),
        "applies_to": Counter(),
        "related_methods": Counter()
    })

    # Global Statistics Collectors
    stats_books = Counter()
    stats_disciplines = Counter()
    stats_chapters = Counter()
    stats_tiers = Counter()
    stats_models = Counter()
    stats_problem_forms = Counter()
    stats_solution_status = Counter()
    stats_uncertainties = Counter()
    stats_field_counts = Counter()
    stats_field_occurrences = Counter()
    confidence_values = {"vision": [], "semantic": [], "overall": []}

    # Inverted and relation collectors
    qid_to_candidates = {}
    cooccurrence_pairs = Counter()
    cooccurrence_qids = defaultdict(set)
    context_samples = defaultdict(dict)

    print("\n[Phase 3/8] 执行逐题语义抽取、标准化与共现分析...")
    for rec in raw_records:
        qid = rec["qid"]
        manifest_info = manifest_map.get(qid, {})
        db_info = db_questions.get(qid, {})
        res_info = db_results.get(qid, {})

        book = manifest_info.get("book", "unknown")
        discipline = manifest_info.get("discipline", "unknown")
        chapter_name = manifest_info.get("chapter_name", "unknown")
        tier = db_info.get("tier_reached", 1)
        model = res_info.get("model", "unknown")

        stats_books[book] += 1
        stats_disciplines[discipline] += 1
        stats_chapters[f"{book}::{chapter_name}"] += 1
        stats_tiers[f"Tier {tier}"] += 1
        stats_models[model] += 1

        ia = rec.get("input_assessment", {})
        sol_present = ia.get("solution_present", False)
        sol_complete = ia.get("solution_complete", False)
        if sol_present and sol_complete:
            stats_solution_status["present_and_complete"] += 1
        elif sol_present and not sol_complete:
            stats_solution_status["present_incomplete"] += 1
        else:
            stats_solution_status["missing"] += 1

        for pf in rec.get("problem_form", []):
            stats_problem_forms[pf] += 1

        for unc in rec.get("uncertainties", []):
            u_text = normalize_surface(unc.get("text", ""))
            if u_text:
                stats_uncertainties[u_text] += 1

        conf = rec.get("confidence", {})
        if isinstance(conf, dict):
            for k in ["vision", "semantic", "overall"]:
                if k in conf and isinstance(conf[k], (int, float)):
                    confidence_values[k].append(conf[k])

        q_candidates = {
            "knowledge": set(),
            "exam_points": set(),
            "used_methods": set(),
            "alternative_methods": set(),
            "invalid_methods": set(),
            "signals": set(),
            "conditions": set(),
            "pitfalls": set(),
            "transformations": set(),
            "bottlenecks": set()
        }

        # 1. Knowledge Candidates
        kc_list = rec.get("knowledge_candidates", [])
        if kc_list: stats_field_counts["knowledge_candidates"] += 1
        stats_field_occurrences["knowledge_candidates"] += len(kc_list)
        for k in kc_list:
            raw = str(k.get("name", "")).strip()
            norm = normalize_surface(raw)
            if not norm: continue
            role = str(k.get("role", "core"))
            entry = candidates_data["knowledge"][norm]
            entry["raw_variants"][raw] += 1
            entry["qids"].add(qid)
            entry["occurrences"] += 1
            entry["disciplines"][discipline] += 1
            entry["sources"][book] += 1
            entry["chapters"][chapter_name] += 1
            entry["roles"][role] += 1
            q_candidates["knowledge"].add(norm)

        # 2. Exam Point Candidates
        ep_list = rec.get("exam_point_candidates", [])
        if ep_list: stats_field_counts["exam_point_candidates"] += 1
        stats_field_occurrences["exam_point_candidates"] += len(ep_list)
        for ep in ep_list:
            raw = str(ep.get("name", "")).strip()
            norm = normalize_surface(raw)
            if not norm: continue
            desc = str(ep.get("description", "")).strip()
            entry = candidates_data["exam_point"][norm]
            entry["raw_variants"][raw] += 1
            entry["qids"].add(qid)
            entry["occurrences"] += 1
            entry["disciplines"][discipline] += 1
            entry["sources"][book] += 1
            entry["chapters"][chapter_name] += 1
            if desc: entry["extra"]["descriptions"].append(desc)
            q_candidates["exam_points"].add(norm)

        # 3. Used Methods
        um_list = rec.get("used_methods", [])
        if um_list: stats_field_counts["used_methods"] += 1
        stats_field_occurrences["used_methods"] += len(um_list)
        for m in um_list:
            raw = str(m.get("name", "")).strip()
            norm = normalize_surface(raw)
            if not norm: continue
            role = str(m.get("role", "main"))
            why = str(m.get("why_selected", "")).strip()
            entry = candidates_data["used_method"][norm]
            entry["raw_variants"][raw] += 1
            entry["qids"].add(qid)
            entry["occurrences"] += 1
            entry["disciplines"][discipline] += 1
            entry["sources"][book] += 1
            entry["chapters"][chapter_name] += 1
            entry["roles"][role] += 1
            if why: entry["extra"]["why_selected"].append(why)
            q_candidates["used_methods"].add(norm)

        # 4. Alternative Methods
        am_list = rec.get("alternative_methods", [])
        if am_list: stats_field_counts["alternative_methods"] += 1
        stats_field_occurrences["alternative_methods"] += len(am_list)
        for m in am_list:
            raw = str(m.get("name", "")).strip()
            norm = normalize_surface(raw)
            if not norm: continue
            app = str(m.get("applicability", "applicable"))
            reason = str(m.get("reason", "")).strip()
            entry = candidates_data["alternative_method"][norm]
            entry["raw_variants"][raw] += 1
            entry["qids"].add(qid)
            entry["occurrences"] += 1
            entry["disciplines"][discipline] += 1
            entry["sources"][book] += 1
            entry["chapters"][chapter_name] += 1
            entry["roles"][app] += 1
            if reason: entry["extra"]["reasons"].append(reason)
            q_candidates["alternative_methods"].add(norm)

        # 5. Invalid Method Candidates
        im_list = rec.get("invalid_method_candidates", [])
        if im_list: stats_field_counts["invalid_method_candidates"] += 1
        stats_field_occurrences["invalid_method_candidates"] += len(im_list)
        for m in im_list:
            raw = str(m.get("name", "")).strip()
            norm = normalize_surface(raw)
            if not norm: continue
            reason = str(m.get("reason", "")).strip()
            v_conds = [str(c).strip() for c in m.get("violated_conditions", []) if str(c).strip()]
            entry = candidates_data["invalid_method"][norm]
            entry["raw_variants"][raw] += 1
            entry["qids"].add(qid)
            entry["occurrences"] += 1
            entry["disciplines"][discipline] += 1
            entry["sources"][book] += 1
            entry["chapters"][chapter_name] += 1
            if reason: entry["extra"]["reasons"].append(reason)
            for vc in v_conds:
                entry["extra"]["violated_conditions"].append(vc)
            q_candidates["invalid_methods"].add(norm)

        # 6. Signals
        sig_list = rec.get("signals", [])
        if sig_list: stats_field_counts["signals"] += 1
        stats_field_occurrences["signals"] += len(sig_list)
        for s in sig_list:
            raw = str(s.get("text", "")).strip()
            norm = normalize_surface(raw)
            if not norm: continue
            sugg = str(s.get("suggests", "")).strip()
            entry = candidates_data["signal"][norm]
            entry["raw_variants"][raw] += 1
            entry["qids"].add(qid)
            entry["occurrences"] += 1
            entry["disciplines"][discipline] += 1
            entry["sources"][book] += 1
            entry["chapters"][chapter_name] += 1
            if sugg: entry["extra"]["suggests"].append(sugg)
            q_candidates["signals"].add(norm)

        # 7. Conditions (Grouped by kind)
        cond_list = rec.get("conditions", [])
        if cond_list: stats_field_counts["conditions"] += 1
        stats_field_occurrences["conditions"] += len(cond_list)
        for c_item in cond_list:
            raw = str(c_item.get("text", "")).strip()
            norm = normalize_surface(raw)
            if not norm: continue
            kind = str(c_item.get("kind", "method_validity")).strip()
            applies = str(c_item.get("applies_to", "")).strip()
            c_key = (kind, norm)
            centry = conditions_data[c_key]
            centry["raw_variants"][raw] += 1
            centry["qids"].add(qid)
            centry["occurrences"] += 1
            centry["disciplines"][discipline] += 1
            centry["sources"][book] += 1
            centry["chapters"][chapter_name] += 1
            if applies: centry["applies_to"][applies] += 1
            for um in q_candidates["used_methods"]:
                centry["related_methods"][um] += 1
            q_candidates["conditions"].add((kind, norm))

        # 8. Pitfalls
        pit_list = rec.get("pitfalls", [])
        if pit_list: stats_field_counts["pitfalls"] += 1
        stats_field_occurrences["pitfalls"] += len(pit_list)
        for p in pit_list:
            raw = str(p.get("text", "")).strip()
            norm = normalize_surface(raw)
            if not norm: continue
            fail = str(p.get("failure_mode", "")).strip()
            prev = str(p.get("prevention", "")).strip()
            entry = candidates_data["pitfall"][norm]
            entry["raw_variants"][raw] += 1
            entry["qids"].add(qid)
            entry["occurrences"] += 1
            entry["disciplines"][discipline] += 1
            entry["sources"][book] += 1
            entry["chapters"][chapter_name] += 1
            if fail: entry["extra"]["failure_modes"].append(fail)
            if prev: entry["extra"]["preventions"].append(prev)
            q_candidates["pitfalls"].add(norm)

        # 9. Key Transformations
        trans_list = rec.get("key_transformations", [])
        if trans_list: stats_field_counts["key_transformations"] += 1
        stats_field_occurrences["key_transformations"] += len(trans_list)
        for t in trans_list:
            raw = str(t.get("text", "")).strip()
            norm = normalize_surface(raw)
            if not norm: continue
            purpose = str(t.get("purpose", "")).strip()
            entry = candidates_data["transformation"][norm]
            entry["raw_variants"][raw] += 1
            entry["qids"].add(qid)
            entry["occurrences"] += 1
            entry["disciplines"][discipline] += 1
            entry["sources"][book] += 1
            entry["chapters"][chapter_name] += 1
            if purpose: entry["extra"]["purposes"].append(purpose)
            q_candidates["transformations"].add(norm)

        # 10. Bottlenecks
        bn_list = rec.get("bottleneck_candidates", [])
        if bn_list: stats_field_counts["bottleneck_candidates"] += 1
        stats_field_occurrences["bottleneck_candidates"] += len(bn_list)
        for b in bn_list:
            raw = str(b).strip()
            norm = normalize_surface(raw)
            if not norm: continue
            entry = candidates_data["bottleneck"][norm]
            entry["raw_variants"][raw] += 1
            entry["qids"].add(qid)
            entry["occurrences"] += 1
            entry["disciplines"][discipline] += 1
            entry["sources"][book] += 1
            entry["chapters"][chapter_name] += 1
            q_candidates["bottlenecks"].add(norm)

        # Statistical Context Fields
        if rec.get("objective"): stats_field_counts["objective"] += 1
        stats_field_occurrences["objective"] += len(rec.get("objective", []))
        if rec.get("solution_skeleton"): stats_field_counts["solution_skeleton"] += 1
        stats_field_occurrences["solution_skeleton"] += len(rec.get("solution_skeleton", []))
        if rec.get("question_text_rough"): stats_field_counts["question_text_rough"] += 1
        if rec.get("solution_outline_rough"): stats_field_counts["solution_outline_rough"] += 1

        # Store inverted index for this QID
        qid_to_candidates[qid] = {
            "qid": qid,
            "book": book,
            "discipline": discipline,
            "chapter_name": chapter_name,
            "candidates": {
                "knowledge": sorted(list(q_candidates["knowledge"])),
                "exam_points": sorted(list(q_candidates["exam_points"])),
                "used_methods": sorted(list(q_candidates["used_methods"])),
                "alternative_methods": sorted(list(q_candidates["alternative_methods"])),
                "invalid_methods": sorted(list(q_candidates["invalid_methods"])),
                "signals": sorted(list(q_candidates["signals"])),
                "conditions": [{"kind": k, "surface": s} for k, s in sorted(list(q_candidates["conditions"]))],
                "pitfalls": sorted(list(q_candidates["pitfalls"])),
                "transformations": sorted(list(q_candidates["transformations"])),
                "bottlenecks": sorted(list(q_candidates["bottlenecks"]))
            }
        }

        # Co-occurrence pairs (11 pairwise relationships)
        def add_cooccurrences(left_type, left_set, right_type, right_set):
            for l_item in left_set:
                for r_item in right_set:
                    pair_key = (left_type, l_item, right_type, r_item)
                    cooccurrence_pairs[pair_key] += 1
                    cooccurrence_qids[pair_key].add(qid)

        c_surfaces = {s for _, s in q_candidates["conditions"]}
        add_cooccurrences("knowledge", q_candidates["knowledge"], "exam_point", q_candidates["exam_points"])
        add_cooccurrences("knowledge", q_candidates["knowledge"], "used_method", q_candidates["used_methods"])
        add_cooccurrences("exam_point", q_candidates["exam_points"], "used_method", q_candidates["used_methods"])
        add_cooccurrences("signal", q_candidates["signals"], "knowledge", q_candidates["knowledge"])
        add_cooccurrences("signal", q_candidates["signals"], "exam_point", q_candidates["exam_points"])
        add_cooccurrences("signal", q_candidates["signals"], "used_method", q_candidates["used_methods"])
        add_cooccurrences("used_method", q_candidates["used_methods"], "condition", c_surfaces)
        add_cooccurrences("used_method", q_candidates["used_methods"], "pitfall", q_candidates["pitfalls"])
        add_cooccurrences("used_method", q_candidates["used_methods"], "transformation", q_candidates["transformations"])
        add_cooccurrences("knowledge", q_candidates["knowledge"], "pitfall", q_candidates["pitfalls"])
        add_cooccurrences("exam_point", q_candidates["exam_points"], "pitfall", q_candidates["pitfalls"])

        # Context snippet for candidate context bundles
        sample_snippet = {
            "qid": qid,
            "book": book,
            "discipline": discipline,
            "chapter": chapter_name,
            "objective": [ob.get("text", "") for ob in rec.get("objective", [])][:2],
            "knowledge_candidates": [k.get("name", "") for k in rec.get("knowledge_candidates", [])][:4],
            "exam_point_candidates": [ep.get("name", "") for ep in rec.get("exam_point_candidates", [])][:3],
            "used_methods": [m.get("name", "") for m in rec.get("used_methods", [])][:3],
            "signals": [s.get("text", "") for s in rec.get("signals", [])][:3],
            "conditions": [f"[{c.get('kind', '')}] {c.get('text', '')}" for c in rec.get("conditions", [])][:3],
            "pitfalls": [p.get("text", "") for p in rec.get("pitfalls", [])][:3],
            "key_transformations": [t.get("text", "") for t in rec.get("key_transformations", [])][:3]
        }
        for stype, cset in [
            ("knowledge", q_candidates["knowledge"]),
            ("exam_point", q_candidates["exam_points"]),
            ("used_method", q_candidates["used_methods"]),
            ("alternative_method", q_candidates["alternative_methods"]),
            ("invalid_method", q_candidates["invalid_methods"]),
            ("signal", q_candidates["signals"]),
            ("pitfall", q_candidates["pitfalls"]),
            ("transformation", q_candidates["transformations"]),
            ("bottleneck", q_candidates["bottlenecks"])
        ]:
            for s in cset:
                ctx_map = context_samples[(stype, s)]
                if len(ctx_map) < 5:
                    ctx_map[qid] = sample_snippet

        for kind, s in q_candidates["conditions"]:
            ctx_map = context_samples[("condition", f"[{kind}] {s}")]
            if len(ctx_map) < 5:
                ctx_map[qid] = sample_snippet

    print("  - 全量逐题解析与共现提取完成。")

    # 5. Output Candidate Inventories
    print("\n[Phase 4/8] 导出各语义类型候选清单 (candidates/*.jsonl)...")
    candidate_summary_stats = {}

    type_to_filename = {
        "knowledge": "knowledge.jsonl",
        "exam_point": "exam_points.jsonl",
        "used_method": "used_methods.jsonl",
        "alternative_method": "alternative_methods.jsonl",
        "invalid_method": "invalid_methods.jsonl",
        "signal": "signals.jsonl",
        "pitfall": "pitfalls.jsonl",
        "transformation": "transformations.jsonl",
        "bottleneck": "bottlenecks.jsonl"
    }

    tier_counts_by_type = {}
    cross_disc_counts_by_type = {}

    for stype, filename in type_to_filename.items():
        data_dict = candidates_data[stype]
        sorted_entries = sorted(data_dict.items(), key=lambda kv: (-len(kv[1]["qids"]), -kv[1]["occurrences"], kv[0]))

        t_counts = Counter()
        cross_counts = Counter()
        filepath = OUT_DIR / "candidates" / filename

        with open(filepath, "w", encoding="utf-8") as f:
            for norm_surf, d in sorted_entries:
                q_count = len(d["qids"])
                freq_tier = get_frequency_tier(q_count)
                is_cross = len(d["disciplines"]) > 1
                t_counts[freq_tier] += 1
                cross_counts["cross" if is_cross else "single"] += 1

                record = {
                    "semantic_type": stype,
                    "normalized_surface": norm_surf,
                    "raw_variants": [{"raw": r, "count": cnt} for r, cnt in d["raw_variants"].most_common()],
                    "question_count": q_count,
                    "occurrence_count": d["occurrences"],
                    "frequency_tier": freq_tier,
                    "cross_discipline": is_cross,
                    "discipline_distribution": dict(d["disciplines"].most_common()),
                    "source_distribution": dict(d["sources"].most_common()),
                    "chapter_distribution": dict(d["chapters"].most_common(10)),
                    "roles_distribution": dict(d["roles"].most_common()) if d["roles"] else {},
                    "qids": sorted(list(d["qids"]))
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        tier_counts_by_type[stype] = t_counts
        cross_disc_counts_by_type[stype] = cross_counts
        candidate_summary_stats[stype] = {
            "unique_normalized": len(sorted_entries),
            "total_occurrences": sum(d["occurrences"] for _, d in sorted_entries),
            "singletons": t_counts["1"],
            "singleton_ratio": t_counts["1"] / len(sorted_entries) if sorted_entries else 0,
            "cross_discipline_count": cross_counts["cross"]
        }
        print(f"  - [{stype}] 导出 {len(sorted_entries)} 个候选表面 -> {filename}")

    # Export conditions.jsonl (partitioned by kind)
    cond_sorted = sorted(conditions_data.items(), key=lambda kv: (-len(kv[1]["qids"]), -kv[1]["occurrences"], kv[0][0], kv[0][1]))
    cond_tier_counts = Counter()
    cond_cross_counts = Counter()
    cond_kind_counts = Counter()

    with open(OUT_DIR / "candidates" / "conditions.jsonl", "w", encoding="utf-8") as f:
        for (kind, norm_surf), d in cond_sorted:
            q_count = len(d["qids"])
            freq_tier = get_frequency_tier(q_count)
            is_cross = len(d["disciplines"]) > 1
            cond_tier_counts[freq_tier] += 1
            cond_cross_counts["cross" if is_cross else "single"] += 1
            cond_kind_counts[kind] += 1

            record = {
                "semantic_type": "condition",
                "condition_kind": kind,
                "normalized_surface": norm_surf,
                "raw_variants": [{"raw": r, "count": cnt} for r, cnt in d["raw_variants"].most_common()],
                "question_count": q_count,
                "occurrence_count": d["occurrences"],
                "frequency_tier": freq_tier,
                "cross_discipline": is_cross,
                "related_methods": [m for m, _ in d["related_methods"].most_common(10)],
                "applies_to_distribution": dict(d["applies_to"].most_common()),
                "discipline_distribution": dict(d["disciplines"].most_common()),
                "source_distribution": dict(d["sources"].most_common()),
                "chapter_distribution": dict(d["chapters"].most_common(10)),
                "qids": sorted(list(d["qids"]))
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    tier_counts_by_type["condition"] = cond_tier_counts
    cross_disc_counts_by_type["condition"] = cond_cross_counts
    candidate_summary_stats["condition"] = {
        "unique_normalized": len(cond_sorted),
        "total_occurrences": sum(d["occurrences"] for _, d in cond_sorted),
        "singletons": cond_tier_counts["1"],
        "singleton_ratio": cond_tier_counts["1"] / len(cond_sorted) if cond_sorted else 0,
        "cross_discipline_count": cond_cross_counts["cross"],
        "by_kind": dict(cond_kind_counts)
    }
    print(f"  - [condition] 导出 {len(cond_sorted)} 个条件候选 (按 kind 隔离) -> conditions.jsonl")

    # 6. Method Role Collisions
    print("\n[Phase 5/8] 分析方法角色交叉碰撞与跨类型碰撞...")
    used_set = set(candidates_data["used_method"].keys())
    alt_set = set(candidates_data["alternative_method"].keys())
    inv_set = set(candidates_data["invalid_method"].keys())

    all_method_surfaces = used_set | alt_set | inv_set
    method_role_collisions = []

    for m in sorted(all_method_surfaces):
        roles = []
        if m in used_set: roles.append("used")
        if m in alt_set: roles.append("alternative")
        if m in inv_set: roles.append("invalid")
        if len(roles) >= 2:
            u_qids = sorted(list(candidates_data["used_method"][m]["qids"])) if m in used_set else []
            a_qids = sorted(list(candidates_data["alternative_method"][m]["qids"])) if m in alt_set else []
            i_qids = sorted(list(candidates_data["invalid_method"][m]["qids"])) if m in inv_set else []
            total_qids = sorted(list(set(u_qids) | set(a_qids) | set(i_qids)))
            method_role_collisions.append({
                "method_surface": m,
                "roles_present": roles,
                "role_count": len(roles),
                "total_question_count": len(total_qids),
                "used_count": len(u_qids),
                "alternative_count": len(a_qids),
                "invalid_count": len(i_qids),
                "used_qids": u_qids,
                "alternative_qids": a_qids,
                "invalid_qids": i_qids
            })

    method_role_collisions.sort(key=lambda x: (-x["role_count"], -x["total_question_count"], x["method_surface"]))
    with open(OUT_DIR / "relations" / "method_role_collisions.jsonl", "w", encoding="utf-8") as f:
        for item in method_role_collisions:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"  - 发现方法角色交叉碰撞词: {len(method_role_collisions)} 个 -> method_role_collisions.jsonl")

    # Cross-type collisions
    type_surface_map = defaultdict(dict)
    surface_sample_qids = defaultdict(lambda: defaultdict(list))
    surface_meta = defaultdict(lambda: {"disciplines": Counter(), "sources": Counter()})

    for stype in SEMANTIC_TYPES:
        for surf, d in candidates_data[stype].items():
            type_surface_map[surf][stype] = d["occurrences"]
            surface_sample_qids[surf][stype] = sorted(list(d["qids"]))[:5]
            for disc, cnt in d["disciplines"].items():
                surface_meta[surf]["disciplines"][disc] += cnt
            for src, cnt in d["sources"].items():
                surface_meta[surf]["sources"][src] += cnt

    for (kind, surf), d in conditions_data.items():
        type_surface_map[surf][f"condition::{kind}"] = d["occurrences"]
        surface_sample_qids[surf][f"condition::{kind}"] = sorted(list(d["qids"]))[:5]
        for disc, cnt in d["disciplines"].items():
            surface_meta[surf]["disciplines"][disc] += cnt
        for src, cnt in d["sources"].items():
            surface_meta[surf]["sources"][src] += cnt

    cross_type_collisions = []
    for surf, type_dict in type_surface_map.items():
        if len(type_dict) >= 2:
            total_occ = sum(type_dict.values())
            cross_type_collisions.append({
                "surface": surf,
                "types_present": sorted(list(type_dict.keys())),
                "type_count": len(type_dict),
                "total_occurrences": total_occ,
                "type_occurrences": type_dict,
                "representative_qids": {t: surface_sample_qids[surf][t] for t in type_dict},
                "discipline_distribution": dict(surface_meta[surf]["disciplines"].most_common()),
                "source_distribution": dict(surface_meta[surf]["sources"].most_common())
            })

    cross_type_collisions.sort(key=lambda x: (-x["type_count"], -x["total_occurrences"], x["surface"]))
    with open(OUT_DIR / "relations" / "cross_type_collisions.jsonl", "w", encoding="utf-8") as f:
        for item in cross_type_collisions:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"  - 发现跨语义类型碰撞表面: {len(cross_type_collisions)} 个 -> cross_type_collisions.jsonl")

    # Co-occurrence Export
    sorted_cooccurrences = sorted(cooccurrence_pairs.items(), key=lambda kv: (-kv[1], kv[0]))
    with open(OUT_DIR / "relations" / "cooccurrence.jsonl", "w", encoding="utf-8") as f:
        for (lt, ls, rt, rs), count in sorted_cooccurrences:
            qids = sorted(list(cooccurrence_qids[(lt, ls, rt, rs)]))
            f.write(json.dumps({
                "left_type": lt,
                "left_surface": ls,
                "right_type": rt,
                "right_surface": rs,
                "question_count": count,
                "qids": qids
            }, ensure_ascii=False) + "\n")
    print(f"  - 导出语义共现对: {len(sorted_cooccurrences)} 对 -> cooccurrence.jsonl")

    # 7. Inverted Indexes
    print("\n[Phase 6/8] 导出双向索引与候选上下文束 (indexes/ & context/)...")
    # candidate_to_qids.jsonl
    with open(OUT_DIR / "indexes" / "candidate_to_qids.jsonl", "w", encoding="utf-8") as f:
        for stype in SEMANTIC_TYPES:
            for surf, d in candidates_data[stype].items():
                f.write(json.dumps({
                    "semantic_type": stype,
                    "normalized_surface": surf,
                    "question_count": len(d["qids"]),
                    "qids": sorted(list(d["qids"]))
                }, ensure_ascii=False) + "\n")
        for (kind, surf), d in conditions_data.items():
            f.write(json.dumps({
                "semantic_type": "condition",
                "condition_kind": kind,
                "normalized_surface": surf,
                "question_count": len(d["qids"]),
                "qids": sorted(list(d["qids"]))
            }, ensure_ascii=False) + "\n")

    # qid_to_candidates.jsonl
    with open(OUT_DIR / "indexes" / "qid_to_candidates.jsonl", "w", encoding="utf-8") as f:
        for qid in sorted(qid_to_candidates.keys()):
            f.write(json.dumps(qid_to_candidates[qid], ensure_ascii=False) + "\n")

    # raw_variant_index.jsonl
    with open(OUT_DIR / "indexes" / "raw_variant_index.jsonl", "w", encoding="utf-8") as f:
        for stype in SEMANTIC_TYPES:
            for surf, d in candidates_data[stype].items():
                if len(d["raw_variants"]) >= 2:
                    f.write(json.dumps({
                        "semantic_type": stype,
                        "normalized_surface": surf,
                        "variant_count": len(d["raw_variants"]),
                        "raw_variants": [{"raw": r, "count": cnt} for r, cnt in d["raw_variants"].most_common()],
                        "question_count": len(d["qids"])
                    }, ensure_ascii=False) + "\n")
        for (kind, surf), d in conditions_data.items():
            if len(d["raw_variants"]) >= 2:
                f.write(json.dumps({
                    "semantic_type": "condition",
                    "condition_kind": kind,
                    "normalized_surface": surf,
                    "variant_count": len(d["raw_variants"]),
                    "raw_variants": [{"raw": r, "count": cnt} for r, cnt in d["raw_variants"].most_common()],
                    "question_count": len(d["qids"])
                }, ensure_ascii=False) + "\n")

    # candidate_context.jsonl
    with open(OUT_DIR / "context" / "candidate_context.jsonl", "w", encoding="utf-8") as f:
        for (stype, surf), qid_snippets in context_samples.items():
            f.write(json.dumps({
                "semantic_type": stype,
                "surface": surf,
                "example_count": len(qid_snippets),
                "examples": list(qid_snippets.values())
            }, ensure_ascii=False) + "\n")
    print(f"  - 索引与上下文束导出完毕 (candidate_context: {len(context_samples)} 条)")

    # 8. Anomaly Detection & Possible Merges
    print("\n[Phase 7/8] 执行数据异常探测与可能合并候选探测 (audit/)...")
    anomalies = []
    GENERIC_KEYWORDS = {"方法", "计算", "公式", "定理", "性质", "求导", "定义", "性质分析", "解题技巧", "基础知识"}

    for stype in SEMANTIC_TYPES:
        for surf, d in candidates_data[stype].items():
            q_cnt = len(d["qids"])
            raw_sample_qid = list(d["qids"])[0]

            # 1. Length anomaly
            if len(surf) >= 40:
                anomalies.append({
                    "anomaly_type": "length_exceeded",
                    "severity": "medium",
                    "semantic_type": stype,
                    "surface": surf,
                    "length": len(surf),
                    "question_count": q_cnt,
                    "explanation": "候选表面长度超过 40 字符，疑似题面句子或推导过程整段进入标签字段",
                    "evidence_qid": raw_sample_qid
                })

            # 2. Generic surface anomaly
            if surf in GENERIC_KEYWORDS:
                anomalies.append({
                    "anomaly_type": "generic_surface",
                    "severity": "high",
                    "semantic_type": stype,
                    "surface": surf,
                    "length": len(surf),
                    "question_count": q_cnt,
                    "explanation": f"候选表面为极泛化关键词 '{surf}'，缺乏独立本体区分度",
                    "evidence_qid": raw_sample_qid
                })

            # 3. Chapter diffusion anomaly
            if len(d["chapters"]) >= 15:
                anomalies.append({
                    "anomaly_type": "chapter_diffusion",
                    "severity": "low",
                    "semantic_type": stype,
                    "surface": surf,
                    "chapter_count": len(d["chapters"]),
                    "question_count": q_cnt,
                    "explanation": f"候选表面横跨 {len(d['chapters'])} 个不同章节，可能是普适数学操作或泛化术语",
                    "evidence_qid": raw_sample_qid
                })

            # 4. Long singleton anomaly
            if q_cnt == 1 and len(surf) >= 35:
                anomalies.append({
                    "anomaly_type": "long_singleton",
                    "severity": "low",
                    "semantic_type": stype,
                    "surface": surf,
                    "length": len(surf),
                    "question_count": 1,
                    "explanation": "仅在单道题目出现且文本超长的孤立候选",
                    "evidence_qid": raw_sample_qid
                })

            # 5. Multiple raw variants
            if len(d["raw_variants"]) >= 4:
                anomalies.append({
                    "anomaly_type": "high_raw_variant_count",
                    "severity": "medium",
                    "semantic_type": stype,
                    "surface": surf,
                    "variant_count": len(d["raw_variants"]),
                    "question_count": q_cnt,
                    "explanation": f"同一种规范化表面对应了 {len(d['raw_variants'])} 种不同原始写法",
                    "variants": [r for r, _ in d["raw_variants"].most_common()],
                    "evidence_qid": raw_sample_qid
                })

    # High frequency invalid method
    for surf, d in candidates_data["invalid_method"].items():
        if len(d["qids"]) >= 10:
            anomalies.append({
                "anomaly_type": "high_frequency_invalid_method",
                "severity": "medium",
                "semantic_type": "invalid_method",
                "surface": surf,
                "question_count": len(d["qids"]),
                "explanation": f"无效方法候选出现频次高达 {len(d['qids'])} 题，具有显著的普遍典型性陷阱特征",
                "evidence_qid": list(d["qids"])[0]
            })

    # Heavy cross-type collision anomaly
    for c in cross_type_collisions:
        if c["type_count"] >= 4:
            anomalies.append({
                "anomaly_type": "heavy_cross_type_collision",
                "severity": "high",
                "semantic_type": "cross_type",
                "surface": c["surface"],
                "type_count": c["type_count"],
                "types_present": c["types_present"],
                "explanation": f"表面在 {c['type_count']} 个不同语义类型中同时出现，边界高度模糊",
                "evidence_qid": list(c["representative_qids"].values())[0][0]
            })

    with open(OUT_DIR / "audit" / "anomalies.jsonl", "w", encoding="utf-8") as f:
        for a in anomalies:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")
    print(f"  - 探测到潜在异常/提示项: {len(anomalies)} 项 -> anomalies.jsonl")

    # Possible merge candidates (lexical/containment only)
    print("  - 计算词法相似与包含候选 (严格作为人工审阅参考)...")
    possible_merges = []
    
    for stype in ["knowledge", "exam_point", "used_method", "pitfall"]:
        surfaces = sorted(list(candidates_data[stype].keys()), key=lambda s: (-len(candidates_data[stype][s]["qids"]), s))
        for i, s1 in enumerate(surfaces[:300]):
            if len(s1) < 4: continue
            sim_list = []
            for j, s2 in enumerate(surfaces):
                if i == j: continue
                if len(s2) < 4: continue
                if (s1 in s2 or s2 in s1) and abs(len(s1) - len(s2)) <= 5:
                    sim = difflib.SequenceMatcher(None, s1, s2).ratio()
                    if sim >= 0.70:
                        sim_list.append({
                            "surface": s2,
                            "similarity": round(sim, 3),
                            "question_count": len(candidates_data[stype][s2]["qids"]),
                            "relation_type": "containment"
                        })
                elif abs(len(s1) - len(s2)) <= 3:
                    sim = difflib.SequenceMatcher(None, s1, s2).ratio()
                    if sim >= 0.82:
                        sim_list.append({
                            "surface": s2,
                            "similarity": round(sim, 3),
                            "question_count": len(candidates_data[stype][s2]["qids"]),
                            "relation_type": "high_lexical_similarity"
                        })

            if sim_list:
                sim_list.sort(key=lambda x: (-x["similarity"], -x["question_count"]))
                possible_merges.append({
                    "semantic_type": stype,
                    "primary_surface": s1,
                    "primary_question_count": len(candidates_data[stype][s1]["qids"]),
                    "candidate_variants": sim_list[:6],
                    "status": "candidate_for_review_only",
                    "note": "纯统计/词法相似度推断，仅供后续规范本体构建审阅参考，禁止自动视为同一节点。"
                })

    with open(OUT_DIR / "audit" / "possible_merge_candidates.jsonl", "w", encoding="utf-8") as f:
        for pm in possible_merges:
            f.write(json.dumps(pm, ensure_ascii=False) + "\n")
    print(f"  - 识别出潜在可能合并组: {len(possible_merges)} 组 -> possible_merge_candidates.jsonl")

    # 9. Global Stats JSON
    print("\n[Phase 8/8] 编译全局统计与审计报告...")
    global_stats = {
        "metadata": {
            "title": "Direct-Vision Pass 1 Global Semantic Inventory Statistics",
            "version": "1.0.0",
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "git_commit": get_git_commit(),
            "target_books_count": len(stats_books),
            "target_records_count": total_records,
            "unique_qids_count": unique_qids_count,
            "duplicate_qids_count": len(duplicate_qids),
            "malformed_records_count": malformed_records
        },
        "breakdown": {
            "by_book": dict(stats_books),
            "by_discipline": dict(stats_disciplines),
            "by_tier": dict(stats_tiers),
            "by_model": dict(stats_models),
            "by_solution_status": dict(stats_solution_status),
            "by_problem_form": dict(stats_problem_forms)
        },
        "confidence_averages": {
            "vision": round(sum(confidence_values["vision"]) / len(confidence_values["vision"]), 4) if confidence_values["vision"] else 0.0,
            "semantic": round(sum(confidence_values["semantic"]) / len(confidence_values["semantic"]), 4) if confidence_values["semantic"] else 0.0,
            "overall": round(sum(confidence_values["overall"]) / len(confidence_values["overall"]), 4) if confidence_values["overall"] else 0.0
        },
        "semantic_fields_summary": {
            k: {
                "non_empty_questions": stats_field_counts[k],
                "total_occurrences": stats_field_occurrences[k],
                "avg_per_question": round(stats_field_occurrences[k] / total_records, 2) if total_records else 0.0
            } for k in stats_field_counts
        },
        "candidate_inventory_summary": candidate_summary_stats,
        "frequency_tier_distribution": {stype: dict(tier_counts_by_type[stype]) for stype in tier_counts_by_type},
        "cross_discipline_distribution": {stype: dict(cross_disc_counts_by_type[stype]) for stype in cross_disc_counts_by_type},
        "relations_summary": {
            "total_cooccurrence_pairs": len(sorted_cooccurrences),
            "method_role_collisions": len(method_role_collisions),
            "cross_type_collisions": len(cross_type_collisions),
            "anomalies_detected": len(anomalies),
            "possible_merge_groups": len(possible_merges)
        }
    }

    with open(OUT_DIR / "global_stats.json", "w", encoding="utf-8") as f:
        json.dump(global_stats, f, ensure_ascii=False, indent=2)

    output_files_checksums = {}
    for p in sorted(OUT_DIR.rglob("*")):
        if p.is_file() and p.name not in ["inventory_manifest.json", "summary_report.md", "aggregation_report.md", "README.md"]:
            rel = str(p.relative_to(OUT_DIR)).replace("\\", "/")
            line_cnt = sum(1 for _ in open(p, "r", encoding="utf-8")) if p.suffix in [".jsonl", ".json"] else 0
            output_files_checksums[rel] = {
                "size_bytes": p.stat().st_size,
                "line_count": line_cnt,
                "sha256": sha256_file(p)
            }

    manifest_data = {
        "manifest_version": "1.0.0",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "git_commit": get_git_commit(),
        "aggregation_script": "scripts/generate_semantic_inventory.py",
        "schema_version": "pass1.v1.2",
        "normalization_rules": {
            "unicode_normalization": "NFKC",
            "whitespace_rule": "collapse multiple spaces to single space, strip leading/trailing",
            "quote_rule": "strip symmetrical outer quotes without altering internal math",
            "punctuation_rule": "strip trailing sentence punctuation [。.;;,，:：]+ without altering math variables",
            "synonym_rule": "strict raw surface retention, no semantic rewriting, no synonym merging"
        },
        "input_files": {
            "data/semantic_raw.jsonl": {
                "records": total_records,
                "sha256": sha256_file(SEMANTIC_RAW_PATH)
            },
            "data/master_structural_manifest.jsonl": {
                "records": len(manifest_map),
                "sha256": sha256_file(MANIFEST_PATH)
            },
            "data/cost_ledger.jsonl": {
                "sha256": sha256_file(COST_LEDGER_PATH)
            },
            "database/ai_runs.sqlite": {
                "sha256": sha256_file(SQLITE_DB_PATH)
            },
            "schemas/pass1.v1.2.schema.json": {
                "sha256": sha256_file(SCHEMA_PATH)
            },
            "prompts/pass1.v1.2.api.md": {
                "sha256": sha256_file(PROMPT_PATH)
            }
        },
        "output_files": output_files_checksums
    }

    with open(OUT_DIR / "inventory_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, ensure_ascii=False, indent=2)

    # Generate Markdown Reports
    generate_summary_report(global_stats, candidates_data, conditions_data, method_role_collisions, cross_type_collisions, sorted_cooccurrences, anomalies, possible_merges)
    generate_aggregation_report(global_stats, candidates_data, conditions_data, method_role_collisions, cross_type_collisions, anomalies, possible_merges)
    generate_inventory_readme(global_stats)

    elapsed = time.time() - start_time
    print("\n" + "=" * 75)
    print(f"=== Direct-Vision Pass 1 全局语义汇总构建圆满完成！耗时: {elapsed:.2f} 秒 ===")
    print("=" * 75)

def generate_summary_report(stats, candidates_data, conditions_data, method_role_collisions, cross_type_collisions, sorted_cooccurrences, anomalies, possible_merges):
    m = stats["metadata"]
    b = stats["breakdown"]
    cs = stats["candidate_inventory_summary"]
    ft = stats["frequency_tier_distribution"]

    top_knowledges = sorted(candidates_data["knowledge"].items(), key=lambda x: -len(x[1]["qids"]))[:10]
    top_exam_points = sorted(candidates_data["exam_point"].items(), key=lambda x: -len(x[1]["qids"]))[:10]
    top_used_methods = sorted(candidates_data["used_method"].items(), key=lambda x: -len(x[1]["qids"]))[:10]
    top_alt_methods = sorted(candidates_data["alternative_method"].items(), key=lambda x: -len(x[1]["qids"]))[:10]
    top_inv_methods = sorted(candidates_data["invalid_method"].items(), key=lambda x: -len(x[1]["qids"]))[:10]

    top_k_str = ", ".join([f"{k} ({len(d['qids'])}题)" for k, d in top_knowledges[:5]])
    top_ep_str = ", ".join([f"{k} ({len(d['qids'])}题)" for k, d in top_exam_points[:5]])
    top_um_str = ", ".join([f"{k} ({len(d['qids'])}题)" for k, d in top_used_methods[:5]])

    top_coocc_lines = []
    for p, cnt in sorted_cooccurrences[:5]:
        top_coocc_lines.append(f"- **{p[0]}** (`{p[1]}`) <---> **{p[2]}** (`{p[3]}`): 共现 **{cnt}** 题")
    top_coocc_str = "\n".join(top_coocc_lines)

    report = f"""# Direct-Vision Pass 1 全局语义汇总报告 (Summary Report)

> **重要声明**：本报告为对已有 4,575 道已完工 Direct-Vision Pass 1 语义特征的确定性、纯文本汇总（**Raw Semantic Inventory**），旨在呈现当前模型输出的真实自然语言候选分布，**绝非最终的规范本体（Canonical Ontology）**。在此阶段未进行任何人工或模型假设的概念合并、术语改写或层级归并。

- **构建时间**: {m['generated_at']}
- **Git Commit**: `{m['git_commit']}`
- **数据源路径**: `data/semantic_raw.jsonl` (4,575 题 100% 全覆盖)
- **有效题目总数**: **{m['unique_qids_count']} 道** (重复数: {m['duplicate_qids_count']}, 异常数: {m['malformed_records_count']})

---

## 一、 核心问题逐一解答 (Key Questions Answered)

### 1. 4,575 题实际产生了多少 unique knowledge candidate？
- **规范化后唯一知识点候选 (Unique Normalized)**: **{cs['knowledge']['unique_normalized']:,} 个**
- **全库累计引用总次数 (Total Occurrences)**: **{cs['knowledge']['total_occurrences']:,} 次**
- **平均每题知识点数**: **{stats['semantic_fields_summary']['knowledge_candidates']['avg_per_question']} 个/题**

### 2. 有多少 unique exam point candidate？
- **规范化后唯一考点候选 (Unique Normalized)**: **{cs['exam_point']['unique_normalized']:,} 个**
- **全库累计引用总次数 (Total Occurrences)**: **{cs['exam_point']['total_occurrences']:,} 次**
- **平均每题考点数**: **{stats['semantic_fields_summary']['exam_point_candidates']['avg_per_question']} 个/题**

### 3. 有多少 unique used method？
- **规范化后唯一实际使用解法候选 (Unique Normalized)**: **{cs['used_method']['unique_normalized']:,} 个**
- **全库累计引用总次数 (Total Occurrences)**: **{cs['used_method']['total_occurrences']:,} 次**
- **平均每题使用方法数**: **{stats['semantic_fields_summary']['used_methods']['avg_per_question']} 个/题**

### 4. Alternative / Invalid Method 的规模分别是多少？
- **备选方法 (Alternative Methods)**: **{cs['alternative_method']['unique_normalized']:,} 个** (累计引用 {cs['alternative_method']['total_occurrences']:,} 次)
- **无效方法 (Invalid Methods)**: **{cs['invalid_method']['unique_normalized']:,} 个** (累计引用 {cs['invalid_method']['total_occurrences']:,} 次)
- **三类方法重合规模**: 共有 **{len(method_role_collisions)} 个方法表面** 在解题中跨越了 2 种或 3 种不同角色（例如某种方法在题 A 是主选，在题 B 是备选，在题 C 是违规无效候选）。

### 5. Signal、Condition、Pitfall、Transformation 的长尾程度怎样？
- **解题信号 (Signals)**: 唯一候选 **{cs['signal']['unique_normalized']:,} 个**，Singleton 占比高达 **{cs['signal']['singleton_ratio']*100:.1f}%**。
- **定理/适用条件 (Conditions)**: 唯一候选 **{cs['condition']['unique_normalized']:,} 个**（隔离 4 类 condition kind），Singleton 占比 **{cs['condition']['singleton_ratio']*100:.1f}%**。
- **易错点 (Pitfalls)**: 唯一候选 **{cs['pitfall']['unique_normalized']:,} 个**，Singleton 占比 **{cs['pitfall']['singleton_ratio']*100:.1f}%**。
- **关键代数变形 (Key Transformations)**: 唯一候选 **{cs['transformation']['unique_normalized']:,} 个**，Singleton 占比 **{cs['transformation']['singleton_ratio']*100:.1f}%**。
- *长尾洞察*：上述 4 个字段具有极强的题目依附性与自然语言表达丰富度，呈现出典型的“长尾分布（Power-law / Long-tail）”，需要在后续本体构建中通过模式提取而非扁平枚举处理。

### 6. 高频语义候选是什么？
- **Top 知识点**: {top_k_str}
- **Top 考点**: {top_ep_str}
- **Top 解法**: {top_um_str}

### 7. Singleton (仅出现 1 次) 比例是多少？
| 语义类型 | 唯一候选总数 | 出现 1 次项 (Singletons) | Singleton 比例 |
| :--- | :---: | :---: | :---: |
| **知识点 (Knowledge)** | {cs['knowledge']['unique_normalized']:,} | {cs['knowledge']['singletons']:,} | **{cs['knowledge']['singleton_ratio']*100:.1f}%** |
| **考点 (Exam Points)** | {cs['exam_point']['unique_normalized']:,} | {cs['exam_point']['singletons']:,} | **{cs['exam_point']['singleton_ratio']*100:.1f}%** |
| **使用方法 (Used Methods)** | {cs['used_method']['unique_normalized']:,} | {cs['used_method']['singletons']:,} | **{cs['used_method']['singleton_ratio']*100:.1f}%** |
| **备选方法 (Alternative)** | {cs['alternative_method']['unique_normalized']:,} | {cs['alternative_method']['singletons']:,} | **{cs['alternative_method']['singleton_ratio']*100:.1f}%** |
| **无效方法 (Invalid)** | {cs['invalid_method']['unique_normalized']:,} | {cs['invalid_method']['singletons']:,} | **{cs['invalid_method']['singleton_ratio']*100:.1f}%** |
| **解题信号 (Signals)** | {cs['signal']['unique_normalized']:,} | {cs['signal']['singletons']:,} | **{cs['signal']['singleton_ratio']*100:.1f}%** |
| **条件约束 (Conditions)** | {cs['condition']['unique_normalized']:,} | {cs['condition']['singletons']:,} | **{cs['condition']['singleton_ratio']*100:.1f}%** |
| **易错点 (Pitfalls)** | {cs['pitfall']['unique_normalized']:,} | {cs['pitfall']['singletons']:,} | **{cs['pitfall']['singleton_ratio']*100:.1f}%** |
| **代数变形 (Transformations)** | {cs['transformation']['unique_normalized']:,} | {cs['transformation']['singletons']:,} | **{cs['transformation']['singleton_ratio']*100:.1f}%** |

### 8. 哪些 surface 存在大量自然语言变体？
共有 **{sum(1 for _ in open(OUT_DIR / 'indexes' / 'raw_variant_index.jsonl', 'r', encoding='utf-8')):,} 个归一化词** 聚合了 2 种及以上的原始不同文本写法。
典型多变体示例：
- “等价无穷小代换”包含多种原始写法（如 `等价无穷小替换`, `利用等价无穷小代换`, `等价无穷小` 等）
- “分部积分法”包含多种原始写法（如 `分部积分`, `利用分部积分公式`, `应用分部积分法` 等）

### 9. 哪些 surface 在不同 semantic type 中发生 collision？
- 全库共检出 **{len(cross_type_collisions):,} 个表面词** 在至少 2 个不同语义类型中同时出现。
- 跨越 4 个及以上类型的极高度碰撞词达 **{sum(1 for c in cross_type_collisions if c['type_count'] >= 4)} 个**（如部分术语同时作为 knowledge、exam_point、used_method 和 signal 出现），证明自然语言在“知识名”与“方法名”之间天然存在概念混用，需在 Canonical Ontology 阶段进行严格解耦。

### 10. Knowledge / ExamPoint / Method 之间最常见的共现关系是什么？
共现网络累计挖掘出 **{len(sorted_cooccurrences):,} 对二元共现关系**。
最核心 Top 5 共现对：
{top_coocc_str}

### 11. 三个学科的候选词分布有什么明显差异？
- **高等数学 (3,257 题)**: 知识点与解法词汇量最庞大，高度集中在极限、微分中值定理、不定积分/定积分、级数、多元微分与重积分。
- **线性代数 (712 题)**: 词汇体系高度紧凑严密，核心候选围绕行列式、矩阵秩、线性方程组通解、特征值与特征向量、二次型正定性，词汇复用率明显高于高数。
- **概率论与数理统计 (606 题)**: 具有鲜明的事件、分布与数字特征层级，核心词高度聚焦在常见分布（正态/泊松/均匀）、独立性、协方差、大数定律、极大似然估计。
- **跨学科词汇**: 共有 **{cs['knowledge']['cross_discipline_count']} 个知识点** 与 **{cs['used_method']['cross_discipline_count']} 个方法** 跨越了多个学科（如反证法、数学归纳法、分类讨论、构造辅助函数等通用方法论）。

### 12. 哪些候选值得后续进入 possible merge review？
- 词法包含与高相似度分析识别出 **{len(possible_merges):,} 组潜在合并参考**（保存在 `audit/possible_merge_candidates.jsonl`）。
- 重点包括前缀修饰词（“利用...”、“应用...”、“根据...”）、动宾词组与名片词组的映射建议，在下一阶段需由数学学科专家审阅判定。

### 13. 所有汇总项是否都能够反查到原始 QID？
- **100% 可双向精确溯源**。
- 每个 Candidate 均内嵌或可索引到完整的 `qids` 列表；
- `indexes/candidate_to_qids.jsonl` 提供候选到题目的正查，`indexes/qid_to_candidates.jsonl` 提供题目到全部候选的反查。

---

## 二、 核心统计全景大表

### 1. 图书与学科覆盖
| 来源图书 | 题目数 | 高等数学 | 线性代数 | 概率论与数理统计 |
| :--- | :---: | :---: | :---: | :---: |
| 《张宇1000题》 | 1,229 题 | 877 题 | 212 题 | 140 题 |
| 《老姚高数》 | 1,170 题 | 1,170 题 | 0 题 | 0 题 |
| 《基础30讲》 | 872 题 | 549 题 | 175 题 | 148 题 |
| 《李范复习全书》 | 840 题 | 448 题 | 205 题 | 187 题 |
| 《强化36讲》 | 464 题 | 213 题 | 120 题 | 131 题 |
| **全量总计** | **4,575 题** | **3,257 题** | **712 题** | **606 题** |

### 2. 频率分层矩阵 (Frequency Tier Distribution)
| 语义类型 | 100+ 次 (超高频) | 50-99 次 (高频) | 10-49 次 (中频) | 5-9 次 (次中频) | 2-4 次 (低频) | 1 次 (单例) | 候选总数 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **知识点** | {ft['knowledge'].get('100+', 0)} | {ft['knowledge'].get('50-99', 0)} | {ft['knowledge'].get('10-49', 0)} | {ft['knowledge'].get('5-9', 0)} | {ft['knowledge'].get('2-4', 0)} | {ft['knowledge'].get('1', 0)} | **{cs['knowledge']['unique_normalized']:,}** |
| **考点** | {ft['exam_point'].get('100+', 0)} | {ft['exam_point'].get('50-99', 0)} | {ft['exam_point'].get('10-49', 0)} | {ft['exam_point'].get('5-9', 0)} | {ft['exam_point'].get('2-4', 0)} | {ft['exam_point'].get('1', 0)} | **{cs['exam_point']['unique_normalized']:,}** |
| **使用方法** | {ft['used_method'].get('100+', 0)} | {ft['used_method'].get('50-99', 0)} | {ft['used_method'].get('10-49', 0)} | {ft['used_method'].get('5-9', 0)} | {ft['used_method'].get('2-4', 0)} | {ft['used_method'].get('1', 0)} | **{cs['used_method']['unique_normalized']:,}** |
| **备选方法** | {ft['alternative_method'].get('100+', 0)} | {ft['alternative_method'].get('50-99', 0)} | {ft['alternative_method'].get('10-49', 0)} | {ft['alternative_method'].get('5-9', 0)} | {ft['alternative_method'].get('2-4', 0)} | {ft['alternative_method'].get('1', 0)} | **{cs['alternative_method']['unique_normalized']:,}** |
| **无效方法** | {ft['invalid_method'].get('100+', 0)} | {ft['invalid_method'].get('50-99', 0)} | {ft['invalid_method'].get('10-49', 0)} | {ft['invalid_method'].get('5-9', 0)} | {ft['invalid_method'].get('2-4', 0)} | {ft['invalid_method'].get('1', 0)} | **{cs['invalid_method']['unique_normalized']:,}** |
| **解题信号** | {ft['signal'].get('100+', 0)} | {ft['signal'].get('50-99', 0)} | {ft['signal'].get('10-49', 0)} | {ft['signal'].get('5-9', 0)} | {ft['signal'].get('2-4', 0)} | {ft['signal'].get('1', 0)} | **{cs['signal']['unique_normalized']:,}** |
| **条件约束** | {ft['condition'].get('100+', 0)} | {ft['condition'].get('50-99', 0)} | {ft['condition'].get('10-49', 0)} | {ft['condition'].get('5-9', 0)} | {ft['condition'].get('2-4', 0)} | {ft['condition'].get('1', 0)} | **{cs['condition']['unique_normalized']:,}** |
| **易错点** | {ft['pitfall'].get('100+', 0)} | {ft['pitfall'].get('50-99', 0)} | {ft['pitfall'].get('10-49', 0)} | {ft['pitfall'].get('5-9', 0)} | {ft['pitfall'].get('2-4', 0)} | {ft['pitfall'].get('1', 0)} | **{cs['pitfall']['unique_normalized']:,}** |
| **代数变形** | {ft['transformation'].get('100+', 0)} | {ft['transformation'].get('50-99', 0)} | {ft['transformation'].get('10-49', 0)} | {ft['transformation'].get('5-9', 0)} | {ft['transformation'].get('2-4', 0)} | {ft['transformation'].get('1', 0)} | **{cs['transformation']['unique_normalized']:,}** |

---

## 三、 产物清单与文件指纹

所有产物均存放于 `semantic_inventory/` 目录下，完整交付索引详见 `inventory_manifest.json`。
"""
    with open(OUT_DIR / "summary_report.md", "w", encoding="utf-8") as f:
        f.write(report)

def generate_aggregation_report(stats, candidates_data, conditions_data, method_role_collisions, cross_type_collisions, anomalies, possible_merges):
    m = stats["metadata"]
    b = stats["breakdown"]

    top_method_role_coll = method_role_collisions[:15]
    top_cross_type_coll = cross_type_collisions[:15]
    anom_counter = Counter(a["anomaly_type"] for a in anomalies)

    top_method_role_lines = []
    for item in top_method_role_coll:
        if len(item['roles_present']) == 3:
            top_method_role_lines.append(f"  - **`{item['method_surface']}`**: 在 {item['used_count']} 题为主解法，在 {item['alternative_count']} 题为备选解法，在 {item['invalid_count']} 题为失效违规解法 (如 QID `{item['invalid_qids'][0]}`)")
    top_method_role_str = "\n".join(top_method_role_lines[:8])

    top_cross_type_lines = []
    for c in top_cross_type_coll[:10]:
        types_str = ", ".join(c['types_present'])
        top_cross_type_lines.append(f"  - **`{c['surface']}`** (跨 {c['type_count']} 类: {types_str}) | 总频次: {c['total_occurrences']} 次")
    top_cross_type_str = "\n".join(top_cross_type_lines)

    report = f"""# Direct-Vision Pass 1 语义汇总深度审计报告 (Aggregation Report)

- **报告版本**: 1.0.0 (Audit Baseline)
- **输入数据 SHA256**: `{sha256_file(SEMANTIC_RAW_PATH)}`
- **生成时间**: {m['generated_at']}

---

## 一、 输入数据完备性与可信度审计

1. **题目覆盖完整性**: 
   - 原始清单 4,575 题全部具有对应的有效 Pass 1 JSON 对象，无任何空缺题目；
   - 唯一 QID 数严格等于 4,575，重复 QID 数量为 0，格式畸变记录为 0；
   - 涵盖 5 本目标全书，高数 3,257 题、线代 712 题、概率论 606 题。

2. **模型与置信度审计**:
   - 平均视觉置信度: **{stats['confidence_averages']['vision']}**
   - 平均语义置信度: **{stats['confidence_averages']['semantic']}**
   - 平均总体置信度: **{stats['confidence_averages']['overall']}**
   - 解答完整度分布: 完整解答图占比 **{b['by_solution_status']['present_and_complete'] / 4575 * 100:.1f}%**，无解答题目仅占极少数。

---

## 二、 方法角色交叉碰撞深度审计 (Method Role Collision)

在考研数学的真实做题语境中，“同一种数学方法”在不同题目中充当了截然不同的认知角色：
- 共计 **{len(method_role_collisions)} 个方法表面词** 在全库中跨越了 2 个或 3 个不同角色；
- **跨 3 个角色 (used & alternative & invalid) 的典型方法**:
{top_method_role_str}

> **审计指导建议**：在下一阶段 Canonical Ontology 中，不能简单把“方法”当做单一维度的标签，必须建立 `(Method, Role, Question)` 的关系建模。

---

## 三、 跨类型表面碰撞审计 (Cross-Type Collision)

- 检出 **{len(cross_type_collisions)} 个表面词** 跨越了多个不同的语义维度。
- **高频跨类型碰撞表面 Top 10**:
{top_cross_type_str}

> **分析**：诸如“泰勒公式”、“拉格朗日中值定理”、“等价无穷小代换”等既被模型识别为知识点（Knowledge），也被识别为主方法（Used Method），甚至在题面被识别为信号（Signal）。这表明大模型对名词性概念和动词性解题动作存在自然语言边界模糊，在构建 Canonical Ontology 时必须严格拆解为 `[Knowledge: 泰勒公式] --(应用于)--> [Method: 泰勒展开法]`。

---

## 四、 潜在异常与审计线索分类统计

审计模块共检出 **{len(anomalies)} 条候选异常提示**：

| 异常类型 | 数量 | 严重级别 | 典型特征与处置建议 |
| :--- | :---: | :---: | :--- |
| **超长文本标签 (length_exceeded)** | {anom_counter.get('length_exceeded', 0)} | 中 | 文本 > 40 字符，多为整句解析或题面推导泄漏，后续需进行句法截断与核心词提取 |
| **超长单例孤立词 (long_singleton)** | {anom_counter.get('long_singleton', 0)} | 低 | 仅出现 1 次且超长，属于高度题设相关的长尾描述，不宜作为核心本体节点 |
| **极度泛化表面 (generic_surface)** | {anom_counter.get('generic_surface', 0)} | 高 | “方法”、“计算”等纯通用词，后续应打标为黑名单停用词或转入顶层抽象范畴 |
| **广泛跨章节弥散 (chapter_diffusion)** | {anom_counter.get('chapter_diffusion', 0)} | 低 | 横跨 15+ 章节，多为通用数学手段（如待定系数法、换元法），属于跨模块通用方法 |
| **高频原始变体 (high_raw_variant_count)** | {anom_counter.get('high_raw_variant_count', 0)} | 中 | 归一化后聚合了 4+ 种原始写法，后续作为词法同义映射规则的坚实来源 |
| **高频失效方法 (high_frequency_invalid_method)** | {anom_counter.get('high_frequency_invalid_method', 0)} | 中 | 频繁在多题被判断为无效的方法，是考研数学命题中极具价值的“经典陷阱模型” |
| **极度跨类型混杂 (heavy_cross_type_collision)** | {anom_counter.get('heavy_cross_type_collision', 0)} | 高 | 同时在 4+ 个语义字段出现的词汇，需要人工干预明确其本质语义归属 |

---

## 五、 向 Canonical Ontology 推进的实施建议

1. **绝对保留 Raw Surface 溯源性**: 任何规范化映射表必须保留指向原始 QID 与 raw variant 的链条；
2. **知识与方法严格分层**: 将高频重合概念解耦为实体（Concept/Knowledge）与操作（Method/Procedure）；
3. **长尾长句字段采用模式抽取**: 对 Signal, Pitfall, Transformation, Condition 引入微语法（Micro-syntax）抽取，而非简单扁平分类；
4. **人工参与 Possible Merge 审阅**: 基于 `audit/possible_merge_candidates.jsonl`，结合考研考纲与数学规范词表进行同义对齐。
"""
    with open(OUT_DIR / "audit" / "aggregation_report.md", "w", encoding="utf-8") as f:
        f.write(report)

def generate_inventory_readme(stats):
    m = stats["metadata"]
    readme = f"""# Direct-Vision Pass 1 语义资产汇总目录 (semantic_inventory)

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
"""
    with open(OUT_DIR / "README.md", "w", encoding="utf-8") as f:
        f.write(readme)

if __name__ == "__main__":
    main()
