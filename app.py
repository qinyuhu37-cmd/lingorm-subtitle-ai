import streamlit as st
import google.generativeai as genai
import tempfile
import os
import subprocess
import time
from pathlib import Path

# --- 1. 页面配置 ---
st.set_page_config(
    page_title="LingOrm AI Subtitles",
    page_icon="🦋",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- 2. CSS: 极简主义高端设计 ---
st.markdown("""
<style>
    /* 引入 Inter 字体，现代 App 标配 */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&family=Playfair+Display:ital,wght@1,400&display=swap');
    
    /* 全局背景：极其干净的灰白 */
    .stApp {
        background-color: #F8F9FA;
        font-family: 'Inter', sans-serif;
        color: #1F2937;
    }

    /* 隐藏 Streamlit 默认头部和菜单 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* 标题区设计 */
    .hero-container {
        text-align: center;
        padding: 40px 0 20px 0;
    }
    .hero-title {
        font-size: 2.5rem;
        font-weight: 700;
        background: -webkit-linear-gradient(45deg, #6D28D9, #A855F7);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 10px;
        letter-spacing: -0.02em;
    }
    .hero-quote {
        font-family: 'Playfair Display', serif; /* 衬线体，致敬电影感 */
        font-style: italic;
        font-size: 1.2rem;
        color: #6B7280;
        margin-top: 5px;
    }

    /* 卡片容器：苹果风的阴影和圆角 */
    .clean-card {
        background: white;
        padding: 30px;
        border-radius: 16px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        border: 1px solid #E5E7EB;
        margin-bottom: 24px;
    }

    /* 按钮：LingOrm 品牌色 */
    .stButton>button {
        background-color: #7C3AED;
        color: white;
        border-radius: 10px;
        border: none;
        height: 48px;
        font-weight: 600;
        box-shadow: 0 4px 12px rgba(124, 58, 237, 0.2);
        transition: all 0.2s;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #6D28D9;
        transform: translateY(-1px);
        box-shadow: 0 6px 16px rgba(124, 58, 237, 0.3);
    }
    .stButton>button:active {
        transform: translateY(0px);
    }

    /* 输入框样式 */
    .stTextInput>div>div>input {
        background-color: #F9FAFB;
        border: 1px solid #E5E7EB;
        color: #374151;
        border-radius: 8px;
    }
    
    /* 上传框去边框化 */
    [data-testid='stFileUploader'] {
        border: 1px dashed #D1D5DB;
        border-radius: 12px;
        padding: 20px;
        background-color: white;
    }

    /* 进度条 */
    .stProgress > div > div > div > div {
        background-color: #7C3AED;
    }

</style>
""", unsafe_allow_html=True)

# --- 3. 逻辑核心 (使用 Secrets & Flash) ---

def get_gemini_response(file, prompt, api_key):
    """优先使用 Flash，不再尝试 Pro 以避免繁忙"""
    genai.configure(api_key=api_key)
    try:
        # 使用 Flash 1.5，这是目前最快最稳的模型
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content([file, prompt], request_options={"timeout": 600})
        return response
    except Exception as e:
        raise e

# --- 4. 获取 API Key (安全模式) ---
# 优先从 Secrets 获取，如果本地没有配置 Secrets，则尝试从环境变量或留空
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    # 如果没配置 Secrets (比如在本地测试)，为了不报错，给个空值或者提示
    API_KEY = None

# --- 5. 界面构建 ---

# Header Section
st.markdown("""
<div class="hero-container">
    <div class="hero-title">LingOrm AI Studio</div>
    <div class="hero-quote">“Can you stay forever?”</div>
</div>
""", unsafe_allow_html=True)

# Main Card
with st.container():
    st.markdown('<div class="clean-card">', unsafe_allow_html=True)
    
    # 1. File Upload
    uploaded_file = st.file_uploader("Upload Video / Audio (MP4, MOV, MP3)", type=["mp4", "mov", "mkv", "mp3", "wav"])
    
    # 2. Advanced Settings (Collapsed by default)
    with st.expander("⚙️ Advanced Settings (Role Names & Filter)", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            role_1 = st.text_input("Role A (Thai)", value="LingLing")
            role_1_cn = st.text_input("Role A (CN)", value="Ling姐")
        with col2:
            role_2 = st.text_input("Role B (Thai)", value="Orm")
            role_2_cn = st.text_input("Role B (CN)", value="Orm")
            
        blacklist_str = st.text_input("Blacklist (Ignore Words)", value="迪哥,妈妈达,迪桑达,条纹,时髦,鲁尼特,字幕组")
        blacklist = [x.strip() for x in blacklist_str.split(",") if x.strip()]

    # 3. Action Button
    st.write("") # Spacer
    if uploaded_file:
        generate_btn = st.button("✨ Generate Subtitles")
    else:
        st.info("👆 Please upload a file to start.")
        generate_btn = False

    st.markdown('</div>', unsafe_allow_html=True)

# Logic Execution
if generate_btn and uploaded_file:
    if not API_KEY:
        st.error("🔒 Server Configuration Error: API Key not found. Please configure Secrets.")
    else:
        # Status Container
        status_card = st.empty()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp_file:
            tmp_file.write(uploaded_file.read())
            tmp_video_path = tmp_file.name
        
        audio_path = None
        
        try:
            # Step 1: Extract
            status_card.info("🎧 Processing Audio Stream...")
            audio_path = tmp_video_path.replace(Path(tmp_video_path).suffix, ".mp3")
            
            # FFmpeg (Quiet mode)
            cmd = ["ffmpeg", "-i", tmp_video_path, "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k", "-y", audio_path]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Step 2: Upload
            status_card.info("☁️ Syncing with Gemini Cloud...")
            genai.configure(api_key=API_KEY)
            video_file = genai.upload_file(path=audio_path)
            
            # Wait for processing
            while video_file.state.name == "PROCESSING":
                time.sleep(1)
                video_file = genai.get_file(video_file.name)
            
            if video_file.state.name == "FAILED": raise Exception("Google Audio Processing Failed")

            # Step 3: Generate
            status_card.info("💜 Analyzing & Translating (The Secret Voice)...")
            
            prompt = f"""
            Task: Transcribe and translate the audio to Simplified Chinese Subtitles (SRT format).
            Context: A sweet conversation between two Thai girls, {role_1} and {role_2}.
            
            Rules:
            1. Speaker Identification: Mark "{role_1_cn}:" or "{role_2_cn}:" at the start of dialogue.
            2. Terminology: "Phi Ling" -> "{role_1_cn}".
            3. Tone: Casual, sweet, close relationship (CP fans

