import logging
import sys
import os
import datetime
import re
from ..config import LOG_LEVEL, LOG_FILE, ensure_directories

# 确保日志目录存在
ensure_directories()

# 创建一个日志过滤器，用于过滤掉不需要的日志
class LogFilter(logging.Filter):
    def __init__(self, exclude_patterns=None):
        super().__init__()
        self.exclude_patterns = exclude_patterns or [
            # 模型加载和配置相关
            r'loading configuration file',
            r'loading weights file',
            r'Model config',
            r'Generate config',
            r'Instantiating',
            r'loading file',
            r'All model checkpoint',
            r'All the weights',
            r'If your task',
            r'DocAnalysis init done',
            # PDF处理相关进度信息
            r'magic_pdf',
            r'Layout Predict',
            r'MFD Predict',
            r'MFR Predict', 
            r'OCR-det Predict',
            r'Table Predict',
            r'Processing pages',
            # 其他详细技术信息
            r'architectures',
            r'decoder',
            r'encoder',
            r'attention_heads',
            r'model_type',
            r'torch_dtype',
            r'transformers_version'
        ]
        self.exclude_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.exclude_patterns]
    
    def filter(self, record):
        # 获取日志消息
        try:
            message = record.getMessage()
            # 检查消息是否匹配任何排除模式
            for pattern in self.exclude_patterns:
                if pattern.search(message):
                    return False
            return True
        except Exception:
            # 如果获取消息出错，仍然允许记录
            return True

# 创建一个自定义的日志记录器类
class RunSessionLogger(logging.Logger):
    def __init__(self, name, level=logging.NOTSET):
        super(RunSessionLogger, self).__init__(name, level)
        
        # 记录会话开始消息
        current_time = datetime.datetime.now()
        formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
        self.info(f"=== SLAIS 会话开始: {formatted_time} ===")

# 注册自定义的Logger类
logging.setLoggerClass(RunSessionLogger)

# 创建或获取一个logger - 基本配置
logger = logging.getLogger('slais_app')
logger.setLevel(LOG_LEVEL.upper()) # 设置级别，但此时还没有处理器

# 日志过滤器实例
log_filter = LogFilter()

def setup_logging():
    """配置并激活日志记录器，包括处理器和格式化器。"""
    # 确保日志目录存在 (config.py中已调用，这里可以再次确认或移除)
    # ensure_directories() # 如果config.py导入时已确保，这里可能多余

    logger.addFilter(log_filter)

    # 如果logger已经有处理器，先移除它们以避免重复添加 (防止多次调用setup_logging)
    if logger.handlers:
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
    
    # 创建一个handler，用于写入日志文件
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8', mode='w')
    file_handler.setLevel(LOG_LEVEL.upper())
    file_handler.addFilter(log_filter)

    # 创建一个handler，用于将日志输出到控制台
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(LOG_LEVEL.upper()) # 控制台也应用LOG_LEVEL
    console_handler.addFilter(log_filter)

    # 定义handler的输出格式
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # 给logger添加handler
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # 配置其他库的日志级别 (减少外部库日志输出)
    for lib_logger_name in ['magic_pdf', 'transformers', 'PIL', 'httpx', 'matplotlib', 'huggingface_hub', 'anyio', 'httpcore']:
        lib_logger = logging.getLogger(lib_logger_name)
        lib_logger.setLevel(logging.WARNING) # 将第三方库日志级别设为WARNING或更高

    # 根记录器过滤器 (如果需要全局过滤print等)
    # root_logger = logging.getLogger()
    # root_logger.addFilter(log_filter) # 谨慎添加，可能影响其他非本项目日志

    # 记录启动消息 - 现在由调用者（如main.py）在setup_logging后记录
    logger.info(f"SLAIS 日志系统已启动 - 日志文件: {LOG_FILE}")

# 注意：不再在模块导入时自动记录 "SLAIS 应用程序启动" 消息。
# setup_logging() 函数需要被显式调用。
