import streamlit as st
import google.generativeai as genai
import tempfile
import os
import subprocess
import time
from pathlib import Path

# --- 1. 页面配置 (必须在第一行) ---
st.set_page_config(
    page_title="LingOrm · The Secret Voice",
    page_icon="💜",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- 2. 🎨 高端 UI 注入 (CSS 魔法) ---
st.markdown("""
<style>
    /* 引入 Kanit 字体 (泰剧御用字体) */
    @import url('https://fonts.googleapis.com/css2?family=Kanit:wght@200;300;400;500;600&display=swap');
    
    /* 全局重置 */
    html, body, [class*="css"] {
        font-family: 'Kanit', sans-serif;
        color: #2D2D2D;
    }

    /* 🟣 背景：梦幻极光紫渐变 */
    .stApp {
        background: radial-gradient(circle at 10% 20%, rgb(239, 235, 255) 0%, rgb(235, 225, 255) 90%);
        background-attachment: fixed;
    }

    /* ✨ 标题：渐变流光字体 */
    .lingorm-title {
        background: linear-gradient(45deg, #6a11cb 0%, #2575fc 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3.5rem;
        font-weight: 700;
        text-align: center;
        letter-spacing: -2px;
        margin-bottom: 0.5rem;
    }
    
    .lingorm-subtitle {
        text-align: center;
        color: #888;
        font-weight: 300;
        letter-spacing: 1px;
        margin-bottom: 2rem;
        font-size: 1.1rem;
    }

    /* 🌫️ 毛玻璃卡片 (Glassmorphism) */
    .glass-card {
        background: rgba(255, 255, 255, 0.65);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border-radius: 20px;
        border: 1px solid rgba(255, 255, 255, 0.5);
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.07);
        padding: 30px;
        margin-bottom: 25px;
    }

    /* 🟣 按钮：LingOrm 专属渐变紫 */
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 15px;
        height: 55px;
        font-size: 18px;
        font-weight: 500;
        width: 100%;
        transition: all 0.4s ease;
        box-shadow: 0 4px 15px rgba(118, 75, 162, 0.3);
        letter-spacing: 0.5px;
    }

    .stButton>button:hover {
        transform: translateY(-3px) scale(1.01);
        box-shadow: 0 10px 25px rgba(118, 75, 162, 0.5);
        background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
    }

    /* 输入框美化 */
    .stTextInput>div>div>input {
        border-radius: 12px;
        border: 1px solid #E0E0E0;
        background-color: rgba(255,255,255,0.8);
        height: 45px;
    }
    .stTextInput>div>div>input:focus {
        border-color: #764ba2;
        box-shadow: 0 0 0 2px rgba(118, 75, 162, 0.2);
    }

    /* 进度条紫色 */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #667eea, #764ba2);
    }

    /* 隐藏杂项 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

</style>
""", unsafe_allow_html=True)

# --- 3. 逻辑核心 (保持最强双保险) ---

def get_gemini_response(file, prompt):
    """智能模型调用：Pro 优先，Flash 兜底"""
    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        response = model.generate_content([file, prompt], request_options={"timeout": 600})
        return response
    except Exception:
        st.toast("⚠️ Pro 线路繁忙，正在切换至极速通道...", icon="🚀")
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content([file, prompt], request_options={"timeout": 600})
        return response

# --- 4. 侧边栏 (极简设计) ---
with st.sidebar:
    st.markdown("## ⚙️ Setting")
    api_key = st.text_input("Google API Key", type="password")
    
    st.markdown("---")
    st.markdown("### 🦋 Characters")
    col1, col2 = st.columns(2)
    with col1:
        role_1 = st.text_input("Role A", value="LingLing")
        role_1_cn = st.text_input("CN A", value="Ling姐")
    with col2:
        role_2 = st.text_input("Role B", value="Orm")
        role_2_cn = st.text_input("CN B", value="Orm")
        
    st.markdown("### 🚫 Blacklist")
    blacklist_str = st.text_area("", value="迪哥,妈妈达,迪桑达,条纹,时髦,鲁尼特", height=80)
    blacklist = [x.strip() for x in blacklist_str.split(",") if x.strip()]

# --- 5. 主界面布局 ---

# 头部 Logo 与 标题
st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
st.markdown("<h1 class='lingorm-title'>LingOrm AI Subtitles</h1>", unsafe_allow_html=True)
st.markdown("<p class='lingorm-subtitle'>Unlock the Secret of Their Voices · 我们的秘密</p>", unsafe_allow_html=True)

# 毛玻璃容器 1: 上传区
with st.container():
    st.markdown("""
    <div class='glass-card'>
        <h4 style='color:#555; margin-bottom:15px;'>📂 Upload Video / Audio</h4>
    </div>
    """, unsafe_allow_html=True)
    # Streamlit 的组件无法直接放入 HTML div 中，利用视觉欺骗，把uploader紧贴在上面的div下
    uploaded_file = st.file_uploader("", type=["mp4", "mov", "mkv", "mp3", "wav"], label_visibility="collapsed")

if uploaded_file:
    # 视频预览区
    with st.expander("📹 Preview Video (点击展开)", expanded=False):
        st.video(uploaded_file)
    
    st.write("") 

    # 按钮区
    if st.button("🔮 生成字幕 (Generate Magic)"):
        if not api_key:
            st.error("🔒 Please enter your API Key in the sidebar.")
        else:
            # 进度显示区
            status_container = st.empty()
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp_file:
                tmp_file.write(uploaded_file.read())
                tmp_video_path = tmp_file.name
            
            audio_path = None
            
            try:
                # 步骤 1
                status_container.info("🎧 Extracting Audio... (正在提取纯净人声)")
                audio_path = tmp_video_path.replace(Path(tmp_video_path).suffix, ".mp3")
                cmd = ["ffmpeg", "-i", tmp_video_path, "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", "-y", audio_path]
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                # 步骤 2
                status_container.info("☁️ Uploading to Gemini... (正在连接云端大脑)")
                genai.configure(api_key=api_key)
                video_file = genai.upload_file(path=audio_path)
                
                while video_file.state.name == "PROCESSING":
                    time.sleep(2)
                    video_file = genai.get_file(video_file.name)
                
                if video_file.state.name == "FAILED": raise Exception("Audio Processing Failed")

                # 步骤 3
                status_container.info("💜 AI Listening & Translating... (正在嗑糖并翻译中)")
                
                prompt = f"""
                你是一个精通泰语的字幕组翻译。请处理这段音频。
                【角色】A: {role_1}({role_1_cn}), B: {role_2}({role_2_cn})。Phi Ling译为{role_1_cn}。
                【要求】输出SRT格式。口语化甜美风。多人对话在文本前加名字。
                【过滤】忽略BGM、噪音、幻觉词({",".join(blacklist)})。
                """
                
                response = get_gemini_response(video_file, prompt)
                srt_content = response.text.replace("```srt", "").replace("```", "").strip()

                # 完成状态
                status_container.success("✨ Completed! The Secret is Revealed.")
                st.balloons()

                # 毛玻璃容器 2: 结果展示
                st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
                st.text_area("SRT Result", srt_content, height=300, label_visibility="collapsed")
                st.markdown("</div>", unsafe_allow_html=True)

                col1, col2 = st.columns([1,1])
                with col1:
                    st.download_button(
                        label="📥 Download .SRT",
                        data=srt_content,
                        file_name=f"{Path(uploaded_file.name).stem}_LingOrm.srt",
                        mime="text/plain"
                    )

            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                if audio_path and os.path.exists(audio_path): os.remove(audio_path)
                if os.path.exists(tmp_video_path): os.remove(tmp_video_path)

# 页脚
st.markdown("""
<div style='text-align: center; margin-top: 50px; opacity: 0.6;'>
    <p style='font-size: 0.8rem;'>Made with 💜 for 🦋 & 🐶</p>
</div>
""", unsafe_allow_html=True)
