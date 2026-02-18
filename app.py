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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=Playfair+Display:ital,wght@1,400&display=swap');
    
    .stApp { background-color: #F8F9FA; font-family: 'Inter', sans-serif; color: #1F2937; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}

    .hero-container { text-align: center; padding: 60px 0 30px 0; }
    .hero-title {
        font-size: 2.8rem; font-weight: 700;
        background: -webkit-linear-gradient(45deg, #7C3AED, #C084FC);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 8px; letter-spacing: -0.03em;
    }
    .hero-quote { font-family: 'Playfair Display', serif; font-style: italic; font-size: 1.3rem; color: #6B7280; margin-top: 10px; }

    .clean-card {
        background: white; padding: 40px; border-radius: 24px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.01);
        border: 1px solid #F3F4F6; margin-bottom: 24px;
    }

    .stButton>button {
        background: linear-gradient(135deg, #7C3AED 0%, #6D28D9 100%);
        color: white; border-radius: 12px; border: none; height: 55px;
        font-size: 16px; font-weight: 600; box-shadow: 0 4px 14px 0 rgba(124, 58, 237, 0.3);
        transition: all 0.2s ease-in-out; width: 100%;
    }
    .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(124, 58, 237, 0.4); }

    [data-testid='stFileUploader'] { border: 2px dashed #E5E7EB; border-radius: 16px; padding: 30px; background-color: #F9FAFB; transition: border-color 0.3s; }
    [data-testid='stFileUploader']:hover { border-color: #7C3AED; }

    .stTextInput>div>div>input { background-color: #ffffff; border: 1px solid #E5E7EB; color: #374151; border-radius: 10px; padding: 10px; }
    .stProgress > div > div > div > div { background-color: #7C3AED; }
    .stTextArea textarea { background-color: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 12px; font-family: monospace; }
</style>
""", unsafe_allow_html=True)

# --- 3. 核心逻辑：强制使用 Flash + 自动重试 ---

def generate_with_retry(file_obj, prompt, api_key):
    """
    稳健的生成函数：
    1. 强制使用 gemini-1.5-flash (免费层额度最高)
    2. 如果遇到 429 错误，自动等待并重试
    """
    genai.configure(api_key=api_key)
    
    # 强制指定模型列表，不再动态探测
    # 优先级：Flash (标准) -> Flash-001 (备用) -> Flash-8b (轻量)
    safe_models = ["gemini-1.5-flash", "gemini-1.5-flash-001", "gemini-1.5-flash-8b"]
    
    last_exception = None

    for model_name in safe_models:
        # 重试机制：每个模型尝试 2 次
        for attempt in range(2):
            try:
                # st.toast(f"Trying {model_name} (Attempt {attempt+1})...", icon="🤖")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content([file_obj, prompt], request_options={"timeout": 600})
                return response.text, model_name
                
            except Exception as e:
                error_str = str(e)
                last_exception = e
                
                # 如果是 429 (Too Many Requests) 或 Quota Exceeded
                if "429" in error_str or "quota" in error_str.lower():
                    wait_time = 5 * (attempt + 1) # 第一次等5秒，第二次等10秒
                    st.warning(f"⚠️ High traffic (429). Cooling down for {wait_time}s...")
                    time.sleep(wait_time)
                    continue # 重试当前模型
                
                # 如果是 404 (模型未找到)，直接跳出当前循环，尝试下一个模型
                if "404" in error_str:
                    break 
                
                # 其他错误，记录并继续
                print(f"Error with {model_name}: {e}")

    # 如果所有尝试都失败
    raise last_exception

# --- 4. 获取 API Key ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    API_KEY = None

# --- 5. 界面构建 ---
st.markdown("""
<div class="hero-container">
    <div class="hero-title">LingOrm AI Studio</div>
    <div class="hero-quote">“Can you stay forever?”</div>
</div>
""", unsafe_allow_html=True)

with st.container():
    st.markdown('<div class="clean-card">', unsafe_allow_html=True)
    st.markdown("##### 1. Upload Video / Audio")
    uploaded_file = st.file_uploader("", type=["mp4", "mov", "mkv", "mp3", "wav"], label_visibility="collapsed")
    
    st.markdown("---")
    
    with st.expander("⚙️ Advanced Settings (Role Names & Filters)", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            role_1 = st.text_input("Role A (Thai)", value="LingLing")
            role_1_cn = st.text_input("Role A (CN)", value="Ling姐")
        with col2:
            role_2 = st.text_input("Role B (Thai)", value="Orm")
            role_2_cn = st.text_input("Role B (CN)", value="Orm")
        blacklist_str = st.text_input("Blacklist", value="迪哥,妈妈达,迪桑达,条纹,时髦,鲁尼特,字幕组")
        blacklist = [x.strip() for x in blacklist_str.split(",") if x.strip()]

    st.write("")
    if uploaded_file:
        generate_btn = st.button("✨ Generate Magic (开始生成)")
    else:
        st.info("👆 Please upload a file to start.")
        generate_btn = False

    st.markdown('</div>', unsafe_allow_html=True)

# --- 6. 执行逻辑 ---
if generate_btn and uploaded_file:
    if not API_KEY:
        st.error("🔒 Error: No API Key found in Secrets.")
    else:
        status_msg = st.empty()
        progress_bar = st.progress(0)
        tmp_video_path = None
        audio_path = None
        
        try:
            # 1. 处理文件
            status_msg.markdown("**📂 Processing File...**")
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp_file:
                tmp_file.write(uploaded_file.read())
                tmp_video_path = tmp_file.name
            
            # 2. 提取音频
            status_msg.markdown("**🎧 Extracting Audio Stream...**")
            progress_bar.progress(20)
            audio_path = tmp_video_path + ".mp3"
            
            cmd = ["ffmpeg", "-i", tmp_video_path, "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k", "-y", audio_path]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # 3. 上传到云端
            status_msg.markdown("**☁️ Syncing with Gemini Cloud...**")
            progress_bar.progress(40)
            genai.configure(api_key=API_KEY)
            video_file = genai.upload_file(path=audio_path)
            
            # 等待文件激活
            while video_file.state.name == "PROCESSING":
                time.sleep(2)
                video_file = genai.get_file(video_file.name)
            
            if video_file.state.name == "FAILED": raise Exception("Audio Processing Failed")

            # 4. 生成字幕 (调用新写的重试函数)
            status_msg.markdown(f"**💜 Analyzing & Translating...**")
            progress_bar.progress(60)
            
            prompt = f"""
            Task: Transcribe and translate the audio to Simplified Chinese Subtitles (SRT format).
            Context: A conversation between {role_1} and {role_2}.
            Rules:
            1. Mark "{role_1_cn}:" or "{role_2_cn}:" at dialogue start.
            2. "Phi Ling" -> "{role_1_cn}", "Nong Orm" -> "{role_2_cn}".
            3. Tone: Casual, sweet, romantic.
            4. Filter out: {', '.join(blacklist)}.
            5. Output ONLY valid SRT format. No Markdown blocks.
            """
            
            # 这里调用带重试的函数
            subtitle_text, used_model = generate_with_retry(video_file, prompt, API_KEY)
            
            # 清理云端文件
            try: video_file.delete()
            except: pass

            # 5. 完成
            progress_bar.progress(100)
            status_msg.success(f"✨ Magic Happened! (Used model: {used_model})")
            
            st.markdown('<div class="clean-card">', unsafe_allow_html=True)
            st.markdown("##### 📝 Subtitle Preview")
            st.text_area("SRT Content", subtitle_text, height=300, label_visibility="collapsed")
            col_d1, col_d2 = st.columns([1, 2])
            with col_d1:
                st.download_button("📥 Download .SRT", subtitle_text, f"{Path(uploaded_file.name).stem}_LingOrm.srt", "text/plain")
            st.markdown('</div>', unsafe_allow_html=True)

        except subprocess.CalledProcessError:
            st.error("❌ FFmpeg Error: Please verify ffmpeg is installed.")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            st.info("💡 Tip: If you see '429' or 'Quota', the API is busy. Wait 1 min and try again.")
        
        finally:
            if tmp_video_path and os.path.exists(tmp_video_path): os.remove(tmp_video_path)
            if audio_path and os.path.exists(audio_path): os.remove(audio_path)
