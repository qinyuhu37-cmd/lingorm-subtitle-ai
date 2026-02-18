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

# --- 3. 核心逻辑：智能模型匹配 (彻底解决 404 和 429) ---

def get_valid_flash_model(api_key):
    """
    1. 获取当前 Key 能用的所有模型。
    2. 只筛选出 'flash' 系列 (速度快、配额高)。
    3. 排除掉 '8b' 这种不稳定版本 (除非只有它)。
    """
    genai.configure(api_key=api_key)
    try:
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        
        # 筛选逻辑：必须包含 flash，且优先选择 1.5-flash
        flash_models = [m for m in available_models if "flash" in m]
        
        # 如果找不到 flash，才退而求其次找 pro
        if not flash_models:
            pro_models = [m for m in available_models if "pro" in m]
            if pro_models:
                return pro_models[0] # 返回第一个能用的 pro
            else:
                return "gemini-1.5-flash" # 最后的保底，虽然可能不存在
        
        # 在 Flash 模型中，优先找标准版，排除 experimental 或 8b
        # 排序：让名字短的排前面 (gemini-1.5-flash 优于 gemini-1.5-flash-001)
        flash_models.sort(key=len)
        
        return flash_models[0] # 返回最标准的那个 Flash 模型名称

    except Exception as e:
        # 如果列出模型失败，直接返回硬编码的最稳模型
        return "gemini-1.5-flash"

def generate_safe(file_obj, prompt, model_name):
    """
    带重试机制的生成
    """
    # 最多重试 3 次
    for attempt in range(3):
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content([file_obj, prompt], request_options={"timeout": 600})
            return response.text
        except Exception as e:
            error_str = str(e).lower()
            
            # 如果是 429 (Quota/Resource Exhausted)
            if "429" in error_str or "quota" in error_str or "exhausted" in error_str:
                wait_time = 10 * (attempt + 1) # 10秒, 20秒, 30秒
                st.warning(f"⚠️ Google API is busy (Traffic Limit). Cooling down for {wait_time}s... (Attempt {attempt+1}/3)")
                time.sleep(wait_time)
                continue # 重试
            
            # 如果是其他错误，直接抛出
            raise e
            
    raise Exception("Failed after 3 retries due to busy API.")

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
            # 0. 确定模型 (关键修复)
            status_msg.markdown("**🛰️ Finding best available model...**")
            valid_model_name = get_valid_flash_model(API_KEY)
            # st.toast(f"Locked on model: {valid_model_name}", icon="🔒")
            
            # 1. 处理文件
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

            # 4. 生成字幕
            status_msg.markdown(f"**💜 Analyzing with {valid_model_name}...**")
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
            
            # 调用带重试的函数
            subtitle_text = generate_safe(video_file, prompt, valid_model_name)
            
            # 清理云端文件
            try: video_file.delete()
            except: pass

            # 5. 完成
            progress_bar.progress(100)
            status_msg.success(f"✨ Magic Happened!")
            
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
            st.info("💡 如果依然报错，可能是您的 Google API 免费配额已耗尽，请尝试更换一个新的 API Key。")
        
        finally:
            if tmp_video_path and os.path.exists(tmp_video_path): os.remove(tmp_video_path)
            if audio_path and os.path.exists(audio_path): os.remove(audio_path)
