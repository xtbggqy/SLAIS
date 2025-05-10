import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional
import datetime

# 加载项目根目录下的 .env 文件
dotenv_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=dotenv_path)

# 当前时间戳，用于日志文件名
CURRENT_TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

# API 配置
PUBMED_API_BASE_URL = os.getenv("PUBMED_API_BASE_URL", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_MODEL = os.getenv("OPENAI_API_MODEL", "gpt-4")

# NCBI 配置
NCBI_EMAIL: Optional[str] = os.getenv("NCBI_EMAIL") # 用于NCBI E-utils请求的邮箱
RELATED_ARTICLES_YEARS_BACK: int = int(os.getenv("RELATED_ARTICLES_YEARS_BACK", "5")) # 相关文献回溯年限

# Semantic Scholar API 配置
SEMANTIC_SCHOLAR_API_KEY: Optional[str] = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
SEMANTIC_SCHOLAR_API_BASE_URL: str = os.getenv("SEMANTIC_SCHOLAR_API_BASE_URL", "https://api.semanticscholar.org/graph/v1")
S2_REQUEST_TIMEOUT: float = float(os.getenv("S2_REQUEST_TIMEOUT", "45.0")) # Semantic Scholar 请求超时时间
S2_CONN_LIMIT: int = int(os.getenv("S2_CONN_LIMIT", "10")) # Semantic Scholar 并发连接限制
S2_RETRY_COUNT: int = int(os.getenv("S2_RETRY_COUNT", "3")) # Semantic Scholar 请求重试次数
S2_REQUEST_DELAY: float = float(os.getenv("S2_REQUEST_DELAY", "1.0")) # 无API Key时的基础延迟
S2_REQUEST_DELAY_WITH_KEY: float = float(os.getenv("S2_REQUEST_DELAY_WITH_KEY", "0.25")) # 有API Key时的基础延迟


# PDF路径配置
PDF_INPUT_DIR = os.getenv("PDF_INPUT_DIR", "pdfs")
DEFAULT_PDF_PATH = os.getenv("DEFAULT_PDF_PATH", os.path.join(PDF_INPUT_DIR, "example.pdf"))

# 新增：文章DOI配置
ARTICLE_DOI: Optional[str] = os.getenv("ARTICLE_DOI")

# 输出目录配置
OUTPUT_BASE_DIR = os.getenv("OUTPUT_BASE_DIR", "output")

# 缓存配置
CACHE_DIR = os.getenv("CACHE_DIR", "cache")
CACHE_EXPIRY_DAYS = int(os.getenv("CACHE_EXPIRY_DAYS", "30"))

# 日志配置
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
# 在日志文件名中添加时间戳
LOG_DIR = os.getenv("LOG_DIR", os.getenv("LOG_DIR", "logs"))
LOG_FILE = os.getenv("LOG_FILE", os.path.join(LOG_DIR, f"slais_{CURRENT_TIMESTAMP}.log"))

# 分析配置
MAX_PAGES_TO_SCAN_FOR_DOI = int(os.getenv("MAX_PAGES_TO_SCAN_FOR_DOI", "5"))
MAX_QUESTIONS_TO_GENERATE = int(os.getenv("MAX_QUESTIONS_TO_GENERATE", "30"))

# 确保必要的目录存在
def ensure_directories():
    """确保所有必要的目录存在"""
    directories = [
        PDF_INPUT_DIR,
        OUTPUT_BASE_DIR,
        CACHE_DIR,
        os.path.dirname(LOG_FILE)
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)

# 当模块被导入时自动确保目录存在
ensure_directories()
