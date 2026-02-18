import streamlit as st
import google.generativeai as genai
import tempfile
import os
import subprocess
import time
from pathlib import Path

# --- 1. 页面配置 ---
st.set_page_config(
    page_title="LingOrm · The Secret Voice",
    page_icon="🦋",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- 2. CSS: 诺丁山·极简高端风格 ---
st.markdown("""
<style>
    /* 引入 Google Fonts: Inter (现代感) + Playfair Display (电影感) */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=Playfair+Display:ital,wght@1,400&display=swap');
    
    /* 全局背景 */
    .stApp {
        background-color: #F8F9FA; /* 极简灰白底 */
        font-family: 'Inter', sans-serif;
        color: #1F2937;
    }

    /* 隐藏 Streamlit 原生杂项 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* 顶部 Title 设计 */
    .hero-container {
        text-align: center;
        padding: 60px 0 30px 0;
    }
    .hero-title {
        font-size: 2.8rem;
        font-weight: 700;
        /* 渐变紫：LingOrm 品牌色 */
        background: -webkit-linear-gradient(45deg, #7C3AED, #C084FC);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 8px;
        letter-spacing: -0.03em;
    }
    .hero-quote {
        font-family: 'Playfair Display', serif;
        font-style: italic;
        font-size: 1.3rem;
        color: #6B7280;
        margin-top: 10px;
    }

    /* 卡片容器：悬浮感 */
    .clean-card {
        background: white;
        padding: 40px;
        border-radius: 24px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.01);
        border: 1px solid #F3F4F6;
        margin-bottom: 24px;
    }

    /* 按钮美化 */
    .stButton>button {
        background: linear-gradient(135deg, #7C3AED 0%, #6D28D9 100%);
        color: white;
        border-radius: 12px;
        border: none;
        height: 55px;
        font-size: 16px;
        font-weight: 600;
        box-shadow: 0 4px 14px 0 rgba(124, 58, 237, 0.3);
        transition: all 0.2s ease-in-out;
        width: 100%;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(124, 58, 237, 0.4);
    }

    /* 上传框去边框化 */
    [data-testid='stFileUploader'] {
        border: 2px dashed #E5E7EB;
        border-radius: 16px;
        padding: 30px;
        background-color: #F9FAFB;
        transition: border-color 0.3s;
    }
    [data-testid='stFileUploader']:hover {
        border-color: #7C3AED;
    }

    /* 输入框样式 */
    .stTextInput>div>div>input {
        background-color: #ffffff;
        border: 1px solid #E5E7EB;
        color: #374151;
        border-radius: 10px;
        padding: 10px;
    }
    
    /* 进度条紫色 */
    .stProgress > div > div > div > div {
        background-color: #7C3AED;
    }

    /* 文本域样式 */
    .stTextArea textarea {
        background-color: #F9FAFB;
        border: 1px solid #E5E7EB;
        border-radius: 12px;
        font-family: monospace;
    }

</style>
""", unsafe_allow_html=True)

# --- 3. 核心逻辑 (Flash 极速版) ---

def get_gemini_response(file, prompt, api_key):
    """
    使用 Flash 模型：速度快、不报错、适合字幕
    """
    genai.configure(api_key=api_key)
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content([file, prompt], request_options={"timeout": 600})
        return response
    except Exception as e:
        raise e

# --- 4. 自动获取 API Key ---
# 优先从 Secrets 获取 (如果不设置，则 API_KEY 为 None)
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    API_KEY = None

# --- 5. 界面构建 ---

# 头部 Header
st.markdown("""
<div class="hero-container">
    <div class="hero-title">LingOrm AI Studio</div>
    <div class="hero-quote">“Can you stay forever?”</div>
</div>
""", unsafe_allow_html=True)

# 主卡片容器 (包含上传和设置)
with st.container():
    st.markdown('<div class="clean-card">', unsafe_allow_html=True)
    
    # 1. 上传区
    st.markdown("##### 1. Upload Video / Audio")
    uploaded_file = st.file_uploader("", type=["mp4", "mov", "mkv", "mp3", "wav"], label_visibility="collapsed")
    
    st.markdown("---")
    
    # 2. 设置区 (折叠在主界面下方，不占地方)
    with st.expander("⚙️ Advanced Settings (Role Names & Filters)", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            role_1 = st.text_input("Role A (Thai)", value="LingLing")
            role_1_cn = st.text_input("Role A (CN)", value="Ling姐")
        with col2:
            role_2 = st.text_input("Role B (Thai)", value="Orm")
            role_2_cn = st.text_input("Role B (CN)", value="Orm")
            
        blacklist_str = st.text_input("Blacklist (Words to ignore)", value="迪哥,妈妈达,迪桑达,条纹,时髦,鲁尼特,字幕组")
        blacklist = [x.strip() for x in blacklist_str.split(",") if x.strip()]

    # 3. 按钮区
    st.write("")
    if uploaded_file:
        generate_btn = st.button("✨ Generate Magic (开始生成)")
    else:
        st.info("👆 Please upload a file to start.")
        generate_btn = False

    st.markdown('</div>', unsafe_allow_html=True)

# --- 6. 执行逻辑 (完整修复版) ---
if generate_btn and uploaded_file:
    # 检查 Key 是否存在
    if not API_KEY:
        st.error("🔒 错误：未配置 API Key。请在 Streamlit Secrets 中配置 GOOGLE_API_KEY。")
    else:
        # 状态显示
        status_msg = st.empty()
        progress_bar = st.progress(0)
        
        # 临时文件处理
        tmp_video_path = None
        audio_path = None
        
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp_file:
                tmp_file.write(uploaded_file.read())
                tmp_video_path = tmp_file.name
            
            # 步骤 1: 提取音频
            status_msg.markdown("**🎧 Extracting Audio Stream...**")
            progress_bar.progress(20)
            
            audio_path = tmp_video_path + ".mp3" # 简单命名确保兼容
            
            # 使用 ffmpeg 提取音频 (确保环境中有安装 ffmpeg)
            cmd = [
                "ffmpeg", "-i", tmp_video_path, 
                "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k", 
                "-y", audio_path
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # 步骤 2: 上传到 Gemini
            status_msg.markdown("**☁️ Syncing with Gemini Cloud...**")
            progress_bar.progress(40)
            
            genai.configure(api_key=API_KEY)
            video_file = genai.upload_file(path=audio_path)
            
            # 等待处理完成 (必须步骤)
            while video_file.state.name == "PROCESSING":
                time.sleep(2)
                video_file = genai.get_file(video_file.name)
            
            if video_file.state.name == "FAILED":
                raise Exception("Google Audio Processing Failed")

            # 步骤 3: 构造 Prompt 并生成 (修复了这里的 SyntaxError)
            status_msg.markdown("**💜 Analyzing & Translating (The Secret Voice)...**")
            progress_bar.progress(60)
            
            prompt = f"""
            Task: Transcribe and translate the audio to Simplified Chinese Subtitles (SRT format).
            Context: A sweet conversation between two Thai girls, {role_1} and {role_2}.
            
            Rules:
            1. Speaker Identification: Mark "{role_1_cn}:" or "{role_2_cn}:" at the start of dialogue.
            2. Terminology: "Phi Ling" -> "{role_1_cn}", "Nong Orm" -> "{role_2_cn}".
            3. Tone: Casual, sweet, romantic style.
            4. Filter: Do not translate or transcribe words listed here: {', '.join(blacklist)}.
            5. Format: Output ONLY valid SRT format. No markdown code blocks, no intro text.
            """
            
            # 调用 AI
            response = get_gemini_response(video_file, prompt, API_KEY)
            subtitle_text = response.text
            
            # 清理云端文件
            try:
                video_file.delete()
            except:
                pass

            # 步骤 4: 结果展示
            progress_bar.progress(100)
            status_msg.success("✨ Magic Happened! Subtitle Generated.")
            
            st.markdown('<div class="clean-card">', unsafe_allow_html=True)
            st.markdown("##### 📝 Subtitle Preview")
            
            # 文本展示
            st.text_area("SRT Content", subtitle_text, height=300, label_visibility="collapsed")
            
            # 下载按钮
            col_d1, col_d2 = st.columns([1, 2])
            with col_d1:
                st.download_button(
                    label="📥 Download .SRT",
                    data=subtitle_text,
                    file_name=f"{Path(uploaded_file.name).stem}_LingOrm.srt",
                    mime="text/plain"
                )
            st.markdown('</div>', unsafe_allow_html=True)

        except subprocess.CalledProcessError:
            st.error("❌ FFmpeg Error: Failed to extract audio. Please check if ffmpeg is installed.")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
        
        finally:
            # 清理本地临时文件
            if tmp_video_path and os.path.exists(tmp_video_path):
                os.remove(tmp_video_path)
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)
