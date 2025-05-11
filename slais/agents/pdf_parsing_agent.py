class PDFParsingAgent:
    """PDF解析智能体，处理PDF文件并提取内容"""
    
    async def extract_content(self, pdf_path):
        """提取PDF内容
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            PDF内容的Markdown格式
        """
        from slais.utils.logging_utils import logger
        from slais.pdf_utils import convert_pdf_to_markdown
        from slais import config
        import os
        from pathlib import Path
        
        logger.info(f"开始解析PDF文件: {pdf_path}")
        
        # 获取PDF文件名（不含扩展名）
        pdf_filename = os.path.basename(pdf_path)
        pdf_name_without_ext = os.path.splitext(pdf_filename)[0]
        
        # 创建最终输出目录
        output_dir = os.path.join(config.OUTPUT_BASE_DIR, pdf_name_without_ext)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # 调用转换功能，直接指定最终输出目录
        markdown_content = await convert_pdf_to_markdown(pdf_path, output_dir=output_dir)
        
        logger.info(f"PDF解析完成，内容长度: {len(markdown_content)} 字符")
        return markdown_content