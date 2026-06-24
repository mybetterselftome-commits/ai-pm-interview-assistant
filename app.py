"""AI PM 求职准备工作台 V4 - 把求职准备转化成岗位认可的面试材料"""
import os
import re
import json
import time
import uuid
import html
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
import prompts.portfolio_prompt as portfolio_prompt
import prompts.loop_prompt as loop_prompt
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
    page_title="AI PM 求职准备工作台",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "AI PM 求职准备工作台 · 把经历、作品集和面试回答转化为面试材料"
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

    .section-title { font-weight: 850; font-size: 1.12rem; margin: 0.4rem 0 0.45rem 0; color: #111827; }
    .subtle-note { color: #6b7280; font-size: 0.86rem; margin-bottom: 0.6rem; }
    .rail-brand { font-size: 1rem; font-weight: 900; color: #111827; line-height: 1.25; margin: 0.2rem 0 0.15rem 0; }
    .rail-subtitle { color: #6b7280; font-size: 0.78rem; line-height: 1.4; margin-bottom: 0.75rem; }
    .rail-toggle-hint { color: #9ca3af; font-size: 0.72rem; text-align: center; }
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
        display: block;
        width: 100%;
        min-width: 980px;
        overflow-x: auto;
        border-collapse: separate;
        border-spacing: 0;
        margin: 1rem 0 1.2rem 0;
        font-size: 0.9rem;
        table-layout: auto;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
    }
    .result-box th,
    div[data-testid="stMarkdown"] table th {
        background: #f8fafc;
        color: #111827;
        font-weight: 850;
        border: 1px solid #e5e7eb;
        padding: 0.85rem 0.9rem;
        text-align: left;
        white-space: normal;
        min-width: 140px;
        line-height: 1.55;
    }
    .result-box td,
    div[data-testid="stMarkdown"] table td {
        border: 1px solid #e5e7eb;
        padding: 0.9rem;
        vertical-align: top;
        color: #111827;
        word-break: normal;
        overflow-wrap: anywhere;
        white-space: normal;
        min-width: 150px;
        max-width: 420px;
        line-height: 1.65;
    }
    div[data-testid="stMarkdown"] table {
        display: block;
        width: 100%;
        max-width: 100%;
        min-width: 980px;
        overflow-x: auto;
        border-collapse: separate;
        border-spacing: 0;
        margin: 1rem 0 1.3rem 0;
        font-size: 0.9rem;
        table-layout: auto;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        background: #fff;
    }
    div[data-testid="stMarkdown"] table tr:nth-child(even) td { background: #fbfdff; }
    div[data-testid="stMarkdown"] table th:first-child,
    div[data-testid="stMarkdown"] table td:first-child {
        min-width: 130px;
        font-weight: 800;
    }
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
    "通用 AI 产品岗": ["LLM 基础", "RAG 产品方案", "Agent 工作流", "Prompt 工程", "模型评估", "产品指标"],
    "AI 产品经理": ["LLM 基础", "RAG 产品方案", "Agent 工作流", "模型评估", "AI 产品流程", "人机协同"],
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
    "增长与反馈": {
        "说明": "考察你是否理解产品上线后的用户反馈、效果监控和持续迭代。",
        "知识点": ["用户反馈闭环", "数据指标", "A/B 测试", "模型效果监控", "内容质量控制", "合规审核"],
    },
    "面试表达": {
        "说明": "把经历讲成面试官能认可的产品能力。",
        "知识点": ["STAR 法则", "项目复盘", "失败案例", "业务指标表达", "技术选型表达", "面试追问", "简历项目包装", "个人优势提炼"],
    },
}

INTERVIEW_QUESTIONS = {
    "通用 AI 产品岗": [
        "请介绍一个你做过的项目，并说明它可以如何迁移到 AI 产品场景。",
        "如果要把一个传统业务流程改造成 AI 产品，你会如何判断适不适合用 AI？",
        "你如何评估一个 AI 功能是否真的解决了用户问题？",
    ],
    "AI 产品经理": [
        "请介绍一个你做过或设计过的 AI 产品项目，并说明为什么这个场景适合用 AI。",
        "如果模型效果不稳定，你作为产品经理会如何定位问题并推动优化？",
        "RAG 和模型微调分别适合什么场景？你会如何做选型？",
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

EXAMPLES = {
    "内容运营转 AI 产品（你的背景）": {
        "background": EXAMPLE_BACKGROUND,
        "project": EXAMPLE_PROJECT,
        "confusion": "不知道自己更适合通用 AI 产品岗还是更垂直的 AI 产品经理方向，也不知道如何把内容运营经历包装成 AI 产品能力。",
        "jd": EXAMPLE_JD,
        "portfolio_goal": "想做一个能证明 AI 产品能力的小作品集，但不确定做 RAG、Agent 还是 AI 运营工具。",
        "answer": EXAMPLE_ANSWER,
        "mastery_topic": "RAG",
        "mastery_explanation": "RAG 是检索增强生成，可以让大模型先查知识库再回答，减少幻觉。",
    },
    "建筑商务转 AI 成本分析产品": {
        "background": "我有建筑行业商务/成本相关经验，参与过项目成本台账、分包结算、材料价格跟踪、工程量清单核对和月度成本分析。熟悉施工项目的成本构成、合同条款、签证变更和结算流程，但对 AI 产品设计、RAG、Agent、模型评估还不系统。",
        "project": "曾参与一个项目月度成本分析工作：整理合同金额、已完产值、分包结算、材料采购和现场签证数据，对比目标成本和实际成本，定位钢筋、混凝土、劳务等费用偏差，并协助输出月度成本分析表和风险提示。希望把这段经历转成 AI 成本分析/工程管理产品相关能力。",
        "confusion": "不知道建筑商务经验能不能转成 AI 产品能力，也不知道如何把成本分析、合同结算和数据表格经验讲成 AI 产品经理能听懂的项目。",
        "jd": """岗位：AI 产品经理（工程成本/企业管理方向）
职责：
1. 负责工程成本分析、合同风险识别、经营数据看板等 AI 应用产品设计；
2. 梳理业务人员在成本测算、分包结算、签证变更、材料价格跟踪中的真实场景；
3. 结合 RAG、结构化抽取、Agent 流程等能力，提升报表分析、风险提示和资料检索效率；
4. 与业务、工程、数据、算法团队协作，建立产品指标和上线后的反馈闭环。
要求：
1. 有建筑、工程、商务、成本、合同、供应链或企业管理相关经验优先；
2. 能理解业务流程，并把复杂表格/文档场景拆成产品需求；
3. 了解 LLM、RAG、Prompt、Agent 基础概念；
4. 具备数据分析、流程梳理和跨部门沟通能力。""",
        "portfolio_goal": "想做一个 AI 工程成本分析助手作品集，证明自己能把建筑商务场景、成本数据和 AI 能力结合起来。",
        "answer": "我参与过项目月度成本分析工作。当时需要把合同金额、已完产值、分包结算、材料采购和现场签证数据整理到一起，对比目标成本和实际成本，找出费用偏差。我主要做数据整理、表格核对和异常项标注，比如钢筋、混凝土、劳务费用是否超出预期。如果迁移到 AI 产品场景，我会把它设计成一个工程成本分析助手：先结构化读取成本表和合同资料，再自动提示异常费用和可能原因，最后由商务人员确认。",
        "mastery_topic": "RAG 在工程资料检索中的应用",
        "mastery_explanation": "RAG 可以让系统先检索合同、清单、签证单、成本台账等资料，再基于检索结果回答成本分析问题，减少模型乱编。",
    },
    "客服运营转 AI Agent 产品": {
        "background": "我有 4 年客服运营和服务流程优化经验，负责过工单分类、FAQ 维护、客服质检和服务满意度提升。用过智能客服后台和知识库工具，对 Agent、Function Calling、RAG 只了解概念。",
        "project": "曾主导一次客服工单分流优化：分析 3 个月工单数据，把问题分为账户、支付、物流、售后和投诉 5 类，重构 FAQ 和客服话术，并上线工单标签规则，使人工转接率下降约 15%，首次响应时长下降约 22%。希望转向 AI Agent/智能客服产品。",
        "confusion": "我不确定客服运营经验如何证明 Agent 产品能力，也担心自己技术不够，不知道面试时怎么讲工具调用、兜底和权限边界。",
        "jd": """岗位：AI Agent 产品经理
职责：
1. 负责智能客服 Agent 的任务流程、工具调用、知识库和人工兜底设计；
2. 梳理用户服务场景，设计多轮对话、意图识别、工单流转和质检闭环；
3. 与算法、工程、客服运营协作，提升问题解决率和用户满意度；
4. 建立 Agent 任务完成率、转人工率、错误率、满意度等评估指标。
要求：
1. 理解 LLM、Agent、RAG、Function Calling 基础概念；
2. 有客服、SaaS、工单、CRM 或服务流程经验优先；
3. 能设计复杂流程、异常兜底和权限边界；
4. 具备数据分析和跨团队推动能力。""",
        "portfolio_goal": "想做一个智能客服 Agent 流程设计作品集，重点证明任务流程、工具调用失败兜底和转人工机制。",
        "answer": "我做过客服工单分流优化。当时客服问题分散，很多简单问题也进入人工队列，导致响应慢。我分析了 3 个月工单，把问题拆成 5 类，重构 FAQ 和话术，并上线标签规则，人工转接率下降约 15%，首次响应时长下降约 22%。如果做 AI Agent，我会把它设计成先识别意图，再查询知识库，必要时调用订单或物流工具，失败时转人工。",
        "mastery_topic": "Agent 工具调用",
        "mastery_explanation": "Agent 工具调用就是让大模型在需要时调用外部工具，比如查订单、查物流或创建工单，从而完成用户任务。",
    },
}

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
        "active_section": "JD解码",
        "profile_result": "",
        "jd_result": "",
        "portfolio_result": "",
        "interview_question": "",
        "interview_review": "",
        "kb_result": "",
        "mastery_result": "",
        "loop_result": "",
        "assets": [],
        "feedback": [],
        "interview_index": 0,
        "profile_background": "",
        "profile_project": "",
        "profile_confusion": "",
        "selected_example": "内容运营转 AI 产品（你的背景）",
        "show_left_nav": True,
        "jd_text": "",
        "jd_user_summary": "",
        "portfolio_goal": "",
        "portfolio_time_budget": "7 天",
        "portfolio_tech_level": "会简单 Streamlit / Python",
        "interview_answer": "",
        "interview_context_mode": "引用全部上下文",
        "kb_search": "",
        "mastery_topic": "RAG",
        "mastery_explanation": "",
        "loop_goal": "准备面试",
        "loop_time_budget": "7 天",
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
    status.caption("模型正在生成结果，大约需要 60 秒，请稍等。")
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


def markdown_to_html(title, markdown_text):
    """Convert the generated Markdown report into a self-contained HTML file."""
    title = html.escape(title or "AI 输出结果")
    body_parts = []
    lines = markdown_text.splitlines()
    in_ul = False
    in_ol = False
    i = 0

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            body_parts.append("</ul>")
            in_ul = False
        if in_ol:
            body_parts.append("</ol>")
            in_ol = False

    while i < len(lines):
        raw = lines[i]
        line = raw.strip()
        if not line:
            close_lists()
            i += 1
            continue

        if line.startswith("|") and i + 1 < len(lines) and lines[i + 1].strip().startswith("|"):
            close_lists()
            table_rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [html.escape(cell.strip()) for cell in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"[:\-\s]+", cell) for cell in cells):
                    table_rows.append(cells)
                i += 1
            if table_rows:
                body_parts.append("<table>")
                for row_index, cells in enumerate(table_rows):
                    tag = "th" if row_index == 0 else "td"
                    body_parts.append("<tr>" + "".join(f"<{tag}>{cell}</{tag}>" for cell in cells) + "</tr>")
                body_parts.append("</table>")
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            close_lists()
            level = min(len(heading.group(1)), 4)
            body_parts.append(f"<h{level}>{html.escape(heading.group(2))}</h{level}>")
            i += 1
            continue

        bullet = re.match(r"^[-*]\s+(.*)$", line)
        if bullet:
            if in_ol:
                body_parts.append("</ol>")
                in_ol = False
            if not in_ul:
                body_parts.append("<ul>")
                in_ul = True
            body_parts.append(f"<li>{html.escape(bullet.group(1))}</li>")
            i += 1
            continue

        numbered = re.match(r"^\d+[.)]\s+(.*)$", line)
        if numbered:
            if in_ul:
                body_parts.append("</ul>")
                in_ul = False
            if not in_ol:
                body_parts.append("<ol>")
                in_ol = True
            body_parts.append(f"<li>{html.escape(numbered.group(1))}</li>")
            i += 1
            continue

        close_lists()
        text = html.escape(line)
        text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)
        body_parts.append(f"<p>{text}</p>")
        i += 1

    close_lists()
    body = "\n".join(body_parts)
    return f"""<!doctype html>
<html lang=\"zh-CN\">
<head>
<meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
<title>{title}</title>
<style>
body {{ margin: 0; background: #f7f8fb; color: #111827; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.72; }}
.container {{ max-width: 1080px; margin: 40px auto; background: #fff; border: 1px solid #e5e7eb; border-radius: 18px; padding: 40px 46px; box-shadow: 0 18px 48px rgba(15,23,42,.08); }}
h1 {{ font-size: 30px; margin: 0 0 24px; letter-spacing: -0.03em; }}
h2 {{ font-size: 24px; margin: 34px 0 14px; padding-top: 12px; border-top: 1px solid #e5e7eb; }}
h3 {{ font-size: 19px; margin: 26px 0 10px; }}
h4 {{ font-size: 16px; margin: 18px 0 8px; }}
p {{ margin: 10px 0; }}
ul, ol {{ padding-left: 1.4rem; margin: 10px 0; }}
li {{ margin: 6px 0; }}
table {{ width: 100%; border-collapse: collapse; margin: 18px 0 24px; font-size: 14px; }}
th {{ background: #f8fafc; font-weight: 800; }}
th, td {{ border: 1px solid #e5e7eb; padding: 10px 12px; vertical-align: top; }}
strong {{ font-weight: 850; }}
.meta {{ color: #6b7280; font-size: 13px; margin-bottom: 26px; }}
</style>
</head>
<body>
<div class=\"container\">
<h1>{title}</h1>
<div class=\"meta\">由 AI PM 求职准备工作台导出</div>
{body}
</div>
</body>
</html>"""


def render_result(markdown_text, asset_type=None, asset_title=None, feedback_module=None, key_prefix="result", next_section=None, next_label=None):
    if not markdown_text:
        return
    st.markdown(markdown_text)

    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    with col1:
        if asset_type and st.button("保存为资产", key=f"{key_prefix}_save", use_container_width=True):
            save_asset(asset_type, asset_title or asset_type, markdown_text)
            st.success("已保存到我的求职资产库")
    with col2:
        st.download_button(
            "导出 HTML",
            data=markdown_to_html(asset_title or asset_type or "AI 输出结果", markdown_text),
            file_name=f"{key_prefix}_result.html",
            mime="text/html",
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


def asset_count_any(asset_types):
    types = set(asset_types)
    return sum(1 for asset in st.session_state.assets if asset["type"] in types)


def weakness_context(limit=6):
    if not st.session_state.weakness_tags:
        return ""
    return "\n".join(
        f"- {t['tag']}（{t.get('dimension') or '未分类'}，severity {t['severity']}，命中 {t['hit_count']} 次）"
        for t in st.session_state.weakness_tags[:limit]
    )


def build_evidence_context(mode="引用全部上下文"):
    parts = []
    if mode in ("引用 JD 解码", "引用全部上下文") and st.session_state.jd_result:
        parts.append("## JD 解读报告\n" + st.session_state.jd_result[:1400])
    if mode in ("引用经历转译", "引用全部上下文") and st.session_state.profile_result:
        parts.append("## 经历经历转译\n" + st.session_state.profile_result[:1400])
    if mode in ("引用作品集规划", "引用全部上下文") and st.session_state.portfolio_result:
        parts.append("## 作品集规划\n" + st.session_state.portfolio_result[:1400])
    return "\n\n".join(parts)


def summarize_assets(limit=8):
    lines = []
    for asset in st.session_state.assets[:limit]:
        content = (asset.get("content") or "").replace("\n", " ")[:500]
        lines.append(f"- [{asset['type']}] {asset['title']}（{asset['created_at']}）：{content}")
    return "\n".join(lines)


def fill_example(example_name=None):
    example_name = example_name or st.session_state.get("selected_example") or next(iter(EXAMPLES))
    example = EXAMPLES[example_name]
    st.session_state.selected_example = example_name
    st.session_state.profile_background = example["background"]
    st.session_state.profile_project = example["project"]
    st.session_state.profile_confusion = example["confusion"]
    st.session_state.jd_text = example["jd"]
    st.session_state.jd_user_summary = example["background"] + "\n" + example["project"]
    st.session_state.portfolio_goal = example["portfolio_goal"]
    st.session_state.interview_answer = example["answer"]
    st.session_state.kb_search = f"{example['mastery_topic']} 怎么讲给面试官听？"
    st.session_state.mastery_topic = example["mastery_topic"]
    st.session_state.mastery_explanation = example["mastery_explanation"]


def render_example_buttons(key_prefix):
    labels = [
        ("填入示例1", "内容运营"),
        ("填入示例2", "建筑商务"),
        ("填入示例3", "客服运营"),
    ]
    example_names = list(EXAMPLES.keys())
    cols = st.columns(3)
    for index, (button_label, short_label) in enumerate(labels):
        with cols[index]:
            if st.button(f"{button_label} · {short_label}", key=f"{key_prefix}_example_{index}", use_container_width=True):
                fill_example(example_names[index])
                st.rerun()

# ========== 顶部与目录 ==========
nav_items = [
    ("JD解码", "01", "看懂岗位要求"),
    ("经历转译", "02", "找到可用经历"),
    ("作品集规划", "03", "补项目经历"),
    ("面试训练", "04", "改成岗位证明"),
    ("补强闭环/我的资产", "05", "沉淀下一步"),
]

if st.session_state.show_left_nav:
    left_col, toggle_col, main_col = st.columns([0.18, 0.035, 0.785], gap="small")
    with left_col:
        st.markdown('<div class="rail-brand">AI PM 求职准备工作台</div>', unsafe_allow_html=True)
        st.markdown('<div class="rail-subtitle">AI PM 面试准备助手<br/>从 JD 到面试，一步步准备</div>', unsafe_allow_html=True)
        for section, num, text in nav_items:
            active_mark = "● " if st.session_state.active_section == section else ""
            if st.button(f"{active_mark}{num} {section}", key=f"nav_{section}", use_container_width=True):
                st.session_state.active_section = section
                st.rerun()
else:
    toggle_col, main_col = st.columns([0.035, 0.965], gap="small")

with toggle_col:
    toggle_icon = "‹" if st.session_state.show_left_nav else "›"
    if st.button(toggle_icon, key="toggle_left_nav", help="隐藏/展开目录"):
        st.session_state.show_left_nav = not st.session_state.show_left_nav
        st.rerun()

with main_col:

    # ========== 模块 1：JD 解码 ==========
    if st.session_state.active_section == "JD解码":
        st.markdown('<div class="section-title">JD 解码：先看岗位到底看重什么</div>', unsafe_allow_html=True)
        st.markdown('<div class="subtle-note">把 JD 原文拆成真实岗位要求、能力重点、高风险追问和适合补充的项目方向。即使还没整理经历，也能先看懂岗位筛选逻辑。</div>', unsafe_allow_html=True)

        render_example_buttons("jd")

        jd_text = st.text_area("目标岗位 JD", key="jd_text", height=240)
        user_summary = st.text_area(
            "可选：简单介绍一下你自己，系统会一起看你和这份 JD 的差距",
            key="jd_user_summary",
            height=120,
            placeholder="可以简单写：你现在做什么、做过哪些项目、用过哪些 AI 工具、有什么数据结果、想转什么方向。\n如果你还没整理好，也可以先留空，系统会先单独解读 JD。",
            help="这里不是必填。填写后，系统会结合你的经历，判断你和这个岗位的匹配点、差距和准备重点。",
        )
        jd_submitted = st.button("生成 JD 解读报告", type="primary", use_container_width=True)

        if jd_submitted:
            profile_context = user_summary or build_profile_context_for_agent() or "用户暂未提供背景，请先按通用 AI PM 候选人标准解读 JD，并标注后续需要补充的信息。"
            if len(jd_text.strip()) < 80:
                st.warning("请补充更完整的 JD。JD 建议包含岗位职责和任职要求。")
            else:
                prompt = jd_prompt.build_user_prompt(profile_context, jd_text)
                st.session_state.jd_result = call_ai_with_progress(
                    jd_prompt.SYSTEM_PROMPT,
                    prompt,
                    title=f"生成 JD 解读报告 · {jd_prompt.PROMPT_VERSION}",
                    steps=["读取岗位要求", "拆解背后能力", "定义判断标准", "整理追问风险"],
                )

        render_result(
            st.session_state.jd_result,
            "JD解读报告",
            "AI PM 岗位解读报告",
            "JD解码",
            "jd",
            next_section="经历转译",
            next_label="下一步：把我的经历转译成岗位材料",
        )

    # ========== 模块 2：经历转译 ==========
    elif st.session_state.active_section == "经历转译":
        st.markdown('<div class="section-title">经历转译：把过往经历翻译成 AI PM 岗位能力</div>', unsafe_allow_html=True)
        st.markdown('<div class="subtle-note">系统会引用 JD 解读报告，判断哪些经历能写进简历、能讲成面试故事、能支撑作品集，哪些不能过度包装。</div>', unsafe_allow_html=True)

        render_example_buttons("profile")

        if st.session_state.jd_result:
            st.caption("✅ 已检测到 JD 解读报告，本模块会自动引用前 1500 字作为岗位材料上下文。")
        else:
            st.caption("提示：可以先做 JD 解码；也可以直接转译经历，系统会按你更想准备哪类岗位？处理。")

        current_background = st.text_area("你的过往背景", key="profile_background", height=120)
        target_role = st.selectbox("你更想准备哪类岗位？", list(CAREER_PATHS.keys()), key="profile_target_role")
        ai_level_options = ["1 完全小白", "2 了解基础概念", "3 熟练使用 AI 工具", "4 做过 AI 项目/能设计方案"]
        if st.session_state.get("profile_ai_level") not in ai_level_options:
            st.session_state.profile_ai_level = ai_level_options[2]
        st.markdown("**AI 基础水平（请选择一个等级）**")
        ai_level = st.radio(
            "AI 基础水平",
            options=ai_level_options,
            key="profile_ai_level",
            horizontal=True,
            label_visibility="collapsed",
        )
        product_experience = st.text_area("你已有的项目/产品/运营经历", key="profile_project", height=110)
        biggest_confusion = st.text_input("当前最大困惑", key="profile_confusion")
        submitted = st.button("生成经历转译", type="primary", use_container_width=True)

        if submitted:
            if len(current_background.strip()) < 20 or len(product_experience.strip()) < 20:
                st.warning("为了生成有价值的经历转译，请至少补充一段过往背景和一段项目/经历，建议包含职责、动作和结果。")
            else:
                prompt = profile_prompt.build_user_prompt(
                    current_background,
                    target_role,
                    ai_level,
                    product_experience,
                    biggest_confusion,
                    st.session_state.jd_result[:1500],
                )
                st.session_state.profile_result = call_ai_with_progress(
                    profile_prompt.SYSTEM_PROMPT,
                    prompt,
                    title=f"生成经历经历转译 · {profile_prompt.PROMPT_VERSION}",
                    steps=["读取个人背景", "提炼可迁移经历", "识别包装边界", "整理转译报告"],
                )

        render_result(
            st.session_state.profile_result,
            "经历经历转译",
            "经历到 AI PM 能力经历转译报告",
            "经历转译",
            "profile",
            next_section="作品集规划",
            next_label="下一步：用作品集补齐缺失内容",
        )

    # ========== 模块 3：作品集规划 ==========
    elif st.session_state.active_section == "作品集规划":
        st.markdown('<div class="section-title">作品集规划：用一个可完成的项目补齐岗位材料</div>', unsafe_allow_html=True)
        st.markdown('<div class="subtle-note">不是做大而全的 Demo，而是围绕 JD 缺口规划最小可行作品集：证明场景理解、AI 能力设计、指标、边界和面试讲法。</div>', unsafe_allow_html=True)

        context_cols = st.columns(3)
        context_cols[0].metric("JD 解读报告", "已生成" if st.session_state.jd_result else "未生成")
        context_cols[1].metric("经历转译", "已生成" if st.session_state.profile_result else "未生成")
        context_cols[2].metric("短板标签", len(st.session_state.weakness_tags))

        target_role = st.selectbox("你更想准备哪类岗位？", list(CAREER_PATHS.keys()), key="portfolio_target_role")
        time_budget = st.selectbox("可投入时间", ["3 天", "7 天", "14 天", "30 天"], key="portfolio_time_budget")
        tech_level = st.selectbox(
            "技术实现水平",
            ["只会用 AI 工具", "会简单 Streamlit / Python", "会 API 调用", "能做前后端原型", "已有完整项目经验"],
            key="portfolio_tech_level",
        )
        portfolio_goal = st.text_area("你想证明的能力 / 想做的方向（可选）", key="portfolio_goal", height=100)
        portfolio_submitted = st.button("生成作品集材料方案", type="primary", use_container_width=True)

        if portfolio_submitted:
            prompt = portfolio_prompt.build_user_prompt(
                st.session_state.jd_result[:1800],
                st.session_state.profile_result[:1800],
                weakness_context(),
                target_role,
                time_budget,
                tech_level,
                portfolio_goal,
            )
            st.session_state.portfolio_result = call_ai_with_progress(
                portfolio_prompt.SYSTEM_PROMPT,
                prompt,
                title=f"生成作品集规划 · {portfolio_prompt.PROMPT_VERSION}",
                steps=["读取岗位材料", "定位作品集主题", "设计 MVP 范围", "整理面试讲法"],
            )

        render_result(
            st.session_state.portfolio_result,
            "作品集规划",
            "AI PM 作品集材料方案",
            "作品集规划",
            "portfolio",
            next_section="面试训练",
            next_label="下一步：验证我的回答能不能扛追问",
        )

    # ========== 模块 4：面试训练 ==========
    elif st.session_state.active_section == "面试训练":
        st.markdown('<div class="section-title">面试训练：把回答从学习笔记改成岗位证明</div>', unsafe_allow_html=True)
        st.markdown('<div class="subtle-note">这个模块不是泛泛打分，而是固定输出：原回答评分、为什么不像岗位证明、缺少的产品支撑材料、改写版回答、追问防守。</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="kb-card">
            <h4>本模块会输出什么？</h4>
            <p>① 原回答评分 · ② 原回答为什么不像岗位证明 · ③ 缺少的产品支撑材料 · ④ 改写版回答 · ⑤ 追问防守</p>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state.weakness_tags:
            focus_tags = "、".join(f"{t['tag']}（{t['dimension']}）" for t in st.session_state.weakness_tags[:5])
            st.caption(f"📌 系统已记录的薄弱点（会用于个性化追问与抽题）：{focus_tags}")

        mode_label = st.radio(
            "训练模式",
            ["single", "agent"],
            format_func=lambda x: "单轮面试复盘" if x == "single" else "多轮抗追问 Agent",
            horizontal=True,
            key="interview_mode",
        )

        if mode_label == "single":
            role = st.selectbox("选择模拟岗位", list(INTERVIEW_QUESTIONS.keys()), key="interview_role")
            context_mode = st.selectbox(
                "背景上下文",
                ["不引用", "引用 JD 解码", "引用经历转译", "引用作品集规划", "引用全部上下文"],
                key="interview_context_mode",
            )
            question_bank = INTERVIEW_QUESTIONS[role]

            weak_dims = top_weak_dimensions(st.session_state.device_id, top_n=2)
            if weak_dims:
                st.caption(f"🎯 本次抽题将优先考察你的弱项维度：{', '.join(weak_dims)}")

            col_a, col_b, col_c = st.columns([1, 1, 1])
            with col_a:
                if st.button("下一道面试题", type="primary", use_container_width=True):
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
                st.markdown('<div class="voice-row"><div class="title">输入你的回答</div><div class="hint">提交后系统会拆解你的回答主张，判断每个主张是否有真实经历、项目、指标或作品集材料支撑。</div></div>', unsafe_allow_html=True)

                answer = st.text_area("回答内容", key="interview_answer", height=190, label_visibility="collapsed")
                voice_payload = realtime_speech(
                    target_label="回答内容",
                    title="实时语音写入回答框",
                    hint="点击开始后直接说话，文字会边说边写入上方回答框。停止后再提交复盘。",
                    key="voice_interview_answer",
                )
                if isinstance(voice_payload, dict):
                    st.session_state.voice_metrics = voice_payload
                    if voice_payload.get("transcript"):
                        st.session_state.last_voice_transcript = voice_payload.get("transcript", "")
                review_submitted = st.button("提交面试复盘", type="primary", use_container_width=True)

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
                            build_evidence_context(context_mode),
                        )
                        st.session_state.interview_review = call_ai_with_progress(
                            interview_prompt.SYSTEM_PROMPT,
                            prompt,
                            title=f"生成面试复盘 · {interview_prompt.PROMPT_VERSION}",
                            steps=["读取面试回答", "拆解回答主张", "检查回答支撑是否充分", "整理复盘建议"],
                        )
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

            render_result(st.session_state.interview_review, "面试面试复盘", "模拟面试面试复盘", "面试训练", "interview", next_section="面试训练", next_label="下一步：继续做知识掌握度自测")

        else:
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
                    st.session_state.agent_dialogue = [{"role": "interviewer", "content": question_bank[idx]}]
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
                            weak_focus = [t["dimension"] for t in st.session_state.weakness_tags[:3] if t.get("dimension")]
                            followup_user_prompt = agent_prompt.build_agent_opening_prompt(
                                agent_role,
                                build_profile_context_for_agent(),
                                weak_focus,
                                st.session_state.agent_question,
                            )
                            dialogue_block = "\n".join(
                                f"{'面试官' if t['role'] == 'interviewer' else '候选人'}：{t['content']}"
                                for t in st.session_state.agent_dialogue
                            )
                            evidence_context = build_evidence_context("引用全部上下文")
                            full_user_prompt = followup_user_prompt + "\n\n## 可用经历上下文\n" + evidence_context + "\n\n## 对话历史\n" + dialogue_block + "\n\n请输出下一个追问。"
                            with st.spinner(f"AI 面试官正在追问（第 {st.session_state.agent_round + 1} 轮 / {st.session_state.agent_max_rounds}）..."):
                                followup = call_ai_raw(agent_prompt.AGENT_OPENING_SYSTEM, full_user_prompt, temperature=0.7)
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
                        build_profile_context_for_agent() + "\n\n" + build_evidence_context("引用全部上下文"),
                        weak_focus,
                    )
                    st.session_state.agent_final_review = call_ai_with_progress(
                        agent_prompt.AGENT_FINAL_SYSTEM,
                        final_prompt,
                        title=f"抗追问最终复盘 · {agent_prompt.AGENT_PROMPT_VERSION}",
                        steps=["还原追问过程", "定位破绽", "生成合格答案", "抽取短板标签"],
                    )
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
                        "面试面试复盘",
                        f"抗追问面试复盘 · {agent_role}",
                        "多轮面试",
                        "agent_review",
                        next_section="面试训练",
                        next_label="下一步：根据破绽地图补强知识掌握度",
                    )
            else:
                st.caption("点击「开始一场抗追问面试」启动 AI 面试官。系统会基于你的画像、作品集和历史短板自动选题并连续追问。")

        st.markdown("---")
        st.markdown('<div class="section-title">面试知识补强：只保留掌握度自测</div>', unsafe_allow_html=True)
        st.markdown('<div class="subtle-note">这里不再做大面积知识库展示，只判断一个知识点是否达到面试可用、产品可用、抗追问可用的深度。</div>', unsafe_allow_html=True)

        topic = st.text_input("要自测的知识点", key="mastery_topic", placeholder="例如：RAG、Agent、模型评估、Prompt 工程")
        target_role = st.selectbox("你更想准备哪类岗位？", list(CAREER_PATHS.keys()), key="mastery_target_role")
        user_explanation = st.text_area("先用你自己的话解释这个知识点", key="mastery_explanation", height=150, placeholder="不要复制定义，按你面试时会怎么说来写。")
        mastery_voice = realtime_speech(
            target_label="先用你自己的话解释这个知识点",
            title="实时语音写入自测解释",
            hint="点击开始后直接解释这个知识点，文字会边说边写入上方输入框。",
            key="voice_mastery_explanation",
        )
        if isinstance(mastery_voice, dict):
            st.session_state.voice_metrics = mastery_voice
        mastery_submitted = st.button("评估掌握度", type="primary", use_container_width=True)
        if mastery_submitted:
            if len(user_explanation.strip()) < 20:
                st.warning("请先用自己的话解释，至少写 20 字。")
            else:
                prompt = knowledge_prompt.build_mastery_prompt(topic, user_explanation, target_role, weakness_context())
                st.session_state.mastery_result = call_ai_with_progress(
                    knowledge_prompt.MASTERY_SYSTEM_PROMPT,
                    prompt,
                    title=f"评估掌握度 · {knowledge_prompt.MASTERY_PROMPT_VERSION}",
                    steps=["读取你的解释", "按 Rubric 评分", "定位追问风险", "生成补强卡片"],
                )
        render_result(st.session_state.mastery_result, "知识掌握卡", f"{st.session_state.mastery_topic} 掌握度自测", "面试知识补强", "mastery", next_section="补强闭环/我的资产", next_label="下一步：生成补强闭环")

    # ========== 模块 6：补强闭环 / 我的资产 ==========
    elif st.session_state.active_section == "补强闭环/我的资产":
        st.markdown('<div class="section-title">补强闭环 / 我的资产：从生成内容到下一步行动</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="subtle-note">资产已按设备 ID 持久化保存。当前设备：<code>{st.session_state.device_id}</code>。把当前页面 URL 收藏，下次回来资产仍在。</div>', unsafe_allow_html=True)

        st.markdown("#### 生成下一轮补强闭环")
        target_role = st.selectbox("你更想准备哪类岗位？", list(CAREER_PATHS.keys()), key="loop_target_role")
        target_goal = st.selectbox("近期目标", ["本周投递", "准备面试", "补作品集", "补 AI 技术理解", "重写简历"], key="loop_goal")
        time_budget = st.selectbox("可投入时间", ["3 天", "7 天", "14 天", "30 天"], key="loop_time_budget")
        loop_submitted = st.button("生成补强闭环计划", type="primary", use_container_width=True)

        if loop_submitted:
            feedback_summary = "\n".join(f"- {item['created_at']} · {item['module']} · {item['value']}" for item in st.session_state.feedback[:20])
            prompt = loop_prompt.build_user_prompt(
                summarize_assets(),
                weakness_context(10),
                feedback_summary,
                target_goal,
                time_budget,
                target_role,
            )
            st.session_state.loop_result = call_ai_with_progress(
                loop_prompt.SYSTEM_PROMPT,
                prompt,
                title=f"生成补强闭环 · {loop_prompt.PROMPT_VERSION}",
                steps=["盘点已有资产", "合并短板标签", "排序准备缺口", "生成下一步任务"],
            )

        render_result(st.session_state.loop_result, "补强闭环计划", "AI PM 求职准备补强闭环计划", "补强闭环", "loop")

        st.markdown("---")
        st.markdown('<div class="section-title">我的求职准备材料库</div>', unsafe_allow_html=True)
        if not st.session_state.assets:
            st.info("还没有保存资产。先完成 JD 解码、经历转译、作品集规划或面试训练，然后点击“保存为资产”。")
        else:
            export_text = "# AI PM 求职准备材料\n\n"
            for asset in st.session_state.assets:
                export_text += f"## {asset['title']}\n\n类型：{asset['type']}  \n时间：{asset['created_at']}\n\n{asset['content']}\n\n---\n\n"

            interview_pack = f"""# AI PM 面试准备稿

    ## 项目一句话介绍
    我做了一个面向 AI 产品转行者的求职准备工作台，帮助用户把 JD 要求、过往经历、作品集和面试回答整理成岗位认可的面试材料。

    ## 已沉淀材料
    {export_text}

    ## 面试讲法提醒
    - 不要说系统替用户编造项目；强调信息边界和待补充内容。
    - 强调差异点：JD 解读、经历转译、作品集规划、面试复盘、短板闭环。
    - 当前是 MVP：不做自动投递，不声称完整 RAG，不替用户完成作品集。
    """

            col_export1, col_export2 = st.columns(2)
            with col_export1:
                st.download_button(
                    "下载全部资产 HTML",
                    data=markdown_to_html("AI PM 求职准备材料", export_text),
                    file_name="ai_pm_assets.html",
                    mime="text/html",
                    use_container_width=True,
                )
            with col_export2:
                st.download_button(
                    "生成并下载面试准备稿 HTML",
                    data=markdown_to_html("AI PM 面试准备稿", interview_pack),
                    file_name="ai_pm_interview_pack.html",
                    mime="text/html",
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
        st.caption("每次面试复盘后，系统会自动抽取你的能力短板标签并合并到这里。下次抽题、追问、知识掌握度和补强闭环都会引用这些标签。")
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
