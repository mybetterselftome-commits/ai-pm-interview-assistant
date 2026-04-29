"""AI 面试助手 V2 - 个性化知识记忆系统"""
import os
import random
import uuid
import httpx
import streamlit as st
from openai import OpenAI
from db import (init_db, get_or_create_user, save_chat, update_knowledge,
                get_user_profile, get_relevant_history, clear_user_data,
                restore_messages)

# ========== 绕过系统代理 ==========
for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
    os.environ.pop(key, None)

# ========== 读取 API Key ==========
api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key:
    try:
        # 兼容 Streamlit Cloud secrets
        api_key = st.secrets.get("DEEPSEEK_API_KEY")
    except:
        pass
if not api_key:
    try:
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.getenv("DEEPSEEK_API_KEY")
    except:
        pass

# ========== 初始化 DeepSeek 客户端 ==========
http_client = httpx.Client(proxy=None)
client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com", http_client=http_client)

# ========== 初始化数据库 ==========
init_db()
# ========== AI 面试知识点体系 ==========
TOPICS = {
    "机器学习": ["机器学习", "ml", "machine learning"],
    "监督学习": ["监督学习", "supervised"],
    "无监督学习": ["无监督学习", "unsupervised"],
    "强化学习": ["强化学习", "reinforcement"],
    "过拟合": ["过拟合", "overfitting", "过拟合"],
    "欠拟合": ["欠拟合", "underfitting"],
    "准确率": ["准确率", "precision", "精确率"],
    "召回率": ["召回率", "recall"],
    "F1分数": ["f1", "f1分数"],
    "混淆矩阵": ["混淆矩阵", "confusion matrix"],
    "AUC": ["auc", "roc", "auc-roc"],
    "偏差方差": ["偏差", "方差", "bias", "variance", "bias-variance"],
    "LLM": ["llm", "大语言模型", "大模型"],
    "Prompt工程": ["prompt", "提示词", "few-shot", "chain-of-thought", "cot"],
    "RAG": ["rag", "检索增强", "向量数据库"],
    "Agent": ["agent", "智能体", "tool use", "function calling", "工具调用"],
    "AIGC": ["aigc", "生成式", "文生图", "文生视频"],
    "模型评估": ["模型评估", "评估指标", "模型效果"],
    "模型选型": ["模型选型", "模型选择", "自研", "调api"],
    "深度学习": ["深度学习", "神经网络", "transformer", "注意力机制"],
    "训练集": ["训练集", "验证集", "测试集", "训练/验证/测试"],
    "RLHF": ["rlhf", "人类反馈", "强化学习人类反馈"],
    "数据分析指标": ["数据分析", "数据指标", "数据运营", "metrics"],
    "用户增长": ["用户增长", "增长策略", "用户运营", "用户活跃", "growth"],
    "内容运营": ["内容运营", "内容管理", "内容策略", "内容审核"],
    "模型监控": ["模型监控", "模型部署", "效果监控", "生产环境", "监控告警"],
    "AB测试": ["ab测试", "a/b测试", "ab test", "实验", "灰度发布"],
}

def extract_topics(text):
    """从文本中提取涉及的知识点"""
    text_lower = text.lower()
    found = []
    for topic, keywords in TOPICS.items():
        if any(kw in text_lower for kw in keywords):
            found.append(topic)
    return found

def extract_questions(text):
    """判断是否是一个问题"""
    question_words = ["什么", "怎么", "为什么", "如何", "区别", "关系", "对比",
                      "啥", "吗", "是不是", "能不能", "举例", "why", "how", "what"]
    text_lower = text.lower()
    if any(qw in text_lower for qw in question_words):
        return True
    if text.endswith("？") or text.endswith("?"):
        return True
    return False


# ========== 构建设备 ID ==========
def get_device_id():
    """从 query params 读取或生成设备 ID"""
    params = st.query_params
    if "device_id" in params and params["device_id"]:
        return params["device_id"]

    new_id = str(uuid.uuid4())[:8]
    st.query_params["device_id"] = new_id
    return new_id

# ========== 构建个性化 prompt ==========
def build_personalized_context(device_id, question):
    """根据用户历史构建个性化上下文"""
    profile = get_user_profile(device_id)
    question_topics = extract_topics(question)
    relevant_history = get_relevant_history(device_id, question_topics)

    context_parts = []

    # 知识状态
    if question_topics:
        known = []
        new = []
        for t in question_topics:
            if t in profile["knowledge"]:
                known.append(f"{t}（已了解，问过{profile['knowledge'][t]['count']}次）")
            else:
                new.append(t)
        if known:
            context_parts.append(f"用户已了解的知识点：{'、'.join(known)}")
        if new:
            context_parts.append(f"用户新接触的知识点：{'、'.join(new)}，请做基础解释")

    # 历史相关问答
    if relevant_history:
        context_parts.append("\n用户历史相关问答：")
        for role, content in relevant_history[:2]:
            label = "用户问" if role == "user" else "你回答过"
            context_parts.append(f"[{label}] {content[:200]}")

    # 总体情况
    context_parts.append(f"\n用户总提问数：{profile['total_questions']}次")
    if profile["total_questions"] == 0:
        context_parts.append("这是用户第一次提问，请热情友好地引导。")

    return "\n".join(context_parts)

# ========== 页面配置 ==========
st.set_page_config(
    page_title="AI 面试助手 V2",
    page_icon="🎯",
    layout="centered",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "AI 面试助手 V2 · 个性化知识记忆系统\n专为 AI 产品经理 / AI 运营 / Agent / AIGC 方向面试准备而设计。"
    }
)

# ========== Open Graph 分享优化（转发时显示预览卡片） ==========
st.markdown("""
<meta property="og:title" content="🎯 AI 面试助手 V2 - 个性化知识记忆系统">
<meta property="og:description" content="专为 AI 产品经理 / AI 运营 / Agent / AIGC 方向打造的智能面试准备助手。涵盖机器学习、深度学习、LLM、RAG、模型评估等 26+ 知识点，越用越懂你。">
<meta property="og:type" content="website">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="🎯 AI 面试助手 V2 - 个性化知识记忆系统">
<meta name="twitter:description" content="AI 产品经理面试准备助手，涵盖机器学习、LLM、Agent、AIGC 等 26+ 知识点。">
""", unsafe_allow_html=True)

# ========== CSS ==========
st.markdown("""
<style>
    .stApp { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); }
    .main .block-container { padding-top: 1.5rem; padding-bottom: 1.5rem; }
    .header-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem 2rem; border-radius: 16px; margin-bottom: 1rem;
        text-align: center; box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
    }
    .header-container h1 { color: white; font-size: 1.8rem; margin-bottom: 0.3rem; font-weight: 700; }
    .header-container p { color: rgba(255,255,255,0.85); font-size: 0.95rem; margin: 0; }
    .welcome-box {
        background: white; border-radius: 12px; padding: 1rem 1.5rem;
        margin-bottom: 1rem; border-left: 4px solid #667eea;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }
    .welcome-box p { margin: 0.2rem 0; }
    .stChatMessage[data-testid="chat-message-user"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white; border-radius: 18px 18px 4px 18px;
        padding: 12px 16px; margin: 8px 0; max-width: 80%; margin-left: auto;
        box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
    }
    .stChatMessage[data-testid="chat-message-assistant"] {
        background: white; border: 1px solid #e8ecf1;
        border-radius: 18px 18px 18px 4px;
        padding: 12px 16px; margin: 8px 0; max-width: 80%;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    section[data-testid="stSidebar"] { background: white; border-right: 1px solid #e8ecf1; }
    .preset-section { background: white; border-radius: 12px; padding: 0.5rem; margin-bottom: 1rem; border: 1px solid #e8ecf1; }
    .stButton button { border-radius: 8px; font-size: 0.85rem; }
    div[data-testid="stSidebar"] .stButton button { background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
    div[data-testid="stSidebar"] .stButton button:hover { background: #fee2e2; }
    /* ===== 搜索框（放大加粗） ===== */
    .search-container {
        background: white;
        border-radius: 16px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 1.2rem;
        border: 2px solid #e0e4ea;
        box-shadow: 0 4px 20px rgba(102, 126, 234, 0.1);
    }
    .search-container .search-label {
        font-size: 1.1rem;
        font-weight: 700;
        color: #1a1a2e;
        margin-bottom: 0.5rem;
    }
    .search-container .search-label span {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-size: 0.7rem;
        padding: 2px 10px;
        border-radius: 20px;
        margin-left: 8px;
        font-weight: 600;
    }
    .stChatInputContainer {
        border-radius: 14px !important;
        border: 2px solid #667eea !important;
        padding: 6px !important;
        background: white !important;
        box-shadow: 0 2px 12px rgba(102, 126, 234, 0.15) !important;
    }
    .stChatInputContainer:focus-within {
        border-color: #764ba2 !important;
        box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.2) !important;
    }
    .stChatInputContainer input {
        font-size: 1.05rem !important;
        font-weight: 500 !important;
    }
    /* ===== 统计卡片 ===== */
    .stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 0.8rem; margin-bottom: 1rem; }
    .stat-card {
        background: white; border-radius: 12px; padding: 0.8rem 1rem;
        text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        border: 1px solid #e8ecf1;
    }
    .stat-card .num { font-size: 1.6rem; font-weight: 800; color: #667eea; }
    .stat-card .label { font-size: 0.75rem; color: #6b7280; margin-top: 2px; }
    /* ===== 知识进度条 ===== */
    .progress-bar {
        background: #e8ecf1; border-radius: 10px; height: 6px; margin: 6px 0; overflow: hidden;
    }
    .progress-bar .fill {
        background: linear-gradient(90deg, #667eea, #764ba2);
        height: 100%; border-radius: 10px; transition: width 0.5s;
    }
    .topic-tag {
        display: inline-block; background: #f0f2f6; border-radius: 6px;
        padding: 2px 10px; font-size: 0.75rem; margin: 2px 4px 2px 0;
    }
    .topic-tag.learned { background: #e8f5e9; color: #2e7d32; }
    .topic-tag.new { background: #e3f2fd; color: #1565c0; }
    /* ===== 推荐区 ===== */
    .recommend-box {
        background: linear-gradient(135deg, #faf5ff 0%, #f5f3ff 100%);
        border-radius: 12px; padding: 0.8rem 1.2rem; margin-bottom: 1rem;
        border: 1px solid #e8d5f5;
    }
    .recommend-box p { margin: 0.2rem 0; font-size: 0.9rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 0; background: #f0f2f6; border-radius: 8px; padding: 4px; }
    .stTabs [data-baseweb="tab"] { border-radius: 6px; padding: 6px 14px; font-size: 0.8rem; }
    .stTabs [aria-selected="true"] { background: white; }
    hr { margin: 0.8rem 0; border-color: #e8ecf1; }
</style>
""", unsafe_allow_html=True)

# ========== 初始化 session ==========
if "device_id" not in st.session_state:
    st.session_state.device_id = get_device_id()
if "messages" not in st.session_state:
    st.session_state.messages = []
if "preset_clicked" not in st.session_state:
    st.session_state.preset_clicked = None
if "db_loaded" not in st.session_state:
    get_or_create_user(st.session_state.device_id)
    saved = restore_messages(st.session_state.device_id)
    if saved:
        st.session_state.messages = saved
    st.session_state.db_loaded = True

# ========== 设备 ID ==========
device_id = st.session_state.device_id

# ========== 标题 ==========
st.markdown("""
<div class="header-container">
    <h1>🎯 AI 面试助手 V2</h1>
    <p>个性化知识记忆 · 越用越懂你</p>
</div>
""", unsafe_allow_html=True)

# ========== 🔥 搜索框（顶部） ==========
with st.form("search_form", clear_on_submit=True):
    cols = st.columns([8, 1])
    with cols[0]:
        search_query = st.text_input("搜索", placeholder="例如：过拟合和欠拟合有什么区别？怎么评估一个AI产品好不好？", label_visibility="collapsed")
    with cols[1]:
        submitted = st.form_submit_button("🚀 提问", use_container_width=True, type="primary")

if submitted and search_query.strip():
    if not api_key:
        st.error("❌ 未检测到 API Key")
        st.stop()
    process_question(search_query.strip())
    st.rerun()

# ========== 话题预设（搜索框下面） ==========
st.markdown('<div class="preset-section">', unsafe_allow_html=True)
with st.expander("📌 面试话题速查（点击展开）", expanded=True):
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🤖 AI 基础", "📊 模型评估", "🏗️ AI 产品", "🛠️ Agent/AIGC", "📈 AI 运营"])
    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🤖 什么是机器学习？", use_container_width=True, key="pi1"):
                st.session_state.preset_clicked = "用通俗的话解释什么是机器学习，并举一个产品中的例子"
            if st.button("🔍 监督 vs 无监督？", use_container_width=True, key="pi2"):
                st.session_state.preset_clicked = "监督学习和无监督学习的区别是什么？各自用在什么场景？"
        with col2:
            if st.button("⚠️ 过拟合怎么解决？", use_container_width=True, key="pi3"):
                st.session_state.preset_clicked = "什么是过拟合？怎么发现和解决过拟合问题？"
            if st.button("🧠 什么是 LLM？", use_container_width=True, key="pi4"):
                st.session_state.preset_clicked = "什么是大语言模型(LLM)？它和传统机器学习模型有什么区别？"
    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🎯 准确率 vs 召回率", use_container_width=True, key="pi5"):
                st.session_state.preset_clicked = "准确率(Precision)和召回率(Recall)的区别是什么？在什么场景下更关注哪一个？"
            if st.button("📋 混淆矩阵", use_container_width=True, key="pi6"):
                st.session_state.preset_clicked = "什么是混淆矩阵？如何用它计算准确率、精确率、召回率和F1分数？"
        with col2:
            if st.button("📊 F1 分数", use_container_width=True, key="pi7"):
                st.session_state.preset_clicked = "什么是F1分数？为什么要用F1而不是只用准确率？"
            if st.button("📈 AUC-ROC", use_container_width=True, key="pi8"):
                st.session_state.preset_clicked = "什么是AUC-ROC曲线？作为AI产品经理，怎么用它评估模型？"
    with tab3:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 AI 产品设计流程", use_container_width=True, key="pi9"):
                st.session_state.preset_clicked = "AI产品经理的工作流程和传统产品经理有什么不同？"
            if st.button("⚖️ 自研 vs 调 API？", use_container_width=True, key="pi10"):
                st.session_state.preset_clicked = "做AI产品时，怎么决定自研模型还是调用API？各自的优缺点是什么？"
        with col2:
            if st.button("🔧 模型选型因素", use_container_width=True, key="pi11"):
                st.session_state.preset_clicked = "作为AI产品经理，给一个具体场景选择模型时，应该考虑哪些因素？"
            if st.button("📏 AI 产品评估", use_container_width=True, key="pi12"):
                st.session_state.preset_clicked = "怎么评估一个AI产品是否成功？除了模型指标，还要看哪些指标？"
    with tab4:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🤖 什么是 AI Agent？", use_container_width=True, key="pi13"):
                st.session_state.preset_clicked = "什么是AI Agent？它和普通的LLM应用有什么本质区别？"
            if st.button("📚 RAG 是什么？", use_container_width=True, key="pi14"):
                st.session_state.preset_clicked = "什么是RAG（检索增强生成）？它解决了什么问题？"
        with col2:
            if st.button("🎨 什么是 AIGC？", use_container_width=True, key="pi15"):
                st.session_state.preset_clicked = "什么是AIGC？AIGC产品在质量控制方面面临哪些挑战？"
            if st.button("💡 Prompt 工程", use_container_width=True, key="pi16"):
                st.session_state.preset_clicked = "什么是Prompt Engineering？Few-shot、Chain-of-Thought分别是什么？"
    with tab5:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📊 数据指标", use_container_width=True, key="pi17"):
                st.session_state.preset_clicked = "AI产品运营需要关注哪些核心数据指标？怎么用数据驱动产品优化？"
            if st.button("📈 用户增长", use_container_width=True, key="pi18"):
                st.session_state.preset_clicked = "AI产品怎么做用户增长？和传统产品的增长策略有什么不同？"
        with col2:
            if st.button("🎯 内容运营", use_container_width=True, key="pi19"):
                st.session_state.preset_clicked = "AIGC产品的内容运营策略是什么？怎么保证内容质量和合规性？"
            if st.button("🔍 模型监控", use_container_width=True, key="pi20"):
                st.session_state.preset_clicked = "上线后的AI模型怎么监控效果？发现效果下降或者数据漂移怎么办？"
st.markdown('</div>', unsafe_allow_html=True)

# ========== 用户画像（紧凑信息） ==========
profile = get_user_profile(device_id)
total_q = profile["total_questions"]
knowledge = profile["knowledge"]
total_topics = len(TOPICS)
covered = len(knowledge)
progress_pct = int(covered / total_topics * 100) if total_topics else 0

familiar_count = sum(1 for v in knowledge.values() if v["familiarity"] >= 3)

st.markdown(f"""
<div class="stat-grid">
    <div class="stat-card">
        <div class="num">{total_q}</div>
        <div class="label">总提问</div>
    </div>
    <div class="stat-card">
        <div class="num">{covered}</div>
        <div class="label">已学</div>
    </div>
    <div class="stat-card">
        <div class="num">{familiar_count}</div>
        <div class="label">掌握</div>
    </div>
    <div class="stat-card">
        <div class="num">{total_topics - covered}</div>
        <div class="label">待探索</div>
    </div>
</div>
""", unsafe_allow_html=True)

with st.expander("📊 知识进度详情", expanded=False):
    st.markdown(f"""
    <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 4px;">
        <span><b>AI PM 知识点体系</b></span>
        <span>{covered}/{total_topics} · <b>{progress_pct}%</b></span>
    </div>
    <div class="progress-bar">
        <div class="fill" style="width: {progress_pct}%"></div>
    </div>
    <div style="margin-top: 8px;">
        {"".join(f'<span class="topic-tag learned">✅ {t}</span>' for t in list(knowledge.keys())[:8])}
        {f'<span class="topic-tag">+{covered - 8}个</span>' if covered > 8 else ''}
    </div>
    """, unsafe_allow_html=True)

    # 推荐学习
    all_topic_names = list(TOPICS.keys())
    unlearned = [t for t in all_topic_names if t not in knowledge]
    if unlearned:
        random.seed(hash(device_id) % 10000)
        recommendations = random.sample(unlearned, min(3, len(unlearned)))
        st.markdown(f"""
        <div style="margin-top: 12px; padding: 8px 12px; background: #faf5ff; border-radius: 8px; font-size: 0.85rem;">
            <b>💡 推荐学习：</b>{" · ".join(f"<b>{t}</b>" for t in recommendations)}
        </div>
        """, unsafe_allow_html=True)

# ========== 聊天区 ==========
chat_count = len([m for m in st.session_state.messages if m["role"] == "user"])
st.markdown(f"##### 💬 对话记录 · 共 {chat_count} 条提问")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if chat_count == 0:
    st.markdown("""
    <div style="text-align: center; padding: 2rem; color: #9ca3af;">
        <p style="font-size: 2rem; margin: 0;">☝️</p>
        <p>在上方输入问题，或从下方话题速查开始</p>
    </div>
    """, unsafe_allow_html=True)

# ========== 侧边栏：AI 知识体系框架图 ==========
with st.sidebar:
    st.markdown("### 🎯 AI PM 知识体系")
    st.markdown("点击知识点直接提问 ↓")
    st.markdown("---")

    # ===== 知识体系树 =====
    framework = {
        "🤖 机器学习基础": {
            "icon": "🤖",
            "children": {
                "监督学习": "用通俗的话解释监督学习，并举一个产品中的例子",
                "无监督学习": "用通俗的话解释无监督学习，并举一个产品中的例子",
                "强化学习": "用通俗的话解释强化学习，并举一个产品中的例子",
                "过拟合与欠拟合": "什么是过拟合和欠拟合？怎么发现和解决？",
            }
        },
        "📊 模型评估": {
            "icon": "📊",
            "children": {
                "准确率与召回率": "准确率和召回率的区别？什么场景更关注哪一个？",
                "F1 分数": "什么是F1分数？为什么要用F1而不是只用准确率？",
                "混淆矩阵": "什么是混淆矩阵？如何计算各项指标？",
                "AUC-ROC": "什么是AUC-ROC曲线？AI产品经理怎么用它评估模型？",
            }
        },
        "🧠 深度学习": {
            "icon": "🧠",
            "children": {
                "神经网络基础": "用通俗的话解释神经网络是怎么工作的",
                "Transformer": "什么是Transformer？为什么它这么重要？",
                "训练/验证/测试集": "训练集、验证集、测试集的区别和用途是什么？",
            }
        },
        "📚 大语言模型": {
            "icon": "📚",
            "children": {
                "LLM 原理": "什么是大语言模型(LLM)？它和传统ML模型有什么区别？",
                "Prompt 工程": "什么是Prompt Engineering？Few-shot、CoT分别是什么？",
                "RLHF": "什么是RLHF？为什么它对LLM很重要？",
                "幻觉问题": "大模型为什么会有幻觉？怎么缓解？",
            }
        },
        "🛠️ Agent 与 RAG": {
            "icon": "🛠️",
            "children": {
                "AI Agent": "什么是AI Agent？和普通LLM应用有什么本质区别？",
                "Tool Use": "什么是Tool Use/Function Calling？Agent怎么调用工具？",
                "RAG 检索增强": "什么是RAG？它解决了什么问题？",
                "向量数据库": "什么是向量数据库？在RAG中起什么作用？",
            }
        },
        "🏗️ AI 产品经理": {
            "icon": "🏗️",
            "children": {
                "AI 产品设计流程": "AI产品经理的工作流程和传统PM有什么不同？",
                "自研 vs 调 API": "做AI产品时，怎么决定自研还是调API？",
                "模型选型": "给一个场景选模型时，要考虑哪些因素？",
                "AI 产品评估": "怎么评估一个AI产品是否成功？",
            }
        },
        "📈 AI 产品运营": {
            "icon": "📈",
            "children": {
                "数据分析与指标": "AI产品运营需要关注哪些核心数据指标？怎么用数据驱动优化？",
                "用户增长策略": "AI产品怎么做用户增长？和传统产品的增长策略有什么不同？",
                "内容运营": "AIGC产品的内容运营策略是什么？怎么保证内容质量和合规？",
                "模型效果监控": "上线后的AI模型怎么监控效果？发现效果下降怎么办？",
            }
        },
        "🎨 AIGC": {
            "icon": "🎨",
            "children": {
                "AIGC 原理": "什么是AIGC？生成式AI有哪些类型？",
                "内容质量控制": "AIGC产品在质量控制方面面临哪些挑战？",
            }
        },
    }

    for category, cat_info in framework.items():
        with st.expander(category, expanded=False):
            for topic, question in cat_info["children"].items():
                # 智能匹配是否已学
                learned = False
                for k in knowledge:
                    if k in topic or topic[:2] in k:
                        learned = True
                        break
                prefix = "✅ " if learned else "📌 "
                btn_key = f"tree_{category}_{topic}"
                if st.button(f"{prefix}{topic}", use_container_width=True, key=btn_key):
                    st.session_state.preset_clicked = question
                    st.rerun()

    st.markdown("---")
    st.markdown(f"**提问总数：** {total_q}  |  **已学：** {len(knowledge)}/{total_topics}")

    if knowledge:
        st.markdown("**⭐ 掌握度：**")
        sorted_k = sorted(knowledge.items(), key=lambda x: -x[1]["familiarity"])
        for topic, info in sorted_k[:5]:
            stars = "⭐" * info["familiarity"]
            st.caption(f"{topic} {stars}")

    st.markdown("---")
    if st.button("🗑️ 清空数据", use_container_width=True):
        clear_user_data(device_id)
        st.session_state.messages = []
        st.rerun()

# ========== AI 调用 ==========
def call_ai(question, device_id):
    context = build_personalized_context(device_id, question)
    question_topics = extract_topics(question)

    system_prompt = f"""你是一个 AI 面试辅导助手，帮助 AI 产品经理候选人准备面试。

## 个性化上下文
{context}

## 回答要求
1. 根据用户的知识水平调整回答深度——已了解的简略带过，新的概念详细解释
2. 结合产品案例说明
3. 指出面试官想考察什么
4. 如果用户追问，基于之前聊过的内容继续深入
5. 回答要结构化——用分点、小标题让信息清晰"""

    msgs = [{"role": "system", "content": system_prompt}]
    for m in st.session_state.messages[-6:]:  # 最近6条作为上下文
        msgs.append({"role": m["role"], "content": m["content"]})

    response = client.chat.completions.create(model="deepseek-chat", messages=msgs, stream=False)
    return response.choices[0].message.content, question_topics

# ========== 处理输入 ==========
def process_question(question):
    # 展示用户消息
    with st.chat_message("user"):
        st.markdown(question)
    st.session_state.messages.append({"role": "user", "content": question})
    save_chat(device_id, "user", question)

    # 调用 AI
    with st.chat_message("assistant"):
        with st.spinner("🤔 思考中..."):
            try:
                reply, topics = call_ai(question, device_id)
                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
                save_chat(device_id, "assistant", reply, topics)
                if topics:
                    update_knowledge(device_id, topics)
            except Exception as e:
                st.error(f"❌ 出错：{e}")

# 预设按钮
if st.session_state.preset_clicked:
    question = st.session_state.preset_clicked
    st.session_state.preset_clicked = None
    process_question(question)
    st.rerun()
