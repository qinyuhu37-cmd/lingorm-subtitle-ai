import streamlit as st
import google.generativeai as genai
import tempfile
import os
import subprocess
import time
from pathlib import Path

# --- 页面配置 ---
st.set_page_config(
    page_title="LingOrm 字幕组 AI 工作台",
    page_icon="💜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义 CSS 美化
st.markdown("""
<style>
    .stButton>button {
        background-color: #FF4B4B;
        color: white;
        border-radius: 10px;
        height: 3em;
        width: 100%;
    }
    .stTextInput>div>div>input {
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

st.title("💜 LingOrm 字幕组 · AI 一键生肉转熟肉")
st.markdown("🚀 **Powered by Google Gemini 1.5 Pro** | 听写 + 翻译 + 打轴 一步到位")

# --- 侧边栏：设置区 ---
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/8/8a/Google_Gemini_logo.svg", width=200)
    st.header("🔑 核心设置")
    
    # 获取 API Key
    api_key = st.text_input("请输入 Google API Key", type="password", help="去 aistudio.google.com 免费申请")
    
    st.divider()
    
    st.subheader("🎭 角色设定 (CP模式)")
    col1, col2 = st.columns(2)
    with col1:
        role_1 = st.text_input("角色 A (泰名)", value="LingLing")
        role_1_cn = st.text_input("角色 A (中译)", value="Ling姐")
    with col2:
        role_2 = st.text_input("角色 B (泰名)", value="Orm")
        role_2_cn = st.text_input("角色 B (中译)", value="Orm")
    
    st.divider()
    
    st.subheader("🧹 噪音/幻觉拦截")
    blacklist_input = st.text_area(
        "黑名单词汇 (AI听到这些不翻译)", 
        value="迪哥,妈妈达,迪桑达,条纹,时髦,鲁尼特,字幕组,下载,关注",
        height=100
    )
    blacklist = [x.strip() for x in blacklist_input.split(",") if x.strip()]

# --- 核心函数 ---

def extract_audio(video_path):
    """提取音频为 MP3 (减小体积，防止超时)"""
    audio_path = video_path.replace(Path(video_path).suffix, ".mp3")
    # -vn: 去掉视频, -ac 1: 单声道, -ar 16000: 采样率16k (人声够用了)
    cmd = [
        "ffmpeg", "-i", video_path, 
        "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k",
        "-y", audio_path
    ]
    # 在 Streamlit Cloud 上运行必须捕获错误
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return audio_path
    except subprocess.CalledProcessError:
        st.error("❌ FFmpeg 音频提取失败，请检查文件是否损坏。")
        return None

def generate_subtitles(api_key, audio_file_path, roles, blacklist):
    """调用 Gemini 1.5 Pro"""
    genai.configure(api_key=api_key)
    
    status_text = st.empty()
    progress_bar = st.progress(0)

    # 1. 上传音频
    status_text.info("☁️ 正在上传音频到 Google 云端...")
    progress_bar.progress(20)
    
    try:
        video_file = genai.upload_file(path=audio_file_path)
    except Exception as e:
        st.error(f"上传失败: {e}")
        return None

    # 等待处理
    while video_file.state.name == "PROCESSING":
        time.sleep(2)
        video_file = genai.get_file(video_file.name)
    
    if video_file.state.name == "FAILED":
        st.error("❌ Google 处理音频失败")
        return None

    status_text.info("🧠 AI 正在听写并翻译中 (Gemini 1.5 Pro)...")
    progress_bar.progress(50)

    # 2. 构建超级提示词 (Prompt)
    prompt = f"""
    你是一个精通泰语、粤语、英语和中文的字幕组翻译。
    任务：根据音频生成 SRT 字幕。
    
    【角色定义】：
    - 说话人A: "{roles['r1']}"，中译为 "{roles['r1_cn']}"。
    - 说话人B: "{roles['r2']}"，中译为 "{roles['r2_cn']}"。
    - 注意：Orm 叫 LingLing "Phi Ling" 时，必须翻译为 "{roles['r1_cn']}"。
    
    【翻译要求】：
    1. 风格：口语化、甜蜜、符合嗑CP的语境。
    2. 格式：严格的 SRT 格式，不要包含任何代码块标记(如 ```srt)。
    3. 多人对话：在字幕文本开头标记名字，如 "Ling: 文本" 或 "Orm: 文本"。
    
    【严格过滤 (防幻觉)】：
    1. 如果音频是背景音乐(BGM)、噪音或无人声，绝对不要输出字幕。
    2. 忽略以下幻觉词汇：{", ".join(blacklist)}。
    3. 不要添加任何"翻译说明"或"结束语"，只输出字幕内容。
    
    【输出示例】：
    1
    00:00:01,000 --> 00:00:03,000
    Ling: 今天我们去哪里吃？
    
    2
    00:00:03,500 --> 00:00:05,000
    Orm: 去吃好吃的，Ling姐~
    """

    # 3. 调用模型
    model = genai.GenerativeModel(model_name="gemini-1.5-pro-latest")
    
    try:
        response = model.generate_content(
            [video_file, prompt],
            request_options={"timeout": 600}
        )
        progress_bar.progress(100)
        status_text.success("✅ 生成完成！")
        return response.text
    except Exception as e:
        st.error(f"API 调用超时或错误: {e}")
        return None

# --- 主界面逻辑 ---

st.markdown("### 1. 上传视频文件")
uploaded_file = st.file_uploader("支持 MP4, MOV, MKV, MP3, WAV (建议 < 200MB)", type=["mp4", "mov", "mkv", "mp3", "wav"])

if uploaded_file:
    st.video(uploaded_file)
    
    st.markdown("### 2. 开始生成")
    if st.button("🎬 立即制作字幕"):
        if not api_key:
            st.error("❌ 哎呀，你忘记在左侧填入 Google API Key 啦！")
        else:
            # 临时保存文件
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp_file:
                tmp_file.write(uploaded_file.read())
                tmp_video_path = tmp_file.name
            
            try:
                # 提取音频
                audio_path = extract_audio(tmp_video_path)
                
                if audio_path:
                    # AI 生成
                    roles = {"r1": role_1, "r1_cn": role_1_cn, "r2": role_2, "r2_cn": role_2_cn}
                    srt_content = generate_subtitles(api_key, audio_path, roles, blacklist)
                    
                    if srt_content:
                        # 清洗 Markdown 标记
                        clean_srt = srt_content.replace("```srt", "").replace("```", "").strip()
                        
                        st.divider()
                        st.subheader("📝 字幕预览")
                        st.text_area("SRT 内容", clean_srt, height=300)
                        
                        st.download_button(
                            label="📥 下载 .SRT 字幕文件",
                            data=clean_srt,
                            file_name=f"{Path(uploaded_file.name).stem}_LingOrm.srt",
                            mime="text/plain"
                        )
                    
                    # 清理音频临时文件
                    if os.path.exists(audio_path):
                        os.remove(audio_path)
            
            except Exception as e:
                st.error(f"发生未知错误: {e}")
            finally:
                # 清理视频临时文件
                if os.path.exists(tmp_video_path):
                    os.remove(tmp_video_path)

st.markdown("---")
st.markdown("Made with 💜 for LingOrm | 基于 Gemini 1.5 Pro")