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
# 从 slais.utils.logging_utils 导入 get_log_file_path
from slais.utils.logging_utils import get_log_file_path, logger # 导入 logger

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
    
    # LOGO显示（使用 st.image，更稳定）
    logo_path = project_root / "logo.svg"
    if logo_path.exists():
        st.image(str(logo_path), width=120, use_container_width=False) # 替换 use_column_width 为 use_container_width
    else:
        logger.warning(f"Logo文件未找到: {logo_path.resolve()}")
        st.markdown("<div style='width:100%;text-align:center;margin-bottom:0.5em;'><b>SLAIS</b></div>", unsafe_allow_html=True)

    st.title("SLAIS 文献智能分析系统")
    st.markdown("高效、结构化的PDF学术文献分析与报告生成工具。")

    # 使用两列布局来优化空间利用
    col1, col2 = st.columns([3, 1])
    
    with col2:
        st.header("参数设置")
        
        # API接口选择
        api_choices = list(config.settings.LLM_MODEL_CHOICES.keys())
        if not api_choices:
            api_choices = ["OpenAI"] # 默认选项，以防配置为空
            st.warning("LLM模型配置为空，请检查 slais/config.py 或 .env 文件。")

        # 尝试根据配置中的默认API设置默认索引
        default_api_name = config.settings.DEFAULT_TEXT_MODEL_FOR_API.get("OpenAI", "OpenAI") # 假设OpenAI是默认API
        try:
            default_api_index = api_choices.index(default_api_name)
        except ValueError:
            default_api_index = 0 # 如果没有找到，则默认为第一个

        selected_api = st.selectbox("API接口", options=api_choices, index=default_api_index, help="选择用于模型调用的API接口。不同的API接口可能有不同的模型选择和性能表现。")

        # 文本大模型选择
        text_model_choices = config.settings.LLM_MODEL_CHOICES.get(selected_api, [])
        if not text_model_choices:
            text_model_choices = [config.settings.OPENAI_API_MODEL] # 回退到 .env 中的默认文本模型
            st.warning(f"API接口 '{selected_api}' 未配置文本模型，使用默认值 '{config.settings.OPENAI_API_MODEL}'。")
        
        # 尝试设置默认选中的文本模型
        default_text_model = config.settings.DEFAULT_TEXT_MODEL_FOR_API.get(selected_api, text_model_choices[0] if text_model_choices else "default-model")
        try:
            default_text_model_index = text_model_choices.index(default_text_model)
        except ValueError:
            default_text_model_index = 0 # 如果默认模型不在列表中，选择第一个
        
        text_model = st.selectbox("文本大模型", options=text_model_choices, index=default_text_model_index, help="选择用于文本分析的模型。不同的模型可能在处理速度和分析深度上有所不同。")

        # 图像模型选择
        image_model_choices = config.settings.LLM_MODEL_CHOICES.get(selected_api, [])
        if not image_model_choices:
            image_model_choices = [config.settings.IMAGE_LLM_API_MODEL] # 回退到 .env 中的默认图像模型
            st.warning(f"API接口 '{selected_api}' 未配置图像模型，使用默认值 '{config.settings.IMAGE_LLM_API_MODEL}'。")
        
        # 尝试设置默认选中的图像模型
        default_image_model = config.settings.DEFAULT_IMAGE_MODEL_FOR_API.get(selected_api, image_model_choices[0] if image_model_choices else "default-image-model")
        try:
            default_image_model_index = image_model_choices.index(default_image_model)
        except ValueError:
            default_image_model_index = 0 # 如果默认模型不在列表中，选择第一个
        
        image_model = st.selectbox("图像大模型", options=image_model_choices, index=default_image_model_index, help="选择用于图片内容分析的模型。确保选择支持图像处理的模型。")

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
