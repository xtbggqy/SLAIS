import streamlit as st
from pathlib import Path
import tempfile
import logging
import os
import sys
import re
from io import BytesIO

from app import process_article_pipeline, save_report
from slais import config
from pathlib import Path

def get_log_file_path():
    # 获取最新的日志文件路径
    log_dir = Path(config.settings.LOG_DIR)
    if not log_dir.exists():
        return None
    log_files = sorted(log_dir.glob("slais_*.log"), reverse=True)
    return log_files[0] if log_files else None
from slais import config
from web.models import load_models_from_config_file, get_model_choices

# Add project root to sys.path
project_root = Path(__file__).parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 确保nest_asyncio在导入其他模块前应用
import nest_asyncio
nest_asyncio.apply()

# 避免重复导入
from slais.utils.logging_utils import setup_logging, logger

# 确保日志系统被初始化
setup_logging()

# 加载外部CSS文件
def load_css_file(css_file_path):
    """从文件读取CSS样式"""
    with open(css_file_path, "r", encoding="utf-8") as f:
        return f.read()

def run_slais_web_ui():
    st.set_page_config(page_title="SLAIS 文献智能分析", layout="wide")
    
    # LOGO显示（优先本地SVG，回退到 slais_logo.svg），LOGO单独一行且无其他字符
    logo_path = Path(__file__).parent.parent / "logo.svg"
    if not logo_path.exists():
        logo_path = Path(__file__).parent.parent / "slais_logo.svg"
    if logo_path.exists():
        try:
            with open(logo_path, "r", encoding="utf-8") as f:
                svg_logo = f.read()
            # 检查svg_logo是否为字符串且包含<svg
            if not isinstance(svg_logo, str) or "<svg" not in svg_logo:
                raise ValueError("logo文件内容不是有效的SVG字符串")
            st.markdown(
                f"""<div style="width:100%;text-align:center;margin-bottom:0.5em;">{svg_logo}</div>""",
                unsafe_allow_html=True
            )
        except Exception as e:
            st.markdown(
                f"<div style='width:100%;text-align:center;margin-bottom:0.5em;color:red;'>LOGO加载失败: {e}</div>",
                unsafe_allow_html=True
            )
    else:
        st.markdown(
            "<div style='width:100%;text-align:center;margin-bottom:0.5em;'><b>SLAIS</b></div>",
            unsafe_allow_html=True
        )

    st.title("SLAIS 文献智能分析系统")
    st.markdown("高效、结构化的PDF学术文献分析与报告生成工具。")

    # 加载config.txt中的模型数据
    config_file_path = Path(__file__).parent / "config.txt"
    all_available_models = load_models_from_config_file(str(config_file_path))

    # 使用两列布局来优化空间利用
    col1, col2 = st.columns([3, 1])
    
    with col2:
        st.header("参数设置")
        # API接口选择
        api_choices = list(all_available_models.keys())
        if not api_choices:
            api_choices = ["OpenAI"] # 默认选项，以防config.txt为空或解析失败
            st.warning("config.txt中未找到API接口配置，请检查文件。")

        # 尝试根据图片中的“阿里云”设置默认索引
        try:
            default_api_index = api_choices.index("阿里云")
        except ValueError:
            default_api_index = 0 # 如果没有“阿里云”，则默认为第一个

        selected_api = st.selectbox("API接口", options=api_choices, index=default_api_index, help="选择用于模型调用的API接口。不同的API接口可能有不同的模型选择和性能表现。")

        # 根据API接口选择对应的模型列表
        # 默认模型名称，以防config.txt中没有对应API的模型
        default_text_model_for_api = {
            "OpenAI": config.settings.OPENAI_API_MODEL,
            "Gemini": "gemini-pro",
            "xAI": "grok-1",
            "阿里云": "qwen-turbo", # 阿里云的默认模型
            "DeepSeek": "deepseek-chat",
            "OpenRouter": "openrouter-auto"
        }
        text_model_choices = get_model_choices(selected_api, all_available_models, default_text_model_for_api.get(selected_api, "default-model"))
        text_model = st.selectbox("文本大模型", options=text_model_choices, index=0, help="选择用于文本分析的模型。不同的模型可能在处理速度和分析深度上有所不同。")

        # 图像模型选择：与文本模型使用同一API接口下的模型
        # 优先使用当前API接口下的模型作为图像模型选项
        image_model_choices = get_model_choices(selected_api, all_available_models, default_text_model_for_api.get(selected_api, "default-image-model"))
        # 如果当前API接口没有提供模型，或者没有明确的图像模型，可以考虑一个通用的图像模型
        if not image_model_choices:
            # 备用方案：如果当前API没有模型，可以尝试从OpenAI获取，或者设置一个通用默认值
            image_model_choices = get_model_choices("OpenAI", all_available_models, config.settings.IMAGE_LLM_API_MODEL)
            if not image_model_choices:
                image_model_choices = [config.settings.IMAGE_LLM_API_MODEL] # 最终回退到环境变量或硬编码默认值

        image_model = st.selectbox("图像大模型", options=image_model_choices, index=0, help="选择用于图片内容分析的模型。确保选择支持图像处理的模型。")

        article_doi = st.text_input("文章DOI", value=config.settings.ARTICLE_DOI or "", help="输入文章的数字对象标识符(DOI)，用于获取文章的元数据和相关文献。")
        ncbi_email = st.text_input("NCBI邮箱", value=config.settings.NCBI_EMAIL or "", help="输入您的NCBI邮箱，用于访问PubMed数据库获取相关文献信息。")
        max_questions = st.number_input("最大问答数", min_value=1, max_value=50, value=int(config.settings.MAX_QUESTIONS_TO_GENERATE), help="设置分析过程中生成的最大问题数量，影响分析的深度和广度。")
        st.markdown("---")
        st.info("请上传PDF文件，或直接使用默认配置。")

    with col1:
        st.header("文件上传")
        uploaded_file = st.file_uploader("上传PDF文件", type=["pdf"], help="上传您要分析的学术文献PDF文件。支持的文件格式为PDF。")
        pdf_path = None
        pdf_stem = None

        if uploaded_file:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded_file.read())
                pdf_path = tmp.name
                pdf_stem = Path(uploaded_file.name).stem
            st.success(f"文件 '{uploaded_file.name}' 上传成功！")
        else:
            pdf_path = config.settings.DEFAULT_PDF_PATH
            pdf_stem = Path(pdf_path).stem
            st.info("未上传文件，将使用默认PDF文件进行分析。")

        # 分析按钮，居中显示
        st.markdown("---")
        st.subheader("启动分析")
        # 初始化session state
        if 'analysis_started' not in st.session_state:
            st.session_state.analysis_started = False
        if 'pipeline_output' not in st.session_state: # 存储process_article_pipeline的完整输出
            st.session_state.pipeline_output = None
        if 'pdf_stem' not in st.session_state:
            st.session_state.pdf_stem = None
        if 'pdf_path' not in st.session_state:
            st.session_state.pdf_path = None

        analyze_button = st.button("开始分析", type="primary", use_container_width=True, help="点击开始分析上传的PDF文件。请确保已填写所有必要参数。")
        
        # 进度条和步骤文本
        st.markdown("---")
        st.subheader("分析进度")
        progress_bar = st.progress(0, text="准备中...")
        step_text = st.empty()
        result_placeholder = st.empty()  # 用于后续显示分析完成/失败

        return {
            "analyze_button": analyze_button,
            "article_doi": article_doi,
            "ncbi_email": ncbi_email,
            "pdf_path": pdf_path,
            "pdf_stem": pdf_stem,
            "progress_bar": progress_bar,
            "step_text": step_text,
            "result_placeholder": result_placeholder
        }

if __name__ == "__main__":
    run_slais_web_ui()
