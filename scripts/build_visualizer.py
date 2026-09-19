#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate Rich Interactive HTML Visualizer for Canonical Semantic Graph v1.0
Produces:
  1. Standalone Visualizer Artifact: ontology_visualizer.html (Full Dashboard)
  2. Compact Chat Embed Card: ontology_card_widget.html (Under 450px)
"""

import json
import re
from pathlib import Path
from collections import defaultdict, Counter

BASE_DIR = Path(r"D:\tj\822\考研题库\题库\kaoyan-semantic-data")
BRAIN_DIR = Path(r"C:\Users\Zhangwh\.gemini\antigravity\brain\fc36dd93-a0f0-4e7e-82af-03193f591af2")

CARD_WIDGET_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>考研数学教学知识图谱 v1.0 概览</title>
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
</head>
<body class="bg-transparent text-[var(--foreground)] antialiased p-3 font-sans">
  <div class="bg-[var(--card)] text-[var(--foreground)] border border-[var(--border)] rounded-2xl p-4 shadow-sm max-w-full">
    <!-- Header -->
    <div class="flex items-center justify-between border-b border-[var(--border)] pb-3 mb-3">
      <div class="flex items-center space-x-2">
        <div class="w-8 h-8 rounded-lg bg-indigo-500/20 text-indigo-400 flex items-center justify-center font-bold text-lg">
          Ω
        </div>
        <div>
          <h2 class="font-bold text-base leading-tight tracking-tight">考研数学教学知识图谱 v1.0</h2>
          <p class="text-xs text-[var(--muted-foreground)]">Canonical Semantic Graph · 权威教研与题目实证全景图</p>
        </div>
      </div>
      <span class="text-xs px-2.5 py-1 rounded-full font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
        ● 77.42% 题目挂载
      </span>
    </div>

    <!-- 4 Key KPI Metrics -->
    <div class="grid grid-cols-4 gap-2 mb-3">
      <div class="bg-[var(--content)]/40 p-2.5 rounded-xl border border-[var(--border)] text-center">
        <div class="text-[11px] text-[var(--muted-foreground)]">规范本体节点</div>
        <div class="text-lg font-bold text-indigo-400 leading-tight mt-0.5">__TOTAL_NODES__</div>
        <div class="text-[10px] text-[var(--muted-foreground)] mt-0.5">3 大学科 / 79 专题</div>
      </div>
      <div class="bg-[var(--content)]/40 p-2.5 rounded-xl border border-[var(--border)] text-center">
        <div class="text-[11px] text-[var(--muted-foreground)]">真题习题挂载</div>
        <div class="text-lg font-bold text-emerald-400 leading-tight mt-0.5">__LINKED_QUESTIONS__</div>
        <div class="text-[10px] text-[var(--muted-foreground)] mt-0.5">共 __TOTAL_QUESTIONS__ 题 (__COVERAGE_RATE__%)</div>
      </div>
      <div class="bg-[var(--content)]/40 p-2.5 rounded-xl border border-[var(--border)] text-center">
        <div class="text-[11px] text-[var(--muted-foreground)]">认知推理边</div>
        <div class="text-lg font-bold text-amber-400 leading-tight mt-0.5">__TOTAL_EDGES__</div>
        <div class="text-[10px] text-[var(--muted-foreground)] mt-0.5">8 类因果关系闭环</div>
      </div>
      <div class="bg-[var(--content)]/40 p-2.5 rounded-xl border border-[var(--border)] text-center">
        <div class="text-[11px] text-[var(--muted-foreground)]">多源三维共识</div>
        <div class="text-lg font-bold text-purple-400 leading-tight mt-0.5">__CONSENSUS_NODES__</div>
        <div class="text-[10px] text-[var(--muted-foreground)] mt-0.5">讲义/李范/强化36讲</div>
      </div>
    </div>

    <!-- Node Type Distribution Bar -->
    <div class="mb-3 bg-[var(--content)]/30 p-2.5 rounded-xl border border-[var(--border)]">
      <div class="flex justify-between items-center text-xs mb-1.5 font-medium">
        <span class="text-[var(--muted-foreground)]">规范节点层级构成</span>
        <span class="text-[var(--foreground)]">ExamPoint(1051) · KP(139) · Method(110) · Topic(79)</span>
      </div>
      <div class="w-full h-2 rounded-full overflow-hidden flex bg-gray-700/30">
        <div style="width: 75.67%" class="bg-blue-500" title="题型/考点 75.7%"></div>
        <div style="width: 10.01%" class="bg-emerald-500" title="理论知识点 10.0%"></div>
        <div style="width: 7.92%" class="bg-amber-500" title="解题方法 7.9%"></div>
        <div style="width: 5.69%" class="bg-purple-500" title="宏观专题 5.7%"></div>
        <div style="width: 0.72%" class="bg-rose-500" title="易错陷阱 0.7%"></div>
      </div>
      <div class="flex items-center justify-between text-[10px] text-[var(--muted-foreground)] mt-1.5">
        <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-blue-500 inline-block"></span> 题型/考点 75.7%</span>
        <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-emerald-500 inline-block"></span> 基础知识点 10.0%</span>
        <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-amber-500 inline-block"></span> 解题方法 7.9%</span>
        <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-purple-500 inline-block"></span> 宏观专题 5.7%</span>
      </div>
    </div>

    <!-- Core Consensus Highlights -->
    <div class="flex items-center justify-between pt-1 text-xs">
      <div class="flex items-center gap-1.5 flex-wrap">
        <span class="text-[11px] text-[var(--muted-foreground)]">核心共识考点:</span>
        <span class="px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 text-[11px] border border-blue-500/20">洛必达法则</span>
        <span class="px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 text-[11px] border border-amber-500/20">等价无穷小替换</span>
        <span class="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[11px] border border-emerald-500/20">分部积分法</span>
        <span class="px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 text-[11px] border border-purple-500/20">极大似然估计法</span>
      </div>
      <div class="text-[11px] text-indigo-400 font-medium">
        详见独立可视化大屏 ➔
      </div>
    </div>
  </div>
</body>
</html>
"""

FULL_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>考研数学教学知识图谱与语义推理可视化系统 (Canonical Semantic Graph v1.0)</title>
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
  <style>
    /* Custom scrollbar styling */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: rgba(0,0,0,0.05); }
    ::-webkit-scrollbar-thumb { background: rgba(150,150,150,0.3); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(150,150,150,0.5); }
    .glass-panel { backdrop-filter: blur(12px); background: rgba(15, 23, 42, 0.75); }
    .tab-btn.active { border-bottom: 2px solid #6366f1; color: #818cf8; font-weight: 600; }
  </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen font-sans flex flex-col antialiased selection:bg-indigo-500 selection:text-white">

  <!-- Top Navigation Header -->
  <header class="bg-slate-900/90 border-b border-slate-800 sticky top-0 z-40 backdrop-blur px-6 py-3.5 flex items-center justify-between">
    <div class="flex items-center space-x-3">
      <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-purple-500 flex items-center justify-center text-white font-bold text-xl shadow-lg shadow-indigo-500/20">
        Ω
      </div>
      <div>
        <div class="flex items-center space-x-2">
          <h1 class="text-lg font-bold text-white tracking-tight">考研数学教学知识图谱可视化系统</h1>
          <span class="text-xs px-2 py-0.5 rounded-full font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">v1.0 Canonical</span>
          <span class="text-xs px-2 py-0.5 rounded-full font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">Pass 1 实证对齐</span>
        </div>
        <p class="text-xs text-slate-400">结合《讲义资料》《李范全书》《强化36讲》与 4,575 题 Direct-Vision 认知语义</p>
      </div>
    </div>

    <!-- Navigation Tabs -->
    <div class="flex space-x-1 text-sm bg-slate-800/80 p-1 rounded-xl border border-slate-700/60">
      <button onclick="switchTab('analytics')" id="btn-analytics" class="tab-btn active px-3.5 py-1.5 rounded-lg text-slate-300 hover:text-white transition flex items-center gap-1.5">
        <span>📊</span> 全景看板
      </button>
      <button onclick="switchTab('graph')" id="btn-graph" class="tab-btn px-3.5 py-1.5 rounded-lg text-slate-400 hover:text-white transition flex items-center gap-1.5">
        <span>🕸️</span> 知识网络
      </button>
      <button onclick="switchTab('tree')" id="btn-tree" class="tab-btn px-3.5 py-1.5 rounded-lg text-slate-400 hover:text-white transition flex items-center gap-1.5">
        <span>🌲</span> 教学树谱
      </button>
      <button onclick="switchTab('questions')" id="btn-questions" class="tab-btn px-3.5 py-1.5 rounded-lg text-slate-400 hover:text-white transition flex items-center gap-1.5">
        <span>📝</span> 题目推理
      </button>
      <button onclick="switchTab('lexicon')" id="btn-lexicon" class="tab-btn px-3.5 py-1.5 rounded-lg text-slate-400 hover:text-white transition flex items-center gap-1.5">
        <span>🔍</span> 对齐词典
      </button>
    </div>

    <!-- Quick Global Search Input -->
    <div class="relative w-64">
      <input type="text" id="globalSearchInput" placeholder="全局搜索概念/考点/方法..." 
        class="w-full bg-slate-800/90 text-xs text-slate-200 pl-8 pr-3 py-2 rounded-xl border border-slate-700 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition"
        oninput="handleGlobalSearch(this.value)">
      <span class="absolute left-2.5 top-2 text-slate-400 text-xs">🔍</span>
      <!-- Search dropdown results -->
      <div id="searchResults" class="hidden absolute left-0 right-0 top-10 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl max-h-80 overflow-y-auto z-50 p-2 text-xs"></div>
    </div>
  </header>

  <!-- Main Workspace Content -->
  <main class="flex-1 flex overflow-hidden">

    <!-- ======================================================== -->
    <!-- TAB 1: 全景大屏 (Analytics Dashboard) -->
    <!-- ======================================================== -->
    <section id="tab-analytics" class="flex-1 overflow-y-auto p-6 space-y-6">
      <!-- 5 Big KPI Hero Cards -->
      <div class="grid grid-cols-1 md:grid-cols-5 gap-4">
        <div class="bg-gradient-to-br from-indigo-950/50 to-slate-900 p-4 rounded-2xl border border-indigo-500/20 shadow-sm relative overflow-hidden">
          <div class="text-xs font-medium text-indigo-300">规范教学节点 (Canonical Nodes)</div>
          <div class="text-3xl font-extrabold text-white mt-2" id="kpi-nodes">1,389</div>
          <div class="text-xs text-slate-400 mt-1 flex items-center justify-between">
            <span>79 专题 · 1051 题型考点</span>
            <span class="text-indigo-400 font-semibold">100% 固化</span>
          </div>
        </div>

        <div class="bg-gradient-to-br from-emerald-950/50 to-slate-900 p-4 rounded-2xl border border-emerald-500/20 shadow-sm relative overflow-hidden">
          <div class="text-xs font-medium text-emerald-300">题目语义挂载率 (Question Linked)</div>
          <div class="text-3xl font-extrabold text-white mt-2" id="kpi-linked">77.42%</div>
          <div class="text-xs text-slate-400 mt-1 flex items-center justify-between">
            <span>3,542 / 4,575 题已挂载</span>
            <span class="text-emerald-400 font-semibold">高保真</span>
          </div>
        </div>

        <div class="bg-gradient-to-br from-amber-950/50 to-slate-900 p-4 rounded-2xl border border-amber-500/20 shadow-sm relative overflow-hidden">
          <div class="text-xs font-medium text-amber-300">认知推理因果边 (Reasoning Edges)</div>
          <div class="text-3xl font-extrabold text-white mt-2" id="kpi-edges">9,302</div>
          <div class="text-xs text-slate-400 mt-1 flex items-center justify-between">
            <span>8 大强类型因果关系</span>
            <span class="text-amber-400 font-semibold">自适应支撑</span>
          </div>
        </div>

        <div class="bg-gradient-to-br from-purple-950/50 to-slate-900 p-4 rounded-2xl border border-purple-500/20 shadow-sm relative overflow-hidden">
          <div class="text-xs font-medium text-purple-300">多源强共识核心考点 (Consensus)</div>
          <div class="text-3xl font-extrabold text-white mt-2" id="kpi-consensus">244</div>
          <div class="text-xs text-slate-400 mt-1 flex items-center justify-between">
            <span>讲义/李范/强化36讲共识</span>
            <span class="text-purple-400 font-semibold">权威教研</span>
          </div>
        </div>

        <div class="bg-gradient-to-br from-cyan-950/50 to-slate-900 p-4 rounded-2xl border border-cyan-500/20 shadow-sm relative overflow-hidden">
          <div class="text-xs font-medium text-cyan-300">对齐表面词汇量 (Surfaces)</div>
          <div class="text-3xl font-extrabold text-white mt-2" id="kpi-surfaces">2,655</div>
          <div class="text-xs text-slate-400 mt-1 flex items-center justify-between">
            <span>高置信对齐 (无低分噪点)</span>
            <span class="text-cyan-400 font-semibold">精确归口</span>
          </div>
        </div>
      </div>

      <!-- Charts & Visual Composition Row -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- 1. Node Types Distribution -->
        <div class="bg-slate-900/80 p-5 rounded-2xl border border-slate-800 flex flex-col justify-between">
          <div>
            <div class="flex items-center justify-between mb-4">
              <h3 class="font-bold text-white text-sm flex items-center gap-2">
                <span class="w-2.5 h-2.5 rounded-full bg-blue-500"></span> 知识图谱节点类型构成
              </h3>
              <span class="text-xs text-slate-400">总计 1,389 节点</span>
            </div>
            <!-- Interactive Donut Chart -->
            <div class="flex items-center justify-center my-2">
              <svg width="180" height="180" viewBox="0 0 42 42" class="donut">
                <circle class="donut-ring" cx="21" cy="21" r="15.91549430918954" fill="transparent" stroke="#1e293b" stroke-width="5"></circle>
                <!-- ExamPoint 75.67% -->
                <circle cx="21" cy="21" r="15.91549430918954" fill="transparent" stroke="#3b82f6" stroke-width="5" stroke-dasharray="75.67 24.33" stroke-dashoffset="25"></circle>
                <!-- KnowledgePoint 10.01% -->
                <circle cx="21" cy="21" r="15.91549430918954" fill="transparent" stroke="#10b981" stroke-width="5" stroke-dasharray="10.01 89.99" stroke-dashoffset="49.33"></circle>
                <!-- Method 7.92% -->
                <circle cx="21" cy="21" r="15.91549430918954" fill="transparent" stroke="#f59e0b" stroke-width="5" stroke-dasharray="7.92 92.08" stroke-dashoffset="39.32"></circle>
                <!-- Topic 5.69% -->
                <circle cx="21" cy="21" r="15.91549430918954" fill="transparent" stroke="#8b5cf6" stroke-width="5" stroke-dasharray="5.69 94.31" stroke-dashoffset="31.4"></circle>
                <!-- Pitfall 0.72% -->
                <circle cx="21" cy="21" r="15.91549430918954" fill="transparent" stroke="#ef4444" stroke-width="5" stroke-dasharray="0.72 99.28" stroke-dashoffset="25.71"></circle>
                <text x="50%" y="47%" text-anchor="middle" fill="#fff" font-size="4" font-weight="bold">1,389</text>
                <text x="50%" y="57%" text-anchor="middle" fill="#94a3b8" font-size="2.2">NODES</text>
              </svg>
            </div>
          </div>
          <!-- Legend list -->
          <div class="grid grid-cols-2 gap-2 text-xs text-slate-300 mt-2">
            <div class="flex items-center justify-between p-2 rounded-lg bg-slate-800/50 border border-slate-700/50">
              <span class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-blue-500"></span> 题型考点 (ExamPoint)</span>
              <span class="font-bold text-white">1,051 (75.7%)</span>
            </div>
            <div class="flex items-center justify-between p-2 rounded-lg bg-slate-800/50 border border-slate-700/50">
              <span class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-emerald-500"></span> 理论知识 (Knowledge)</span>
              <span class="font-bold text-white">139 (10.0%)</span>
            </div>
            <div class="flex items-center justify-between p-2 rounded-lg bg-slate-800/50 border border-slate-700/50">
              <span class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-amber-500"></span> 解题方法 (Method)</span>
              <span class="font-bold text-white">110 (7.9%)</span>
            </div>
            <div class="flex items-center justify-between p-2 rounded-lg bg-slate-800/50 border border-slate-700/50">
              <span class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-purple-500"></span> 宏观专题 (Topic)</span>
              <span class="font-bold text-white">79 (5.7%)</span>
            </div>
          </div>
        </div>

        <!-- 2. Discipline Knowledge Coverage -->
        <div class="bg-slate-900/80 p-5 rounded-2xl border border-slate-800 flex flex-col justify-between">
          <div>
            <div class="flex items-center justify-between mb-4">
              <h3 class="font-bold text-white text-sm flex items-center gap-2">
                <span class="w-2.5 h-2.5 rounded-full bg-cyan-500"></span> 三大学科覆盖与题库分布
              </h3>
              <span class="text-xs text-slate-400">考研数学一/二/三</span>
            </div>
            <!-- Discipline bars -->
            <div class="space-y-3.5 my-3">
              <div>
                <div class="flex justify-between text-xs mb-1">
                  <span class="text-cyan-300 font-medium">高等数学 (Calculus)</span>
                  <span class="text-white font-bold">944 节点 (67.96%) · 3,257 题</span>
                </div>
                <div class="w-full h-2.5 bg-slate-800 rounded-full overflow-hidden">
                  <div class="bg-cyan-500 h-full rounded-full" style="width: 68%"></div>
                </div>
              </div>

              <div>
                <div class="flex justify-between text-xs mb-1">
                  <span class="text-amber-300 font-medium">概率论与数理统计 (Probability)</span>
                  <span class="text-white font-bold">272 节点 (19.58%) · 606 题</span>
                </div>
                <div class="w-full h-2.5 bg-slate-800 rounded-full overflow-hidden">
                  <div class="bg-amber-500 h-full rounded-full" style="width: 20%"></div>
                </div>
              </div>

              <div>
                <div class="flex justify-between text-xs mb-1">
                  <span class="text-purple-300 font-medium">线性代数 (Linear Algebra)</span>
                  <span class="text-white font-bold">173 节点 (12.45%) · 712 题</span>
                </div>
                <div class="w-full h-2.5 bg-slate-800 rounded-full overflow-hidden">
                  <div class="bg-purple-500 h-full rounded-full" style="width: 12%"></div>
                </div>
              </div>
            </div>
          </div>

          <!-- Book breakdown tags -->
          <div class="border-t border-slate-800 pt-3">
            <div class="text-[11px] text-slate-400 mb-2 font-medium">已覆盖五大经典题库:</div>
            <div class="flex flex-wrap gap-1.5 text-[11px]">
              <span class="px-2 py-1 bg-slate-800 rounded-lg text-slate-300 border border-slate-700/60">《张宇1000题》: 1,229 题</span>
              <span class="px-2 py-1 bg-slate-800 rounded-lg text-slate-300 border border-slate-700/60">《老姚高数》: 1,170 题</span>
              <span class="px-2 py-1 bg-slate-800 rounded-lg text-slate-300 border border-slate-700/60">《基础30讲》: 872 题</span>
              <span class="px-2 py-1 bg-slate-800 rounded-lg text-slate-300 border border-slate-700/60">《李范全书》: 840 题</span>
              <span class="px-2 py-1 bg-slate-800 rounded-lg text-slate-300 border border-slate-700/60">《强化36讲》: 464 题</span>
            </div>
          </div>
        </div>

        <!-- 3. Reasoning Edges Breakdown -->
        <div class="bg-slate-900/80 p-5 rounded-2xl border border-slate-800 flex flex-col justify-between">
          <div>
            <div class="flex items-center justify-between mb-4">
              <h3 class="font-bold text-white text-sm flex items-center gap-2">
                <span class="w-2.5 h-2.5 rounded-full bg-amber-500"></span> 8 类认知推理边拓扑分布
              </h3>
              <span class="text-xs text-slate-400">总计 9,302 边</span>
            </div>
            <div class="space-y-2 text-xs">
              <div class="flex items-center justify-between p-2 rounded-lg bg-slate-800/40">
                <span class="text-slate-300">Question ➔ Method (APPLIES)</span>
                <span class="font-bold text-amber-400">3,525 条</span>
              </div>
              <div class="flex items-center justify-between p-2 rounded-lg bg-slate-800/40">
                <span class="text-slate-300">Question ➔ Knowledge (EXERCISES)</span>
                <span class="font-bold text-emerald-400">1,905 条</span>
              </div>
              <div class="flex items-center justify-between p-2 rounded-lg bg-slate-800/40">
                <span class="text-slate-300">Question ➔ ExamPoint (INSTANCE_OF)</span>
                <span class="font-bold text-blue-400">1,671 条</span>
              </div>
              <div class="flex items-center justify-between p-2 rounded-lg bg-slate-800/40">
                <span class="text-slate-300">Method ➔ Pitfall (AVOIDS)</span>
                <span class="font-bold text-rose-400">595 条</span>
              </div>
              <div class="flex items-center justify-between p-2 rounded-lg bg-slate-800/40">
                <span class="text-slate-300">ExamPoint ➔ Method (SOLVED_BY)</span>
                <span class="font-bold text-indigo-400">526 条</span>
              </div>
              <div class="flex items-center justify-between p-2 rounded-lg bg-slate-800/40">
                <span class="text-slate-300">Signal ➔ ExamPoint (TRIGGERS)</span>
                <span class="font-bold text-purple-400">437 条</span>
              </div>
              <div class="flex items-center justify-between p-2 rounded-lg bg-slate-800/40">
                <span class="text-slate-300">ExamPoint ➔ Knowledge (REQUIRES)</span>
                <span class="font-bold text-teal-400">337 条</span>
              </div>
              <div class="flex items-center justify-between p-2 rounded-lg bg-slate-800/40">
                <span class="text-slate-300">Method ➔ Condition (PREREQUISITE)</span>
                <span class="font-bold text-yellow-400">306 条</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Multi-source Consensus & High-Frequency Hubs -->
      <div class="bg-slate-900/80 p-5 rounded-2xl border border-slate-800">
        <div class="flex items-center justify-between mb-4">
          <div>
            <h3 class="font-bold text-white text-sm flex items-center gap-2">
              <span class="w-2.5 h-2.5 rounded-full bg-purple-500"></span> 跨源三维强共识核心考点与解题枢纽 (Top Consensus Hubs)
            </h3>
            <p class="text-xs text-slate-400 mt-0.5">在《讲义资料》《李范全书》《强化36讲》中被同时作为命题重点，且在题目中高频应用的考点</p>
          </div>
          <span class="text-xs px-3 py-1 bg-purple-500/10 text-purple-300 border border-purple-500/20 rounded-lg">244 个核心共识考点</span>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 text-xs" id="consensusHubsContainer">
          <!-- Populated by JS -->
        </div>
      </div>
    </section>

    <!-- ======================================================== -->
    <!-- TAB 2: 知识网络交互图 (Interactive Canvas Force Graph) -->
    <!-- ======================================================== -->
    <section id="tab-graph" class="flex-1 flex hidden relative overflow-hidden">
      <!-- Left Graph Control Bar -->
      <div class="w-72 bg-slate-900 border-r border-slate-800 p-4 flex flex-col justify-between z-10 shrink-0">
        <div class="space-y-4">
          <div>
            <h3 class="font-bold text-white text-sm mb-1">网络图谱控制器</h3>
            <p class="text-[11px] text-slate-400">力导向交互网络 · 缩放/拖拽/探查</p>
          </div>

          <!-- Discipline Filter -->
          <div>
            <label class="text-xs text-slate-400 block mb-1.5 font-medium">学科范围筛选</label>
            <div class="grid grid-cols-2 gap-1.5 text-xs">
              <button onclick="setGraphDiscipline('ALL')" id="filter-disc-ALL" class="graph-filter-btn active py-1.5 px-2 rounded-lg bg-indigo-600 text-white font-medium">全学科</button>
              <button onclick="setGraphDiscipline('高等数学')" id="filter-disc-CALC" class="graph-filter-btn py-1.5 px-2 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700">高等数学</button>
              <button onclick="setGraphDiscipline('线性代数')" id="filter-disc-LA" class="graph-filter-btn py-1.5 px-2 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700">线性代数</button>
              <button onclick="setGraphDiscipline('概率论与数理统计')" id="filter-disc-PROB" class="graph-filter-btn py-1.5 px-2 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700">概率统计</button>
            </div>
          </div>

          <!-- Node Type Toggles -->
          <div>
            <label class="text-xs text-slate-400 block mb-1.5 font-medium">节点类型过滤</label>
            <div class="space-y-1.5 text-xs">
              <label class="flex items-center gap-2 cursor-pointer text-slate-300 hover:text-white">
                <input type="checkbox" id="check-topic" checked onchange="updateGraphFilters()" class="rounded border-slate-700 text-purple-500 focus:ring-0">
                <span class="w-2.5 h-2.5 rounded-full bg-purple-500"></span> 宏观专题 (Topic)
              </label>
              <label class="flex items-center gap-2 cursor-pointer text-slate-300 hover:text-white">
                <input type="checkbox" id="check-ep" checked onchange="updateGraphFilters()" class="rounded border-slate-700 text-blue-500 focus:ring-0">
                <span class="w-2.5 h-2.5 rounded-full bg-blue-500"></span> 题型考点 (ExamPoint)
              </label>
              <label class="flex items-center gap-2 cursor-pointer text-slate-300 hover:text-white">
                <input type="checkbox" id="check-kp" checked onchange="updateGraphFilters()" class="rounded border-slate-700 text-emerald-500 focus:ring-0">
                <span class="w-2.5 h-2.5 rounded-full bg-emerald-500"></span> 理论知识 (Knowledge)
              </label>
              <label class="flex items-center gap-2 cursor-pointer text-slate-300 hover:text-white">
                <input type="checkbox" id="check-method" checked onchange="updateGraphFilters()" class="rounded border-slate-700 text-amber-500 focus:ring-0">
                <span class="w-2.5 h-2.5 rounded-full bg-amber-500"></span> 解题方法 (Method)
              </label>
              <label class="flex items-center gap-2 cursor-pointer text-slate-300 hover:text-white">
                <input type="checkbox" id="check-pitfall" checked onchange="updateGraphFilters()" class="rounded border-slate-700 text-rose-500 focus:ring-0">
                <span class="w-2.5 h-2.5 rounded-full bg-rose-500"></span> 易错避坑 (Pitfall)
              </label>
            </div>
          </div>

          <!-- View Controls -->
          <div class="border-t border-slate-800 pt-3 space-y-2 text-xs">
            <button onclick="resetGraphView()" class="w-full py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg border border-slate-700 transition flex items-center justify-center gap-1.5">
              <span>🎯</span> 视角居中复位
            </button>
            <button onclick="togglePhysics()" id="btn-physics" class="w-full py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg border border-slate-700 transition flex items-center justify-center gap-1.5">
              <span>⏸️</span> 暂停/恢复物理模拟
            </button>
          </div>
        </div>

        <div class="text-[11px] text-slate-500 border-t border-slate-800 pt-3">
          提示：鼠标滚轮缩放，拖拽背景平移画布，点击任意节点查看全维档案。
        </div>
      </div>

      <!-- Canvas Area -->
      <div class="flex-1 relative bg-slate-950">
        <canvas id="graphCanvas" class="w-full h-full block"></canvas>
        <div id="graphTooltip" class="hidden absolute pointer-events-none bg-slate-900/90 text-white text-xs p-2.5 rounded-xl border border-slate-700 shadow-2xl backdrop-blur z-20 max-w-xs"></div>
      </div>

      <!-- Right Node Details Drawer -->
      <div id="nodeDrawer" class="hidden w-96 bg-slate-900 border-l border-slate-800 p-5 overflow-y-auto z-10 shrink-0 flex flex-col justify-between">
        <div id="nodeDrawerContent" class="space-y-4">
          <!-- Populated by JS -->
        </div>
        <button onclick="closeNodeDrawer()" class="mt-4 w-full py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs rounded-xl border border-slate-700">
          关闭面板
        </button>
      </div>
    </section>

    <!-- ======================================================== -->
    <!-- TAB 3: 教学层级树谱 (Curriculum Tree) -->
    <!-- ======================================================== -->
    <section id="tab-tree" class="flex-1 overflow-y-auto p-6 hidden">
      <div class="max-w-5xl mx-auto space-y-4">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-base font-bold text-white">教学大纲认知层级树 (Curriculum Tree)</h2>
            <p class="text-xs text-slate-400">学科 ➔ 79 宏观专题 (Topic) ➔ 题型/考点 (ExamPoint) ➔ 解法与理论知识</p>
          </div>
          <div class="flex gap-2">
            <input type="text" id="treeFilterInput" placeholder="过滤树节点 (如: 极坐标 / 特征值)..." 
              class="w-64 bg-slate-800 text-xs text-slate-200 px-3 py-1.5 rounded-xl border border-slate-700 focus:outline-none focus:border-indigo-500"
              oninput="renderTree(this.value)">
          </div>
        </div>

        <div id="curriculumTreeContainer" class="space-y-4">
          <!-- Populated by JS -->
        </div>
      </div>
    </section>

    <!-- ======================================================== -->
    <!-- TAB 4: 题目与认知推理链检验 (Questions & Reasoning) -->
    <!-- ======================================================== -->
    <section id="tab-questions" class="flex-1 flex hidden overflow-hidden">
      <!-- Left Questions List -->
      <div class="w-96 bg-slate-900 border-r border-slate-800 p-4 flex flex-col shrink-0">
        <div class="mb-3 space-y-2">
          <h3 class="font-bold text-white text-sm">真题挂载与推理验算 (4,575 题)</h3>
          <input type="text" id="qSearchInput" placeholder="搜索 QID 或关键词..." 
            class="w-full bg-slate-800 text-xs text-slate-200 px-3 py-2 rounded-xl border border-slate-700 focus:outline-none focus:border-indigo-500"
            oninput="renderQuestionsList(this.value)">
          <div class="flex gap-1.5 text-[11px] overflow-x-auto pb-1" id="bookFilterButtons">
            <button onclick="setBookFilter('ALL')" class="px-2 py-0.5 bg-indigo-600 rounded text-white font-medium">全部</button>
            <button onclick="setBookFilter('1000题')" class="px-2 py-0.5 bg-slate-800 rounded text-slate-300 hover:bg-slate-700">1000题</button>
            <button onclick="setBookFilter('老姚')" class="px-2 py-0.5 bg-slate-800 rounded text-slate-300 hover:bg-slate-700">老姚高数</button>
            <button onclick="setBookFilter('基础30讲')" class="px-2 py-0.5 bg-slate-800 rounded text-slate-300 hover:bg-slate-700">基础30讲</button>
            <button onclick="setBookFilter('李范全书')" class="px-2 py-0.5 bg-slate-800 rounded text-slate-300 hover:bg-slate-700">李范全书</button>
            <button onclick="setBookFilter('强化36讲')" class="px-2 py-0.5 bg-slate-800 rounded text-slate-300 hover:bg-slate-700">强化36讲</button>
          </div>
        </div>

        <!-- Question List Container -->
        <div class="flex-1 overflow-y-auto space-y-2 pr-1" id="questionsListContainer">
          <!-- Populated by JS -->
        </div>
      </div>

      <!-- Right Reasoning Path Visualizer -->
      <div class="flex-1 overflow-y-auto p-6 bg-slate-950" id="questionDetailContainer">
        <div class="h-full flex items-center justify-center text-slate-500 text-sm">
          👈 请在左侧选择一道考研试题查看其规范认知推理路径链 (Cognitive Path)
        </div>
      </div>
    </section>

    <!-- ======================================================== -->
    <!-- TAB 5: 对齐词典与同义库 (Semantic Lexicon) -->
    <!-- ======================================================== -->
    <section id="tab-lexicon" class="flex-1 overflow-y-auto p-6 hidden">
      <div class="max-w-6xl mx-auto space-y-4">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-base font-bold text-white">语义对齐与同义归口词典 (Semantic Lexicon)</h2>
            <p class="text-xs text-slate-400">将 Direct-Vision Pass 1 自然语言表面精准对齐至权威教研规范节点</p>
          </div>
          <input type="text" id="lexiconFilterInput" placeholder="搜索原始提法 (如: 洛必达 / 夹逼 / 麦克劳林)..." 
            class="w-72 bg-slate-800 text-xs text-slate-200 px-3 py-2 rounded-xl border border-slate-700 focus:outline-none focus:border-indigo-500"
            oninput="renderLexiconTable(this.value)">
        </div>

        <!-- Table -->
        <div class="bg-slate-900 rounded-2xl border border-slate-800 overflow-hidden">
          <table class="w-full text-left text-xs text-slate-300">
            <thead class="bg-slate-800/80 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-700">
              <tr>
                <th class="py-3 px-4">原始自然语言提法 (Raw Surface)</th>
                <th class="py-3 px-4">概念类型</th>
                <th class="py-3 px-4">学科</th>
                <th class="py-3 px-4">对齐规范节点 (Canonical Node)</th>
                <th class="py-3 px-4">置信度</th>
                <th class="py-3 px-4">对齐规则说明</th>
                <th class="py-3 px-4 text-right">佐证题数</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-800/60" id="lexiconTableBody">
              <!-- Populated by JS -->
            </tbody>
          </table>
        </div>
      </div>
    </section>
  </main>

  <!-- Embedded Data Payload -->
  <script>
    const ONTOLOGY_DATA = __JSON_DATA_BUNDLE__;
  </script>

  <!-- Interactive Logic Script -->
  <script>
    // State
    let currentTab = 'analytics';
    let graphDiscipline = 'ALL';
    let selectedNode = null;
    let selectedBookFilter = 'ALL';
    let selectedQuestion = null;

    // Initialize on load
    window.addEventListener('DOMContentLoaded', () => {
      initAnalytics();
      initGraph();
      renderTree('');
      renderQuestionsList('');
      renderLexiconTable('');
    });

    // Tab Switching
    function switchTab(tabId) {
      currentTab = tabId;
      document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
      document.getElementById('btn-' + tabId).classList.add('active');

      document.querySelectorAll('main > section').forEach(sec => sec.classList.add('hidden'));
      document.getElementById('tab-' + tabId).classList.remove('hidden');

      if (tabId === 'graph') {
        resizeCanvas();
        startPhysics();
      }
    }

    // ==========================================================
    // Analytics Dashboard Tab
    // ==========================================================
    function initAnalytics() {
      const stats = ONTOLOGY_DATA.stats;
      document.getElementById('kpi-nodes').innerText = stats.total_nodes.toLocaleString();
      document.getElementById('kpi-linked').innerText = stats.coverage_rate + '%';
      document.getElementById('kpi-edges').innerText = stats.total_edges.toLocaleString();
      document.getElementById('kpi-consensus').innerText = stats.consensus_nodes.toLocaleString();
      document.getElementById('kpi-surfaces').innerText = stats.aligned_surfaces.toLocaleString();

      // Render top consensus hubs
      const hubsContainer = document.getElementById('consensusHubsContainer');
      hubsContainer.innerHTML = '';
      
      // Filter high consensus nodes
      const consensusNodes = ONTOLOGY_DATA.nodes.filter(n => (n.provenance || []).length >= 3).slice(0, 16);
      consensusNodes.forEach(node => {
        const card = document.createElement('div');
        card.className = 'p-3 bg-slate-800/40 hover:bg-slate-800 rounded-xl border border-slate-700/60 transition cursor-pointer flex flex-col justify-between';
        card.onclick = () => {
          switchTab('graph');
          focusNodeInGraph(node.id);
        };

        let typeBadge = 'bg-blue-500/20 text-blue-300';
        if (node.type === 'Method') typeBadge = 'bg-amber-500/20 text-amber-300';
        if (node.type === 'KnowledgePoint') typeBadge = 'bg-emerald-500/20 text-emerald-300';

        card.innerHTML = `
          <div>
            <div class="flex items-center justify-between mb-1.5">
              <span class="text-[10px] px-1.5 py-0.5 rounded font-medium ${typeBadge}">${node.type}</span>
              <span class="text-[10px] text-slate-400">${node.discipline}</span>
            </div>
            <div class="font-bold text-white text-xs truncate" title="${node.display_name}">${node.display_name}</div>
            <div class="text-[11px] text-slate-400 mt-1 truncate">${node.parent || '核心考点'}</div>
          </div>
          <div class="flex items-center justify-between mt-2 pt-2 border-t border-slate-700/50 text-[10px] text-indigo-400 font-medium">
            <span>实证佐证: ${node.evidence_question_count || 0} 题</span>
            <span>在图谱中定位 ➔</span>
          </div>
        `;
        hubsContainer.appendChild(card);
      });
    }

    // ==========================================================
    // Interactive Canvas Force Graph
    // ==========================================================
    let canvas, ctx;
    let graphNodes = [];
    let graphLinks = [];
    let isPhysicsRunning = true;
    let transform = { x: 0, y: 0, k: 1 };
    let dragNode = null;
    let isPanning = false;
    let panStart = { x: 0, y: 0 };
    let hoveredNode = null;
    let animationId = null;

    function initGraph() {
      canvas = document.getElementById('graphCanvas');
      ctx = canvas.getContext('2d');
      resizeCanvas();
      window.addEventListener('resize', resizeCanvas);

      // Mouse events for canvas
      canvas.addEventListener('mousedown', onMouseDown);
      canvas.addEventListener('mousemove', onMouseMove);
      canvas.addEventListener('mouseup', onMouseUp);
      canvas.addEventListener('wheel', onWheel, { passive: false });

      buildGraphData();
    }

    function resizeCanvas() {
      if (!canvas) return;
      canvas.width = canvas.parentElement.clientWidth;
      canvas.height = canvas.parentElement.clientHeight;
      if (!transform.x && !transform.y) {
        transform.x = canvas.width / 2;
        transform.y = canvas.height / 2;
      }
    }

    function buildGraphData() {
      // Filter nodes according to discipline and checkboxes
      const checkTopic = document.getElementById('check-topic')?.checked ?? true;
      const checkEp = document.getElementById('check-ep')?.checked ?? true;
      const checkKp = document.getElementById('check-kp')?.checked ?? true;
      const checkMethod = document.getElementById('check-method')?.checked ?? true;
      const checkPitfall = document.getElementById('check-pitfall')?.checked ?? true;

      const allowedTypes = new Set();
      if (checkTopic) allowedTypes.add('Topic');
      if (checkEp) allowedTypes.add('ExamPoint');
      if (checkKp) allowedTypes.add('KnowledgePoint');
      if (checkMethod) allowedTypes.add('Method');
      if (checkPitfall) allowedTypes.add('Pitfall');

      // Select nodes
      const candidateNodes = ONTOLOGY_DATA.nodes.filter(n => {
        if (graphDiscipline !== 'ALL' && n.discipline !== graphDiscipline) return false;
        if (!allowedTypes.has(n.type)) return false;
        // Limit exam points to top 200 by question evidence or consensus to ensure super smooth 60fps
        if (n.type === 'ExamPoint' && (n.evidence_question_count || 0) < 1 && (n.provenance || []).length < 2) return false;
        return true;
      });

      const nodeMap = new Map();
      graphNodes = candidateNodes.map((n, i) => {
        const angle = (i / candidateNodes.length) * Math.PI * 2;
        const radius = 100 + Math.random() * 250;
        const nodeObj = {
          id: n.id,
          name: n.display_name,
          type: n.type,
          discipline: n.discipline,
          raw: n,
          x: Math.cos(angle) * radius,
          y: Math.sin(angle) * radius,
          vx: 0,
          vy: 0,
          radius: getNodeRadius(n.type),
          color: getNodeColor(n.type)
        };
        nodeMap.set(n.id, nodeObj);
        return nodeObj;
      });

      // Build links between filtered nodes
      graphLinks = [];
      ONTOLOGY_DATA.sample_edges.forEach(e => {
        const s = nodeMap.get(e.source);
        const t = nodeMap.get(e.target);
        if (s && t) {
          graphLinks.push({
            source: s,
            target: t,
            relation: e.relation
          });
        }
      });

      // Also add parent topic edges
      candidateNodes.forEach(n => {
        if (n.type === 'ExamPoint') {
          const sourceNode = nodeMap.get(n.id);
          if (sourceNode) {
            for (let gn of graphNodes) {
              if (gn.type === 'Topic' && n.parent && (gn.name.includes(n.parent) || n.parent.includes(gn.name))) {
                graphLinks.push({ source: gn, target: sourceNode, relation: 'PARENT_OF' });
                break;
              }
            }
          }
        }
      });
    }

    function getNodeRadius(type) {
      switch(type) {
        case 'Topic': return 14;
        case 'ExamPoint': return 7;
        case 'Method': return 8;
        case 'KnowledgePoint': return 8;
        case 'Pitfall': return 6;
        default: return 6;
      }
    }

    function getNodeColor(type) {
      switch(type) {
        case 'Topic': return '#8b5cf6'; // Purple
        case 'ExamPoint': return '#3b82f6'; // Blue
        case 'KnowledgePoint': return '#10b981'; // Emerald
        case 'Method': return '#f59e0b'; // Amber
        case 'Pitfall': return '#ef4444'; // Red
        default: return '#94a3b8';
      }
    }

    function setGraphDiscipline(d) {
      graphDiscipline = d;
      document.querySelectorAll('.graph-filter-btn').forEach(btn => btn.classList.remove('active', 'bg-indigo-600', 'text-white'));
      const activeBtn = document.getElementById('filter-disc-' + (d === 'ALL' ? 'ALL' : (d === '高等数学' ? 'CALC' : (d === '线性代数' ? 'LA' : 'PROB'))));
      if (activeBtn) activeBtn.classList.add('active', 'bg-indigo-600', 'text-white');
      buildGraphData();
    }

    function updateGraphFilters() {
      buildGraphData();
    }

    function resetGraphView() {
      transform = { x: canvas.width / 2, y: canvas.height / 2, k: 1 };
    }

    function togglePhysics() {
      isPhysicsRunning = !isPhysicsRunning;
      document.getElementById('btn-physics').innerHTML = isPhysicsRunning ? '<span>⏸️</span> 暂停物理模拟' : '<span>▶️</span> 恢复物理模拟';
    }

    function startPhysics() {
      if (animationId) cancelAnimationFrame(animationId);
      function step() {
        if (isPhysicsRunning) {
          updatePhysics();
        }
        renderGraph();
        animationId = requestAnimationFrame(step);
      }
      step();
    }

    function updatePhysics() {
      for (let i = 0; i < graphNodes.length; i++) {
        const a = graphNodes[i];
        for (let j = i + 1; j < graphNodes.length; j++) {
          const b = graphNodes[j];
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const distSq = dx * dx + dy * dy + 1;
          const dist = Math.sqrt(distSq);
          if (dist < 220) {
            const force = (220 - dist) / (dist * 18);
            a.vx -= dx * force;
            a.vy -= dy * force;
            b.vx += dx * force;
            b.vy += dy * force;
          }
        }
      }

      for (let link of graphLinks) {
        const dx = link.target.x - link.source.x;
        const dy = link.target.y - link.source.y;
        const dist = Math.sqrt(dx * dx + dy * dy) + 0.1;
        const force = (dist - 80) * 0.003;
        link.source.vx += dx * force;
        link.source.vy += dy * force;
        link.target.vx -= dx * force;
        link.target.vy -= dy * force;
      }

      for (let n of graphNodes) {
        if (n === dragNode) continue;
        n.vx -= n.x * 0.001;
        n.vy -= n.y * 0.001;
        n.vx *= 0.85;
        n.vy *= 0.85;
        n.x += n.vx;
        n.y += n.vy;
      }
    }

    function renderGraph() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.save();
      ctx.translate(transform.x, transform.y);
      ctx.scale(transform.k, transform.k);

      // Links
      ctx.lineWidth = 1;
      for (let link of graphLinks) {
        let isHighlighted = hoveredNode && (link.source === hoveredNode || link.target === hoveredNode);
        ctx.strokeStyle = isHighlighted ? '#e2e8f0' : '#334155';
        ctx.globalAlpha = isHighlighted ? 0.9 : (hoveredNode ? 0.15 : 0.4);
        ctx.beginPath();
        ctx.moveTo(link.source.x, link.source.y);
        ctx.lineTo(link.target.x, link.target.y);
        ctx.stroke();
      }

      // Nodes
      for (let n of graphNodes) {
        const isHovered = n === hoveredNode;
        const isConnected = hoveredNode && graphLinks.some(l => (l.source === hoveredNode && l.target === n) || (l.target === hoveredNode && l.source === n));
        const isDimmed = hoveredNode && !isHovered && !isConnected;

        ctx.globalAlpha = isDimmed ? 0.2 : 1.0;

        if (isHovered) {
          ctx.beginPath();
          ctx.arc(n.x, n.y, n.radius + 6, 0, Math.PI * 2);
          ctx.fillStyle = n.color + '44';
          ctx.fill();
        }

        ctx.beginPath();
        ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2);
        ctx.fillStyle = n.color;
        ctx.fill();
        ctx.strokeStyle = isHovered ? '#ffffff' : '#0f172a';
        ctx.lineWidth = 1.5;
        ctx.stroke();

        if (n.type === 'Topic' || transform.k > 1.4 || isHovered || isConnected) {
          ctx.fillStyle = isHovered ? '#ffffff' : '#cbd5e1';
          ctx.font = (n.type === 'Topic' ? 'bold 11px' : '9px') + ' sans-serif';
          ctx.textAlign = 'center';
          ctx.fillText(n.name, n.x, n.y + n.radius + 12);
        }
      }

      ctx.restore();
    }

    function getMousePos(e) {
      const rect = canvas.getBoundingClientRect();
      const clientX = e.clientX - rect.left;
      const clientY = e.clientY - rect.top;
      return {
        screenX: clientX,
        screenY: clientY,
        worldX: (clientX - transform.x) / transform.k,
        worldY: (clientY - transform.y) / transform.k
      };
    }

    function findNodeAt(pos) {
      for (let i = graphNodes.length - 1; i >= 0; i--) {
        const n = graphNodes[i];
        const dx = n.x - pos.worldX;
        const dy = n.y - pos.worldY;
        if (dx * dx + dy * dy <= (n.radius + 4) * (n.radius + 4)) {
          return n;
        }
      }
      return null;
    }

    function onMouseDown(e) {
      const pos = getMousePos(e);
      const clicked = findNodeAt(pos);
      if (clicked) {
        dragNode = clicked;
        openNodeDrawer(clicked.raw);
      } else {
        isPanning = true;
        panStart = { x: e.clientX - transform.x, y: e.clientY - transform.y };
      }
    }

    function onMouseMove(e) {
      const pos = getMousePos(e);
      if (dragNode) {
        dragNode.x = pos.worldX;
        dragNode.y = pos.worldY;
        dragNode.vx = 0;
        dragNode.vy = 0;
      } else if (isPanning) {
        transform.x = e.clientX - panStart.x;
        transform.y = e.clientY - panStart.y;
      } else {
        const node = findNodeAt(pos);
        if (node !== hoveredNode) {
          hoveredNode = node;
          updateTooltip(node, pos);
        }
      }
    }

    function onMouseUp() {
      dragNode = null;
      isPanning = false;
    }

    function onWheel(e) {
      e.preventDefault();
      const pos = getMousePos(e);
      const zoomFactor = e.deltaY < 0 ? 1.15 : 0.85;
      const newK = Math.max(0.2, Math.min(5.0, transform.k * zoomFactor));

      transform.x = pos.screenX - (pos.screenX - transform.x) * (newK / transform.k);
      transform.y = pos.screenY - (pos.screenY - transform.y) * (newK / transform.k);
      transform.k = newK;
    }

    function updateTooltip(node, pos) {
      const tip = document.getElementById('graphTooltip');
      if (!node) {
        tip.classList.add('hidden');
        return;
      }
      tip.classList.remove('hidden');
      tip.style.left = (pos.screenX + 15) + 'px';
      tip.style.top = (pos.screenY + 15) + 'px';
      tip.innerHTML = `
        <div class="font-bold text-white text-xs">${node.name}</div>
        <div class="text-[10px] text-slate-300 mt-0.5">${node.type} · ${node.discipline}</div>
        <div class="text-[10px] text-indigo-400 mt-1">点击查看全维档案 ➔</div>
      `;
    }

    function focusNodeInGraph(nodeId) {
      const target = graphNodes.find(n => n.id === nodeId);
      if (target) {
        transform.x = canvas.width / 2 - target.x * 1.5;
        transform.y = canvas.height / 2 - target.y * 1.5;
        transform.k = 1.5;
        hoveredNode = target;
        openNodeDrawer(target.raw);
      }
    }

    function openNodeDrawer(node) {
      const drawer = document.getElementById('nodeDrawer');
      const content = document.getElementById('nodeDrawerContent');
      drawer.classList.remove('hidden');

      let typeBadge = 'bg-blue-500/20 text-blue-300 border border-blue-500/30';
      if (node.type === 'Method') typeBadge = 'bg-amber-500/20 text-amber-300 border border-amber-500/30';
      if (node.type === 'KnowledgePoint') typeBadge = 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30';
      if (node.type === 'Topic') typeBadge = 'bg-purple-500/20 text-purple-300 border border-purple-500/30';

      const provBadges = (node.provenance || []).map(p => {
        let label = p;
        if (p === 'LECTURE_NOTES') label = '讲义资料';
        if (p === 'LI_FAN') label = '李范全书';
        if (p === 'QIANGHUA36') label = '强化36讲';
        if (p === 'PASS1_VISION') label = 'Direct-Vision 实证';
        return `<span class="px-2 py-0.5 bg-slate-800 text-slate-300 rounded text-[10px] border border-slate-700">${label}</span>`;
      }).join(' ');

      const aliasesTags = (node.aliases || []).map(a => 
        `<span class="px-1.5 py-0.5 bg-slate-800/80 text-slate-300 rounded text-[10px] border border-slate-700">${a}</span>`
      ).join(' ') || '<span class="text-slate-500 text-[11px]">无别名</span>';

      const signalsList = (node.relations?.signals || []).map(s => 
        `<li class="text-[11px] text-slate-300 bg-slate-800/40 p-1.5 rounded border border-slate-700/50">${s}</li>`
      ).join('') || '<div class="text-slate-500 text-[11px]">暂无实证题面信号</div>';

      content.innerHTML = `
        <div class="border-b border-slate-800 pb-3">
          <div class="flex items-center justify-between mb-2">
            <span class="px-2.5 py-0.5 rounded-full text-xs font-semibold ${typeBadge}">${node.type}</span>
            <span class="text-xs text-slate-400">${node.discipline}</span>
          </div>
          <h2 class="text-base font-bold text-white tracking-tight">${node.display_name}</h2>
          <div class="text-[11px] text-slate-400 font-mono mt-1">${node.id}</div>
        </div>

        <div>
          <div class="text-xs font-semibold text-slate-300 mb-1">所属章节/宏观专题:</div>
          <div class="text-xs text-indigo-300 bg-indigo-950/40 p-2 rounded-xl border border-indigo-900/50">${node.parent || '核心考点'}</div>
        </div>

        <div>
          <div class="text-xs font-semibold text-slate-300 mb-1">教学数据源证据 (Provenance):</div>
          <div class="flex flex-wrap gap-1.5">${provBadges}</div>
        </div>

        <div>
          <div class="text-xs font-semibold text-slate-300 mb-1">自然语言同义变体 (Aliases):</div>
          <div class="flex flex-wrap gap-1.5">${aliasesTags}</div>
        </div>

        <div>
          <div class="text-xs font-semibold text-slate-300 mb-1.5">题面特征触发信号 (Signals):</div>
          <ul class="space-y-1">${signalsList}</ul>
        </div>

        <div class="border-t border-slate-800 pt-3">
          <div class="flex items-center justify-between text-xs">
            <span class="text-slate-400">真题实证挂载数:</span>
            <span class="text-emerald-400 font-bold">${node.evidence_question_count || 0} 道题</span>
          </div>
        </div>
      `;
    }

    function closeNodeDrawer() {
      document.getElementById('nodeDrawer').classList.add('hidden');
    }

    function renderTree(filterText) {
      const container = document.getElementById('curriculumTreeContainer');
      container.innerHTML = '';
      const lowerFilter = (filterText || '').toLowerCase();

      for (let disc in ONTOLOGY_DATA.tree) {
        const topics = ONTOLOGY_DATA.tree[disc];
        let discHasMatch = false;

        const discCard = document.createElement('div');
        discCard.className = 'bg-slate-900 rounded-2xl border border-slate-800 overflow-hidden';
        
        let topicRows = '';
        for (let tName in topics) {
          const tObj = topics[tName];
          const eps = tObj.exam_points || [];
          const methods = tObj.methods || [];
          const kps = tObj.knowledge || [];

          const matches = !lowerFilter || tName.toLowerCase().includes(lowerFilter) || 
                          eps.some(e => e.name.toLowerCase().includes(lowerFilter)) ||
                          methods.some(m => m.name.toLowerCase().includes(lowerFilter));

          if (!matches) continue;
          discHasMatch = true;

          const epPills = eps.map(e => 
            `<span onclick="switchTab('graph'); focusNodeInGraph('${e.id}')" class="cursor-pointer px-2 py-0.5 rounded bg-blue-500/10 hover:bg-blue-500/20 text-blue-300 text-[11px] border border-blue-500/20 transition">${e.name}</span>`
          ).join(' ') || '<span class="text-slate-500 text-[11px]">暂无考点</span>';

          const methodPills = methods.map(m => 
            `<span onclick="switchTab('graph'); focusNodeInGraph('${m.id}')" class="cursor-pointer px-2 py-0.5 rounded bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 text-[11px] border border-amber-500/20 transition">${m.name}</span>`
          ).join(' ') || '<span class="text-slate-500 text-[11px]">暂无解法</span>';

          topicRows += `
            <div class="p-4 border-b border-slate-800/80 last:border-0 hover:bg-slate-850/50 transition">
              <div class="flex items-center justify-between mb-2">
                <span class="font-bold text-white text-sm flex items-center gap-2">
                  <span class="w-2 h-2 rounded-full bg-purple-500"></span>
                  ${tName}
                </span>
                <span class="text-xs text-slate-400">${eps.length} 题型 · ${methods.length} 方法</span>
              </div>
              <div class="space-y-2 text-xs">
                <div>
                  <span class="text-slate-400 text-[11px] mr-2">核心考点:</span>
                  <div class="inline-flex flex-wrap gap-1.5">${epPills}</div>
                </div>
                <div>
                  <span class="text-slate-400 text-[11px] mr-2">解题方法:</span>
                  <div class="inline-flex flex-wrap gap-1.5">${methodPills}</div>
                </div>
              </div>
            </div>
          `;
        }

        if (discHasMatch || !lowerFilter) {
          discCard.innerHTML = `
            <div class="bg-slate-800/80 px-5 py-3 border-b border-slate-700/80 flex items-center justify-between">
              <h3 class="font-bold text-white text-sm flex items-center gap-2">
                <span>📚</span> ${disc}
              </h3>
              <span class="text-xs text-indigo-300 font-medium">${Object.keys(topics).length} 个宏观教学专题</span>
            </div>
            <div>${topicRows}</div>
          `;
          container.appendChild(discCard);
        }
      }
    }

    function setBookFilter(book) {
      selectedBookFilter = book;
      document.querySelectorAll('#bookFilterButtons button').forEach(b => {
        b.className = 'px-2 py-0.5 rounded text-slate-300 hover:bg-slate-700 text-[11px]';
      });
      event.target.className = 'px-2 py-0.5 bg-indigo-600 rounded text-white font-medium text-[11px]';
      renderQuestionsList(document.getElementById('qSearchInput').value);
    }

    function renderQuestionsList(keyword) {
      const container = document.getElementById('questionsListContainer');
      container.innerHTML = '';
      const kw = (keyword || '').toLowerCase();

      const filtered = ONTOLOGY_DATA.sample_questions.filter(q => {
        if (selectedBookFilter !== 'ALL' && !q.book.includes(selectedBookFilter)) return false;
        if (kw && !q.qid.toLowerCase().includes(kw)) return false;
        return true;
      });

      filtered.forEach((q, idx) => {
        const item = document.createElement('div');
        item.className = 'p-3 bg-slate-800/40 hover:bg-slate-800 rounded-xl border border-slate-700/60 transition cursor-pointer';
        item.onclick = () => renderQuestionDetail(q);

        const epsCount = q.exam_points?.length || 0;
        const methodsCount = q.methods?.length || 0;

        item.innerHTML = `
          <div class="flex items-center justify-between text-[10px] text-slate-400 mb-1">
            <span class="px-1.5 py-0.5 bg-slate-700 rounded text-slate-200">${q.book}</span>
            <span>${q.discipline}</span>
          </div>
          <div class="text-xs font-semibold text-white truncate" title="${q.qid}">${q.qid.split('::').pop()}</div>
          <div class="text-[10px] text-slate-400 mt-1 flex gap-2">
            <span>考点: <b class="text-blue-400">${epsCount}</b></span>
            <span>解法: <b class="text-amber-400">${methodsCount}</b></span>
          </div>
        `;
        container.appendChild(item);
      });

      if (filtered.length > 0 && !selectedQuestion) {
        renderQuestionDetail(filtered[0]);
      }
    }

    function renderQuestionDetail(q) {
      selectedQuestion = q;
      const container = document.getElementById('questionDetailContainer');

      const epObjs = (q.exam_points || []).map(id => ONTOLOGY_DATA.nodes.find(n => n.id === id) || { id, display_name: id });
      const kpObjs = (q.knowledge_points || []).map(id => ONTOLOGY_DATA.nodes.find(n => n.id === id) || { id, display_name: id });
      const methodObjs = (q.methods || []).map(id => ONTOLOGY_DATA.nodes.find(n => n.id === id) || { id, display_name: id });

      container.innerHTML = `
        <div class="max-w-3xl space-y-6">
          <div class="bg-slate-900 p-5 rounded-2xl border border-slate-800">
            <div class="flex items-center justify-between text-xs mb-2">
              <span class="px-2.5 py-1 bg-indigo-500/20 text-indigo-300 font-semibold rounded-lg border border-indigo-500/30">${q.book} · ${q.discipline}</span>
              <span class="text-emerald-400 font-medium">● 规范语义已锚定 (Pass 1 Direct-Vision)</span>
            </div>
            <h2 class="text-base font-bold text-white font-mono break-all">${q.qid}</h2>
          </div>

          <div class="bg-slate-900 p-6 rounded-2xl border border-slate-800 space-y-5">
            <h3 class="font-bold text-white text-sm flex items-center gap-2">
              <span>🧠</span> 认知推理链条 (Cognitive Reasoning Path)
            </h3>

            <div class="flex items-start gap-3">
              <div class="w-8 h-8 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center font-bold text-xs shrink-0 mt-0.5">
                1
              </div>
              <div class="flex-1 bg-slate-800/50 p-3.5 rounded-xl border border-slate-700/60">
                <div class="text-xs font-semibold text-blue-300 mb-1">【步骤 1】题型定位 (INSTANCE_OF)</div>
                <div class="text-xs text-slate-300">
                  ${epObjs.map(ep => `<span class="inline-block px-2.5 py-1 bg-blue-500/20 text-blue-300 rounded-lg mr-2 font-medium border border-blue-500/30">${ep.display_name}</span>`).join('') || '<span class="text-slate-500">综合题型 (跨章节综合考查)</span>'}
                </div>
              </div>
            </div>

            <div class="flex items-start gap-3">
              <div class="w-8 h-8 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold text-xs shrink-0 mt-0.5">
                2
              </div>
              <div class="flex-1 bg-slate-800/50 p-3.5 rounded-xl border border-slate-700/60">
                <div class="text-xs font-semibold text-emerald-300 mb-1">【步骤 2】考查基础理论知识 (EXERCISES_KNOWLEDGE)</div>
                <div class="text-xs text-slate-300">
                  ${kpObjs.map(kp => `<span class="inline-block px-2.5 py-1 bg-emerald-500/20 text-emerald-300 rounded-lg mr-2 font-medium border border-emerald-500/30">${kp.display_name}</span>`).join('') || '<span class="text-slate-500">基础定义与推论</span>'}
                </div>
              </div>
            </div>

            <div class="flex items-start gap-3">
              <div class="w-8 h-8 rounded-full bg-amber-500/20 text-amber-400 flex items-center justify-center font-bold text-xs shrink-0 mt-0.5">
                3
              </div>
              <div class="flex-1 bg-slate-800/50 p-3.5 rounded-xl border border-slate-700/60">
                <div class="text-xs font-semibold text-amber-300 mb-1">【步骤 3】核心解题算法策略 (APPLIES_METHOD)</div>
                <div class="text-xs text-slate-300">
                  ${methodObjs.map(m => `<span class="inline-block px-2.5 py-1 bg-amber-500/20 text-amber-300 rounded-lg mr-2 font-medium border border-amber-500/30">${m.display_name}</span>`).join('') || '<span class="text-slate-500">标准代数化简</span>'}
                </div>
              </div>
            </div>

            <div class="flex items-start gap-3">
              <div class="w-8 h-8 rounded-full bg-rose-500/20 text-rose-400 flex items-center justify-center font-bold text-xs shrink-0 mt-0.5">
                4
              </div>
              <div class="flex-1 bg-slate-800/50 p-3.5 rounded-xl border border-slate-700/60">
                <div class="text-xs font-semibold text-rose-300 mb-1">【步骤 4】防踩坑与适用条件拦截 (AVOIDS_PITFALL)</div>
                <div class="text-xs text-slate-300">
                  严格检验公式前置条件（如等价无穷小代换原则只在乘除因式有效，加减法需泰勒展开），杜绝典型常见失分点。
                </div>
              </div>
            </div>
          </div>
        </div>
      `;
    }

    function renderLexiconTable(keyword) {
      const tbody = document.getElementById('lexiconTableBody');
      tbody.innerHTML = '';
      const kw = (keyword || '').toLowerCase();

      const filtered = ONTOLOGY_DATA.sample_alignments.filter(item => {
        if (!kw) return true;
        return item.surface.toLowerCase().includes(kw) || 
               item.matched_name.toLowerCase().includes(kw) ||
               (item.matching_reason || '').toLowerCase().includes(kw);
      }).slice(0, 150);

      filtered.forEach(item => {
        const row = document.createElement('tr');
        row.className = 'hover:bg-slate-800/40 transition';

        let confBadge = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
        if (item.confidence < 0.90) confBadge = 'bg-amber-500/10 text-amber-400 border-amber-500/20';

        row.innerHTML = `
          <td class="py-3 px-4 font-bold text-white">${item.surface}</td>
          <td class="py-3 px-4 text-slate-400">${item.semantic_type}</td>
          <td class="py-3 px-4 text-slate-400">${item.discipline}</td>
          <td class="py-3 px-4">
            <span class="text-indigo-400 font-semibold">${item.matched_name}</span>
            <span class="text-[10px] text-slate-500 font-mono block">${item.matched_node}</span>
          </td>
          <td class="py-3 px-4">
            <span class="px-2 py-0.5 rounded-full text-[10px] font-bold border ${confBadge}">${item.confidence.toFixed(2)}</span>
          </td>
          <td class="py-3 px-4 text-slate-400 max-w-xs truncate" title="${item.matching_reason}">${item.matching_reason}</td>
          <td class="py-3 px-4 text-right font-mono font-bold text-slate-300">${item.total_evidence_count} 题</td>
        `;
        tbody.appendChild(row);
      });
    }

    function handleGlobalSearch(keyword) {
      const box = document.getElementById('searchResults');
      if (!keyword || keyword.trim().length < 1) {
        box.classList.add('hidden');
        return;
      }
      const kw = keyword.trim().toLowerCase();
      const matches = ONTOLOGY_DATA.nodes.filter(n => 
        n.display_name.toLowerCase().includes(kw) || 
        (n.aliases || []).some(a => a.toLowerCase().includes(kw))
      ).slice(0, 10);

      if (matches.length === 0) {
        box.innerHTML = '<div class="p-2 text-slate-500">未找到匹配规范概念</div>';
        box.classList.remove('hidden');
        return;
      }

      box.innerHTML = matches.map(m => `
        <div onclick="selectGlobalSearchResult('${m.id}')" class="p-2 hover:bg-slate-800 rounded-lg cursor-pointer flex items-center justify-between">
          <div>
            <div class="font-bold text-white text-xs">${m.display_name}</div>
            <div class="text-[10px] text-slate-400">${m.type} · ${m.discipline}</div>
          </div>
          <span class="text-[10px] text-indigo-400">定位 ➔</span>
        </div>
      `).join('');
      box.classList.remove('hidden');
    }

    function selectGlobalSearchResult(nodeId) {
      document.getElementById('searchResults').classList.add('hidden');
      switchTab('graph');
      focusNodeInGraph(nodeId);
    }
  </script>
</body>
</html>
"""

def main():
    print("Loading canonical nodes...")
    with open(BASE_DIR / "canonical_nodes.json", "r", encoding="utf-8") as f:
        canonical_nodes = json.load(f)

    print(f"Loaded {len(canonical_nodes)} canonical nodes.")

    type_counts = Counter(n["type"] for n in canonical_nodes)
    disc_counts = Counter(n["discipline"] for n in canonical_nodes)
    
    prov_counts = Counter()
    consensus_count = 0
    for n in canonical_nodes:
        prov = n.get("provenance", [])
        for p in prov:
            prov_counts[p] += 1
        if len(prov) >= 3:
            consensus_count += 1

    print("Loading reasoning graph...")
    edge_type_counts = Counter()
    graph_edges = []
    with open(BASE_DIR / "reasoning_graph.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            rel = e.get("relation")
            edge_type_counts[rel] += 1
            s = e.get("source")
            t = e.get("target")
            if not s.startswith("math::") and not t.startswith("math::"):
                graph_edges.append({
                    "source": s,
                    "target": t,
                    "relation": rel,
                    "weight": e.get("weight", 1.0)
                })

    print("Loading question links...")
    book_counts = Counter()
    linked_q_count = 0
    total_q_count = 0
    sample_questions = []

    with open(BASE_DIR / "question_semantic_links.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            total_q_count += 1
            q = json.loads(line)
            eps = q.get("exam_points", [])
            kps = q.get("knowledge_points", [])
            mts = q.get("methods", [])
            qid = q.get("qid", "")
            
            b = "未知"
            if "::" in qid:
                parts = qid.split("::")
                b = parts[1]
            book_counts[b] += 1
            
            is_linked = bool(eps or kps or mts)
            if is_linked:
                linked_q_count += 1
                if len(sample_questions) < 400:
                    sample_questions.append({
                        "qid": qid,
                        "book": b,
                        "discipline": q.get("discipline", ""),
                        "chapter": q.get("chapter", ""),
                        "exam_points": eps,
                        "knowledge_points": kps,
                        "methods": mts
                    })

    print("Loading alignments...")
    alignments = []
    with open(BASE_DIR / "alignment_candidates" / "semantic_alignment.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            alignments.append(json.loads(line))

    alignments.sort(key=lambda x: (x.get("confidence", 0), x.get("total_evidence_count", 0)), reverse=True)
    sample_alignments = alignments[:600]

    tree_data = {}
    for d in ["高等数学", "线性代数", "概率论与数理统计"]:
        tree_data[d] = {}

    for n in canonical_nodes:
        d = n["discipline"]
        if d not in tree_data:
            tree_data[d] = {}
        if n["type"] == "Topic":
            if n["display_name"] not in tree_data[d]:
                tree_data[d][n["display_name"]] = {
                    "id": n["id"],
                    "display_name": n["display_name"],
                    "exam_points": [],
                    "methods": [],
                    "knowledge": [],
                    "pitfalls": []
                }

    for n in canonical_nodes:
        d = n["discipline"]
        parent = n.get("parent", "")
        matched_topic = None
        for t_name, t_obj in tree_data.get(d, {}).items():
            if t_name in parent or parent in t_name:
                matched_topic = t_obj
                break
        if not matched_topic:
            first_topic = next(iter(tree_data.get(d, {}).values()), None)
            if first_topic:
                matched_topic = first_topic

        if matched_topic:
            if n["type"] == "ExamPoint":
                matched_topic["exam_points"].append({"id": n["id"], "name": n["display_name"]})
            elif n["type"] == "Method":
                matched_topic["methods"].append({"id": n["id"], "name": n["display_name"]})
            elif n["type"] == "KnowledgePoint":
                matched_topic["knowledge"].append({"id": n["id"], "name": n["display_name"]})
            elif n["type"] == "Pitfall":
                matched_topic["pitfalls"].append({"id": n["id"], "name": n["display_name"]})

    data_bundle = {
        "stats": {
            "total_nodes": len(canonical_nodes),
            "total_questions": total_q_count,
            "linked_questions": linked_q_count,
            "coverage_rate": round(linked_q_count / max(total_q_count, 1) * 100, 2),
            "total_edges": sum(edge_type_counts.values()),
            "aligned_surfaces": len(alignments),
            "consensus_nodes": consensus_count,
            "type_counts": dict(type_counts),
            "disc_counts": dict(disc_counts),
            "prov_counts": dict(prov_counts),
            "edge_type_counts": dict(edge_type_counts),
            "book_counts": dict(book_counts)
        },
        "nodes": canonical_nodes,
        "tree": tree_data,
        "sample_edges": graph_edges[:1500],
        "sample_questions": sample_questions,
        "sample_alignments": sample_alignments
    }

    json_bundle_str = json.dumps(data_bundle, ensure_ascii=False)
    print(f"Data bundle prepared. Size: {len(json_bundle_str)/1024:.1f} KB")

    full_html = FULL_HTML_TEMPLATE.replace("__JSON_DATA_BUNDLE__", json_bundle_str)
    
    out_brain = BRAIN_DIR / "ontology_visualizer.html"
    with open(out_brain, "w", encoding="utf-8") as f:
        f.write(full_html)
    print(f"Saved: {out_brain}")

    out_repo = BASE_DIR / "ontology_visualizer.html"
    with open(out_repo, "w", encoding="utf-8") as f:
        f.write(full_html)
    print(f"Saved: {out_repo}")

    stats = data_bundle["stats"]
    card_html = (CARD_WIDGET_TEMPLATE
                 .replace("__TOTAL_NODES__", f"{stats['total_nodes']:,}")
                 .replace("__LINKED_QUESTIONS__", f"{stats['linked_questions']:,}")
                 .replace("__TOTAL_QUESTIONS__", f"{stats['total_questions']:,}")
                 .replace("__COVERAGE_RATE__", f"{stats['coverage_rate']}")
                 .replace("__TOTAL_EDGES__", f"{stats['total_edges']:,}")
                 .replace("__CONSENSUS_NODES__", f"{stats['consensus_nodes']}")
                )
    
    out_card = BRAIN_DIR / "ontology_card_widget.html"
    with open(out_card, "w", encoding="utf-8") as f:
        f.write(card_html)
    print(f"Saved: {out_card}")

    out_repo_card = BASE_DIR / "ontology_card_widget.html"
    with open(out_repo_card, "w", encoding="utf-8") as f:
        f.write(card_html)
    print(f"Saved: {out_repo_card}")

    print("\nVisualizer generation complete!")

if __name__ == "__main__":
    main()
