import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional, List, Dict
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import datetime

# 保存原始系统路径
original_sys_path = sys.path.copy()

# 确保加载的是正确的.env文件
project_root = Path(__file__).parent.parent.absolute()
dotenv_path = project_root / '.env'

# 显式打印调试信息
print(f"DEBUG: 尝试从 {dotenv_path} 加载环境变量")

# 确保.env文件存在
if dotenv_path.exists():
    # 重新加载并强制覆盖现有环境变量
    load_dotenv(dotenv_path=dotenv_path, override=True)
    print(f"DEBUG: 成功加载 .env 文件")
else:
    print(f"警告: .env 文件未找到: {dotenv_path}")

# 重置系统路径以避免潜在冲突
sys.path = original_sys_path

# 当前时间戳，用于日志文件名
CURRENT_TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

def clean_env_var(raw_value: Optional[str]) -> str:
    """清理环境变量值，移除注释、空白和引号"""
    if raw_value is None:
        return ""
    # 移除行尾注释 (从 '#' 开始)
    cleaned_value = raw_value.split('#')[0].strip()
    # 移除可能存在的外部引号
    if (cleaned_value.startswith('"') and cleaned_value.endswith('"')) or \
       (cleaned_value.startswith("'") and cleaned_value.endswith("'")):
        cleaned_value = cleaned_value[1:-1]
    return cleaned_value

# 确保目录存在的函数，用于提前定义
def ensure_directories():
    """确保所有必要的目录存在"""
    directories = [
        PDF_INPUT_DIR,
        OUTPUT_BASE_DIR,
        CACHE_DIR,
        LOG_DIR,
    ]
    
    # 确保 LOG_FILE 所在的目录也存在 (如果 LOG_FILE 不在 LOG_DIR 下)
    log_file_dir = os.path.dirname(LOG_FILE)
    if log_file_dir not in directories:
        directories.append(log_file_dir)
        
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)

# API 配置 - 使用统一的方式加载环境变量
PUBMED_API_BASE_URL = clean_env_var(os.getenv("PUBMED_API_BASE_URL", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"))
DEFAULT_REQUEST_TIMEOUT = float(clean_env_var(os.getenv("DEFAULT_REQUEST_TIMEOUT", "30.0")))

# 获取 API 密钥 - 确保引号和注释都被正确去除
OPENAI_API_KEY = clean_env_var(os.getenv("OPENAI_API_KEY", ""))
DASHSCOPE_API_KEY = clean_env_var(os.getenv("DASHSCOPE_API_KEY", ""))

# 如果 DASHSCOPE_API_KEY 存在且不为空，则优先使用它作为 OPENAI_API_KEY
if DASHSCOPE_API_KEY:
    OPENAI_API_KEY = DASHSCOPE_API_KEY

# 模型配置 - 强制从环境变量重新读取
raw_model = os.environ.get("OPENAI_API_MODEL", "gpt-4")
OPENAI_API_MODEL = clean_env_var(raw_model)
print(f"DEBUG: 从环境变量直接读取的模型名称: '{raw_model}', 清理后: '{OPENAI_API_MODEL}'")

OPENAI_API_BASE_URL = clean_env_var(os.getenv("OPENAI_API_BASE_URL", "https://api.openai.com/v1"))
if not OPENAI_API_BASE_URL:  # 如果清理后为空，使用默认值
    OPENAI_API_BASE_URL = "https://api.openai.com/v1"

# 温度设置
OPENAI_TEMPERATURE = float(clean_env_var(os.getenv("OPENAI_TEMPERATURE", "0.0")))

# NCBI 配置
NCBI_EMAIL = clean_env_var(os.getenv("NCBI_EMAIL"))  # 允许为None
RELATED_ARTICLES_YEARS_BACK = int(clean_env_var(os.getenv("RELATED_ARTICLES_YEARS_BACK", "5")))
PUBMED_TOOL_NAME = clean_env_var(os.getenv("PUBMED_TOOL_NAME", "slais_pubmed_client"))
PUBMED_EFETCH_BATCH_SIZE = int(clean_env_var(os.getenv("PUBMED_EFETCH_BATCH_SIZE", "200")))
PUBMED_REQUEST_TIMEOUT = float(clean_env_var(os.getenv("PUBMED_REQUEST_TIMEOUT", "45.0")))
PUBMED_REQUEST_DELAY = float(clean_env_var(os.getenv("PUBMED_REQUEST_DELAY", "0.35")))
PUBMED_RETRY_COUNT = int(clean_env_var(os.getenv("PUBMED_RETRY_COUNT", "3")))

# 确保NCBI相关配置正确加载
NCBI_EMAIL = os.getenv("NCBI_EMAIL", "example@example.com")
RELATED_ARTICLES_MAX = int(os.getenv("RELATED_ARTICLES_MAX", "30"))
RELATED_ARTICLES_YEARS_BACK = int(os.getenv("RELATED_ARTICLES_YEARS_BACK", "10"))

# Semantic Scholar API 配置
SEMANTIC_SCHOLAR_API_KEY = clean_env_var(os.getenv("SEMANTIC_SCHOLAR_API_KEY"))  # 允许为None
SEMANTIC_SCHOLAR_API_BASE_URL = clean_env_var(os.getenv("SEMANTIC_SCHOLAR_API_BASE_URL", "https://api.semanticscholar.org/graph/v1"))
S2_REQUEST_TIMEOUT = float(clean_env_var(os.getenv("S2_REQUEST_TIMEOUT", "45.0")))
S2_CONN_LIMIT = int(clean_env_var(os.getenv("S2_CONN_LIMIT", "10")))
S2_RETRY_COUNT = int(clean_env_var(os.getenv("S2_RETRY_COUNT", "3")))
S2_BASE_RETRY_DELAY = float(clean_env_var(os.getenv("S2_BASE_RETRY_DELAY", "2.0")))
S2_JITTER_FACTOR = float(clean_env_var(os.getenv("S2_JITTER_FACTOR", "0.25")))
S2_RATE_LIMIT_WITH_KEY = int(clean_env_var(os.getenv("S2_RATE_LIMIT_WITH_KEY", "800")))
S2_RATE_LIMIT_WITHOUT_KEY = int(clean_env_var(os.getenv("S2_RATE_LIMIT_WITHOUT_KEY", "120")))
S2_RATE_LIMIT_BUFFER_FACTOR = float(clean_env_var(os.getenv("S2_RATE_LIMIT_BUFFER_FACTOR", "0.8")))
S2_DEFAULT_FIELDS = clean_env_var(os.getenv("S2_DEFAULT_FIELDS", 
    "paperId,externalIds,url,title,abstract,venue,year,referenceCount,citationCount,influentialCitationCount,isOpenAccess,fieldsOfStudy,publicationTypes,authors.name,authors.url"))
S2_REFERENCES_FIELDS = clean_env_var(os.getenv("S2_REFERENCES_FIELDS", "citedPaper.externalIds"))
S2_REFERENCES_LIMIT = int(clean_env_var(os.getenv("S2_REFERENCES_LIMIT", "1000")))

# PDF路径配置
PDF_INPUT_DIR = clean_env_var(os.getenv("PDF_INPUT_DIR", "pdfs"))
DEFAULT_PDF_PATH = clean_env_var(os.getenv("DEFAULT_PDF_PATH", os.path.join(PDF_INPUT_DIR, "example.pdf")))

# 文章DOI配置
ARTICLE_DOI = clean_env_var(os.getenv("ARTICLE_DOI"))  # 允许为None

# 输出目录配置
OUTPUT_BASE_DIR = clean_env_var(os.getenv("OUTPUT_BASE_DIR", "output"))
PDF_IMAGES_SUBDIR = clean_env_var(os.getenv("PDF_IMAGES_SUBDIR", "images"))

# 缓存配置
CACHE_DIR = clean_env_var(os.getenv("CACHE_DIR", "cache"))
CACHE_EXPIRY_DAYS = int(clean_env_var(os.getenv("CACHE_EXPIRY_DAYS", "30")))

# 日志配置
LOG_LEVEL = clean_env_var(os.getenv("LOG_LEVEL", "INFO"))
LOG_DIR = clean_env_var(os.getenv("LOG_DIR", "logs"))
LOG_FILE = os.getenv("LOG_FILE", os.path.join(LOG_DIR, f"slais_{CURRENT_TIMESTAMP}.log"))

# 分析配置
MAX_PAGES_TO_SCAN_FOR_DOI = int(clean_env_var(os.getenv("MAX_PAGES_TO_SCAN_FOR_DOI", "5")))
MAX_QUESTIONS_TO_GENERATE = int(clean_env_var(os.getenv("MAX_QUESTIONS_TO_GENERATE", "30")))

# 在模块末尾定义完所有变量后再进行目录创建
# 当模块被导入时自动确保目录存在
ensure_directories()

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Logging Configuration
    LOG_LEVEL: str = Field("INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    LOG_DIR: str = Field("logs", description="Directory for log files")

    # Analysis Configuration
    MAX_QUESTIONS_TO_GENERATE: int = Field(10, ge=1, description="Maximum number of Q&A pairs to generate")
    MAX_CONTENT_CHARS_FOR_LLM: int = Field(15000, ge=1000, description="Maximum content characters to pass to LLM for analysis tasks")

    # Derived configurations (like LOG_FILE) can be defined as properties or methods if needed
    @property
    def LOG_FILE(self) -> str:
        return os.path.join(self.LOG_DIR, f"slais_{CURRENT_TIMESTAMP}.log")
