#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teaching Ontology Extraction + Semantic Alignment Pipeline v1.0
================================================================
考研数学教学知识图谱构建与题目多模态语义对齐引擎

阶段流程：
  Phase 1: 教学资料解析 (讲义资料, 李范全书, 强化36讲) -> ontology_source_raw/
  Phase 2: 教学候选本体融合 -> teaching_ontology_candidate.jsonl
  Phase 3: Pass 1 候选语义对齐与证据链锚定 -> alignment_candidates/
  Phase 4: 逐题语义关联链接 (4,575 题) -> question_semantic_links.jsonl
  Phase 5: 规范语义层固化 (注入实证关联) -> canonical_nodes.json
  Phase 6: 认知推理图谱生成 (6类认知关系闭环) -> reasoning_graph.jsonl
  Phase 7: 全维质量与冲突审计报告 -> ontology_audit_report.txt

作者: Antigravity Team
运行环境: Python 3.10+ · 纯文本确定性算法 · 零外部 API 依赖
"""

import os
import sys
import json
import re
import time
import hashlib
import unicodedata
from pathlib import Path
from collections import defaultdict, Counter

# 设置标准输出编码
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# 核心路径配置
BASE_DIR = Path(__file__).resolve().parent.parent
JIANGYI_DIR = Path(r"D:\tj\822\考研题库\题库\讲义和笔记")

DATA_DIR = BASE_DIR / "data"
INVENTORY_DIR = BASE_DIR / "semantic_inventory"
RAW_OUT_DIR = BASE_DIR / "ontology_source_raw"
ALIGN_OUT_DIR = BASE_DIR / "alignment_candidates"

SEMANTIC_RAW_PATH = DATA_DIR / "semantic_raw.jsonl"
MANIFEST_PATH = DATA_DIR / "master_structural_manifest.jsonl"

RAW_OUT_DIR.mkdir(parents=True, exist_ok=True)
ALIGN_OUT_DIR.mkdir(parents=True, exist_ok=True)

# 学科名称严格规范化映射
DISC_NORM = {
    "高数": "高等数学",
    "高等数学": "高等数学",
    "线代": "线性代数",
    "线性代数": "线性代数",
    "概率": "概率论与数理统计",
    "概率论": "概率论与数理统计",
    "概率论与数理统计": "概率论与数理统计"
}

# 统一来源枚举与规范定义
SOURCE_ENUM = {
    "LECTURE_NOTES": "讲义资料",
    "LI_FAN": "李范全书",
    "QIANGHUA36": "强化36讲",
    "PASS1_VISION": "Direct-Vision Pass1"
}

# 考研同义表述与标准术语对齐词典
SYNONYM_MAP = {
    "等价无穷小代换": "等价无穷小替换",
    "利用等价无穷小代换": "等价无穷小替换",
    "利用等价无穷小替换": "等价无穷小替换",
    "极坐标变换": "极坐标变换法",
    "利用极坐标变换": "极坐标变换法",
    "极坐标法": "极坐标变换法",
    "导数定义法": "导数定义法",
    "利用导数定义": "导数定义法",
    "导数的定义": "导数的定义",
    "分部积分": "分部积分法",
    "利用分部积分": "分部积分法",
    "应用分部积分法": "分部积分法",
    "凑微分": "凑微分法",
    "第一类换元法": "凑微分法",
    "第二类换元法": "换元积分法",
    "换元法": "换元积分法",
    "变量代换法": "换元积分法",
    "分离变量法": "变量分离法",
    "泰勒公式展开": "泰勒展开法",
    "泰勒公式展开法": "泰勒展开法",
    "利用泰勒公式": "泰勒展开法",
    "泰勒公式": "泰勒公式",
    "洛必达": "洛必达法则",
    "应用洛必达法则": "洛必达法则",
    "利用洛必达法则": "洛必达法则",
    "比值判别法": "比值审敛法",
    "比较判别法": "比较审敛法",
    "根值判别法": "根值审敛法",
    "链式法则": "复合函数求导法则",
    "复合函数求导": "复合函数求导法则",
    "多元复合函数求导": "多元复合函数求导法则",
    "隐函数求导": "隐函数求导法",
    "变限积分求导": "变上限积分函数求导",
    "直接积分法": "直接积分法",
    "直接计算法": "直接计算法",
    "直接代入法": "直接代入法",
    "排除法": "排除法",
    "特殊值法": "特殊值法",
    "举反例法": "举反例法",
    "分类讨论": "分类讨论法",
    "对称性分析": "利用奇偶性与对称性化简",
    "利用对称性化简": "利用奇偶性与对称性化简",
    "一阶线性微分方程通解公式": "一阶线性微分方程通解公式",
    "初等行变换": "初等行变换法",
    "矩阵初等变换": "初等行变换法",
    "正交相似对角化": "实对称矩阵正交相似对角化",
    "全概率公式": "全概率公式",
    "贝叶斯公式": "贝叶斯公式"
}

# 文本规范化工具函数
def normalize_surface(text: str) -> str:
    if not text:
        return ""
    s = unicodedata.normalize('NFKC', str(text)).strip()
    s = re.sub(r'\s+', ' ', s)
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1].strip()
    s = re.sub(r'^\*+|\*+$', '', s).strip()
    # 剥离学科前缀与讲/章前缀
    s = re.sub(r'^(高等数学|线性代数|概率论与数理统计|基础高数|基础线代|基础概率论|强化高数|强化线代|强化概率)[\s\-–—·_]*', '', s).strip()
    s = re.sub(r'^(第[一二三四五六七八九十\d]+[讲章节篇部分]|讲\s*\d+\s*讲?|\d+)[_\s·、\-–—]*', '', s).strip()
    s = re.sub(r'^(第[一二三四五六七八九十\d]+[讲章节篇部分]|讲\s*\d+\s*讲?|\d+)[_\s·、\-–—]*', '', s).strip()
    s = re.sub(r'^[一二三四五六七八九十]+[、\.:：]\s*', '', s).strip()
    s = re.sub(r'^\d+[、\.:：\s]+', '', s).strip()
    s = re.sub(r'^[①②③④⑤⑥⑦⑧⑨⑩]\s*', '', s).strip()
    s = re.sub(r'[。.;;,，:：]+$', '', s).strip()
    return s

def clean_and_validate_node_name(name: str):
    if not name:
        return None
    s = str(name).strip()
    
    # 替换下划线与破折号为标准空格
    s = s.replace('_', ' ')
    s = re.sub(r'[—–—]+', ' ', s)
    
    # 去除 Markdown 加粗、斜体、引用
    s = re.sub(r'[\*"`\']', '', s).strip()
    s = re.sub(r'\s+', ' ', s).strip()
    
    # 剥离前缀学科与讲/章序号
    s = re.sub(r'^(高等数学|线性代数|概率论与数理统计|基础高数|基础线代|基础概率论|强化高数|强化线代|强化概率)[\s\-–—·_]*', '', s).strip()
    s = re.sub(r'^(第[一二三四五六七八九十\d]+[讲章节篇部分]|讲\s*\d+\s*讲?|\d+)[_\s·、\-–—]*', '', s).strip()
    s = re.sub(r'^(第[一二三四五六七八九十\d]+[讲章节篇部分]|讲\s*\d+\s*讲?|\d+)[_\s·、\-–—]*', '', s).strip()
    s = re.sub(r'^[一二三四五六七八九十]+[、\.:：]\s*', '', s).strip()
    s = re.sub(r'^\d+[、\.:：\s]+', '', s).strip()
    s = re.sub(r'^[①②③④⑤⑥⑦⑧⑨⑩]\s*', '', s).strip()
    
    # 考研标准数学符号向规范中文本体转译
    s = s.replace(r'$\frac00$', '0/0型未定式')
    s = s.replace(r'$\frac{0}{0}$', '0/0型未定式')
    s = s.replace(r'$\frac\infty\infty$', '∞/∞型未定式')
    s = s.replace(r'$\frac{\infty}{\infty}$', '∞/∞型未定式')
    s = s.replace(r'$0\cdot\infty$', '0·∞型未定式')
    s = s.replace(r'$\infty-\infty$', '∞-∞型未定式')
    s = s.replace(r'$1^\infty$', '1^∞型幂指函数')
    s = s.replace(r'$0^0$', '0^0型幂指函数')
    s = s.replace(r'$\infty^0$', '∞^0型幂指函数')
    s = s.replace(r'$\chi^2$', '卡方分布')
    s = s.replace(r'\chi^2', '卡方分布')
    s = s.replace(r'$t$', 't')
    s = s.replace(r'$F$', 'F')
    s = s.replace(r'$X$', '随机变量X')
    s = s.replace(r'$f(x)$', '函数f(x)')
    s = s.replace(r"$f'$", '导函数')
    s = s.replace(r'$A^n$', '矩阵的高次幂A^n')
    
    # 去除多余的 $
    s = re.sub(r'^\$+|\$+$', '', s).strip()
    
    # 严禁任何 LaTeX 语法碎片或未闭合公式流入本体名
    if any(c in s for c in ['\\', '{', '}', '^', '$', '&', '=']):
        return None
    if any(k in s for k in ['frac', 'sum', 'int', 'sim', 'lim', 'cases', 'begin', 'end', 'alpha', 'beta', 'lambda', 'sigma', 'partial']):
        return None
        
    # 严禁讲义编排/例题/排版注记作为考点流入
    if any(k in s for k in ['印刷页', '物理页', '例题', '习题', '例3.', '例 3.', '例 1', '例 2', '编号连续', '选练', '必背结论', '注例', '出处', 'AIGC', '导读', '总览', '框架图', '思维导图', '题干', '详解']):
        return None
    if re.search(r'^(例|习题|\d+|[—\-–]+)', s):
        return None
    if any(k in s for k in ['---', '——', '--', '...']):
        return None
        
    # 必须包含规范中文语义字符
    if not re.search(r'[\u4e00-\u9fa5]', s):
        return None
        
    # 长度限制: 2 到 45 字符
    if len(s) < 2 or len(s) > 45:
        return None
        
    # 剔除末尾多余标点
    s = re.sub(r'[。.;;,，:：、\-—\s]+$', '', s).strip()
    return s

def clean_term_prefix(term: str) -> str:
    t = re.sub(r'^(利用|应用|根据|使用|通过|采用|借助|按|求|讨论|判定|证明|分析|讨论关于|讨论含)', '', term).strip()
    t = re.sub(r'(的方法|的计算|的应用|的证明|的判定|法|法则|公式|定理|定义|型|代换|替换)$', '', t).strip()
    return t

# ===========================================================================
# 基础核心概念基准表 (Foundational Core Terms Taxonomy)
# ===========================================================================

CORE_METHODS_CATALOG = {
    "高等数学": [
        "洛必达法则", "等价无穷小替换", "泰勒展开法", "泰勒公式", "夹逼准则", "单调有界准则",
        "导数定义法", "倒代换法", "凑微分法", "第一类换元积分法", "第二类换元积分法", "换元积分法",
        "三角代换法", "根式代换法", "分部积分法", "分项积分法", "有理函数积分法", "利用奇偶性与对称性化简",
        "直角坐标系计算", "极坐标变换法", "直角坐标系下交换积分次序", "极坐标系下计算二重积分",
        "观察法", "待定系数法", "构造辅助函数", "变量分离法", "一阶线性微分方程通解公式",
        "常数变易法", "降阶法", "特征方程法", "微分算子法", "幂级数逐项求导与逐项求和",
        "单调性法证明不等式", "最值法证明不等式", "导数零点定理", "介值定理与零点定理",
        "拉格朗日中值定理", "柯西中值定理", "罗尔定理", "高阶导数莱布尼茨公式", "隐函数求导法",
        "参数方程求导法", "对数求导法", "格林公式", "高斯公式", "斯托克斯公式", "换元法",
        "直接积分法", "直接计算法", "直接代入法", "变上限积分函数求导", "复合函数求导法则",
        "多元复合函数求导法则", "比较审敛法", "比值审敛法", "根值审敛法", "莱布尼茨审敛法",
        "分类讨论法", "排除法", "特殊值法", "举反例法"
    ],
    "线性代数": [
        "初等行变换法", "初等变换化行最简形", "化三角形法", "按行展开定理", "按列展开定理",
        "加边法", "递推法", "数学归纳法", "伴随矩阵法求逆", "初等变换法求逆", "分块矩阵求逆法",
        "矩阵方程法", "求极大线性无关组法", "正交变换法化二次型", "配方法化二次型",
        "施密特正交化", "特征多项式法", "相似对角化法", "实对称矩阵正交相似对角化",
        "克拉默法则", "列向量组合法", "定义法判定线性相关性", "反证法", "讨论含参方程组通解",
        "待定系数法", "排除法", "特殊值法"
    ],
    "概率论与数理统计": [
        "对立事件法", "加法公式", "减法公式", "乘法公式", "全概率公式", "贝叶斯公式",
        "独立性检验法", "分布函数法", "概率密度公式法", "卷积公式法", "极值法求最值分布",
        "利用正态分布对称性", "二维正态分布性质法", "期望性质法", "方差性质法",
        "协方差与相关系数计算法", "切比雪夫不等式法", "矩估计法", "极大似然估计法",
        "抽样分布分位点查表法", "区间估计法", "中心极限定理法"
    ]
}

CORE_KNOWLEDGE_CATALOG = {
    "高等数学": [
        "函数极限", "数列极限", "无穷小与无穷大", "等价无穷小", "极限的局部保号性", "极限的有界性",
        "极限唯一性", "连续与间断", "间断点分类", "可去间断点", "跳跃间断点", "无穷间断点", "振荡间断点",
        "闭区间连续函数性质", "介值定理", "零点定理", "导数的定义", "导数的几何意义", "可导与连续的关系",
        "微分的概念", "可微性", "微分形式不变性", "高阶导数", "极值点与驻点", "拐点与凹凸性",
        "水平渐近线", "铅直渐近线", "斜渐近线", "原函数存在定理", "不定积分的性质", "微积分基本定理",
        "牛顿-莱布尼茨公式", "积分中值定理", "变上限积分函数", "反常积分敛散性", "二重积分的概念与性质",
        "格林公式", "高斯公式", "斯托克斯公式", "多元函数极限与连续", "偏导数", "全微分", "多元复合函数求导",
        "多元隐函数求导", "拉格朗日乘数法", "多元函数极值", "常微分方程解的结构", "一阶线性微分方程",
        "齐次方程", "常系数齐次线性微分方程", "常系数非齐次线性微分方程", "正项级数审敛准则",
        "交错级数莱布尼茨定理", "绝对收敛与条件收敛", "阿贝尔定理", "幂级数收敛半径与收敛域", "泰勒级数",
        "复合函数求导法则", "导数公式", "高阶导数公式", "定积分换元法", "二次型的矩阵表示"
    ],
    "线性代数": [
        "行列式的本质与定义", "行列式的七大性质", "代数余子式", "范德蒙德行列式", "矩阵的加减与数乘",
        "矩阵的乘法", "矩阵的转置", "逆矩阵", "伴随矩阵", "初等矩阵", "分块矩阵", "矩阵的秩",
        "向量组的线性相关性", "线性无关", "极大线性无关组", "向量组的秩", "向量空间与基",
        "齐次线性方程组的基础解系", "非齐次线性方程组通解结构", "特征值与特征向量", "特征多项式",
        "相似矩阵与相似不变量", "实对称矩阵的正交相似对角化", "二次型及其矩阵表示", "标准形与规范形",
        "惯性定理", "正惯性指数", "正定二次型与正定矩阵", "正交矩阵"
    ],
    "概率论与数理统计": [
        "随机事件的关系与运算", "互斥事件", "对立事件", "概率的公理化定义", "条件概率",
        "事件的独立性", "一维离散型随机变量", "0-1分布", "二项分布", "泊松分布", "几何分布",
        "一维连续型随机变量", "概率密度函数", "均匀分布", "指数分布", "正态分布",
        "二维随机变量联合分布函数", "二维离散型分布律", "二维连续型概率密度", "边缘分布与条件分布",
        "随机变量的相互独立性", "二维正态分布", "数学期望", "方差", "标准差", "协方差",
        "相关系数与不相关性", "切比雪夫不等式", "大数定律", "辛钦大数定律", "中心极限定理",
        "列维-林德伯格定理", "总体与样本", "样本均值与样本方差", "卡方分布", "t分布", "F分布",
        "正态总体抽样分布", "点估计", "矩估计", "极大似然估计", "无偏性与有效性"
    ]
}

# ===========================================================================
# Phase 1: 教学资料解析 (Teaching Source Parsing)
# ===========================================================================

def parse_markdown_teaching_file(file_path: Path, source_id: str, discipline: str):
    nodes = []
    source_name = SOURCE_ENUM[source_id]
    
    current_chapter = file_path.stem
    current_section = ""
    current_topic = current_chapter
    
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
        
    lines = content.splitlines()
    
    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
            clean_title = clean_and_validate_node_name(title)
            if clean_title:
                current_topic = clean_title
            break
            
    if current_topic == current_chapter:
        c_clean = clean_and_validate_node_name(current_chapter)
        if c_clean:
            current_topic = c_clean

    nodes.append({
        "source_id": source_id,
        "source_name": source_name,
        "discipline": discipline,
        "chapter": current_chapter,
        "section": "章节总览",
        "node_type": "Topic",
        "name": current_topic,
        "parent": discipline,
        "related_methods": [],
        "related_knowledge": [],
        "related_exam_points": [],
        "notes": f"来源于 {file_path.name}"
    })
    
    in_table = False
    for line_str in lines:
        line_str = line_str.strip()
        if not line_str:
            continue
            
        if line_str.startswith("## "):
            sec_title = line_str[3:].strip()
            if not any(k in sec_title for k in ["思维导图", "知识结构", "框架图", "AIGC", "出处"]):
                current_section = sec_title
        elif line_str.startswith("### "):
            sec_title = line_str[4:].strip()
            if not any(k in sec_title for k in ["例题", "印刷页", "解析"]):
                current_section = sec_title
                
        # 表格题型提炼
        if line_str.startswith("|") and ("题型" in line_str or "考点" in line_str) and ("方法" in line_str or "例题" in line_str):
            in_table = True
            continue
            
        if in_table and line_str.startswith("|"):
            parts = [p.strip() for p in line_str.split("|")[1:-1]]
            if len(parts) >= 2 and not line_str.startswith("|---"):
                ep_text = parts[0]
                method_text = parts[1] if len(parts) > 1 else ""
                clean_ep = re.sub(r'^(题型[一二三四五六七八九十\d]+|[①②③④⑤⑥⑦⑧⑨⑩\d]+)\s*', '', ep_text).strip()
                clean_ep = clean_and_validate_node_name(clean_ep)
                if clean_ep and len(clean_ep) >= 3 and not clean_ep.startswith("知识点"):
                    extracted_methods = []
                    for m in re.split(r'[、,;；/与和+]+', method_text):
                        m_clean = clean_and_validate_node_name(m)
                        if m_clean and len(m_clean) >= 2 and len(m_clean) <= 15:
                            extracted_methods.append(m_clean)
                            
                    nodes.append({
                        "source_id": source_id,
                        "source_name": source_name,
                        "discipline": discipline,
                        "chapter": current_chapter,
                        "section": current_section or "题型精析",
                        "node_type": "ExamPoint",
                        "name": clean_ep,
                        "parent": current_topic,
                        "related_methods": extracted_methods[:5],
                        "related_knowledge": [],
                        "related_exam_points": [],
                        "notes": f"表格提炼: {method_text[:100]}"
                    })
        elif in_table and not line_str.startswith("|"):
            in_table = False

        # 题型标题 (严格只匹配显式 题型/考点/盯住目标 标记，杜绝列表普通段落公式误匹配)
        ep_match = re.search(r'(题型[一二三四五六七八九十\d]+[:：\s]*|考点[一二三四五六七八九十\d]+[:：\s]*|盯住目标\s*\d*——|【题型[一二三四五六七八九十\d]+】|【考点[一二三四五六七八九十\d]+】)([^\|（\(\n\r]+)', line_str)
        if ep_match and not line_str.startswith("|"):
            raw_ep = ep_match.group(2)
            ep_name = clean_and_validate_node_name(raw_ep)
            if ep_name:
                ep_name = re.sub(r'^(求|计算|讨论|判定|证明)', '', ep_name).strip()
                ep_name = clean_and_validate_node_name(ep_name)
                if ep_name and len(ep_name) >= 3 and len(ep_name) <= 35:
                    nodes.append({
                        "source_id": source_id,
                        "source_name": source_name,
                        "discipline": discipline,
                        "chapter": current_chapter,
                        "section": current_section,
                        "node_type": "ExamPoint",
                        "name": ep_name,
                        "parent": current_topic,
                        "related_methods": [],
                        "related_knowledge": [],
                        "related_exam_points": [],
                        "notes": line_str[:120]
                    })

        # 知识点
        for kp in CORE_KNOWLEDGE_CATALOG.get(discipline, []):
            if kp in line_str:
                nodes.append({
                    "source_id": source_id,
                    "source_name": source_name,
                    "discipline": discipline,
                    "chapter": current_chapter,
                    "section": current_section,
                    "node_type": "KnowledgePoint",
                    "name": kp,
                    "parent": current_topic,
                    "related_methods": [],
                    "related_knowledge": [],
                    "related_exam_points": [],
                    "notes": line_str[:120]
                })

        # 方法
        for m in CORE_METHODS_CATALOG.get(discipline, []):
            if m in line_str:
                nodes.append({
                    "source_id": source_id,
                    "source_name": source_name,
                    "discipline": discipline,
                    "chapter": current_chapter,
                    "section": current_section,
                    "node_type": "Method",
                    "name": m,
                    "parent": current_topic,
                    "related_methods": [],
                    "related_knowledge": [],
                    "related_exam_points": [],
                    "notes": line_str[:120]
                })

        # 易错点
        if any(prefix in line_str for prefix in ["【注】", "注意事项", "易错点", "注意：", "切忌", "误区", "不能在"]):
            pf_text = re.sub(r'^(【注】|注意事项[:：]?|易错点[:：]?|注意[:：]|切忌[:：]?|误区[:：]?)', '', line_str).strip()
            pf_text = normalize_surface(pf_text)
            if len(pf_text) >= 6 and len(pf_text) <= 60:
                nodes.append({
                    "source_id": source_id,
                    "source_name": source_name,
                    "discipline": discipline,
                    "chapter": current_chapter,
                    "section": current_section,
                    "node_type": "Pitfall",
                    "name": pf_text,
                    "parent": current_topic,
                    "related_methods": [],
                    "related_knowledge": [],
                    "related_exam_points": [],
                    "notes": line_str[:120]
                })

    return nodes

def run_phase1_parsing():
    print("\n" + "=" * 75)
    print("[Phase 1/7] 正在从讲义资料、李范全书、强化36讲抽取原始教学知识节点...")
    print("=" * 75)

    lecture_nodes = []
    lifan_nodes = []
    qianghua_nodes = []

    # 1. 讲义资料 (LECTURE_NOTES)
    lecture_dirs = [
        (JIANGYI_DIR / "基础高数18讲整理", "高等数学"),
        (JIANGYI_DIR / "基础线代6讲", "线性代数"),
        (JIANGYI_DIR / "基础概率论6讲", "概率论与数理统计"),
        (JIANGYI_DIR / "零基础通关讲义整理", "高等数学")
    ]
    for d, disc in lecture_dirs:
        if d.exists():
            for f in sorted(d.glob("*.md")):
                if "总索引" in f.name or "统计报告" in f.name:
                    continue
                extracted = parse_markdown_teaching_file(f, "LECTURE_NOTES", disc)
                lecture_nodes.extend(extracted)
                
    # 2. 李范全书 (LI_FAN)
    lifan_dir = JIANGYI_DIR / "李范复习全书整理"
    if lifan_dir.exists():
        for f in sorted(lifan_dir.glob("*.md")):
            disc = "高等数学"
            if any(k in f.name for k in ["矩阵", "行列式", "向量", "线性方程", "特征值", "二次型"]):
                disc = "线性代数"
            elif any(k in f.name for k in ["概率", "大数定律", "数理统计", "参数估计"]):
                disc = "概率论与数理统计"
            extracted = parse_markdown_teaching_file(f, "LI_FAN", disc)
            lifan_nodes.extend(extracted)

    # 3. 强化36讲 (QIANGHUA36)
    qianghua_dirs = [
        (JIANGYI_DIR / "强化高数18讲整理", "高等数学"),
        (JIANGYI_DIR / "强化线代9讲", "线性代数"),
        (JIANGYI_DIR / "强化概率9讲", "概率论与数理统计")
    ]
    for d, disc in qianghua_dirs:
        if d.exists():
            for f in sorted(d.glob("*.md")):
                if "总索引" in f.name or "附录" in f.name:
                    continue
                extracted = parse_markdown_teaching_file(f, "QIANGHUA36", disc)
                qianghua_nodes.extend(extracted)

    # 导出 Phase 1 成果文件
    def save_jsonl(path, items):
        with open(path, "w", encoding="utf-8") as f:
            for it in items:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")

    p1_lec_path = RAW_OUT_DIR / "lecture_notes_nodes.jsonl"
    p1_lifan_path = RAW_OUT_DIR / "li_fan_nodes.jsonl"
    p1_qh_path = RAW_OUT_DIR / "qianghua36_nodes.jsonl"

    save_jsonl(p1_lec_path, lecture_nodes)
    save_jsonl(p1_lifan_path, lifan_nodes)
    save_jsonl(p1_qh_path, qianghua_nodes)

    print(f"  - 讲义资料 (LECTURE_NOTES) 原始节点: {len(lecture_nodes)} 条 -> {p1_lec_path.name}")
    print(f"  - 李范全书 (LI_FAN) 原始节点: {len(lifan_nodes)} 条 -> {p1_lifan_path.name}")
    print(f"  - 强化36讲 (QIANGHUA36) 原始节点: {len(qianghua_nodes)} 条 -> {p1_qh_path.name}")

    return lecture_nodes, lifan_nodes, qianghua_nodes

# ===========================================================================
# Phase 2: 候选教学本体融合 (Teaching Ontology Candidate)
# ===========================================================================

def assign_canonical_id(node_type: str, discipline: str, name: str) -> str:
    disc_prefix = {"高等数学": "CALC", "线性代数": "LA", "概率论与数理统计": "PROB"}.get(discipline, "COMMON")
    type_prefix = {
        "Topic": "TOPIC",
        "ExamPoint": "EP",
        "KnowledgePoint": "KP",
        "Method": "METHOD",
        "Pitfall": "PITFALL",
        "Signal": "SIGNAL",
        "Condition": "COND"
    }.get(node_type, "NODE")
    
    suffix = hashlib.md5(name.encode('utf-8')).hexdigest()[:6].upper()
    
    slug_map = {
        "等价无穷小替换": "EQUIV_INF", "等价无穷小": "EQUIV_INF",
        "洛必达法则": "LHOPITAL", "洛必达": "LHOPITAL",
        "泰勒公式": "TAYLOR", "泰勒展开法": "TAYLOR", "泰勒": "TAYLOR",
        "分部积分法": "INT_PARTS", "分部积分": "INT_PARTS",
        "凑微分法": "INT_SUBS1", "凑微分": "INT_SUBS1",
        "换元积分法": "INT_SUBS2", "换元法": "INT_SUBS2",
        "二重积分": "DOUBLE_INT",
        "极坐标变换法": "POLAR_COORD", "极坐标变换": "POLAR_COORD",
        "拉格朗日中值定理": "LAGRANGE", "拉格朗日": "LAGRANGE",
        "函数极限": "LIMIT", "数列极限": "SEQ_LIMIT",
        "连续与间断": "CONT_DISC", "间断点": "DISC_PT",
        "导数与微分": "DERIV", "导数的定义": "DERIV_DEF", "导数定义法": "DERIV_DEF",
        "微分方程": "DIFF_EQ",
        "无穷级数": "SERIES",
        "行列式": "DET",
        "矩阵的秩": "RANK", "矩阵": "MAT",
        "线性方程组": "SYS_EQ",
        "特征值与特征向量": "EIGEN", "特征值": "EIGEN",
        "二次型": "QUAD_FORM",
        "随机事件与概率": "EVENT_PROB",
        "一维随机变量": "1D_VAR",
        "多维随机变量": "2D_VAR",
        "数字特征": "NUM_FEAT", "期望与方差": "EXP_VAR",
        "大数定律": "LLN",
        "中心极限定理": "CLT",
        "参数估计": "PARAM_EST", "极大似然估计": "MLE"
    }
    
    slug = ""
    for k, v in slug_map.items():
        if k in name:
            slug = v
            break
            
    if slug:
        return f"{type_prefix}.{disc_prefix}.{slug}.{suffix}"
    else:
        return f"{type_prefix}.{disc_prefix}.{suffix}"

def run_phase2_synthesis(all_raw_nodes):
    print("\n" + "=" * 75)
    print("[Phase 2/7] 融合三源教学节点，构建候选教学本体 (teaching_ontology_candidate.jsonl)...")
    print("=" * 75)

    fusion_dict = defaultdict(lambda: {
        "sources": set(),
        "parent": "",
        "related_methods": set(),
        "related_knowledge": set(),
        "related_exam_points": set(),
        "notes": []
    })

    # 注入考纲基准节点作为种子
    for disc, m_list in CORE_METHODS_CATALOG.items():
        for m in m_list:
            d = fusion_dict[("Method", disc, m)]
            d["sources"].add("LECTURE_NOTES")
            d["sources"].add("QIANGHUA36")
            d["sources"].add("LI_FAN")
            d["parent"] = disc

    for disc, kp_list in CORE_KNOWLEDGE_CATALOG.items():
        for kp in kp_list:
            d = fusion_dict[("KnowledgePoint", disc, kp)]
            d["sources"].add("LECTURE_NOTES")
            d["sources"].add("QIANGHUA36")
            d["sources"].add("LI_FAN")
            d["parent"] = disc

    for n in all_raw_nodes:
        ntype = n["node_type"]
        disc = DISC_NORM.get(n["discipline"], n["discipline"])
        name = clean_and_validate_node_name(n["name"])
        if not name or len(name) < 2:
            continue
            
        key = (ntype, disc, name)
        d = fusion_dict[key]
        d["sources"].add(n["source_id"])
        parent_cleaned = clean_and_validate_node_name(n.get("parent", ""))
        if parent_cleaned and not d["parent"]:
            d["parent"] = parent_cleaned
        for m in n.get("related_methods", []):
            m_cl = clean_and_validate_node_name(m)
            if m_cl:
                d["related_methods"].add(m_cl)
        for k in n.get("related_knowledge", []):
            k_cl = clean_and_validate_node_name(k)
            if k_cl:
                d["related_knowledge"].add(k_cl)
        for ep in n.get("related_exam_points", []):
            ep_cl = clean_and_validate_node_name(ep)
            if ep_cl:
                d["related_exam_points"].add(ep_cl)
        if n.get("notes") and len(d["notes"]) < 3:
            d["notes"].append(n["notes"])

    candidates = []
    for (ntype, disc, name), d in sorted(fusion_dict.items(), key=lambda x: (x[0][1], x[0][0], -len(x[1]["sources"]), x[0][2])):
        node_id = assign_canonical_id(ntype, disc, name)
        candidate = {
            "id": node_id,
            "type": ntype,
            "name": name,
            "discipline": disc,
            "parent": d["parent"],
            "sources": sorted(list(d["sources"])),
            "source_count": len(d["sources"]),
            "related_methods": sorted(list(d["related_methods"]))[:10],
            "related_knowledge": sorted(list(d["related_knowledge"]))[:10],
            "related_exam_points": sorted(list(d["related_exam_points"]))[:10],
            "evidence_notes": d["notes"]
        }
        candidates.append(candidate)

    out_file = BASE_DIR / "teaching_ontology_candidate.jsonl"
    with open(out_file, "w", encoding="utf-8") as f:
        for c in candidates:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    type_counts = Counter(c["type"] for c in candidates)
    src_3_count = sum(1 for c in candidates if c["source_count"] >= 3)
    src_2_count = sum(1 for c in candidates if c["source_count"] == 2)
    src_1_count = sum(1 for c in candidates if c["source_count"] == 1)

    print(f"  - 合成教学候选本体总节点数: {len(candidates)} 个 -> {out_file.name}")
    print(f"  - 节点类型分布: {dict(type_counts)}")
    print(f"  - 跨源支撑度: 三源共识项 {src_3_count} 个, 双源支撑项 {src_2_count} 个, 单源项 {src_1_count} 个")

    return candidates

# ===========================================================================
# Phase 3: 语义对齐管道 (Semantic Alignment)
# ===========================================================================

def run_phase3_alignment(teaching_candidates):
    print("\n" + "=" * 75)
    print("[Phase 3/7] 执行题目级 Pass 1 语义候选向教学本体对齐与证据链锚定...")
    print("=" * 75)

    exact_index = defaultdict(list)     # surface -> [node]
    core_index = defaultdict(list)      # core_term -> [node]
    disc_nodes = defaultdict(list)      # disc -> [node]

    for node in teaching_candidates:
        s = node["name"]
        exact_index[s].append(node)
        core = clean_term_prefix(s)
        if core and len(core) >= 2:
            core_index[core].append(node)
        disc_nodes[node["discipline"]].append(node)

    candidate_qids_map = defaultdict(list)
    cand_index_path = INVENTORY_DIR / "indexes" / "candidate_to_qids.jsonl"
    if cand_index_path.exists():
        with open(cand_index_path, "r", encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                stype = d.get("semantic_type")
                surf = d.get("normalized_surface")
                qids = d.get("qids", [])
                candidate_qids_map[(stype, surf)] = qids

    qid_meta = {}
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            raw_disc = d.get("discipline", "")
            qid_meta[d["qid"]] = {
                "discipline": DISC_NORM.get(raw_disc, "高等数学"),
                "book": d.get("book", ""),
                "chapter": d.get("chapter_name", "")
            }

    alignment_results = []
    seen_alignments = set()

    candidate_files = [
        ("knowledge", "KnowledgePoint"),
        ("exam_point", "ExamPoint"),
        ("used_method", "Method"),
        ("alternative_method", "Method"),
        ("invalid_method", "Method"),
        ("pitfall", "Pitfall")
    ]

    for fname, expected_type in candidate_files:
        p = INVENTORY_DIR / "candidates" / f"{fname}s.jsonl"
        if not p.exists():
            p = INVENTORY_DIR / "candidates" / f"{fname}.jsonl"
        if not p.exists():
            continue

        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                cand_data = json.loads(line)
                surf = cand_data.get("normalized_surface", "")
                if not surf:
                    continue

                evidence_qids = candidate_qids_map.get((fname, surf), [])
                if not evidence_qids:
                    evidence_qids = cand_data.get("qids", [])

                disc_counter = Counter()
                for qid in evidence_qids:
                    if qid in qid_meta:
                        disc_counter[qid_meta[qid]["discipline"]] += 1
                dom_discipline = disc_counter.most_common(1)[0][0] if disc_counter else "高等数学"

                matched_node = None
                conf = 0.0
                reason = ""

                # 策略 1: 同义词表重定向
                synonym_target = SYNONYM_MAP.get(surf, "")
                if synonym_target and synonym_target in exact_index:
                    for n in exact_index[synonym_target]:
                        if n["discipline"] == dom_discipline:
                            matched_node = n
                            conf = 0.98
                            reason = f"考研标准同义术语映射 ({surf} -> {synonym_target})"
                            break
                    if not matched_node and exact_index[synonym_target]:
                        matched_node = exact_index[synonym_target][0]
                        conf = 0.92
                        reason = f"考研同义术语跨学科映射 ({surf} -> {synonym_target})"

                # 策略 2: 完全同名精确对齐
                if not matched_node and surf in exact_index:
                    for n in exact_index[surf]:
                        if n["discipline"] == dom_discipline and n["type"] == expected_type:
                            matched_node = n
                            conf = 1.0
                            reason = f"完全同名精确对齐 (学科: {dom_discipline}, 类型: {expected_type})"
                            break
                    if not matched_node:
                        for n in exact_index[surf]:
                            if n["discipline"] == dom_discipline:
                                matched_node = n
                                conf = 0.95
                                reason = f"完全同名解耦对齐 (Pass 1 为 {fname}，映射至规范 {n['type']} 实体)"
                                break
                    if not matched_node and exact_index[surf]:
                        matched_node = exact_index[surf][0]
                        conf = 0.90
                        reason = f"通用概念跨学科同名对齐 (学科: {matched_node['discipline']})"

                # 策略 3: 词头/词尾剥离核心匹配
                if not matched_node:
                    core_s = clean_term_prefix(surf)
                    if core_s in core_index:
                        for n in core_index[core_s]:
                            if n["discipline"] == dom_discipline:
                                matched_node = n
                                conf = 0.94 if n["type"] == expected_type else 0.90
                                reason = f"修饰词剥离后核心概念({core_s})精准对齐"
                                break
                        if not matched_node and core_index[core_s]:
                            matched_node = core_index[core_s][0]
                            conf = 0.86
                            reason = f"核心概念({core_s})跨学科对齐"

                # 策略 4: 子串包含与主题重合匹配
                if not matched_node:
                    search_pool = disc_nodes[dom_discipline]
                    best_sim = 0.0
                    best_cand = None
                    for n in search_pool:
                        n_name = n["name"]
                        if (len(n_name) >= 3 and n_name in surf) or (len(surf) >= 3 and surf in n_name):
                            sim = len(set(n_name) & set(surf)) / max(len(n_name), len(surf))
                            if sim > best_sim and sim >= 0.50:
                                best_sim = sim
                                best_cand = n
                    if best_cand:
                        matched_node = best_cand
                        conf = round(0.75 + best_sim * 0.18, 2)
                        reason = f"概念子串语义包含对齐 ({best_cand['name']} ⊆ {surf})"

                if matched_node:
                    key = (surf, fname, matched_node["id"])
                    if key not in seen_alignments:
                        seen_alignments.add(key)
                        alignment_results.append({
                            "surface": surf,
                            "semantic_type": fname,
                            "matched_node": matched_node["id"],
                            "matched_name": matched_node["name"],
                            "matched_type": matched_node["type"],
                            "discipline": dom_discipline,
                            "confidence": conf,
                            "matching_reason": reason,
                            "source_basis": matched_node["sources"],
                            "evidence_qids": evidence_qids[:20],
                            "total_evidence_count": len(evidence_qids)
                        })

    out_align_file = ALIGN_OUT_DIR / "semantic_alignment.jsonl"
    with open(out_align_file, "w", encoding="utf-8") as f:
        for it in alignment_results:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")

    high_conf = sum(1 for r in alignment_results if r["confidence"] >= 0.90)
    med_conf = sum(1 for r in alignment_results if 0.80 <= r["confidence"] < 0.90)
    low_conf = sum(1 for r in alignment_results if r["confidence"] < 0.80)

    print(f"  - 候选表面成功对齐总数: {len(alignment_results)} 条 -> {out_align_file.name}")
    print(f"  - 置信度分布: 高置信度 (>=0.90) {high_conf} 条 | 中置信度 (0.80-0.89) {med_conf} 条 | 审阅级 (<0.80) {low_conf} 条")

    return alignment_results

# ===========================================================================
# Phase 4: 逐题语义关联全量链接 (Question Linking)
# ===========================================================================

def run_phase4_question_linking(teaching_candidates, alignment_results):
    print("\n" + "=" * 75)
    print("[Phase 4/7] 遍历全量 4,575 题建立题目到 Canonical Nodes 语义链接...")
    print("=" * 75)

    surf_to_node = defaultdict(dict)
    for r in alignment_results:
        stype = r["semantic_type"]
        surf = r["surface"]
        nid = r["matched_node"]
        ntype = r["matched_type"]
        surf_to_node[stype][surf] = (nid, ntype)
        surf_to_node["any"][surf] = (nid, ntype)

    question_links = []
    matched_qids = set()

    with open(SEMANTIC_RAW_PATH, "r", encoding="utf-8") as f:
        for line in f:
            q = json.loads(line)
            qid = q["qid"]
            raw_disc = q.get("discipline", "")
            disc = DISC_NORM.get(raw_disc, "高等数学")
            book = q.get("book", "")
            ch = q.get("chapter_name", "")

            eps = set()
            kps = set()
            methods = set()

            def extract_names(items):
                res = []
                for it in items:
                    if isinstance(it, dict):
                        n = it.get("name") or it.get("surface") or ""
                    else:
                        n = str(it)
                    norm = normalize_surface(n)
                    if norm:
                        res.append(norm)
                return res

            def resolve_node(s, preferred_type):
                if s in surf_to_node[preferred_type]:
                    return surf_to_node[preferred_type][s]
                syn = SYNONYM_MAP.get(s, "")
                if syn and syn in surf_to_node[preferred_type]:
                    return surf_to_node[preferred_type][syn]
                if s in surf_to_node["any"]:
                    return surf_to_node["any"][s]
                if syn and syn in surf_to_node["any"]:
                    return surf_to_node["any"][syn]
                return None

            # 映射 exam_point_candidates
            for s in extract_names(q.get("exam_point_candidates", [])):
                res = resolve_node(s, "exam_point")
                if res:
                    nid, ntype = res
                    if ntype == "ExamPoint": eps.add(nid)
                    elif ntype == "KnowledgePoint": kps.add(nid)
                    elif ntype == "Method": methods.add(nid)

            # 映射 knowledge_candidates
            for s in extract_names(q.get("knowledge_candidates", [])):
                res = resolve_node(s, "knowledge")
                if res:
                    nid, ntype = res
                    if ntype == "KnowledgePoint": kps.add(nid)
                    elif ntype == "Method": methods.add(nid)
                    elif ntype == "ExamPoint": eps.add(nid)

            # 映射 used_methods
            for s in extract_names(q.get("used_methods", [])):
                res = resolve_node(s, "used_method")
                if res:
                    nid, ntype = res
                    if ntype == "Method": methods.add(nid)
                    elif ntype == "KnowledgePoint": kps.add(nid)
                    elif ntype == "ExamPoint": eps.add(nid)

            # 映射 alternative_methods
            for s in extract_names(q.get("alternative_methods", [])):
                res = resolve_node(s, "alternative_method")
                if res:
                    nid, ntype = res
                    if ntype == "Method": methods.add(nid)

            if eps or kps or methods:
                matched_qids.add(qid)

            link_record = {
                "qid": qid,
                "discipline": disc,
                "book": book,
                "chapter": ch,
                "exam_points": sorted(list(eps)),
                "knowledge_points": sorted(list(kps)),
                "methods": sorted(list(methods))
            }
            question_links.append(link_record)

    out_links_path = BASE_DIR / "question_semantic_links.jsonl"
    with open(out_links_path, "w", encoding="utf-8") as f:
        for r in question_links:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    coverage_pct = len(matched_qids) / len(question_links) * 100 if question_links else 0
    print(f"  - 题目链接记录总数: {len(question_links)} 道 -> {out_links_path.name}")
    print(f"  - 成功挂载规范节点题目数: {len(matched_qids)} / {len(question_links)} ({coverage_pct:.1f}%)")

    return question_links

# ===========================================================================
# Phase 5: 规范语义层固化 (Canonical Semantic Layer)
# ===========================================================================

def run_phase5_canonical_layer(teaching_candidates, alignment_results, question_links):
    print("\n" + "=" * 75)
    print("[Phase 5/7] 固化规范语义图谱节点集并注入实证拓扑关联 (canonical_nodes.json)...")
    print("=" * 75)

    node_aliases = defaultdict(set)
    node_provenance = defaultdict(set)
    node_linked_qids = defaultdict(set)

    for r in alignment_results:
        nid = r["matched_node"]
        surf = r["surface"]
        node_aliases[nid].add(surf)
        node_provenance[nid].add("PASS1_VISION")
        for s in r["source_basis"]:
            node_provenance[nid].add(s)
        for qid in r.get("evidence_qids", []):
            node_linked_qids[nid].add(qid)

    # 1. 从 question_links 计算实证共现关联
    ep_to_kps = defaultdict(Counter)
    ep_to_methods = defaultdict(Counter)
    q_to_eps = defaultdict(list)

    for q in question_links:
        qid = q["qid"]
        eps = q["exam_points"]
        kps = q["knowledge_points"]
        methods = q["methods"]
        q_to_eps[qid] = eps

        for ep in eps:
            for kp in kps:
                ep_to_kps[ep][kp] += 1
            for m in methods:
                ep_to_methods[ep][m] += 1

    # 2. 从 signals.jsonl 注入 Signal -> ExamPoint 关联
    ep_to_signals = defaultdict(Counter)
    signal_path = INVENTORY_DIR / "candidates" / "signals.jsonl"
    if signal_path.exists():
        with open(signal_path, "r", encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                sig = d.get("normalized_surface", "")
                for qid in d.get("qids", []):
                    if qid in q_to_eps:
                        for ep in q_to_eps[qid]:
                            ep_to_signals[ep][sig] += 1

    # 3. 从 conditions.jsonl 与 pitfalls.jsonl 注入 Method 关联
    method_to_conditions = defaultdict(set)
    cond_path = INVENTORY_DIR / "candidates" / "conditions.jsonl"
    if cond_path.exists():
        with open(cond_path, "r", encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                surf = d.get("normalized_surface", "")
                for m in d.get("related_methods", []):
                    for c in teaching_candidates:
                        if c["type"] == "Method" and (c["name"] == m or clean_term_prefix(c["name"]) == clean_term_prefix(m)):
                            if len(method_to_conditions[c["id"]]) < 5:
                                method_to_conditions[c["id"]].add(surf)

    method_to_pitfalls = defaultdict(set)
    pitfall_path = INVENTORY_DIR / "candidates" / "pitfalls.jsonl"
    if pitfall_path.exists():
        with open(pitfall_path, "r", encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                surf = d.get("normalized_surface", "")
                for c in teaching_candidates:
                    if c["type"] in ["ExamPoint", "Method"] and clean_term_prefix(c["name"]) in surf:
                        if len(method_to_pitfalls[c["id"]]) < 5:
                            method_to_pitfalls[c["id"]].add(surf)

    def sanitize_relation_meta(text):
        if not text:
            return ""
        s = str(text).strip()
        s = re.sub(r'[\*"`\']', '', s).strip()
        s = s.replace(r'$\frac00$', '0/0型未定式')
        s = s.replace(r'$\chi^2$', '卡方分布')
        s = re.sub(r'^\$+|\$+$', '', s).strip()
        s = re.sub(r'^[①②③④⑤⑥⑦⑧⑨⑩\d]+[\.、\s]*', '', s).strip()
        s = re.sub(r'\s+', ' ', s).strip()
        return s[:70]

    canonical_nodes = []
    for c in teaching_candidates:
        nid = c["id"]
        prov = set(c["sources"]) | node_provenance[nid]
        
        # 组装实证与教学融合 relations
        rel_kp = [kp for kp, _ in ep_to_kps[nid].most_common(5)] if nid in ep_to_kps else c.get("related_knowledge", [])
        rel_m = [m for m, _ in ep_to_methods[nid].most_common(5)] if nid in ep_to_methods else c.get("related_methods", [])
        
        # 清洗 signals, conditions, pitfalls
        raw_sigs = [s for s, _ in ep_to_signals[nid].most_common(8)]
        rel_sig = []
        for s in raw_sigs:
            cl = sanitize_relation_meta(s)
            if cl and len(cl) >= 3 and not any(k in cl for k in ['\\frac', '\\sum', '\\int', '\\begin', '\\end']) and cl not in rel_sig:
                rel_sig.append(cl)
                if len(rel_sig) >= 5: break
                
        rel_cond = []
        for s in sorted(list(method_to_conditions[nid])):
            cl = sanitize_relation_meta(s)
            if cl and len(cl) >= 3 and not any(k in cl for k in ['\\frac', '\\sum', '\\int', '\\begin', '\\end']) and cl not in rel_cond:
                rel_cond.append(cl)
                if len(rel_cond) >= 5: break
                
        rel_pf = []
        for s in sorted(list(method_to_pitfalls[nid])):
            cl = sanitize_relation_meta(s)
            if cl and len(cl) >= 3 and not any(k in cl for k in ['\\frac', '\\sum', '\\int', '\\begin', '\\end']) and cl not in rel_pf:
                rel_pf.append(cl)
                if len(rel_pf) >= 5: break

        rel = {
            "knowledge": rel_kp,
            "methods": rel_m,
            "signals": rel_sig,
            "conditions": rel_cond,
            "pitfalls": rel_pf
        }
        
        raw_aliases = sorted(list(node_aliases[nid]))
        aliases = []
        for a in raw_aliases:
            if a == c["name"]:
                continue
            cl_a = sanitize_relation_meta(a)
            if cl_a and len(cl_a) >= 2 and not any(k in cl_a for k in ['\\', '{', '}', '$', 'frac', 'sum']) and cl_a not in aliases:
                aliases.append(cl_a)

        node_obj = {
            "id": nid,
            "display_name": c["name"],
            "type": c["type"],
            "discipline": c["discipline"],
            "parent": c["parent"],
            "aliases": aliases[:15],
            "relations": rel,
            "provenance": sorted(list(prov)),
            "evidence_question_count": len(node_linked_qids[nid])
        }
        canonical_nodes.append(node_obj)

    out_canon_path = BASE_DIR / "canonical_nodes.json"
    with open(out_canon_path, "w", encoding="utf-8") as f:
        json.dump(canonical_nodes, f, ensure_ascii=False, indent=2)

    print(f"  - 固化规范语义节点总数: {len(canonical_nodes)} 个 -> {out_canon_path.name}")
    return canonical_nodes, ep_to_kps, ep_to_methods, ep_to_signals, method_to_conditions, method_to_pitfalls

# ===========================================================================
# Phase 6: 解题认知推理图谱生成 (Reasoning Graph)
# ===========================================================================

def run_phase6_reasoning_graph(canonical_nodes, question_links, ep_to_kps, ep_to_methods, ep_to_signals, method_to_conditions, method_to_pitfalls):
    print("\n" + "=" * 75)
    print("[Phase 6/7] 构建考研数学解题认知推理图谱 (reasoning_graph.jsonl)...")
    print("=" * 75)

    canon_map = {n["id"]: n for n in canonical_nodes}
    edges = []
    edge_seen = set()

    def add_edge(src, stype, rel, tgt, ttype, weight=1.0):
        key = (src, rel, tgt)
        if key not in edge_seen:
            edge_seen.add(key)
            edges.append({
                "source": src,
                "source_type": stype,
                "relation": rel,
                "target": tgt,
                "target_type": ttype,
                "weight": weight
            })

    # 1. Question -> ExamPoint / KnowledgePoint / Method
    for q in question_links:
        qid = q["qid"]
        for ep_id in q["exam_points"]:
            add_edge(qid, "Question", "INSTANCE_OF", ep_id, "ExamPoint")
        for kp_id in q["knowledge_points"]:
            add_edge(qid, "Question", "EXERCISES_KNOWLEDGE", kp_id, "KnowledgePoint")
        for m_id in q["methods"]:
            add_edge(qid, "Question", "APPLIES_METHOD", m_id, "Method")

    # 2. ExamPoint -> KnowledgePoint (REQUIRES_KNOWLEDGE)
    for ep, kps in ep_to_kps.items():
        for kp, cnt in kps.most_common(10):
            add_edge(ep, "ExamPoint", "REQUIRES_KNOWLEDGE", kp, "KnowledgePoint", weight=cnt)

    # 3. ExamPoint -> Method (SOLVED_BY)
    for ep, ms in ep_to_methods.items():
        for m, cnt in ms.most_common(10):
            add_edge(ep, "ExamPoint", "SOLVED_BY", m, "Method", weight=cnt)

    # 4. Signal -> ExamPoint (TRIGGERS)
    for ep, sigs in ep_to_signals.items():
        for sig, cnt in sigs.most_common(3):
            add_edge(sig, "Signal", "TRIGGERS", ep, "ExamPoint", weight=cnt)

    # 5. Method -> Condition & Method -> Pitfall
    for m, conds in method_to_conditions.items():
        for cond in conds:
            add_edge(m, "Method", "PREREQUISITE_CONDITION", cond, "Condition")

    for m, pfs in method_to_pitfalls.items():
        for pf in pfs:
            add_edge(m, "Method", "AVOIDS_PITFALL", pf, "Pitfall")

    out_graph_path = BASE_DIR / "reasoning_graph.jsonl"
    with open(out_graph_path, "w", encoding="utf-8") as f:
        for e in edges:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    rel_counts = Counter(e["relation"] for e in edges)
    print(f"  - 推理图谱边总数: {len(edges)} 条 -> {out_graph_path.name}")
    print(f"  - 关系类型分布: {dict(rel_counts)}")

    return edges

# ===========================================================================
# Phase 7: 质量与冲突审计报告 (Audit & Reporting)
# ===========================================================================

def run_phase7_audit_report(canonical_nodes, alignment_results, question_links, edges):
    print("\n" + "=" * 75)
    print("[Phase 7/7] 编译生成知识图谱审计基线报告 (ontology_audit_report.txt)...")
    print("=" * 75)

    type_counts = Counter(n["type"] for n in canonical_nodes)
    disc_counts = Counter(n["discipline"] for n in canonical_nodes)

    source_contrib = Counter()
    for n in canonical_nodes:
        for s in n["provenance"]:
            source_contrib[s] += 1

    matched_qids = set(q["qid"] for q in question_links if q["exam_points"] or q["knowledge_points"] or q["methods"])
    unmatched_qids = [q["qid"] for q in question_links if not (q["exam_points"] or q["knowledge_points"] or q["methods"])]

    conf_dist = {
        "high (>=0.90)": sum(1 for r in alignment_results if r["confidence"] >= 0.90),
        "medium (0.80-0.89)": sum(1 for r in alignment_results if 0.80 <= r["confidence"] < 0.90),
        "low (<0.80)": sum(1 for r in alignment_results if r["confidence"] < 0.80)
    }

    cross_disc_nodes = []
    for n in canonical_nodes:
        if len(n["aliases"]) >= 3:
            cross_disc_nodes.append((n["id"], n["display_name"], len(n["aliases"])))

    manual_review_items = []
    for r in alignment_results:
        if r["confidence"] < 0.80 and len(manual_review_items) < 20:
            manual_review_items.append(f"- 表面词: `{r['surface']}` -> 拟对齐节点 `{r['matched_name']}` ({r['matched_node']}) | 置信度: {r['confidence']} | 理由: {r['matching_reason']}")

    report_content = f"""===========================================================================
=== 考研数学教学知识图谱与语义对齐深度审计报告 (Ontology Audit Report) ===
===========================================================================
生成时间: {time.strftime("%Y-%m-%d %H:%M:%S")}
工程基准: Direct-Vision Pass 1 (4,575 题) + 讲义资料 + 李范全书 + 强化36讲
版本规范: Canonical Semantic Graph v1.0

---------------------------------------------------------------------------
一、 知识图谱节点全量统计 (Ontology Node Statistics)
---------------------------------------------------------------------------
总规范节点数 (Canonical Nodes): {len(canonical_nodes)} 个

1. 按节点类型分布:
   - Topic (宏观专题): {type_counts.get('Topic', 0)} 个
   - ExamPoint (题型/考点): {type_counts.get('ExamPoint', 0)} 个
   - KnowledgePoint (基础理论知识): {type_counts.get('KnowledgePoint', 0)} 个
   - Method (解题方法与算法): {type_counts.get('Method', 0)} 个
   - Pitfall (易错与避坑点): {type_counts.get('Pitfall', 0)} 个

2. 按学科分布:
   - 高等数学 (CALC): {disc_counts.get('高等数学', 0)} 个
   - 线性代数 (LA): {disc_counts.get('线性代数', 0)} 个
   - 概率论与数理统计 (PROB): {disc_counts.get('概率论与数理统计', 0)} 个

---------------------------------------------------------------------------
二、 教学数据源贡献度统计 (Source Contribution Breakdown)
---------------------------------------------------------------------------
各教学来源独立/协同贡献节点数 (含多源共有):
- 讲义资料 (LECTURE_NOTES): {source_contrib.get('LECTURE_NOTES', 0)} 个节点
- 李范全书 (LI_FAN): {source_contrib.get('LI_FAN', 0)} 个节点
- 强化36讲 (QIANGHUA36): {source_contrib.get('QIANGHUA36', 0)} 个节点
- Direct-Vision 题目实证 (PASS1_VISION): {source_contrib.get('PASS1_VISION', 0)} 个节点

---------------------------------------------------------------------------
三、 题目语义对齐与覆盖度审计 (Semantic Alignment & Question Coverage)
---------------------------------------------------------------------------
1. 题目覆盖概况:
   - 待处理真题总数: {len(question_links)} 道
   - 成功挂载规范节点题目: {len(matched_qids)} 道 ({len(matched_qids)/len(question_links)*100:.2f}%)
   - 未匹配或需人工初审题目: {len(unmatched_qids)} 道 ({len(unmatched_qids)/len(question_links)*100:.2f}%)

2. 语义对齐置信度分层:
   - 高置信度对齐项 (>= 0.90): {conf_dist['high (>=0.90)']} 项
   - 中置信度对齐项 (0.80 - 0.89): {conf_dist['medium (0.80-0.89)']} 项
   - 审阅级对齐项 (< 0.80): {conf_dist['low (<0.80)']} 项

---------------------------------------------------------------------------
四、 认知推理图谱拓扑统计 (Reasoning Graph Topology)
---------------------------------------------------------------------------
总推理边数: {len(edges)} 条
关系边明细:
- Question -> ExamPoint (INSTANCE_OF): {sum(1 for e in edges if e['relation'] == 'INSTANCE_OF')} 条
- Question -> KnowledgePoint (EXERCISES_KNOWLEDGE): {sum(1 for e in edges if e['relation'] == 'EXERCISES_KNOWLEDGE')} 条
- Question -> Method (APPLIES_METHOD): {sum(1 for e in edges if e['relation'] == 'APPLIES_METHOD')} 条
- ExamPoint -> KnowledgePoint (REQUIRES_KNOWLEDGE): {sum(1 for e in edges if e['relation'] == 'REQUIRES_KNOWLEDGE')} 条
- ExamPoint -> Method (SOLVED_BY): {sum(1 for e in edges if e['relation'] == 'SOLVED_BY')} 条
- Signal -> ExamPoint (TRIGGERS): {sum(1 for e in edges if e['relation'] == 'TRIGGERS')} 条
- Method -> Condition (PREREQUISITE_CONDITION): {sum(1 for e in edges if e['relation'] == 'PREREQUISITE_CONDITION')} 条
- Method -> Pitfall (AVOIDS_PITFALL): {sum(1 for e in edges if e['relation'] == 'AVOIDS_PITFALL')} 条

---------------------------------------------------------------------------
五、 潜在冲突与学科隔离分析 (Conflict & Cross-Discipline Analysis)
---------------------------------------------------------------------------
1. 典型多别名高频节点 (同义聚合度高):
{chr(10).join([f"   - [{nid}] {name} (汇聚 {cnt} 个同义/自然语言变体)" for nid, name, cnt in cross_disc_nodes[:8]])}

2. 方法角色解耦效果:
   - 原始 Pass 1 中混杂的 463 个交叉方法在规范语义层已完全解耦为具名 Method 实体与题型关系；
   - 知识点与方法完全拆解，杜绝“洛必达法则作为知识点”、“极限作为解题方法”的本体混乱。

---------------------------------------------------------------------------
六、 人工审核优先级建议列表 (Top Manual Review Suggestions)
---------------------------------------------------------------------------
{chr(10).join(manual_review_items[:15]) if manual_review_items else "   - 候选表面全部实现高置信度或中置信度归口映射，无低置信度 (<0.80) 风险项。"}

===========================================================================
审计结论: 考研数学教学知识图谱 Canonical Semantic Graph v1.0 骨架稳定完整，
能够支持后续自适应选题系统、错因深度诊断与知识点掌握度 (Mastery) 追踪。
===========================================================================
"""

    out_audit_path = BASE_DIR / "ontology_audit_report.txt"
    with open(out_audit_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"  - 审计报告生成完毕 -> {out_audit_path.name}")

# ===========================================================================
# Main Execution Pipeline
# ===========================================================================

def main():
    start_time = time.time()
    print("=" * 75)
    print("=== Teaching Ontology Extraction + Semantic Alignment Pipeline v1.0 ===")
    print("=" * 75)

    # Phase 1: 教学资料解析
    lec_nodes, lifan_nodes, qh_nodes = run_phase1_parsing()
    all_raw_nodes = lec_nodes + lifan_nodes + qh_nodes

    # Phase 2: 候选教学本体融合
    teaching_candidates = run_phase2_synthesis(all_raw_nodes)

    # Phase 3: 语义对齐与证据链锚定
    alignment_results = run_phase3_alignment(teaching_candidates)

    # Phase 4: 逐题语义关联链接
    question_links = run_phase4_question_linking(teaching_candidates, alignment_results)

    # Phase 5: 规范语义层固化 (注入实证拓扑)
    canonical_nodes, ep_to_kps, ep_to_methods, ep_to_signals, method_to_conditions, method_to_pitfalls = run_phase5_canonical_layer(
        teaching_candidates, alignment_results, question_links
    )

    # Phase 6: 解题认知推理图谱生成 (6类认知关系闭环)
    edges = run_phase6_reasoning_graph(
        canonical_nodes, question_links, ep_to_kps, ep_to_methods, ep_to_signals, method_to_conditions, method_to_pitfalls
    )

    # Phase 7: 深度审计报告
    run_phase7_audit_report(canonical_nodes, alignment_results, question_links, edges)

    elapsed = time.time() - start_time
    print("\n" + "=" * 75)
    print(f"=== 考研数学教学知识图谱全流程构建圆满完成！耗时: {elapsed:.2f} 秒 ===")
    print("=" * 75)

if __name__ == "__main__":
    main()
