import os
from pathlib import Path
from slais.utils.logging_utils import logger
from slais.pdf_utils import convert_pdf_to_markdown
from slais import config

class PDFParsingAgent:
    def __init__(self):
        pass

    async def extract_content(self, pdf_path: str) -> str:
        """提取PDF内容
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            PDF内容的Markdown格式
        """
        logger.info(f"开始解析PDF文件: {pdf_path}")
        
        # 获取PDF文件名（不含扩展名）
        pdf_filename = os.path.basename(pdf_path)
        pdf_name_without_ext = os.path.splitext(pdf_filename)[0]
        
        # 创建最终输出目录
        output_dir = os.path.join(config.OUTPUT_BASE_DIR, pdf_name_without_ext)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # 调用转换功能，直接指定最终输出目录
        md_file_path = await convert_pdf_to_markdown(pdf_path, output_dir=output_dir)
        
        # 如果返回的是文件路径，读取文件内容
        if md_file_path and os.path.isfile(md_file_path):
            try:
                with open(md_file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                logger.info(f"PDF解析完成，内容长度: {len(content)} 字符")
                return content
            except Exception as e:
                logger.error(f"读取Markdown文件失败: {e}")
                return ""
        else:
            # 如果convert_pdf_to_markdown直接返回了内容字符串而不是路径
            # (基于旧的 pdf_parsing_agent.py 逻辑，但 convert_pdf_to_markdown 现在应返回路径)
            if isinstance(md_file_path, str) and len(md_file_path) > 100:  # 假设内容长度>100是文本内容
                logger.info(f"PDF解析完成，内容长度: {len(md_file_path)} 字符")
                return md_file_path
            else:
                logger.warning("PDF转换未返回有效的Markdown文件内容或路径")
                return ""
