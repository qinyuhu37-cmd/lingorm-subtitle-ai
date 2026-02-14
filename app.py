import streamlit as st
import google.generativeai as genai
import tempfile
import os
import subprocess
import time
from pathlib import Path

# --- 1. 页面基础配置 ---
st.set_page_config(
    page_title="LingOrm AI Subtitles",
    page_icon="💜",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- 2. 高端 CSS 注入 (UI 美化) ---
st.markdown("""
<style>
    /* 引入 Kanit 字体 */
    @import url('https://fonts.googleapis.com/css2?family=Kanit:wght@300;400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Kanit', sans-serif;
    }

    /* 全局背景：柔和的紫色极光渐变 */
    .stApp {
        background: linear-gradient(135deg, #fdfbfd 0%, #f3e7f5 100%);
    }

    /* 标题样式 */
    h1 {
        color: #4a148c;
        font-weight: 600;
        text-align: center;
        letter-spacing: -1px;
    }
    
    /* 卡片容器样式 */
    .css-card {
        background-color: white;
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        margin-bottom: 20px;
        border: 1px solid #f0f0f0;
    }

    /* 按钮美化 */
    .stButton>button {
        background: linear-gradient(90deg, #7b1fa2, #9c27b0);
        color: white;
        border: none;
        border-radius: 12px;
        height: 50px;
        font-size: 18px;
        font-weight: 500;
        width: 100%;
        transition: all 0.3s ease;
        box-shadow: 0 4px 6px rgba(123, 31, 162, 0.2);
    }

    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 7px 14px rgba(123, 31, 162, 0.3);
        background: linear-gradient(90deg, #6a1b9a, #8e24aa);
    }
    
    /* 隐藏页脚 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
</style>
""", unsafe_allow_html=True)

# --- 3. 侧边栏 (设置) ---
with st.sidebar:
    st.markdown("### ⚙️ 核心设置")
    api_key = st.text_input("Google API Key", type="password", help="必填项")
    
    st.markdown("---")
    st.markdown("### 🎭 角色配置")
    col1, col2 = st.columns(2)
    with col1:
        role_1 = st.text_input("泰名 A", value="LingLing")
        role_1_cn = st.text_input("中译 A", value="Ling姐")
    with col2:
        role_2 = st.text_input("泰名 B", value="Orm")
        role_2_cn = st.text_input("中译 B", value="Orm")
    
    st.markdown("### 🚫 过滤设置")
    blacklist_input = st.text_area("屏蔽词", value="迪哥,妈妈达,迪桑达,条纹,时髦,鲁尼特", height=100)
    blacklist = [x.strip() for x in blacklist_input.split(",") if x.strip()]
    
    st.info("💡 提示：侧边栏可收起，让主界面更清爽。")

# --- 4. 核心逻辑函数 ---

def get_gemini_response(file, prompt):
    """
    智能模型调用：优先尝试 1.5 Pro，失败则降级到 Flash
    """
    try:
        # 优先尝试 Pro 版 (质量最佳)
        model = genai.GenerativeModel("gemini-1.5-pro")
        print("正在尝试使用 Gemini 1.5 Pro...")
        response = model.generate_content([file, prompt], request_options={"timeout": 600})
        return response
    except Exception as e:
        # 如果 Pro 失败 (如 404 或 配额不足)，自动切换到 Flash
        st.warning(f"⚠️ Pro 模型繁忙，正在自动切换至极速版 (Flash)...")
        print(f"Pro 模型错误: {e}")
        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content([file, prompt], request_options={"timeout": 600})
            return response
        except Exception as e2:
            raise e2

# --- 5. 主界面设计 ---

# 头部 Logo 区
st.markdown("<div style='text-align: center; margin-bottom: 30px;'>", unsafe_allow_html=True)
st.title("💜 LingOrm 字幕工坊")
st.markdown("<p style='color: #666; font-size: 1.1em;'>基于 Google Gemini 1.5 | 专为泰剧/CP 优化的 AI 翻译</p>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# 核心功能区
with st.container(border=True):
    st.markdown("### 📂 第一步：上传视频/音频")
    uploaded_file = st.file_uploader("", type=["mp4", "mov", "mkv", "mp3", "wav"], label_visibility="collapsed")

if uploaded_file:
    # 视频预览
    with st.expander("📹 点击预览视频画面", expanded=False):
        st.video(uploaded_file)
    
    st.write("") # 空行布局
    
    # 开始按钮
    if st.button("✨ 开始魔法生成 (Generate)"):
        if not api_key:
            st.error("🔒 请先在左侧侧边栏 (点击左上角 >) 输入 Google API Key")
        else:
            # --- 处理流程 ---
            status_container = st.container(border=True)
            with status_container:
                st.markdown("#### 🚀 正在处理中...")
                prog_bar = st.progress(0)
                status_text = st.empty()
                
                # 创建临时文件
                with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp_file:
                    tmp_file.write(uploaded_file.read())
                    tmp_video_path = tmp_file.name
                
                audio_path = None # 初始化变量
                
                try:
                    # 1. 提取音频
                    status_text.markdown("**正在从视频中提取人声...**")
                    prog_bar.progress(20)
                    
                    audio_path = tmp_video_path.replace(Path(tmp_video_path).suffix, ".mp3")
                    # FFmpeg 命令
                    cmd = ["ffmpeg", "-i", tmp_video_path, "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", "-y", audio_path]
                    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                    # 2. 上传云端
                    status_text.markdown("**正在上传至 Google Gemini 云端大脑...**")
                    prog_bar.progress(40)
                    
                    genai.configure(api_key=api_key)
                    video_file = genai.upload_file(path=audio_path)
                    
                    # 等待 Google 处理完毕
                    while video_file.state.name == "PROCESSING":
                        time.sleep(2)
                        video_file = genai.get_file(video_file.name)
                    
                    if video_file.state.name == "FAILED":
                        raise Exception("Google 处理音频失败")
                        
                    # 3. AI 生成
                    status_text.markdown("**AI 正在听写、翻译并校对时间轴 (LingOrm 模式)...**")
                    prog_bar.progress(60)
                    
                    prompt = f"""
                    你是一个精通泰语的字幕组翻译。请处理这段音频。
                    【角色】A: {role_1}({role_1_cn}), B: {role_2}({role_2_cn})。Phi Ling译为{role_1_cn}。
                    【要求】输出SRT格式。口语化甜美风。多人对话在文本前加名字。
                    【过滤】忽略BGM、噪音、幻觉词({",".join(blacklist)})。
                    【格式】直接输出SRT内容，不要代码块标记。
                    """
                    
                    # 调用双保险函数
                    response = get_gemini_response(video_file, prompt)
                    
                    prog_bar.progress(100)
                    status_text.markdown("✅ **生成完成！**")
                    
                    # 4. 结果展示
                    srt_content = response.text.replace("```srt", "").replace("```", "").strip()
                    
                    st.balloons() # 撒花
                    
                    st.markdown("### 🎉 字幕结果")
                    st.text_area("", srt_content, height=250)
                    
                    col_dl1, col_dl2 = st.columns([1, 1])
                    with col_dl1:
                        st.download_button(
                            label="📥 下载 SRT 字幕",
                            data=srt_content,
                            file_name=f"{Path(uploaded_file.name).stem}_LingOrm.srt",
                            mime="text/plain"
                        )
                    
                except Exception as e:
                    st.error(f"出错啦: {e}")
                finally:
                    # 清理垃圾文件
                    if audio_path and os.path.exists(audio_path): 
                        os.remove(audio_path)
                    if os.path.exists(tmp_video_path): 
                        os.remove(tmp_video_path)

# 底部版权
st.markdown("<div style='text-align: center; margin-top: 50px; color: #aaa; font-size: 0.8em;'>Made with 💜 by LingOrm Fans</div>", unsafe_allow_html=True)
