import streamlit as st
import asyncio
import nest_asyncio
from pathlib import Path

from app import process_article_pipeline
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

# 确保nest_asyncio在导入其他模块前应用
nest_asyncio.apply()

def run_analysis(analyze_button, article_doi, ncbi_email, pdf_path, pdf_stem, progress_bar, step_text, result_placeholder):
    if analyze_button:
        # 重置状态，开始新的分析
        st.session_state.analysis_started = True
        st.session_state.pipeline_output = None
        st.session_state.pdf_stem = None
        st.session_state.pdf_path = None

        if not article_doi:
            st.error("请填写文章DOI。")
            st.session_state.analysis_started = False # 阻止分析继续
            return
        if not ncbi_email:
            st.error("请填写NCBI邮箱。")
            st.session_state.analysis_started = False # 阻止分析继续
            return
        if not pdf_path or not Path(pdf_path).exists():
            st.error("未检测到有效的PDF文件。")
            st.session_state.analysis_started = False # 阻止分析继续
            return

        st.info("正在分析，请稍候...")

        log_path = get_log_file_path()

        loop = asyncio.get_event_loop()

        async def run_pipeline_with_progress():
            def update_ui_progress(percentage: int, text: str):
                progress_bar.progress(percentage, text=text)
                step_text.info(text)

            # 真正的主流程调用
            pipeline_result = await process_article_pipeline(
                pdf_path=pdf_path,
                article_doi=article_doi,
                ncbi_email=ncbi_email,
                progress_callback=update_ui_progress
            )
            return pipeline_result

        with st.spinner("正在处理..."):
            st.session_state.pipeline_output = loop.run_until_complete(run_pipeline_with_progress())
            st.session_state.pdf_stem = pdf_stem
            st.session_state.pdf_path = pdf_path

        # 优化：分析完成后清除“正在分析”提示，只显示最终结果
        step_text.empty()  # 清除步骤提示
        progress_bar.empty()  # 清除进度条
        st.rerun() # 强制刷新UI以显示结果

if __name__ == "__main__":
    # 此文件作为独立脚本运行时，需要从UI获取参数
    # 但通常情况下，它会被web_app.py调用
    pass
