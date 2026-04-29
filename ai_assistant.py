"""AI 问答助手 - 完整版"""
import os
import httpx
import streamlit as st
from openai import OpenAI

# ========== 绕过系统代理 ==========
for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
    os.environ.pop(key, None)

# ========== 读取 API Key ==========
api_key = os.getenv("DEEPSEEK_API_KEY")
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

# ========== 页面配置 ==========
st.set_page_config(page_title="AI 面试助手", page_icon="🎯", layout="centered")

# ========== 自定义 CSS 美化 ==========
st.markdown("""
<style>
    /* 全局样式 */
    .stApp {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    }
    /* 主容器 */
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 1.5rem;
    }
    /* 标题区 */
    .header-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem 2rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        text-align: center;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
    }
    .header-container h1 {
        color: white;
        font-size: 1.8rem;
        margin-bottom: 0.3rem;
        font-weight: 700;
    }
    .header-container p {
        color: rgba(255,255,255,0.85);
        font-size: 0.95rem;
        margin: 0;
    }
    /* 聊天气泡 - 用户 */
    .stChatMessage[data-testid="chat-message-user"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 18px 18px 4px 18px;
        padding: 12px 16px;
        margin: 8px 0;
        max-width: 80%;
        margin-left: auto;
        box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
    }
    /* 聊天气泡 - AI */
    .stChatMessage[data-testid="chat-message-assistant"] {
        background: white;
        border: 1px solid #e8ecf1;
        border-radius: 18px 18px 18px 4px;
        padding: 12px 16px;
        margin: 8px 0;
        max-width: 80%;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    /* 侧边栏 */
    section[data-testid="stSidebar"] {
        background: white;
        border-right: 1px solid #e8ecf1;
    }
    section[data-testid="stSidebar"] .sidebar-content {
        padding: 1.5rem 1rem;
    }
    /* 话题预设区 */
    .preset-section {
        background: white;
        border-radius: 12px;
        padding: 0.5rem;
        margin-bottom: 1rem;
        border: 1px solid #e8ecf1;
    }
    /* 按钮样式 */
    .stButton button {
        border-radius: 8px;
        font-size: 0.85rem;
        transition: all 0.2s;
    }
    .stButton button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    /* 输入框 */
    .stChatInputContainer {
        border-radius: 12px !important;
        border: 2px solid #e8ecf1 !important;
        padding: 4px !important;
    }
    .stChatInputContainer:focus-within {
        border-color: #667eea !important;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1) !important;
    }
    /* 标签页 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        background: #f0f2f6;
        border-radius: 8px;
        padding: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 6px;
        padding: 6px 14px;
        font-size: 0.8rem;
    }
    .stTabs [aria-selected="true"] {
        background: white;
        box-shadow: 0 2px 6px rgba(0,0,0,0.08);
    }
    /* 滚动条 */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: #c1c9d6; border-radius: 3px; }
    /* 分割线 */
    hr {
        margin: 0.8rem 0;
        border-color: #e8ecf1;
    }
    /* 清空按钮 */
    div[data-testid="stSidebar"] .stButton button {
        background: #fef2f2;
        color: #dc2626;
        border: 1px solid #fecaca;
    }
    div[data-testid="stSidebar"] .stButton button:hover {
        background: #fee2e2;
    }
</style>
""", unsafe_allow_html=True)

# ========== 自定义标题 ==========
st.markdown("""
<div class="header-container">
    <h1>🎯 AI 面试助手</h1>
    <p>AI 产品经理 · Agent · AIGC · 面试准备</p>
</div>
""", unsafe_allow_html=True)

# ========== 侧边栏 ==========
with st.sidebar:
    st.markdown("### ℹ️ 信息")
    st.markdown(f"""
    - **模型：** DeepSeek Chat
    - **状态：** ✅ 已接入
    - **对话数：** {len([m for m in st.session_state.get('messages', []) if m['role'] == 'user'])} 条
    """)
    st.markdown("---")
    if st.button("🗑️ 清空对话", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    st.markdown("---")
    st.markdown("##### 📖 使用提示")
    st.caption("""
    1. 点击话题按钮快速提问
    2. 支持连续追问
    3. 回答含面试考点提示
    """)

# ========== 初始化 ==========
if "messages" not in st.session_state:
    st.session_state.messages = []
if "preset_clicked" not in st.session_state:
    st.session_state.preset_clicked = None

# ========== 话题预设区 ==========
st.markdown('<div class="preset-section">', unsafe_allow_html=True)
with st.expander("📌 面试话题速查（点击展开）", expanded=True):
    tab1, tab2, tab3, tab4 = st.tabs(["🤖 AI 基础", "📊 模型评估", "🏗️ AI 产品", "🛠️ Agent/AIGC"])

    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🤖 什么是机器学习？", use_container_width=True, key="p1"):
                st.session_state.preset_clicked = "用通俗的话解释什么是机器学习，并举一个产品中的例子"
            if st.button("🔍 监督 vs 无监督？", use_container_width=True, key="p2"):
                st.session_state.preset_clicked = "监督学习和无监督学习的区别是什么？各自用在什么场景？"
        with col2:
            if st.button("⚠️ 什么是过拟合？", use_container_width=True, key="p3"):
                st.session_state.preset_clicked = "什么是过拟合？怎么发现和解决过拟合问题？"
            if st.button("🧠 什么是 LLM？", use_container_width=True, key="p4"):
                st.session_state.preset_clicked = "什么是大语言模型(LLM)？它和传统机器学习模型有什么区别？"

    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🎯 准确率 vs 召回率", use_container_width=True, key="p5"):
                st.session_state.preset_clicked = "准确率(Precision)和召回率(Recall)的区别是什么？在什么场景下更关注哪一个？"
            if st.button("📋 混淆矩阵", use_container_width=True, key="p6"):
                st.session_state.preset_clicked = "什么是混淆矩阵？如何用它计算准确率、精确率、召回率和F1分数？"
        with col2:
            if st.button("📊 F1 分数", use_container_width=True, key="p7"):
                st.session_state.preset_clicked = "什么是F1分数？为什么要用F1而不是只用准确率？"
            if st.button("📈 AUC-ROC", use_container_width=True, key="p8"):
                st.session_state.preset_clicked = "什么是AUC-ROC曲线？作为AI产品经理，怎么用它评估模型？"

    with tab3:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 AI 产品设计流程", use_container_width=True, key="p9"):
                st.session_state.preset_clicked = "AI产品经理的工作流程和传统产品经理有什么不同？从需求到上线需要关注哪些环节？"
            if st.button("⚖️ 自研 vs 调 API？", use_container_width=True, key="p10"):
                st.session_state.preset_clicked = "做AI产品时，怎么决定自研模型还是调用API？各自的优缺点是什么？"
        with col2:
            if st.button("🔧 模型选型", use_container_width=True, key="p11"):
                st.session_state.preset_clicked = "作为AI产品经理，给一个具体场景选择模型时，应该考虑哪些因素？"
            if st.button("📏 AI 产品评估", use_container_width=True, key="p12"):
                st.session_state.preset_clicked = "怎么评估一个AI产品是否成功？除了模型指标，还要看哪些指标？"

    with tab4:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🤖 什么是 AI Agent？", use_container_width=True, key="p13"):
                st.session_state.preset_clicked = "什么是AI Agent？它和普通的LLM应用有什么本质区别？"
            if st.button("📚 RAG 是什么？", use_container_width=True, key="p14"):
                st.session_state.preset_clicked = "什么是RAG（检索增强生成）？它解决了什么问题？"
        with col2:
            if st.button("🎨 什么是 AIGC？", use_container_width=True, key="p15"):
                st.session_state.preset_clicked = "什么是AIGC？AIGC产品在质量控制方面面临哪些挑战？"
            if st.button("💡 Prompt 工程", use_container_width=True, key="p16"):
                st.session_state.preset_clicked = "什么是Prompt Engineering？Few-shot、Chain-of-Thought分别是什么？"
st.markdown('</div>', unsafe_allow_html=True)

# ========== 聊天区标题 ==========
chat_count = len([m for m in st.session_state.messages if m['role'] == 'user'])
st.markdown(f"##### 💬 对话 · 共 {chat_count} 条提问")

# ========== 显示聊天历史 ==========
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ========== 处理预设按钮点击 ==========
def call_ai(messages, system_prompt):
    msgs = [{"role": "system", "content": system_prompt}]
    for m in messages:
        msgs.append({"role": m["role"], "content": m["content"]})
    response = client.chat.completions.create(model="deepseek-chat", messages=msgs, stream=False)
    return response.choices[0].message.content

if st.session_state.preset_clicked:
    question = st.session_state.preset_clicked
    st.session_state.preset_clicked = None

    with st.chat_message("user"):
        st.markdown(question)
    st.session_state.messages.append({"role": "user", "content": question})

    with st.chat_message("assistant"):
        with st.spinner("🤔 思考中..."):
            try:
                reply = call_ai(
                    st.session_state.messages,
                    "你是一个 AI 面试辅导助手，帮助AI产品经理候选人准备面试。回答要：1）简洁有结构 2）结合产品案例 3）指出面试官想考察什么"
                )
                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
            except Exception as e:
                st.error(f"❌ 出错：{e}")
    st.rerun()

# ========== 输入框 ==========
if prompt := st.chat_input("输入你的问题..."):
    if not api_key:
        st.error("❌ 未检测到 API Key")
        st.stop()

    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        with st.spinner("🤔 思考中..."):
            try:
                reply = call_ai(
                    st.session_state.messages,
                    "你是一个 AI 学习助手，用通俗易懂的方式回答问题。"
                )
                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
            except Exception as e:
                st.error(f"❌ 出错：{e}")
