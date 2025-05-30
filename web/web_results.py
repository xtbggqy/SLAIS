import streamlit as st
import markdown
import re
import os
from pathlib import Path
from bs4 import BeautifulSoup
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.lib import colors
from reportlab.lib.units import inch
from io import BytesIO

from app import save_report
from web.web_ui import get_log_file_path
from slais import config
from web.web_ui import load_css_file
from slais.utils.logging_utils import logger

def read_log_tail(log_path, max_lines=50):
    if not log_path or not Path(log_path).exists():
        return ""
    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return "".join(lines[-max_lines:])

def display_log_section():
    """显示日志输出区域"""
    st.markdown("---")
    with st.expander("📋 查看详细日志", expanded=False):
        log_path = get_log_file_path()

        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            search_term = st.text_input("🔍 搜索日志", placeholder="输入关键词搜索...", key="log_search_term")
        with col2:
            max_lines = st.number_input("显示行数", min_value=10, max_value=1000, value=50, step=10, key="log_max_lines")
        with col3:
            if st.button("🔄 刷新日志", key="refresh_log_button"):
                st.rerun()

        log_text_full = ""
        if log_path and Path(log_path).exists():
            with open(log_path, "r", encoding="utf-8") as f:
                log_text_full = f.read()
        
        if log_text_full:
            lines = log_text_full.splitlines()
            
            if search_term:
                lines = [line for line in lines if search_term.lower() in line.lower()]
            
            display_lines = lines[-max_lines:]
            display_text = "\\n".join(display_lines)
            
            st.text_area("日志内容", value=display_text, height=300, key="log_display_area", disabled=True)
            
            if lines: #提供下载完整过滤后日志或完整日志的选项
                 full_log_to_download = "\\n".join(lines) # 过滤后的完整日志
                 st.download_button(
                    label="📥 下载当前显示日志",
                    data=full_log_to_download,
                    file_name=f"filtered_log_{Path(log_path).name}",
                    mime="text/plain",
                    key="download_filtered_log"
                )
            st.download_button(
                label="📥 下载完整日志文件",
                data=log_text_full, # 原始完整日志
                file_name=Path(log_path).name if log_path else "slais_log.log",
                mime="text/plain",
                key="download_full_log"
            )
        else:
            st.info("📝 暂无日志内容或日志文件未找到。")
            if log_path:
                st.caption(f"预期日志文件路径: {log_path}")


def display_results():
    # 在分析完成后显示结果
    if st.session_state.analysis_started and st.session_state.pipeline_output:
        pipeline_output = st.session_state.pipeline_output
        results = pipeline_output.get("analysis_results")
        stage_times = pipeline_output.get("stage_times", {})
        stage_status = pipeline_output.get("stage_status", {})
        stage_costs = pipeline_output.get("stage_costs", {})
        logger.info(f"Web app 从 session_state 获取的 stage_times: {stage_times}") # 添加日志
        logger.info(f"Web app 从 session_state 获取的 stage_status: {stage_status}") # 添加日志
        logger.info(f"Web app 从 session_state 获取的 stage_costs: {stage_costs}") # 添加日志

        pdf_stem = st.session_state.pdf_stem
        pdf_path = st.session_state.pdf_path

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
        # 合并所有阶段的键，确保显示所有阶段
        all_stages = set(stage_times.keys()) | set(stage_status.keys()) | set(stage_costs.keys())
        if all_stages:
            st.markdown(
                "<table class='slais-stage-table'>"
                "<thead><tr><th>阶段</th><th>完成时间</th><th>耗时（秒）</th><th>状态</th></tr></thead><tbody>"
                + "".join(
                    f"<tr><td>{k}</td><td>{stage_times.get(k, '未完成')}</td><td>{stage_costs.get(k, 0.0):.2f}</td><td>{stage_status.get(k, '未开始')}</td></tr>"
                    for k in sorted(all_stages)
                )
                + "</tbody></table>",
                unsafe_allow_html=True
            )
        else:
            st.info("未获取到阶段时间信息。")

        if results:
            result_placeholder = st.empty()
            result_placeholder.success("解析完成！")
            # 保存报告
            save_report(results, pdf_path)
            # 预览Markdown报告
            output_base_dir = Path(config.settings.OUTPUT_BASE_DIR)
            all_md_files = sorted(output_base_dir.glob("**/*_analysis_report_*.md"), key=os.path.getmtime, reverse=True)
            md_files = [f for f in all_md_files if pdf_stem in f.parent.name or pdf_stem in f.name]
            if not md_files and all_md_files:
                md_files = all_md_files[:1]
            
            if md_files:
                with open(md_files[0], "r", encoding="utf-8") as f:
                    md_content_raw = f.read()
                
                # 直接删除报告中的参考文献和相关文献部分
                # 匹配以"## 7. 参考文献信息"开始的部分，直到下一个##标题或文件末尾
                pattern_references = r"^(## 7\\. 参考文献信息)[\\s\\S]*?(?=\\n^##|\\Z)"
                md_content_processed = re.sub(pattern_references, "", md_content_raw, flags=re.MULTILINE)
                
                # 匹配以"## 8. 相关文献信息"开始的部分，直到下一个##标题或文件末尾
                pattern_related_literature = r"^(## 8\\. 相关文献信息)[\\s\\S]*?(?=\\n^##|\\Z)"
                md_content_cleaned_for_preview = re.sub(pattern_related_literature, "", md_content_processed, flags=re.MULTILINE)

                # 移除可能包含的logo.svg相关内容 (仅针对预览)
                md_content_cleaned_for_preview = md_content_cleaned_for_preview.replace("![logo](logo.svg)", "").replace("<img src=\"logo.svg\" alt=\"logo\">", "")
                
                # 用于下载的完整内容 (保留参考文献和相关文献部分，只移除logo)
                md_content_for_download = md_content_raw.replace("![logo](logo.svg)", "").replace("<img src=\"logo.svg\" alt=\"logo\">", "")
                
                st.markdown("---")
                st.subheader("分析报告预览")
                st.markdown("以下是生成的分析报告，您可以选择不同的渲染方式查看内容。")
                
                tab1, tab2 = st.tabs(["HTML渲染", "Markdown原始格式"])
                
                with tab1:
                    try:
                        html_content = markdown.markdown(md_content_cleaned_for_preview, extensions=['extra', 'toc'])
                        
                        # 加载外部CSS文件
                        css_path = Path(__file__).parent / "markdown_styles.css"
                        if css_path.exists():
                            css_content = load_css_file(str(css_path))
                        else:
                            logger.warning(f"找不到CSS样式文件: {css_path}")
                            css_content = """
                            .markdown-report-container {
                                font-family: Arial, sans-serif;
                                padding: 15px;
                                line-height: 1.6;
                                overflow-x: auto;
                                max-height: 600px;
                            }
                            """
                        
                        # 添加JavaScript来处理目录跳转
                        js_code = """
                        <script>
                        document.addEventListener('DOMContentLoaded', function() {
                            var tocLinks = document.querySelectorAll('.toc a');
                            tocLinks.forEach(function(link) {
                                link.addEventListener('click', function(e) {
                                    e.preventDefault();
                                    var targetId = this.getAttribute('href').substring(1);
                                    var targetElement = document.getElementById(targetId);
                                    if (targetElement) {
                                        targetElement.scrollIntoView({ behavior: 'smooth' });
                                    }
                                });
                            });
                        });
                        </script>
                        """
                        
                        # 应用CSS样式并渲染HTML内容
                        st.markdown(
                            f"""
                            <style>
                            {css_content}
                            </style>
                            <div class="markdown-report-container">
                            {html_content}
                            {js_code}
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    except ImportError as e:
                        logger.error(f"无法以HTML格式渲染报告，因为缺少 'markdown' 模块: {e}")
                        st.warning("无法以HTML格式渲染报告，因为缺少 'markdown' 模块。请安装它：pip install markdown")
                        st.markdown(md_content_cleaned_for_preview, unsafe_allow_html=True)
                    except Exception as e:
                        logger.error(f"HTML渲染过程中发生错误: {e}")
                        st.warning(f"HTML渲染过程中发生错误: {e}")
                        st.markdown(md_content_cleaned_for_preview, unsafe_allow_html=True)
                
                with tab2:
                    st.code(md_content_cleaned_for_preview, language="markdown")
                
                # 提供导出选项
                st.markdown("---")
                st.subheader("导出报告")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    # 下载按钮使用完整内容版本
                    st.download_button("下载Markdown报告", md_content_for_download, file_name=md_files[0].name, help="下载完整的分析报告Markdown格式文件。")
                with col2:
                    try:
                        # PDF生成使用隐藏参考文献和相关文献的版本
                        html_content_for_pdf = markdown.markdown(md_content_cleaned_for_preview, extensions=['extra', 'toc', 'tables', 'fenced_code'])
                        
                        pdf_buffer = BytesIO()
                        pdf_doc = SimpleDocTemplate(pdf_buffer, pagesize=(8.5 * inch, 11 * inch),
                                                  rightMargin=0.75*inch, leftMargin=0.75*inch,
                                                  topMargin=0.75*inch, bottomMargin=0.75*inch)
                        styles = getSampleStyleSheet()

                        # 自定义或修改样式
                        # Define H1 style
                        parent_h1_style = styles['Heading1'] if 'Heading1' in styles else styles['Normal']
                        styles.add(ParagraphStyle(
                            name='H1',
                            parent=parent_h1_style,
                            fontSize=18,
                            spaceBefore=12,
                            spaceAfter=6,
                            alignment=TA_LEFT
                        ))

                        # Define H2 style
                        parent_h2_style = styles['Heading2'] if 'Heading2' in styles else styles['Normal']
                        styles.add(ParagraphStyle(
                            name='H2',
                            parent=parent_h2_style,
                            fontSize=16,
                            spaceBefore=10,
                            spaceAfter=5,
                            alignment=TA_LEFT
                        ))

                        # Define H3 style
                        parent_h3_style = styles['Heading3'] if 'Heading3' in styles else styles['Normal']
                        styles.add(ParagraphStyle(
                            name='H3',
                            parent=parent_h3_style,
                            fontSize=14,
                            spaceBefore=8,
                            spaceAfter=4,
                            alignment=TA_LEFT
                        ))

                        # Modify existing 'Code' style
                        if 'Code' in styles:
                            code_style = styles['Code']
                            code_style.fontName = 'Courier'
                            code_style.fontSize = 9
                            code_style.leading = 11
                            code_style.borderPadding = 5
                            code_style.backColor = colors.HexColor('#f0f0f0')
                            code_style.textColor = colors.HexColor('#333333')
                        else: # Fallback if 'Code' style is somehow not in sample styles
                            styles.add(ParagraphStyle(name='Code', fontName='Courier', fontSize=9, leading=11,
                                                      borderPadding=5, backColor=colors.HexColor('#f0f0f0'), textColor=colors.HexColor('#333333'), parent=styles['Normal']))

                        # Add new custom styles or modify 'Normal' for BodyText if preferred
                        # Ensure 'BodyText' and 'ListItem' are added if they don't exist, or modified if they do.
                        # For simplicity, let's assume we are adding them if they are custom.
                        # If they could exist, a similar check-then-modify or check-then-add pattern would be robust.
                        if 'BodyText' not in styles:
                            styles.add(ParagraphStyle(name='BodyText', parent=styles['Normal'], spaceBefore=6, spaceAfter=6, alignment=TA_JUSTIFY))
                        else:
                            body_text_style = styles['BodyText']
                            body_text_style.spaceBefore = 6
                            body_text_style.spaceAfter = 6
                            body_text_style.alignment = TA_JUSTIFY
                            # Ensure parent is correct if modifying
                            # body_text_style.parent = styles['Normal']


                        if 'ListItem' not in styles:
                            styles.add(ParagraphStyle(name='ListItem', parent=styles['Normal'], leftIndent=18, spaceBefore=2, spaceAfter=2))
                        else:
                            list_item_style = styles['ListItem']
                            list_item_style.leftIndent = 18
                            list_item_style.spaceBefore = 2
                            list_item_style.spaceAfter = 2
                            # list_item_style.parent = styles['Normal']


                        story = []

                        # 解析HTML并转换为ReportLab Flowables
                        # 注意：这是一个简化的HTML解析器，可能无法处理所有复杂的HTML结构
                        soup = BeautifulSoup(html_content_for_pdf, 'html.parser')
                        
                        for element in soup.find_all(True, recursive=False): # Process top-level elements
                            if element.name == 'h1':
                                story.append(Paragraph(element.get_text(separator=' ', strip=True), styles['H1']))
                            elif element.name == 'h2':
                                story.append(Paragraph(element.get_text(separator=' ', strip=True), styles['H2']))
                            elif element.name == 'h3':
                                story.append(Paragraph(element.get_text(separator=' ', strip=True), styles['H3']))
                            elif element.name == 'p':
                                story.append(Paragraph(element.decode_contents(), styles['BodyText'])) # Use decode_contents to preserve inline HTML like <b>, <i>
                            elif element.name == 'pre':
                                code_text = element.code.get_text(separator='\n', strip=True) if element.code else element.get_text(separator='\n', strip=True)
                                story.append(Paragraph(code_text.replace(' ', '&nbsp;').replace('\n', '<br/>'), styles['Code']))
                            elif element.name in ['ul', 'ol']:
                                for li in element.find_all('li', recursive=False):
                                    story.append(Paragraph(f"• {li.decode_contents()}", styles['ListItem'])) # Simple bullet
                            elif element.name == 'table':
                                data = []
                                for row_element in element.find_all('tr'):
                                    row_data = []
                                    for cell_element in row_element.find_all(['th', 'td']):
                                        cell_content = cell_element.decode_contents()
                                        # Wrap cell content in a Paragraph for better formatting
                                        p = Paragraph(cell_content, styles['BodyText'])
                                        row_data.append(p)
                                    data.append(row_data)
                                if data:
                                    table = Table(data, repeatRows=1)
                                    table.setStyle(TableStyle([
                                        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                                        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                                        ('GRID', (0, 0), (-1, -1), 1, colors.black)
                                    ]))
                                    story.append(table)
                                    story.append(Spacer(1, 0.2 * inch))
                            elif element.name == 'hr':
                                story.append(Spacer(1, 0.1 * inch)) # Represent hr as a small spacer
                                # Or draw a line: from reportlab.graphics.shapes import Line; story.append(Line(0,0,500,0))
                            else: # Fallback for other tags
                                story.append(Paragraph(element.decode_contents(), styles['BodyText']))
                            story.append(Spacer(1, 0.1 * inch))

                        if not story: # If HTML parsing yields no flowables, add raw HTML as a fallback
                            story.append(Paragraph("<i>Could not parse HTML content for PDF, showing raw HTML:</i>", styles['Italic']))
                            story.append(Paragraph(html_content_for_pdf.replace('\n', '<br/>'), styles['Code']))

                        pdf_doc.build(story)
                        pdf_data = pdf_buffer.getvalue()
                        pdf_buffer.close()
                        
                        pdf_file_name = md_files[0].with_suffix('.pdf').name
                        st.download_button("下载PDF报告", pdf_data, file_name=pdf_file_name, mime="application/pdf", help="下载分析报告的PDF格式文件。")
                    except ImportError as e:
                        st.warning(f"PDF生成失败: 缺少必要的模块 {e}. 请安装：pip install reportlab markdown beautifulsoup4")
                    except Exception as e:
                        st.warning(f"PDF生成失败: {e}")
                with col3:
                    # 导出参考文献和相关文献CSV文件
                    output_dir = md_files[0].parent
                    ref_files = sorted(output_dir.glob("*_references_*.csv"), key=os.path.getmtime, reverse=True)
                    rel_files = sorted(output_dir.glob("*_related_pubmed_*.csv"), key=os.path.getmtime, reverse=True)
                    if ref_files:
                        with open(ref_files[0], "r", encoding="utf-8") as f:
                            ref_content = f.read()
                        st.download_button("下载参考文献CSV", ref_content, file_name=ref_files[0].name, mime="text/csv", help="下载参考文献的CSV格式文件。") 
                    if rel_files:
                        with open(rel_files[0], "r", encoding="utf-8") as f:
                            rel_content = f.read()
                        st.download_button("下载相关文献CSV", rel_content, file_name=rel_files[0].name, mime="text/csv", help="下载相关文献的CSV格式文件。")
                with col4:
                    if st.button("返回主界面", key="return_button", help="返回主界面以进行新的分析。"):
                        st.session_state.analysis_started = False # 重置状态
                        st.session_state.pipeline_output = None # 清除结果
                        st.rerun()
            else:
                st.warning("未找到生成的Markdown报告。")
    elif st.session_state.analysis_started and not st.session_state.pipeline_output:
        # 如果分析已经开始但结果还未生成（例如，在rerun之后，但结果尚未从session_state中加载）
        st.info("正在分析，请稍候...")
    else:
        # 初始状态或分析未开始
        # st.progress(0, text="准备中...") # 移除或调整这里的进度条，因为它可能与主应用的冲突
        st.info("📋 请先上传PDF文件并开始分析。") # 更清晰的初始提示
        # step_text = st.empty()
        # result_placeholder = st.empty()

    # 日志输出区
    display_log_section()

if __name__ == "__main__":
    # 此文件作为独立脚本运行时，需要从UI获取参数
    # 但通常情况下，它会被web_app.py调用
    pass
