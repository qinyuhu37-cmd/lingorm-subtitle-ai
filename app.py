import streamlit as st
import google.generativeai as genai
import tempfile
import os
import subprocess
import time
import re
import requests
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

# --- 3. 核心功能：SRT 转 ASS (带颜色) ---

def time_srt_to_ass(srt_time):
    """将 SRT 时间格式 (00:00:00,000) 转换为 ASS 时间格式 (0:00:00.00)"""
    try:
        h, m, s_ms = srt_time.split(':')
        s, ms = s_ms.split(',')
        # ASS 只需要两位毫秒
        return f"{int(h)}:{m}:{s}.{ms[:2]}"
    except:
        return "0:00:00.00"

def convert_srt_to_ass_colored(srt_content, role_1_cn, role_2_cn):
    """
    将 SRT 字幕转换为带有角色颜色的 ASS 字幕
    Ling (Role 1) -> Blue
    Orm (Role 2) -> Pink
    Others -> White
    """
    
    # ASS 颜色代码是 BGR 顺序 (Blue, Green, Red)
    # 浅蓝色 (SkyBlue): &H00EBCE87 (BGR) -> RGB(135, 206, 235)
    # 修正蓝色 (Ling): &H00FFBF00 (DeepSkyBlue BGR)
    COLOR_BLUE = "&H00FFBF00" 
    
    # 粉色 (HotPink): RGB(255, 105, 180) -> BGR(180, 105, 255) -> &H00B469FF
    # 修正粉色 (Orm): &H009999FF (Light Pink)
    COLOR_PINK = "&H009999FF"
    
    COLOR_WHITE = "&H00FFFFFF"

    # 定义 ASS 头部
    ass_header = f"""[Script Info]
Title: LingOrm Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: None

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,WenQuanYi Micro Hei,20,{COLOR_WHITE},&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,10,10,20,1
Style: LingStyle,WenQuanYi Micro Hei,20,{COLOR_BLUE},&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,10,10,20,1
Style: OrmStyle,WenQuanYi Micro Hei,20,{COLOR_PINK},&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,10,10,20,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    
    ass_body = ""
    
    # 解析 SRT
    # 简单的 SRT 解析器
    blocks = re.split(r'\n\s*\n', srt_content.strip())
    
    for block in blocks:
        lines = block.split('\n')
        if len(lines) >= 3:
            # line[0] 是序号
            # line[1] 是时间轴
            times = lines[1].split(' --> ')
            if len(times) != 2: continue
            
            start_time = time_srt_to_ass(times[0].strip())
            end_time = time_srt_to_ass(times[1].strip())
            
            # line[2:] 是文本
            text = " ".join(lines[2:])
            
            # 判定角色
            style = "Default"
            if role_1_cn in text or "Ling" in text:
                style = "LingStyle"
            elif role_2_cn in text or "Orm" in text:
                style = "OrmStyle"
            
            # 组装 Dialogue 行
            ass_body += f"Dialogue: 0,{start_time},{end_time},{style},,0,0,0,,{text}\n"

    return ass_header + ass_body

# --- 4. 辅助函数：字体下载与FFmpeg ---

def download_font_if_needed():
    """下载开源中文字体防止乱码"""
    font_path = "wqy-microhei.ttc"
    if not os.path.exists(font_path):
        url = "https://github.com/anthonyfok/fonts-wqy-microhei/raw/master/wqy-microhei.ttc" 
        try:
            r = requests.get(url, allow_redirects=True)
            with open(font_path, 'wb') as f:
                f.write(r.content)
        except:
            pass
    return os.path.abspath(font_path)

def burn_ass_ffmpeg(video_path, ass_path, output_path, mode="soft"):
    """
    mode="soft": 封装 ASS 流 (推荐，播放器可开关，有颜色，可提取编辑)
    mode="hard": 硬烧录 (文字焊死在视频上，有颜色)
    """
    video_abs_path = os.path.abspath(video_path)
    ass_abs_path = os.path.abspath(ass_path).replace("\\", "/")
    
    if mode == "soft":
        # 封装模式：MP4 容器可以容纳 ASS 流，但兼容性最好的其实是 MKV
        # 为了剪映/手机兼容性，我们尝试封装进 MP4，如果不被识别，用户可以使用硬烧录
        cmd = [
            "ffmpeg", "-i", video_abs_path, "-i", ass_abs_path,
            "-c", "copy", "-c:s", "mov_text", # MP4 标准容器不支持 ASS 样式流，只能转 mov_text (会丢失颜色)
            # 这是一个技术两难：MP4软字幕很难带颜色。
            # 为了“可编辑且带颜色”，我们推荐用户下载 .ASS 文件，
            # 或者我们生成 MKV (支持彩色软字幕)，但用户可能要 MP4。
            # 
            # 策略调整：
            # Soft 模式：生成 MKV (完美支持彩色软字幕)
            # Hard 模式：生成 MP4 (烧录颜色)
            "-map", "0", "-map", "1",
            "-c:v", "copy", "-c:a", "copy", "-c:s", "ass", 
            "-y", output_path.replace(".mp4", ".mkv") # 强制改后缀为 mkv 以支持样式
        ]
        final_output = output_path.replace(".mp4", ".mkv")
        
    else:
        # 硬烧录模式
        font_file = download_font_if_needed()
        # 必须指定 fontsdir 否则 Linux 可能找不到字体
        vf_cmd = f"subtitles='{ass_abs_path}':fontsdir='.'"
        
        cmd = [
            "ffmpeg", "-i", video_abs_path, 
            "-vf", vf_cmd,
            "-c:a", "copy", 
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-y", output_path
        ]
        final_output = output_path
    
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise Exception(f"FFmpeg Error: {result.stderr.decode('utf-8')}")
    
    return final_output

# --- 5. 核心逻辑：智能模型 ---

def get_valid_flash_model(api_key):
    genai.configure(api_key=api_key)
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        flash_models = [m for m in available_models if "flash" in m]
        if not flash_models: return "gemini-1.5-flash"
        flash_models.sort(key=len)
        return flash_models[0]
    except:
        return "gemini-1.5-flash"

def generate_safe(file_obj, prompt, model_name):
    for attempt in range(3):
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content([file_obj, prompt], request_options={"timeout": 600})
            return response.text
        except Exception as e:
            if "429" in str(e).lower():
                time.sleep(10 * (attempt + 1))
                continue
            raise e
    raise Exception("API Busy")

# --- 6. 获取 API Key ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    API_KEY = None

# --- 7. 界面构建 ---
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
            role_1 = st.text_input("Role A (Blue)", value="LingLing")
            role_1_cn = st.text_input("Role A (Keyword)", value="Ling姐")
        with col2:
            role_2 = st.text_input("Role B (Pink)", value="Orm")
            role_2_cn = st.text_input("Role B (Keyword)", value="Orm")
        blacklist_str = st.text_input("Blacklist", value="迪哥,妈妈达,迪桑达,条纹,时髦,鲁尼特,字幕组")
        blacklist = [x.strip() for x in blacklist_str.split(",") if x.strip()]

    st.write("")
    if uploaded_file:
        generate_btn = st.button("✨ Generate Magic (开始生成)")
    else:
        st.info("👆 Please upload a file to start.")
        generate_btn = False

    st.markdown('</div>', unsafe_allow_html=True)

# --- 8. 执行逻辑 ---
if generate_btn and uploaded_file:
    if not API_KEY:
        st.error("🔒 Error: No API Key found in Secrets.")
    else:
        status_msg = st.empty()
        progress_bar = st.progress(0)
        
        tmp_video_path = None
        audio_path = None
        srt_path = None
        ass_path = None
        final_video_path = None
        
        try:
            # 1. 准备文件
            status_msg.markdown("**📂 Preparing Workspace...**")
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp_file:
                tmp_file.write(uploaded_file.read())
                tmp_video_path = tmp_file.name
            
            # 2. 提取音频
            status_msg.markdown("**🎧 Extracting Audio Stream...**")
            progress_bar.progress(10)
            audio_path = tmp_video_path + ".mp3"
            subprocess.run(["ffmpeg", "-i", tmp_video_path, "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k", "-y", audio_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # 3. AI 生成字幕
            status_msg.markdown("**☁️ AI Listening & Translating...**")
            progress_bar.progress(30)
            
            genai.configure(api_key=API_KEY)
            video_file = genai.upload_file(path=audio_path)
            while video_file.state.name == "PROCESSING":
                time.sleep(2)
                video_file = genai.get_file(video_file.name)
            
            # Prompt 强调格式
            prompt = f"""
            Task: Transcribe and translate to Simplified Chinese Subtitles (SRT).
            Context: Conversation between {role_1} and {role_2}.
            Rules:
            1. **IMPORTANT**: Start every dialogue line with "{role_1_cn}:" or "{role_2_cn}:".
            2. "Phi Ling" -> "{role_1_cn}", "Nong Orm" -> "{role_2_cn}".
            3. Tone: Sweet, romantic.
            4. No words: {', '.join(blacklist)}.
            5. Output ONLY valid SRT format.
            """
            
            valid_model = get_valid_flash_model(API_KEY)
            subtitle_text = generate_safe(video_file, prompt, valid_model)
            
            # 保存 SRT
            srt_path = tmp_video_path + ".srt"
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(subtitle_text)
            
            # --- 新增步骤：SRT 转 彩色 ASS ---
            status_msg.markdown("**🎨 Painting Subtitle Colors (Blue & Pink)...**")
            ass_content = convert_srt_to_ass_colored(subtitle_text, role_1_cn, role_2_cn)
            ass_path = tmp_video_path + ".ass"
            with open(ass_path, "w", encoding="utf-8") as f:
                f.write(ass_content)

            # 清理云端
            try: video_file.delete()
            except: pass
            
            # 4. 视频合成 UI
            progress_bar.progress(80)
            status_msg.success("✅ Subtitles Generated! Choose Output Format below.")
            
            st.markdown('<div class="clean-card">', unsafe_allow_html=True)
            st.markdown("##### 🎬 Final Video Studio (Colored)")
            
            tab1, tab2 = st.tabs(["🌈 Colored Soft Subs (Editable)", "🔥 Hard Burn (Permanent)"])
            
            with tab1:
                st.info("💡 **Recommended for Players**: Downloads an MKV video with embedded styled subtitles. You can turn them on/off, and colors will show in players like PotPlayer/VLC.")
                st.text_area("ASS Content (Style Source)", ass_content, height=100)
                
                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    st.download_button("📥 Download .ASS File", ass_content, f"{Path(uploaded_file.name).stem}.ass", "text/plain")
                with col_s2:
                    if st.button("🚀 Generate MKV (Soft Subs)"):
                        try:
                            with st.spinner("Embedding ASS stream..."):
                                target_file = tmp_video_path + "_soft.mkv"
                                real_output = burn_ass_ffmpeg(tmp_video_path, ass_path, target_file, mode="soft")
                                with open(real_output, "rb") as v_file:
                                    st.download_button("📥 Download Video (MKV)", v_file, f"{Path(uploaded_file.name).stem}_soft.mkv", "video/x-matroska")
                        except Exception as e:
                            st.error(f"Error: {e}")
            
            with tab2:
                st.info("⚠️ **For Social Media**: Burns the colors permanently into the video. Text cannot be edited afterwards, but colors are guaranteed everywhere.")
                if st.button("🔥 Hard Burn (MP4)"):
                    try:
                        with st.spinner("Rendering video (Slow)..."):
                            target_file = tmp_video_path + "_hard.mp4"
                            real_output = burn_ass_ffmpeg(tmp_video_path, ass_path, target_file, mode="hard")
                            st.success("Render Complete!")
                            with open(real_output, "rb") as v_file:
                                st.download_button("📥 Download Video (MP4)", v_file, f"{Path(uploaded_file.name).stem}_burned.mp4", "video/mp4")
                    except Exception as e:
                        st.error(f"Render Failed: {e}")

            st.markdown('</div>', unsafe_allow_html=True)
            progress_bar.progress(100)

        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
        
        finally:
            if tmp_video_path and os.path.exists(tmp_video_path): os.remove(tmp_video_path)
            if audio_path and os.path.exists(audio_path): os.remove(audio_path)import streamlit as st
import google.generativeai as genai
import tempfile
import os
import subprocess
import time
import re
import requests
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

# --- 3. 核心功能：SRT 转 ASS (带颜色) ---

def time_srt_to_ass(srt_time):
    """将 SRT 时间格式 (00:00:00,000) 转换为 ASS 时间格式 (0:00:00.00)"""
    try:
        h, m, s_ms = srt_time.split(':')
        s, ms = s_ms.split(',')
        # ASS 只需要两位毫秒
        return f"{int(h)}:{m}:{s}.{ms[:2]}"
    except:
        return "0:00:00.00"

def convert_srt_to_ass_colored(srt_content, role_1_cn, role_2_cn):
    """
    将 SRT 字幕转换为带有角色颜色的 ASS 字幕
    Ling (Role 1) -> Blue
    Orm (Role 2) -> Pink
    Others -> White
    """
    
    # ASS 颜色代码是 BGR 顺序 (Blue, Green, Red)
    # 浅蓝色 (SkyBlue): &H00EBCE87 (BGR) -> RGB(135, 206, 235)
    # 修正蓝色 (Ling): &H00FFBF00 (DeepSkyBlue BGR)
    COLOR_BLUE = "&H00FFBF00" 
    
    # 粉色 (HotPink): RGB(255, 105, 180) -> BGR(180, 105, 255) -> &H00B469FF
    # 修正粉色 (Orm): &H009999FF (Light Pink)
    COLOR_PINK = "&H009999FF"
    
    COLOR_WHITE = "&H00FFFFFF"

    # 定义 ASS 头部
    ass_header = f"""[Script Info]
Title: LingOrm Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: None

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,WenQuanYi Micro Hei,20,{COLOR_WHITE},&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,10,10,20,1
Style: LingStyle,WenQuanYi Micro Hei,20,{COLOR_BLUE},&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,10,10,20,1
Style: OrmStyle,WenQuanYi Micro Hei,20,{COLOR_PINK},&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,10,10,20,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    
    ass_body = ""
    
    # 解析 SRT
    # 简单的 SRT 解析器
    blocks = re.split(r'\n\s*\n', srt_content.strip())
    
    for block in blocks:
        lines = block.split('\n')
        if len(lines) >= 3:
            # line[0] 是序号
            # line[1] 是时间轴
            times = lines[1].split(' --> ')
            if len(times) != 2: continue
            
            start_time = time_srt_to_ass(times[0].strip())
            end_time = time_srt_to_ass(times[1].strip())
            
            # line[2:] 是文本
            text = " ".join(lines[2:])
            
            # 判定角色
            style = "Default"
            if role_1_cn in text or "Ling" in text:
                style = "LingStyle"
            elif role_2_cn in text or "Orm" in text:
                style = "OrmStyle"
            
            # 组装 Dialogue 行
            ass_body += f"Dialogue: 0,{start_time},{end_time},{style},,0,0,0,,{text}\n"

    return ass_header + ass_body

# --- 4. 辅助函数：字体下载与FFmpeg ---

def download_font_if_needed():
    """下载开源中文字体防止乱码"""
    font_path = "wqy-microhei.ttc"
    if not os.path.exists(font_path):
        url = "https://github.com/anthonyfok/fonts-wqy-microhei/raw/master/wqy-microhei.ttc" 
        try:
            r = requests.get(url, allow_redirects=True)
            with open(font_path, 'wb') as f:
                f.write(r.content)
        except:
            pass
    return os.path.abspath(font_path)

def burn_ass_ffmpeg(video_path, ass_path, output_path, mode="soft"):
    """
    mode="soft": 封装 ASS 流 (推荐，播放器可开关，有颜色，可提取编辑)
    mode="hard": 硬烧录 (文字焊死在视频上，有颜色)
    """
    video_abs_path = os.path.abspath(video_path)
    ass_abs_path = os.path.abspath(ass_path).replace("\\", "/")
    
    if mode == "soft":
        # 封装模式：MP4 容器可以容纳 ASS 流，但兼容性最好的其实是 MKV
        # 为了剪映/手机兼容性，我们尝试封装进 MP4，如果不被识别，用户可以使用硬烧录
        cmd = [
            "ffmpeg", "-i", video_abs_path, "-i", ass_abs_path,
            "-c", "copy", "-c:s", "mov_text", # MP4 标准容器不支持 ASS 样式流，只能转 mov_text (会丢失颜色)
            # 这是一个技术两难：MP4软字幕很难带颜色。
            # 为了“可编辑且带颜色”，我们推荐用户下载 .ASS 文件，
            # 或者我们生成 MKV (支持彩色软字幕)，但用户可能要 MP4。
            # 
            # 策略调整：
            # Soft 模式：生成 MKV (完美支持彩色软字幕)
            # Hard 模式：生成 MP4 (烧录颜色)
            "-map", "0", "-map", "1",
            "-c:v", "copy", "-c:a", "copy", "-c:s", "ass", 
            "-y", output_path.replace(".mp4", ".mkv") # 强制改后缀为 mkv 以支持样式
        ]
        final_output = output_path.replace(".mp4", ".mkv")
        
    else:
        # 硬烧录模式
        font_file = download_font_if_needed()
        # 必须指定 fontsdir 否则 Linux 可能找不到字体
        vf_cmd = f"subtitles='{ass_abs_path}':fontsdir='.'"
        
        cmd = [
            "ffmpeg", "-i", video_abs_path, 
            "-vf", vf_cmd,
            "-c:a", "copy", 
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-y", output_path
        ]
        final_output = output_path
    
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise Exception(f"FFmpeg Error: {result.stderr.decode('utf-8')}")
    
    return final_output

# --- 5. 核心逻辑：智能模型 ---

def get_valid_flash_model(api_key):
    genai.configure(api_key=api_key)
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        flash_models = [m for m in available_models if "flash" in m]
        if not flash_models: return "gemini-1.5-flash"
        flash_models.sort(key=len)
        return flash_models[0]
    except:
        return "gemini-1.5-flash"

def generate_safe(file_obj, prompt, model_name):
    for attempt in range(3):
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content([file_obj, prompt], request_options={"timeout": 600})
            return response.text
        except Exception as e:
            if "429" in str(e).lower():
                time.sleep(10 * (attempt + 1))
                continue
            raise e
    raise Exception("API Busy")

# --- 6. 获取 API Key ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    API_KEY = None

# --- 7. 界面构建 ---
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
            role_1 = st.text_input("Role A (Blue)", value="LingLing")
            role_1_cn = st.text_input("Role A (Keyword)", value="Ling姐")
        with col2:
            role_2 = st.text_input("Role B (Pink)", value="Orm")
            role_2_cn = st.text_input("Role B (Keyword)", value="Orm")
        blacklist_str = st.text_input("Blacklist", value="迪哥,妈妈达,迪桑达,条纹,时髦,鲁尼特,字幕组")
        blacklist = [x.strip() for x in blacklist_str.split(",") if x.strip()]

    st.write("")
    if uploaded_file:
        generate_btn = st.button("✨ Generate Magic (开始生成)")
    else:
        st.info("👆 Please upload a file to start.")
        generate_btn = False

    st.markdown('</div>', unsafe_allow_html=True)

# --- 8. 执行逻辑 ---
if generate_btn and uploaded_file:
    if not API_KEY:
        st.error("🔒 Error: No API Key found in Secrets.")
    else:
        status_msg = st.empty()
        progress_bar = st.progress(0)
        
        tmp_video_path = None
        audio_path = None
        srt_path = None
        ass_path = None
        final_video_path = None
        
        try:
            # 1. 准备文件
            status_msg.markdown("**📂 Preparing Workspace...**")
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp_file:
                tmp_file.write(uploaded_file.read())
                tmp_video_path = tmp_file.name
            
            # 2. 提取音频
            status_msg.markdown("**🎧 Extracting Audio Stream...**")
            progress_bar.progress(10)
            audio_path = tmp_video_path + ".mp3"
            subprocess.run(["ffmpeg", "-i", tmp_video_path, "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k", "-y", audio_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # 3. AI 生成字幕
            status_msg.markdown("**☁️ AI Listening & Translating...**")
            progress_bar.progress(30)
            
            genai.configure(api_key=API_KEY)
            video_file = genai.upload_file(path=audio_path)
            while video_file.state.name == "PROCESSING":
                time.sleep(2)
                video_file = genai.get_file(video_file.name)
            
            # Prompt 强调格式
            prompt = f"""
            Task: Transcribe and translate to Simplified Chinese Subtitles (SRT).
            Context: Conversation between {role_1} and {role_2}.
            Rules:
            1. **IMPORTANT**: Start every dialogue line with "{role_1_cn}:" or "{role_2_cn}:".
            2. "Phi Ling" -> "{role_1_cn}", "Nong Orm" -> "{role_2_cn}".
            3. Tone: Sweet, romantic.
            4. No words: {', '.join(blacklist)}.
            5. Output ONLY valid SRT format.
            """
            
            valid_model = get_valid_flash_model(API_KEY)
            subtitle_text = generate_safe(video_file, prompt, valid_model)
            
            # 保存 SRT
            srt_path = tmp_video_path + ".srt"
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(subtitle_text)
            
            # --- 新增步骤：SRT 转 彩色 ASS ---
            status_msg.markdown("**🎨 Painting Subtitle Colors (Blue & Pink)...**")
            ass_content = convert_srt_to_ass_colored(subtitle_text, role_1_cn, role_2_cn)
            ass_path = tmp_video_path + ".ass"
            with open(ass_path, "w", encoding="utf-8") as f:
                f.write(ass_content)

            # 清理云端
            try: video_file.delete()
            except: pass
            
            # 4. 视频合成 UI
            progress_bar.progress(80)
            status_msg.success("✅ Subtitles Generated! Choose Output Format below.")
            
            st.markdown('<div class="clean-card">', unsafe_allow_html=True)
            st.markdown("##### 🎬 Final Video Studio (Colored)")
            
            tab1, tab2 = st.tabs(["🌈 Colored Soft Subs (Editable)", "🔥 Hard Burn (Permanent)"])
            
            with tab1:
                st.info("💡 **Recommended for Players**: Downloads an MKV video with embedded styled subtitles. You can turn them on/off, and colors will show in players like PotPlayer/VLC.")
                st.text_area("ASS Content (Style Source)", ass_content, height=100)
                
                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    st.download_button("📥 Download .ASS File", ass_content, f"{Path(uploaded_file.name).stem}.ass", "text/plain")
                with col_s2:
                    if st.button("🚀 Generate MKV (Soft Subs)"):
                        try:
                            with st.spinner("Embedding ASS stream..."):
                                target_file = tmp_video_path + "_soft.mkv"
                                real_output = burn_ass_ffmpeg(tmp_video_path, ass_path, target_file, mode="soft")
                                with open(real_output, "rb") as v_file:
                                    st.download_button("📥 Download Video (MKV)", v_file, f"{Path(uploaded_file.name).stem}_soft.mkv", "video/x-matroska")
                        except Exception as e:
                            st.error(f"Error: {e}")
            
            with tab2:
                st.info("⚠️ **For Social Media**: Burns the colors permanently into the video. Text cannot be edited afterwards, but colors are guaranteed everywhere.")
                if st.button("🔥 Hard Burn (MP4)"):
                    try:
                        with st.spinner("Rendering video (Slow)..."):
                            target_file = tmp_video_path + "_hard.mp4"
                            real_output = burn_ass_ffmpeg(tmp_video_path, ass_path, target_file, mode="hard")
                            st.success("Render Complete!")
                            with open(real_output, "rb") as v_file:
                                st.download_button("📥 Download Video (MP4)", v_file, f"{Path(uploaded_file.name).stem}_burned.mp4", "video/mp4")
                    except Exception as e:
                        st.error(f"Render Failed: {e}")

            st.markdown('</div>', unsafe_allow_html=True)
            progress_bar.progress(100)

        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
        
        finally:
            if tmp_video_path and os.path.exists(tmp_video_path): os.remove(tmp_video_path)
            if audio_path and os.path.exists(audio_path): os.remove(audio_path)
