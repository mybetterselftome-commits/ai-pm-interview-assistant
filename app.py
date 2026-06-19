"""AI 产品求职教练 V3 - 面向转行者的个人求职资产工作台"""
import os
import re
import json
import time
import uuid
from datetime import datetime

import httpx
import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI

from db import (
    init_db,
    get_or_create_user,
    save_career_asset,
    list_career_assets,
    delete_career_asset,
    save_feedback as db_save_feedback,
    list_feedback,
    clear_career_data,
    upsert_weakness_tag,
    list_weakness_tags,
    top_weak_dimensions,
    save_interview_session,
    list_interview_sessions,
)
import prompts.profile_prompt as profile_prompt
import prompts.jd_prompt as jd_prompt
import prompts.interview_prompt as interview_prompt
import prompts.knowledge_prompt as knowledge_prompt
import prompts.agent_prompt as agent_prompt

# ========== 绕过系统代理 ==========
for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
    os.environ.pop(key, None)

# ========== 读取 API Key ==========
api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key:
    try:
        api_key = st.secrets.get("DEEPSEEK_API_KEY")
    except Exception:
        pass
if not api_key:
    try:
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.getenv("DEEPSEEK_API_KEY")
    except Exception:
        pass

# ========== 初始化 DeepSeek 客户端 ==========
http_client = httpx.Client(proxy=None, timeout=60)
client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com", http_client=http_client)

# ========== 页面配置 ==========
st.set_page_config(
    page_title="AI 产品求职教练",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "AI 产品求职教练 · 面向转行者的个人求职资产工作台"
    }
)

# ========== 实时语音转写组件 ==========
REALTIME_SPEECH_PATH = os.path.join(os.path.dirname(__file__), "components", "realtime_speech")
realtime_speech = components.declare_component("realtime_speech", path=REALTIME_SPEECH_PATH)

# ========== CSS ==========
st.markdown("""
<style>
    [data-testid="stHeader"] { display: none; }
    [data-testid="stToolbar"] { display: none; }
    [data-testid="stSidebar"] { display: none; }
    [data-testid="collapsedControl"] { display: none; }
    footer { display: none; }

    .stApp { background: #f7f8fb; color: #111827; }
    .main .block-container {
        max-width: 1420px;
        padding-top: 1rem;
        padding-left: 2rem;
        padding-right: 2rem;
        padding-bottom: 2.4rem;
    }

    .topbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 0.75rem;
        color: #6b7280;
        font-size: 0.82rem;
    }
    .brand { color: #111827; font-weight: 850; letter-spacing: -0.01em; font-size: 1rem; }
    .version-pill {
        background: #eef2ff;
        color: #4f46e5;
        border: 1px solid #e0e7ff;
        border-radius: 999px;
        padding: 4px 10px;
        font-weight: 700;
        font-size: 0.75rem;
    }

    .workspace-header {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 16px;
        padding: 1rem 1.15rem;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
        margin-bottom: 0.85rem;
    }
    .workspace-header h1 {
        margin: 0 0 0.35rem 0;
        color: #0f172a;
        font-size: 1.35rem;
        line-height: 1.2;
        letter-spacing: -0.025em;
        font-weight: 900;
    }
    .workspace-header p { margin: 0; color: #4b5563; line-height: 1.55; font-size: 0.9rem; }

    .asset-strip {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 0.65rem;
        margin-bottom: 0.85rem;
    }
    .asset-stat {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 13px;
        padding: 0.75rem 0.85rem;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.035);
    }
    .asset-stat .num { color: #4f46e5; font-size: 1.2rem; font-weight: 900; line-height: 1.1; }
    .asset-stat .label { color: #6b7280; font-size: 0.78rem; margin-top: 0.25rem; }

    .nav-card button {
        min-height: 92px;
        background: #ffffff !important;
        border: 1px solid #e5e7eb !important;
        border-radius: 13px !important;
        color: #111827 !important;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.035) !important;
        font-weight: 800 !important;
        text-align: left !important;
        white-space: pre-line !important;
    }
    .nav-card button:hover {
        border-color: #6366f1 !important;
        box-shadow: 0 8px 22px rgba(99, 102, 241, 0.12) !important;
        transform: translateY(-1px);
    }

    .section-title { font-weight: 850; font-size: 1.12rem; margin: 0.8rem 0 0.45rem 0; color: #111827; }
    .subtle-note { color: #6b7280; font-size: 0.86rem; margin-bottom: 0.6rem; }
    .result-box {
        background: #ffffff;
        border-radius: 14px;
        border: 1px solid #e5e7eb;
        border-left: 4px solid #6366f1;
        padding: 1rem 1.15rem;
        box-shadow: 0 6px 18px rgba(15, 23, 42, 0.04);
        margin-top: 0.8rem;
        line-height: 1.72;
        overflow-x: auto;
    }
    .result-box table {
        width: 100%;
        min-width: 980px;
        border-collapse: collapse;
        margin: 0.8rem 0 1rem 0;
        font-size: 0.92rem;
        table-layout: fixed;
    }
    .result-box th {
        background: #f8fafc;
        color: #111827;
        font-weight: 850;
        border: 1px solid #e5e7eb;
        padding: 0.7rem 0.75rem;
        text-align: left;
        white-space: nowrap;
    }
    .result-box td {
        border: 1px solid #e5e7eb;
        padding: 0.75rem;
        vertical-align: top;
        color: #111827;
        word-break: normal;
        overflow-wrap: break-word;
    }
    .result-box th:nth-child(1), .result-box td:nth-child(1) { width: 14%; min-width: 110px; font-weight: 800; }
    .result-box th:nth-child(2), .result-box td:nth-child(2) { width: 9%; min-width: 80px; text-align: center; font-weight: 850; color: #4f46e5; white-space: nowrap; }
    .result-box th:nth-child(3), .result-box td:nth-child(3) { width: 37%; }
    .result-box th:nth-child(4), .result-box td:nth-child(4) { width: 40%; }
    .asset-box {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 0.9rem 1rem;
        margin-bottom: 0.75rem;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.035);
    }
    .asset-title { font-weight: 850; color: #111827; margin-bottom: 0.2rem; }
    .asset-meta { color: #6b7280; font-size: 0.78rem; margin-bottom: 0.5rem; }
    .path-tag {
        display: inline-block;
        background: #f1f5f9;
        color: #334155;
        padding: 5px 10px;
        margin: 3px 4px 3px 0;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 650;
    }
    .kb-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 0.95rem 1rem;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.035);
        margin-bottom: 0.75rem;
    }
    .kb-card h4 { margin: 0 0 0.5rem 0; color: #111827; font-size: 0.98rem; }
    .kb-card p { margin: 0; color: #6b7280; font-size: 0.82rem; line-height: 1.55; }

    .voice-row {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 13px;
        padding: 0.75rem 0.9rem;
        margin: 0.7rem 0 0.45rem 0;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.03);
    }
    .voice-row .title {
        font-weight: 800;
        color: #111827;
        margin-bottom: 0.25rem;
    }
    .voice-row .hint {
        color: #6b7280;
        font-size: 0.8rem;
        line-height: 1.45;
    }

    @media (max-width: 900px) {
        .asset-strip { grid-template-columns: repeat(2, 1fr); }
        .workspace-header h1 { font-size: 1.18rem; }
    }
</style>
""", unsafe_allow_html=True)

CAREER_PATHS = {
    "AI 产品经理": ["LLM 基础", "RAG 产品方案", "Agent 工作流", "模型评估", "AI 产品流程", "人机协同"],
    "AI 产品运营": ["数据指标", "用户增长", "内容运营", "A/B 测试", "模型效果监控", "用户反馈闭环"],
    "Agent 产品经理": ["Agent 架构", "Tool Use", "任务规划", "记忆管理", "异常兜底", "权限与安全"],
    "AIGC 产品经理": ["生成式 AI", "内容质量控制", "版权与合规", "多模态能力", "创作流程", "商业化场景"],
}

KNOWLEDGE_BASE = {
    "AI 技术理解": {
        "说明": "面试官用来判断你是否理解 AI 能力边界和技术选型。",
        "知识点": ["LLM", "RAG", "Agent", "Prompt 工程", "模型幻觉", "模型评估", "向量数据库", "Function Calling"],
    },
    "AI 产品设计": {
        "说明": "考察你能否把 AI 技术转化成真实产品方案。",
        "知识点": ["AI 产品流程", "自研 vs 调 API", "模型选型", "人机协同", "兜底策略", "成本与延迟", "产品指标", "灰度发布"],
    },
    "AI 运营增长": {
        "说明": "适合 AI 产品运营方向，关注上线后的增长、内容和效果监控。",
        "知识点": ["用户增长", "数据指标", "内容运营", "A/B 测试", "用户反馈闭环", "模型效果监控", "内容质量控制", "合规审核"],
    },
    "面试表达": {
        "说明": "把经历讲成面试官能认可的产品能力。",
        "知识点": ["STAR 法则", "项目复盘", "失败案例", "业务指标表达", "技术选型表达", "面试追问", "简历项目包装", "个人优势提炼"],
    },
}

INTERVIEW_QUESTIONS = {
    "AI 产品经理": [
        "请介绍一个你做过或设计过的 AI 产品项目，并说明为什么这个场景适合用 AI。",
        "如果模型效果不稳定，你作为产品经理会如何定位问题并推动优化？",
        "RAG 和模型微调分别适合什么场景？你会如何做选型？",
    ],
    "AI 产品运营": [
        "AI 产品上线后，你会重点关注哪些运营指标？为什么？",
        "如果 AIGC 内容质量不稳定，你会如何设计运营和产品机制？",
        "你如何把用户反馈转化为模型和产品迭代依据？",
    ],
    "Agent 产品经理": [
        "请设计一个 AI Agent 的核心工作流，并说明它和普通聊天机器人的区别。",
        "Agent 调用工具失败时，你会如何设计兜底策略？",
        "如何评估一个 Agent 产品是否真正完成了用户任务？",
    ],
    "AIGC 产品经理": [
        "AIGC 产品最核心的用户价值是什么？和传统内容工具有什么区别？",
        "你会如何设计 AIGC 产品的内容审核和质量控制机制？",
        "如果用户生成内容满意度低，你会从哪些维度分析原因？",
    ],
}

EXAMPLE_BACKGROUND = "我有 2 年内容运营经验，做过公众号/短视频内容策划，也负责过用户社群和活动转化。做过一次 AI 工具选型和内部培训，能熟练使用 ChatGPT、DeepSeek、Kimi 等工具，但对 RAG、Agent、模型评估理解还不系统。"
EXAMPLE_PROJECT = "曾主导一个内容增长项目：通过分析用户搜索词和内容点击数据，重构选题库和发布节奏，使单月内容阅读量提升约 35%，社群转化率提升约 12%。目前希望把这段经历包装成 AI 产品/AI 运营相关能力。"
EXAMPLE_JD = """岗位：AI 产品经理
职责：
1. 负责大模型应用产品从需求调研、方案设计到上线迭代；
2. 结合用户场景设计 RAG、Agent、Prompt 等 AI 能力方案；
3. 建立模型效果评估指标，推动算法、工程、运营协作优化体验；
4. 关注用户反馈和业务数据，持续提升产品转化和留存。
要求：
1. 了解 LLM、RAG、Agent、Prompt Engineering 基础概念；
2. 具备产品需求分析、数据分析和跨团队沟通能力；
3. 有 AI 工具使用经验或 AI 应用项目经验优先；
4. 能清晰表达产品方案、技术边界和效果评估方法。"""
EXAMPLE_ANSWER = "我做过一个内容增长项目。当时问题是内容选题比较依赖经验，用户点击和转化不稳定。我先分析了历史内容数据和用户搜索词，把选题分成高意图转化、品牌认知和社群互动三类，然后重构了选题库和发布节奏。结果单月阅读量提升约 35%，社群转化提升约 12%。如果迁移到 AI 产品场景，我会把它理解成一个内容策略智能化的问题：用 AI 辅助选题生成、标题改写和用户反馈分析，但会保留人工审核，避免内容质量和合规风险。"

# ========== 数据库初始化 ==========
init_db()


def get_or_create_device_id():
    """从 URL query params 读取或生成设备 ID，刷新和分享链接都能保持身份。"""
    params = st.query_params
    existing = params.get("device_id")
    if existing:
        return existing
    new_id = str(uuid.uuid4())[:8]
    st.query_params["device_id"] = new_id
    return new_id


# ========== Session ==========
def init_state():
    defaults = {
        "active_section": "求职诊断",
        "profile_result": "",
        "jd_result": "",
        "interview_question": "",
        "interview_review": "",
        "kb_result": "",
        "assets": [],
        "feedback": [],
        "interview_index": 0,
        "profile_background": "",
        "profile_project": "",
        "profile_confusion": "",
        "jd_text": "",
        "jd_user_summary": "",
        "interview_answer": "",
        "kb_search": "",
        "last_voice_transcript": "",
        "voice_metrics": {},
        "device_id": "",
        "db_loaded": False,
        "interview_mode": "single",
        "agent_role": "AI 产品经理",
        "agent_question": "",
        "agent_dialogue": [],
        "agent_round": 0,
        "agent_max_rounds": 4,
        "agent_pending_input": "",
        "agent_state": "idle",
        "agent_final_review": "",
        "weakness_tags": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_state()

if not st.session_state.device_id:
    st.session_state.device_id = get_or_create_device_id()
    get_or_create_user(st.session_state.device_id)

if not st.session_state.db_loaded:
    st.session_state.assets = list_career_assets(st.session_state.device_id)
    st.session_state.feedback = list_feedback(st.session_state.device_id)
    st.session_state.weakness_tags = list_weakness_tags(st.session_state.device_id)
    st.session_state.db_loaded = True

# ========== Helpers ==========
def call_ai(system_prompt, user_prompt):
    if not api_key:
        st.error("未检测到 DeepSeek API Key，请先配置 DEEPSEEK_API_KEY。")
        st.stop()
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=False,
        )
        return response.choices[0].message.content
    except Exception as exc:
        st.error(f"生成失败：{exc}")
        return ""


def call_ai_with_progress(system_prompt, user_prompt, title="正在生成", steps=None):
    """Show staged progress while waiting for the model response."""
    steps = steps or ["理解输入", "拆解任务", "调用模型", "整理结果"]
    progress = st.progress(0)
    status = st.empty()

    for pct, step in zip([12, 28, 45], steps[:3]):
        progress.progress(pct, text=f"{title}：{step}... {pct}%")
        status.caption(f"{title}：{step}...")
        time.sleep(0.25)

    progress.progress(62, text=f"{title}：模型正在生成结果... 62%")
    status.caption("模型正在生成结果，这一步可能需要几秒钟。")
    result = call_ai(system_prompt, user_prompt)

    progress.progress(88, text=f"{title}：整理输出结构... 88%")
    status.caption("正在整理输出结构...")
    time.sleep(0.2)
    progress.progress(100, text=f"{title}：完成 100%")
    status.caption("生成完成。")
    time.sleep(0.35)
    progress.empty()
    status.empty()
    return result


def call_ai_raw(system_prompt, user_prompt, temperature=0.6):
    """Direct call without progress UI, for chained agent turns."""
    if not api_key:
        return ""
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=False,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""
    except Exception as exc:
        return f"[生成失败：{exc}]"


def extract_weakness_tags(markdown_text):
    """Extract structured weakness tags from a review markdown.
    First try JSON inside the text; if not found, fall back to a small extractor call.
    """
    if not markdown_text:
        return []
    matches = re.findall(r"\[\s*\{[^\[\]]*?\}\s*\]", markdown_text, flags=re.DOTALL)
    for raw in matches:
        try:
            data = json.loads(raw)
            if isinstance(data, list) and data and isinstance(data[0], dict) and "tag" in data[0]:
                return data
        except json.JSONDecodeError:
            continue

    # Fallback: ask the model to compress the review into tag JSON
    response = call_ai_raw(
        agent_prompt.WEAKNESS_EXTRACTOR_SYSTEM,
        agent_prompt.build_weakness_extractor_prompt(markdown_text),
        temperature=0.2,
    )
    try:
        data = json.loads(response.strip().strip("`"))
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    return []


def persist_weakness_tags(device_id, tags):
    saved = 0
    for item in tags or []:
        if not isinstance(item, dict):
            continue
        tag = (item.get("tag") or "").strip()
        dimension = (item.get("dimension") or "").strip()
        try:
            severity = int(item.get("severity") or 1)
        except (TypeError, ValueError):
            severity = 1
        severity = max(1, min(3, severity))
        if not tag:
            continue
        upsert_weakness_tag(device_id, tag, dimension, severity)
        saved += 1
    return saved


def build_profile_context_for_agent():
    """Compose a compact context string the agent can use across modules."""
    parts = []
    if st.session_state.profile_result:
        parts.append("## 求职画像摘要\n" + st.session_state.profile_result[:1200])
    if st.session_state.profile_background:
        parts.append("## 用户背景\n" + st.session_state.profile_background)
    if st.session_state.profile_project:
        parts.append("## 已有经历\n" + st.session_state.profile_project)
    return "\n\n".join(parts)


def save_asset(asset_type, title, content):
    if not content:
        return
    device_id = st.session_state.device_id
    save_career_asset(device_id, asset_type, title or asset_type, content)
    st.session_state.assets = list_career_assets(device_id)


def add_feedback(module, value):
    device_id = st.session_state.device_id
    db_save_feedback(device_id, module, value)
    st.session_state.feedback = list_feedback(device_id)


def render_result(markdown_text, asset_type=None, asset_title=None, feedback_module=None, key_prefix="result", next_section=None, next_label=None):
    if not markdown_text:
        return
    st.markdown('<div class="result-box">', unsafe_allow_html=True)
    st.markdown(markdown_text)
    st.markdown('</div>', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    with col1:
        if asset_type and st.button("保存为资产", key=f"{key_prefix}_save", use_container_width=True):
            save_asset(asset_type, asset_title or asset_type, markdown_text)
            st.success("已保存到我的求职资产库")
    with col2:
        st.download_button(
            "导出 Markdown",
            data=f"# {asset_title or asset_type or 'AI 输出结果'}\n\n{markdown_text}",
            file_name=f"{key_prefix}_result.md",
            mime="text/markdown",
            key=f"{key_prefix}_download",
            use_container_width=True,
        )
    with col3:
        if feedback_module and st.button("有帮助", key=f"{key_prefix}_good", use_container_width=True):
            add_feedback(feedback_module, "有帮助")
            st.success("已记录反馈")
    with col4:
        if feedback_module and st.button("太泛/不准", key=f"{key_prefix}_bad", use_container_width=True):
            add_feedback(feedback_module, "太泛或不准确")
            st.info("已记录：后续用于优化 Prompt")

    if next_section and next_label:
        if st.button(next_label, key=f"{key_prefix}_next", type="secondary", use_container_width=True):
            st.session_state.active_section = next_section
            st.rerun()


def asset_count(asset_type):
    return sum(1 for asset in st.session_state.assets if asset["type"] == asset_type)


def fill_example():
    st.session_state.profile_background = EXAMPLE_BACKGROUND
    st.session_state.profile_project = EXAMPLE_PROJECT
    st.session_state.profile_confusion = "不知道自己更适合 AI 产品经理还是 AI 产品运营，也不知道如何把内容运营经历包装成 AI 产品能力。"
    st.session_state.jd_text = EXAMPLE_JD
    st.session_state.jd_user_summary = EXAMPLE_BACKGROUND + "\n" + EXAMPLE_PROJECT
    st.session_state.interview_answer = EXAMPLE_ANSWER
    st.session_state.kb_search = "RAG 怎么讲给面试官听？"

# ========== 顶部 ==========
st.markdown("""
<div class="topbar">
    <div><span class="brand">AI 产品求职教练</span> · 求职资产工作台</div>
    <div class="version-pill">AI Career Workspace</div>
</div>
<div class="workspace-header">
    <h1>把过往经历，转化成 AI 产品岗位认可的能力证据</h1>
    <p>从能力盘点、JD 匹配矩阵、面试 Rubric 复盘到知识补强，把一次性 AI 输出沉淀成可复用的求职资产。资产按设备 ID 持久化保存，刷新和分享 URL 都不会丢。</p>
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="asset-strip">
    <div class="asset-stat"><div class="num">{asset_count('求职画像')}</div><div class="label">求职画像</div></div>
    <div class="asset-stat"><div class="num">{asset_count('JD 匹配报告')}</div><div class="label">JD 匹配报告</div></div>
    <div class="asset-stat"><div class="num">{asset_count('面试复盘')}</div><div class="label">面试复盘</div></div>
    <div class="asset-stat"><div class="num">{len(st.session_state.weakness_tags)}</div><div class="label">能力短板（飞轮）</div></div>
</div>
""", unsafe_allow_html=True)

nav_cols = st.columns(4)
nav_items = [
    ("求职诊断", "01", "我是谁，和岗位差在哪"),
    ("面试训练", "02", "Rubric 评分复盘"),
    ("知识补强", "03", "查询 AI PM 面试知识"),
    ("我的资产", "04", "沉淀可复用材料"),
]
for col, (section, num, text) in zip(nav_cols, nav_items):
    with col:
        st.markdown('<div class="nav-card">', unsafe_allow_html=True)
        if st.button(f"{num}\n\n{section}\n{text}", key=f"nav_{section}", use_container_width=True):
            st.session_state.active_section = section
        st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")

# ========== 模块 1：求职诊断 ==========
if st.session_state.active_section == "求职诊断":
    st.markdown('<div class="section-title">求职诊断：先看你是谁，再看这个岗位差在哪</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtle-note">这是一个连续流程：Step 1 生成个人求职画像，Step 2 自动引用画像分析目标 JD，最后形成一份完整的《AI 产品求职诊断报告》。</div>', unsafe_allow_html=True)

    if st.button("填入完整示例", key="diagnosis_example"):
        fill_example()
        st.rerun()

    st.markdown("#### Step 1：个人求职画像")
    with st.form("profile_form"):
        current_background = st.text_area("你的过往背景", key="profile_background", height=110)
        target_role = st.selectbox("目标岗位方向", list(CAREER_PATHS.keys()))
        ai_level = st.select_slider("AI 基础水平", options=["完全小白", "了解概念", "用过 AI 工具", "做过 AI 项目", "能独立设计 AI 产品方案"])
        product_experience = st.text_area("你已有的项目/产品/运营经历", key="profile_project", height=90)
        biggest_confusion = st.text_input("当前最大困惑", key="profile_confusion")
        submitted = st.form_submit_button("生成个人求职画像", type="primary", use_container_width=True)

    if submitted:
        if len(current_background.strip()) < 20 or len(product_experience.strip()) < 20:
            st.warning("为了生成有价值的求职画像，请至少补充一段过往背景和一段项目/经历，建议包含职责、动作和结果。")
        else:
            prompt = profile_prompt.build_user_prompt(
                current_background,
                target_role,
                ai_level,
                product_experience,
                biggest_confusion,
            )
            st.session_state.profile_result = call_ai_with_progress(
                profile_prompt.SYSTEM_PROMPT,
                prompt,
                title=f"生成求职画像 · {profile_prompt.PROMPT_VERSION}",
                steps=["读取个人背景", "提炼可迁移优势", "识别短板", "整理画像报告"],
            )

    render_result(st.session_state.profile_result, "求职画像", "个人 AI 产品求职画像", "求职诊断", "profile", next_section="求职诊断", next_label="下一步：粘贴目标 JD，验证岗位匹配度")

    st.markdown("---")
    st.markdown("#### Step 2：目标 JD 匹配矩阵")
    st.caption("这一步会自动引用上面的求职画像。用户不需要重复解释自己是谁，只需要粘贴目标 JD。")

    with st.form("jd_form"):
        jd_text = st.text_area("目标岗位 JD", key="jd_text", height=210)
        jd_submitted = st.form_submit_button("基于个人画像生成 JD 匹配矩阵", type="primary", use_container_width=True)

    if jd_submitted:
        profile_context = st.session_state.profile_result or f"用户背景：{st.session_state.profile_background}\n已有经历：{st.session_state.profile_project}\n当前困惑：{st.session_state.profile_confusion}"
        if len(jd_text.strip()) < 80:
            st.warning("请补充更完整的 JD。JD 建议包含岗位职责和任职要求。")
        elif len(profile_context.strip()) < 50:
            st.warning("请先完成 Step 1 能力盘点，或至少填写完整个人背景。")
        else:
            prompt = jd_prompt.build_user_prompt(profile_context, jd_text)
            st.session_state.jd_result = call_ai_with_progress(
                jd_prompt.SYSTEM_PROMPT,
                prompt,
                title=f"生成 JD 匹配矩阵 · {jd_prompt.PROMPT_VERSION}",
                steps=["读取个人画像", "拆解岗位要求", "匹配能力证据", "整理诊断报告"],
            )

    render_result(st.session_state.jd_result, "JD 匹配报告", "AI 产品求职诊断报告", "求职诊断", "jd", next_section="面试训练", next_label="下一步：针对高风险短板做模拟面试")

# ========== 模块 2：模拟面试 ==========
elif st.session_state.active_section == "面试训练":
    st.markdown('<div class="section-title">模拟面试：单轮 Rubric + 多轮抗追问 Agent</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtle-note">单轮模式按五维 Rubric 评分；多轮模式由 AI 面试官连续追问到极限，最终输出破绽地图与合格答案对比。</div>', unsafe_allow_html=True)

    if st.session_state.weakness_tags:
        focus_tags = "、".join(f"{t['tag']}（{t['dimension']}）" for t in st.session_state.weakness_tags[:5])
        st.caption(f"📌 系统已记录的薄弱点（会用于个性化追问与抽题）：{focus_tags}")

    mode_label = st.radio(
        "训练模式",
        ["single", "agent"],
        format_func=lambda x: "单轮 Rubric 复盘" if x == "single" else "多轮抗追问 Agent",
        horizontal=True,
        key="interview_mode",
    )

    if mode_label == "single":
        role = st.selectbox("选择模拟岗位", list(INTERVIEW_QUESTIONS.keys()), key="interview_role")
        question_bank = INTERVIEW_QUESTIONS[role]

        weak_dims = top_weak_dimensions(st.session_state.device_id, top_n=2)
        if weak_dims:
            st.caption(f"🎯 本次抽题将优先考察你的弱项维度：{', '.join(weak_dims)}")

        col_a, col_b, col_c = st.columns([1, 1, 1])
        with col_a:
            if st.button("下一道面试题", type="primary", use_container_width=True):
                # Adaptive selection: prefer questions whose text contains weak dimensions
                ranked = sorted(
                    enumerate(question_bank),
                    key=lambda kv: -sum(1 for d in weak_dims if d.replace(" ", "") in kv[1].replace(" ", "")),
                )
                idx = ranked[st.session_state.interview_index % len(ranked)][0]
                st.session_state.interview_question = question_bank[idx]
                st.session_state.interview_index += 1
                st.session_state.interview_review = ""
        with col_b:
            if st.button("填入示例回答", use_container_width=True):
                if not st.session_state.interview_question:
                    st.session_state.interview_question = question_bank[0]
                st.session_state.interview_answer = EXAMPLE_ANSWER
                st.rerun()
        with col_c:
            if st.button("清空本轮", use_container_width=True):
                st.session_state.interview_question = ""
                st.session_state.interview_review = ""
                st.session_state.interview_answer = ""
                st.session_state.voice_metrics = {}

        if st.session_state.interview_question:
            st.info(f"面试题：{st.session_state.interview_question}")

            st.markdown('<div class="voice-row"><div class="title">输入你的回答</div><div class="hint">直接打字回答；提交后系统会按五维 Rubric 复盘，并自动抽取能力短板写入你的画像。</div></div>', unsafe_allow_html=True)

            answer = st.text_area("回答内容", key="interview_answer", height=190, label_visibility="collapsed")
            review_submitted = st.button("提交 Rubric 复盘", type="primary", use_container_width=True)

            if review_submitted:
                if len(answer.strip()) < 50:
                    st.warning("回答太短，无法做有效复盘。请至少补充背景、行动、结果和反思。")
                else:
                    voice_metrics = st.session_state.get("voice_metrics", {})
                    duration_s = int(voice_metrics.get("duration_ms", 0) / 1000) if voice_metrics else 0
                    pause_count = voice_metrics.get("pause_count", 0) if voice_metrics else 0
                    max_pause_s = (voice_metrics.get("max_pause_ms", 0) / 1000) if voice_metrics else 0
                    prompt = interview_prompt.build_user_prompt(
                        role,
                        st.session_state.interview_question,
                        answer,
                        duration_s,
                        pause_count,
                        max_pause_s,
                    )
                    st.session_state.interview_review = call_ai_with_progress(
                        interview_prompt.SYSTEM_PROMPT,
                        prompt,
                        title=f"生成面试复盘 · {interview_prompt.PROMPT_VERSION}",
                        steps=["读取面试回答", "按 Rubric 评分", "生成追问建议", "整理 STAR 草稿"],
                    )
                    # Data flywheel: extract & persist weakness tags
                    tags = extract_weakness_tags(st.session_state.interview_review)
                    saved = persist_weakness_tags(st.session_state.device_id, tags)
                    st.session_state.weakness_tags = list_weakness_tags(st.session_state.device_id)
                    save_interview_session(
                        st.session_state.device_id,
                        role,
                        "single",
                        st.session_state.interview_question,
                        answer,
                        st.session_state.interview_review,
                        None,
                    )
                    if saved:
                        st.toast(f"已抽取并写入 {saved} 个能力短板标签到你的画像")

        render_result(st.session_state.interview_review, "面试复盘", "模拟面试 Rubric 复盘", "模拟面试", "interview", next_section="知识补强", next_label="下一步：补强暴露出的薄弱知识点")

    else:
        # ========== 多轮抗追问 Agent ==========
        st.session_state.agent_role = st.selectbox("选择模拟岗位", list(INTERVIEW_QUESTIONS.keys()), key="agent_role_select")
        agent_role = st.session_state.agent_role
        question_bank = INTERVIEW_QUESTIONS[agent_role]

        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            max_rounds = st.slider("最多追问轮数", 2, 6, st.session_state.agent_max_rounds, key="agent_max_rounds_slider")
            st.session_state.agent_max_rounds = max_rounds
        with col2:
            if st.button("开始一场抗追问面试", type="primary", use_container_width=True):
                weak_dims = top_weak_dimensions(st.session_state.device_id, top_n=2)
                ranked = sorted(
                    enumerate(question_bank),
                    key=lambda kv: -sum(1 for d in weak_dims if d.replace(" ", "") in kv[1].replace(" ", "")),
                )
                idx = ranked[0][0]
                st.session_state.agent_question = question_bank[idx]
                st.session_state.agent_dialogue = [
                    {"role": "interviewer", "content": question_bank[idx]},
                ]
                st.session_state.agent_round = 0
                st.session_state.agent_state = "awaiting_user"
                st.session_state.agent_final_review = ""
        with col3:
            if st.button("结束并复盘", use_container_width=True, disabled=(st.session_state.agent_state == "idle" or not st.session_state.agent_dialogue)):
                st.session_state.agent_state = "ready_for_review"

        if st.session_state.agent_dialogue:
            st.markdown(f"**起手题：** {st.session_state.agent_question}")
            for turn in st.session_state.agent_dialogue:
                if turn["role"] == "interviewer":
                    with st.chat_message("assistant", avatar="🎙️"):
                        st.markdown(turn["content"])
                else:
                    with st.chat_message("user"):
                        st.markdown(turn["content"])

            if st.session_state.agent_state == "awaiting_user":
                user_reply = st.chat_input("你的回答（说完后回车提交）")
                if user_reply:
                    st.session_state.agent_dialogue.append({"role": "candidate", "content": user_reply})
                    st.session_state.agent_round += 1

                    if st.session_state.agent_round >= st.session_state.agent_max_rounds:
                        st.session_state.agent_state = "ready_for_review"
                    else:
                        # Build follow-up question
                        weak_focus = [t["dimension"] for t in st.session_state.weakness_tags[:3] if t.get("dimension")]
                        followup_user_prompt = agent_prompt.build_agent_opening_prompt(
                            agent_role,
                            build_profile_context_for_agent(),
                            weak_focus,
                            st.session_state.agent_question,
                        )
                        # Compose with prior dialogue for context
                        dialogue_block = "\n".join(
                            f"{'面试官' if t['role'] == 'interviewer' else '候选人'}：{t['content']}"
                            for t in st.session_state.agent_dialogue
                        )
                        full_user_prompt = followup_user_prompt + "\n\n## 对话历史\n" + dialogue_block + "\n\n请输出下一个追问。"
                        with st.spinner(f"AI 面试官正在追问（第 {st.session_state.agent_round + 1} 轮 / {st.session_state.agent_max_rounds}）..."):
                            followup = call_ai_raw(
                                agent_prompt.AGENT_OPENING_SYSTEM,
                                full_user_prompt,
                                temperature=0.7,
                            )
                        if followup:
                            st.session_state.agent_dialogue.append({"role": "interviewer", "content": followup.strip()})
                    st.rerun()

            if st.session_state.agent_state == "ready_for_review" and not st.session_state.agent_final_review:
                weak_focus = [t["dimension"] for t in st.session_state.weakness_tags[:3] if t.get("dimension")]
                dialogue_lines = [
                    f"{'面试官' if t['role'] == 'interviewer' else '候选人'}：{t['content']}"
                    for t in st.session_state.agent_dialogue
                ]
                final_prompt = agent_prompt.build_agent_final_prompt(
                    agent_role,
                    st.session_state.agent_question,
                    dialogue_lines,
                    build_profile_context_for_agent(),
                    weak_focus,
                )
                st.session_state.agent_final_review = call_ai_with_progress(
                    agent_prompt.AGENT_FINAL_SYSTEM,
                    final_prompt,
                    title=f"抗追问最终复盘 · {agent_prompt.AGENT_PROMPT_VERSION}",
                    steps=["还原追问过程", "定位破绽", "生成合格答案", "抽取短板标签"],
                )
                # Data flywheel
                tags = extract_weakness_tags(st.session_state.agent_final_review)
                saved = persist_weakness_tags(st.session_state.device_id, tags)
                st.session_state.weakness_tags = list_weakness_tags(st.session_state.device_id)
                save_interview_session(
                    st.session_state.device_id,
                    agent_role,
                    "agent",
                    st.session_state.agent_question,
                    "\n".join(dialogue_lines),
                    st.session_state.agent_final_review,
                    None,
                )
                if saved:
                    st.toast(f"已抽取并写入 {saved} 个能力短板标签到你的画像")
                st.session_state.agent_state = "reviewed"
                st.rerun()

            if st.session_state.agent_final_review:
                render_result(
                    st.session_state.agent_final_review,
                    "面试复盘",
                    f"抗追问面试复盘 · {agent_role}",
                    "多轮面试",
                    "agent_review",
                    next_section="知识补强",
                    next_label="下一步：根据破绽地图去知识库补强",
                )

        else:
            st.caption("点击「开始一场抗追问面试」启动 AI 面试官。系统会基于你的画像和历史短板自动选题并连续追问。")

# ========== 模块 4：求职知识库 ==========
elif st.session_state.active_section == "知识补强":
    st.markdown('<div class="section-title">AI 产品求职知识库</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtle-note">当前是结构化知识目录 + 面试场景解释，不包装成 RAG。后续可升级为带引用来源的真实知识库。</div>', unsafe_allow_html=True)

    search_question = st.text_input("搜索或提问", key="kb_search")
    if st.button("查询知识库", type="primary", use_container_width=True):
        if not search_question.strip():
            st.warning("请输入一个具体问题，例如：RAG 怎么讲给面试官听？")
        else:
            base_prompt = knowledge_prompt.build_knowledge_prompt(search_question)
            if st.session_state.weakness_tags:
                weak_lines = "\n".join(
                    f"- {t['tag']}（{t['dimension']}，severity {t['severity']}，命中 {t['hit_count']} 次）"
                    for t in st.session_state.weakness_tags[:6]
                )
                prompt = base_prompt + f"\n\n## 用户当前能力短板（请据此调整解释深度，弱的地方多展开、强的地方略过）\n{weak_lines}\n"
            else:
                prompt = base_prompt
            st.session_state.kb_result = call_ai_with_progress(
                knowledge_prompt.KNOWLEDGE_SYSTEM_PROMPT,
                prompt,
                title=f"查询求职知识库 · {knowledge_prompt.KNOWLEDGE_PROMPT_VERSION}",
                steps=["理解问题", "匹配知识点", "组织面试表达", "整理追问模板"],
            )

    render_result(st.session_state.kb_result, "知识库笔记", "AI 产品求职知识笔记", "求职知识库", "kb", next_section="我的资产", next_label="下一步：查看并导出我的求职资产")

    st.markdown("---")
    for category, info in KNOWLEDGE_BASE.items():
        st.markdown(f'<div class="kb-card"><h4>{category}</h4><p>{info["说明"]}</p></div>', unsafe_allow_html=True)
        cols = st.columns(4)
        for index, topic in enumerate(info["知识点"]):
            with cols[index % 4]:
                if st.button(topic, key=f"kb_{category}_{topic}", use_container_width=True):
                    base_prompt = knowledge_prompt.build_topic_prompt(topic)
                    if st.session_state.weakness_tags:
                        weak_lines = "\n".join(
                            f"- {t['tag']}（{t['dimension']}）"
                            for t in st.session_state.weakness_tags[:5]
                        )
                        prompt = base_prompt + f"\n\n## 用户当前能力短板（请在抗追问版回答中重点对应）\n{weak_lines}\n"
                    else:
                        prompt = base_prompt
                    st.session_state.kb_result = call_ai_with_progress(
                        knowledge_prompt.TOPIC_SYSTEM_PROMPT,
                        prompt,
                        title=f"学习 {topic} · {knowledge_prompt.KNOWLEDGE_PROMPT_VERSION}",
                        steps=["读取知识点", "补充产品案例", "生成回答模板", "整理常见追问"],
                    )
                    st.rerun()

    st.markdown("---")
    st.markdown('<div class="section-title">岗位能力补强计划</div>', unsafe_allow_html=True)
    for path, topics in CAREER_PATHS.items():
        with st.expander(path, expanded=False):
            st.markdown("".join(f'<span class="path-tag">{topic}</span>' for topic in topics), unsafe_allow_html=True)
            if st.button(f"生成《{path}》7 天补强计划", key=f"plan_{path}"):
                prompt = knowledge_prompt.build_plan_prompt(path, topics)
                st.session_state.kb_result = call_ai_with_progress(
                    knowledge_prompt.PLAN_SYSTEM_PROMPT,
                    prompt,
                    title=f"生成补强计划 · {knowledge_prompt.PLAN_PROMPT_VERSION}",
                    steps=["分析岗位方向", "拆解能力短板", "安排每日任务", "整理输出物"],
                )
                st.rerun()

# ========== 模块 5：我的资产 ==========
elif st.session_state.active_section == "我的资产":
    st.markdown('<div class="section-title">我的求职资产库</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="subtle-note">资产已持久化到本地数据库，按设备 ID 区分。当前设备：<code>{st.session_state.device_id}</code>。把当前页面 URL 收藏，下次回来资产仍在。</div>', unsafe_allow_html=True)

    if not st.session_state.assets:
        st.info("还没有保存资产。先完成求职诊断、JD 匹配或模拟面试，然后点击“保存为资产”。")
    else:
        export_text = "# AI 产品求职资产\n\n"
        for asset in st.session_state.assets:
            export_text += f"## {asset['title']}\n\n类型：{asset['type']}  \n时间：{asset['created_at']}\n\n{asset['content']}\n\n---\n\n"

        interview_pack = f"""# AI 产品面试准备稿

## 项目一句话介绍
我做了一个面向 AI 产品转行者的求职资产工作台，帮助用户从能力盘点、JD 匹配、模拟面试到知识补强，沉淀可复用的求职材料。

## 已沉淀资产
{export_text}

## 面试讲法提醒
- 不要说这是完整 Agent 或 RAG；当前是 MVP。
- 强调差异点：任务结构化、Rubric 评分、反馈闭环、资产沉淀。
- 下一步迭代：多轮面试 Agent、Prompt 离线评估、RAG 知识库。
"""

        col_export1, col_export2 = st.columns(2)
        with col_export1:
            st.download_button(
                "下载全部资产 Markdown",
                data=export_text,
                file_name="ai_product_career_assets.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with col_export2:
            st.download_button(
                "生成并下载面试准备稿",
                data=interview_pack,
                file_name="ai_pm_interview_pack.md",
                mime="text/markdown",
                use_container_width=True,
            )

        for asset in st.session_state.assets:
            st.markdown('<div class="asset-box">', unsafe_allow_html=True)
            st.markdown(f'<div class="asset-title">{asset["title"]}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="asset-meta">{asset["type"]} · {asset["created_at"]} · ID {asset["id"]}</div>', unsafe_allow_html=True)
            with st.expander("查看内容", expanded=False):
                st.markdown(asset["content"])
            if st.button("删除该资产", key=f"del_asset_{asset['id']}"):
                delete_career_asset(st.session_state.device_id, asset["id"])
                st.session_state.assets = list_career_assets(st.session_state.device_id)
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<div class="section-title">能力短板地图（数据飞轮）</div>', unsafe_allow_html=True)
    st.caption("每次面试复盘后，系统会自动抽取你的能力短板标签并合并到这里。下次抽题、追问和知识库回答都会基于这些标签个性化。")
    if not st.session_state.weakness_tags:
        st.caption("还没有短板记录。先去做一次面试训练，系统会自动写入。")
    else:
        for tag in st.session_state.weakness_tags:
            severity_dot = "🔴" if tag["severity"] >= 3 else ("🟡" if tag["severity"] == 2 else "🟢")
            st.markdown(
                f"- {severity_dot} **{tag['tag']}** · {tag.get('dimension') or '未分类'} "
                f"· 命中 {tag['hit_count']} 次 · 最近 {tag['last_hit_at']}"
            )

    st.markdown("---")
    st.markdown('<div class="section-title">反馈记录</div>', unsafe_allow_html=True)
    if not st.session_state.feedback:
        st.caption("还没有反馈记录。")
    else:
        for item in st.session_state.feedback[:10]:
            st.caption(f"{item['created_at']} · {item['module']} · {item['value']}")

    st.markdown("---")
    if st.button("清空我的所有资产与反馈", key="clear_career_data"):
        clear_career_data(st.session_state.device_id)
        st.session_state.assets = []
        st.session_state.feedback = []
        st.session_state.weakness_tags = []
        st.success("已清空当前设备的全部资产、反馈和短板记录。")
        st.rerun()
