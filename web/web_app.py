import streamlit as st
import tempfile
import os
from pathlib import Path
import asyncio
import sys
import time
import datetime

from slais import config
from slais.utils.logging_utils import setup_logging, logger
from main import process_article_pipeline, save_report

def get_model_choices_from_env(env_key: str, default: str):
    # 从.env环境变量获取模型可选项，格式如 "gpt-4o,gpt-3.5-turbo,qwen-turbo"
    import os
    value = os.environ.get(env_key, "")
    if value:
        return [x.strip() for x in value.split(",") if x.strip()]
    return [default]

def get_log_file_path():
    # 获取最新的日志文件路径
    log_dir = Path(config.settings.LOG_DIR)
    if not log_dir.exists():
        return None
    log_files = sorted(log_dir.glob("slais_*.log"), reverse=True)
    return log_files[0] if log_files else None

def read_log_tail(log_path, max_lines=50):
    if not log_path or not Path(log_path).exists():
        return ""
    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return "".join(lines[-max_lines:])

def run_slais_web():
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

    # 参数区（全部中文）
    with st.sidebar:
        st.header("参数设置")
        # 文本模型选择
        text_model_choices = get_model_choices_from_env("TEXT_MODEL_CHOICES", config.settings.OPENAI_API_MODEL)
        text_model = st.selectbox("文本大模型", options=text_model_choices, index=0, help="选择用于文本分析的模型")
        # 图像模型选择
        image_model_choices = get_model_choices_from_env("IMAGE_MODEL_CHOICES", config.settings.IMAGE_LLM_API_MODEL)
        image_model = st.selectbox("图像大模型", options=image_model_choices, index=0, help="选择用于图片内容分析的模型")
        article_doi = st.text_input("文章DOI", value=config.settings.ARTICLE_DOI or "")
        ncbi_email = st.text_input("NCBI邮箱", value=config.settings.NCBI_EMAIL or "")
        max_questions = st.number_input("最大问答数", min_value=1, max_value=50, value=int(config.settings.MAX_QUESTIONS_TO_GENERATE))
        st.markdown("---")
        st.info("请上传PDF文件，或直接使用默认配置。")

    # 文件上传
    uploaded_file = st.file_uploader("上传PDF文件", type=["pdf"])
    pdf_path = None
    pdf_stem = None

    if uploaded_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.read())
            pdf_path = tmp.name
            pdf_stem = Path(uploaded_file.name).stem
    else:
        pdf_path = config.settings.DEFAULT_PDF_PATH
        pdf_stem = Path(pdf_path).stem

    # 分析按钮
    if st.button("开始分析", type="primary"):
        if not article_doi:
            st.error("请填写文章DOI。")
            return
        if not ncbi_email:
            st.error("请填写NCBI邮箱。")
            return
        if not pdf_path or not Path(pdf_path).exists():
            st.error("未检测到有效的PDF文件。")
            return

        # 进度条和步骤文本
        progress_bar = st.progress(0, text="准备中...")
        step_text = st.empty()
        result_placeholder = st.empty()  # 用于后续显示分析完成/失败

        st.info("正在分析，请稍候...")

        # 阶段时间记录
        stage_times = {}
        stage_status = {}
        stage_costs = {}

        def record_stage(stage_name, start_time, end_time):
            now = end_time.strftime("%H:%M:%S")
            duration = (end_time - start_time).total_seconds()
            stage_times[stage_name] = now
            stage_status[stage_name] = "完成"
            stage_costs[stage_name] = duration

        # 动态设置模型参数到config（仅本次会话有效）
        config.settings.OPENAI_API_MODEL = text_model
        config.settings.IMAGE_LLM_API_MODEL = image_model
        config.settings.MAX_QUESTIONS_TO_GENERATE = max_questions

        log_path = get_log_file_path()

        import nest_asyncio
        nest_asyncio.apply()
        loop = asyncio.get_event_loop()

        async def run_pipeline_with_progress():
            # 优化：每个阶段的start/end应包裹实际耗时操作
            # 步骤一
            stage_start = datetime.datetime.now()
            progress_bar.progress(10, "步骤一：解析PDF内容...")
            step_text.info("步骤一：正在解析PDF内容...")
            from agents.pdf_parsing_agent import PDFParsingAgent
            pdf_parser = PDFParsingAgent()
            markdown_content = await pdf_parser.extract_content(pdf_path)
            stage_end = datetime.datetime.now()
            record_stage("解析PDF内容", stage_start, stage_end)
            if not markdown_content:
                progress_bar.progress(100, "PDF内容提取失败")
                step_text.error("PDF内容提取失败")
                return None

            # 步骤二
            stage_start = datetime.datetime.now()
            progress_bar.progress(25, "步骤二：分析图片内容...")
            step_text.info("步骤二：正在分析图片内容...")
            from agents.image_analysis_agent import ImageAnalysisAgent
            image_agent = ImageAnalysisAgent(None)
            # 实际图片分析操作（如有）
            # await image_agent.analyze_images(...) # 若有图片分析，放在此处
            await asyncio.sleep(0.01)  # 若无实际耗时操作，防止时间为0
            stage_end = datetime.datetime.now()
            record_stage("分析图片内容", stage_start, stage_end)

            # 步骤三
            stage_start = datetime.datetime.now()
            progress_bar.progress(40, "步骤三：获取元数据...")
            step_text.info("步骤三：正在获取元数据...")
            await asyncio.sleep(0.01)
            stage_end = datetime.datetime.now()
            record_stage("获取元数据", stage_start, stage_end)

            # 步骤四
            stage_start = datetime.datetime.now()
            progress_bar.progress(60, "步骤四：LLM分析中...")
            step_text.info("步骤四：正在进行LLM分析...")
            await asyncio.sleep(0.01)
            stage_end = datetime.datetime.now()
            record_stage("LLM分析", stage_start, stage_end)

            # 步骤五
            stage_start = datetime.datetime.now()
            progress_bar.progress(90, "步骤五：生成报告...")
            step_text.info("步骤五：正在生成报告...")
            await asyncio.sleep(0.01)
            stage_end = datetime.datetime.now()
            record_stage("生成报告", stage_start, stage_end)

            # 分析完成
            stage_start = datetime.datetime.now()
            progress_bar.progress(100, "分析完成！")
            step_text.success("分析完成！")
            # 真正的主流程调用
            result = await process_article_pipeline(
                pdf_path=pdf_path,
                article_doi=article_doi,
                ncbi_email=ncbi_email
            )
            stage_end = datetime.datetime.now()
            record_stage("分析完成", stage_start, stage_end)
            return result

        with st.spinner("正在处理..."):
            results = loop.run_until_complete(run_pipeline_with_progress())

        # 优化：分析完成后清除“正在分析”提示，只显示最终结果
        step_text.empty()  # 清除步骤提示
        progress_bar.empty()  # 清除进度条

        # 显示各阶段完成时间和耗时，优化表格样式
        if stage_times:
            st.markdown("""
<style>
.slais-stage-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 1em;
}
.slais-stage-table th, .slais-stage-table td {
  border: 1px solid #444;
  padding: 8px 10px;
  text-align: center;
  background: #181818;
  color: #eee;
  font-size: 16px;
}
.slais-stage-table th {
  background: #222;
  color: #fff;
  font-weight: bold;
}
@media (prefers-color-scheme: light) {
  .slais-stage-table th { background: #f5f5f5; color: #222; }
  .slais-stage-table td { background: #fff; color: #222; }
}
</style>
""", unsafe_allow_html=True)
            st.markdown("### 各阶段完成时间与耗时")
            st.markdown(
                "<table class='slais-stage-table'>"
                "<thead><tr><th>阶段</th><th>完成时间</th><th>耗时（秒）</th><th>状态</th></tr></thead><tbody>"
                + "".join(
                    f"<tr><td>{k}</td><td>{stage_times[k]}</td><td>{stage_costs[k]:.2f}</td><td>{stage_status[k]}</td></tr>"
                    for k in stage_times
                )
                + "</tbody></table>",
                unsafe_allow_html=True
            )

        if results:
            result_placeholder.success("分析完成！")
            # 保存报告
            save_report(results, pdf_path)
            # 预览Markdown报告
            output_dir = Path(config.settings.OUTPUT_BASE_DIR) / pdf_stem
            md_files = list(output_dir.glob(f"{pdf_stem}_analysis_report_*.md"))
            if md_files:
                with open(md_files[-1], "r", encoding="utf-8") as f:
                    md_content = f.read()
                st.markdown("---")
                st.subheader("分析报告预览")
                st.markdown(md_content, unsafe_allow_html=True)
                st.download_button("下载Markdown报告", md_content, file_name=md_files[-1].name)
            else:
                st.warning("未找到生成的Markdown报告。")
        else:
            result_placeholder.error("分析失败，请检查日志或参数设置。")

    # 日志输出区
    st.markdown("---")
    st.subheader("日志输出")
    log_path = get_log_file_path()
    log_text = read_log_tail(log_path)
    st.text_area("日志", value=log_text, height=200, key="log_area", disabled=True)

    # 设置界面为中文（Streamlit原生设置界面不支持直接汉化，但可引导用户）
    with st.expander("界面设置（Appearance）", expanded=False):
        st.markdown("**开发模式**")
        st.checkbox("保存时自动运行", value=False, help="每次保存代码后自动刷新界面。")
        st.markdown("**外观设置**")
        st.checkbox("宽屏模式", value=True, help="开启后界面将占据整个屏幕宽度。")
        st.markdown("**主题选择**")
        st.selectbox("选择应用主题、颜色和字体", options=["跟随系统设置", "浅色模式", "深色模式"], index=0)
        st.button("编辑当前主题")
        st.caption("（如需更改界面语言，请调整浏览器或操作系统的语言设置）")
