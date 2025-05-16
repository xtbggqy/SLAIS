import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional, List, Dict, Any
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

class Settings(BaseSettings):
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    # API Configuration
    PUBMED_API_BASE_URL: str = Field("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/", description="Base URL for PubMed API")
    DEFAULT_REQUEST_TIMEOUT: float = Field(30.0, description="Default timeout for API requests")

    # API Keys
    OPENAI_API_KEY: str = Field("", description="API key for OpenAI or compatible API")
    DASHSCOPE_API_KEY: str = Field("", description="API key for DashScope (优先于OPENAI_API_KEY)")

    # Model Configuration
    OPENAI_API_MODEL: str = Field("gpt-4", description="Model name for OpenAI or compatible API")
    OPENAI_API_BASE_URL: Optional[str] = Field("https://api.openai.com/v1", description="Base URL for OpenAI or compatible API (optional)")
    OPENAI_TEMPERATURE: float = Field(0.0, description="Temperature for OpenAI or compatible API")

    # 图像 LLM 配置
    IMAGE_LLM_API_KEY: str = Field("", description="API key for Image LLM")
    IMAGE_LLM_API_MODEL: str = Field("qwen-vl-plus", description="Model name for Image LLM")
    IMAGE_LLM_API_BASE_URL: str = Field("", description="Base URL for Image LLM")
    IMAGE_LLM_TEMPERATURE: float = Field(0.1, description="Temperature for Image LLM")

    # NCBI Configuration
    NCBI_EMAIL: Optional[str] = Field(None, description="Email address for NCBI API requests")
    RELATED_ARTICLES_YEARS_BACK: int = Field(5, description="Years back to search for related articles in PubMed")
    PUBMED_TOOL_NAME: str = Field("slais_pubmed_client", description="Tool name for PubMed API requests")
    PUBMED_EFETCH_BATCH_SIZE: int = Field(200, description="Batch size for PubMed efetch requests")
    PUBMED_REQUEST_TIMEOUT: float = Field(45.0, description="Timeout for PubMed API requests")
    PUBMED_REQUEST_DELAY: float = Field(0.35, description="Delay between PubMed API requests")
    PUBMED_RETRY_COUNT: int = Field(3, description="Retry count for PubMed API requests")
    RELATED_ARTICLES_MAX: int = Field(30, description="Maximum number of related articles to fetch from PubMed")

    # Semantic Scholar API Configuration
    SEMANTIC_SCHOLAR_API_KEY: Optional[str] = Field(None, description="API key for Semantic Scholar API")
    SEMANTIC_SCHOLAR_API_BASE_URL: str = Field("https://api.semanticscholar.org/graph/v1", description="Base URL for Semantic Scholar API")
    SEMANTIC_SCHOLAR_GRAPH_API_BASE_URL: str = Field("https://api.semanticscholar.org/graph/v1", description="Base URL for Semantic Scholar Graph API")
    SEMANTIC_SCHOLAR_API_BATCH_SIZE: int = Field(10, description="Batch size for Semantic Scholar API requests")
    SEMANTIC_SCHOLAR_REQUEST_DELAY: float = Field(0.5, description="Delay between Semantic Scholar API requests")
    SEMANTIC_SCHOLAR_RETRY_COUNT: int = Field(3, description="Retry count for Semantic Scholar API requests")
    SEMANTIC_SCHOLAR_TIMEOUT: float = Field(30.0, description="Timeout for Semantic Scholar API requests")
    SEMANTIC_SCHOLAR_MAX_REFERENCES_PER_PAGE: int = Field(100, description="Maximum number of references per page for Semantic Scholar API")

    S2_REQUEST_TIMEOUT: float = Field(45.0, description="Timeout for Semantic Scholar API requests")
    S2_CONN_LIMIT: int = Field(10, description="Connection limit for Semantic Scholar API")
    S2_RETRY_COUNT: int = Field(3, description="Retry count for Semantic Scholar API requests")
    S2_BASE_RETRY_DELAY: float = Field(2.0, description="Base retry delay for Semantic Scholar API")
    S2_JITTER_FACTOR: float = Field(0.25, description="Jitter factor for Semantic Scholar API retry delay")
    S2_RATE_LIMIT_WITH_KEY: int = Field(800, description="Rate limit per minute with Semantic Scholar API key")
    S2_RATE_LIMIT_WITHOUT_KEY: int = Field(120, description="Rate limit per minute without Semantic Scholar API key")
    S2_RATE_LIMIT_BUFFER_FACTOR: float = Field(0.8, description="Buffer factor for Semantic Scholar API rate limit")
    S2_DEFAULT_FIELDS: str = Field("paperId,externalIds,url,title,abstract,venue,year,referenceCount,citationCount,influentialCitationCount,isOpenAccess,fieldsOfStudy,publicationTypes,authors,authors.name,authors.url", description="Default fields to retrieve from Semantic Scholar API")
    S2_REFERENCES_FIELDS: str = Field("citedPaper.externalIds", description="Fields to retrieve for references from Semantic Scholar API")
    S2_REFERENCES_LIMIT: int = Field(1000, description="Limit for retrieving references from Semantic Scholar API")

    # PDF Path Configuration
    PDF_INPUT_DIR: str = Field("pdfs", description="Directory for input PDF files")
    DEFAULT_PDF_PATH: str = Field("pdfs/example.pdf", description="Default path for PDF file to process")

    # Article DOI Configuration
    ARTICLE_DOI: Optional[str] = Field(None, description="DOI of the article to process")

    # Output Directory Configuration
    OUTPUT_BASE_DIR: str = Field("output", description="Base directory for output files")
    PDF_IMAGES_SUBDIR: str = Field("images", description="Subdirectory for PDF images within output")

    # Cache Configuration
    CACHE_DIR: str = Field("cache", description="Directory for cache files")
    CACHE_EXPIRY_DAYS: int = Field(30, description="Cache expiry in days")

    # Logging Configuration
    LOG_LEVEL: str = Field("INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    LOG_DIR: str = Field("logs", description="Directory for log files")

    # Analysis Configuration
    MAX_PAGES_TO_SCAN_FOR_DOI: int = Field(5, description="Maximum pages to scan for DOI in PDF")
    MAX_QUESTIONS_TO_GENERATE: int = Field(int(os.getenv("MAX_QUESTIONS_TO_GENERATE", 30)), ge=1, description="Maximum number of Q&A pairs to generate")
    MAX_CONTENT_CHARS_FOR_LLM: int = Field(15000, ge=1000, description="Maximum content characters to pass to LLM for analysis tasks")

    # markdown子目录名，可在.env中配置，未配置时自动为 <pdf_stem>_markdown
    MARKDOWN_SUBDIR: str = ""

    # Derived configurations (like LOG_FILE) can be defined as properties or methods if needed
    @property
    def LOG_FILE(self) -> str:
        return os.path.join(self.LOG_DIR, f"slais_{CURRENT_TIMESTAMP}.log")

    # Ensure directories exist after settings are loaded
    def model_post_init(self, __context: Any) -> None:
        """Ensure directories exist after settings are loaded."""
        directories = [
            self.PDF_INPUT_DIR,
            self.OUTPUT_BASE_DIR,
            self.CACHE_DIR,
            self.LOG_DIR,
            os.path.dirname(self.LOG_FILE), # Ensure log file directory exists
        ]
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)

# Create a global settings instance
settings = Settings(_env_file=".env", _env_file_encoding="utf-8")

# 添加关键配置的调试输出
print(f"DEBUG: 配置加载完成，S2批处理大小: {settings.SEMANTIC_SCHOLAR_API_BATCH_SIZE}")
print(f"DEBUG: 从环境变量加载的DOI: {settings.ARTICLE_DOI}")
print(f"DEBUG: 最大问题生成数量: {settings.MAX_QUESTIONS_TO_GENERATE}")

# Update module-level variables to use the settings instance
PUBMED_API_BASE_URL = settings.PUBMED_API_BASE_URL
DEFAULT_REQUEST_TIMEOUT = settings.DEFAULT_REQUEST_TIMEOUT
OPENAI_API_KEY = settings.OPENAI_API_KEY
DASHSCOPE_API_KEY = settings.DASHSCOPE_API_KEY
OPENAI_API_MODEL = settings.OPENAI_API_MODEL
OPENAI_API_BASE_URL = settings.OPENAI_API_BASE_URL
OPENAI_TEMPERATURE = settings.OPENAI_TEMPERATURE
IMAGE_LLM_API_KEY = settings.IMAGE_LLM_API_KEY
IMAGE_LLM_API_MODEL = settings.IMAGE_LLM_API_MODEL
IMAGE_LLM_API_BASE_URL = settings.IMAGE_LLM_API_BASE_URL
IMAGE_LLM_TEMPERATURE = settings.IMAGE_LLM_TEMPERATURE
NCBI_EMAIL = settings.NCBI_EMAIL
RELATED_ARTICLES_YEARS_BACK = settings.RELATED_ARTICLES_YEARS_BACK
PUBMED_TOOL_NAME = settings.PUBMED_TOOL_NAME
PUBMED_EFETCH_BATCH_SIZE = settings.PUBMED_EFETCH_BATCH_SIZE
PUBMED_REQUEST_TIMEOUT = settings.PUBMED_REQUEST_TIMEOUT
PUBMED_REQUEST_DELAY = settings.PUBMED_REQUEST_DELAY
PUBMED_RETRY_COUNT = settings.PUBMED_RETRY_COUNT
RELATED_ARTICLES_MAX = settings.RELATED_ARTICLES_MAX
SEMANTIC_SCHOLAR_API_KEY = settings.SEMANTIC_SCHOLAR_API_KEY
SEMANTIC_SCHOLAR_API_BASE_URL = settings.SEMANTIC_SCHOLAR_API_BASE_URL
SEMANTIC_SCHOLAR_GRAPH_API_BASE_URL = settings.SEMANTIC_SCHOLAR_GRAPH_API_BASE_URL
SEMANTIC_SCHOLAR_API_BATCH_SIZE = settings.SEMANTIC_SCHOLAR_API_BATCH_SIZE
SEMANTIC_SCHOLAR_REQUEST_DELAY = settings.SEMANTIC_SCHOLAR_REQUEST_DELAY
SEMANTIC_SCHOLAR_RETRY_COUNT = settings.SEMANTIC_SCHOLAR_RETRY_COUNT
SEMANTIC_SCHOLAR_TIMEOUT = settings.SEMANTIC_SCHOLAR_TIMEOUT
SEMANTIC_SCHOLAR_MAX_REFERENCES_PER_PAGE = settings.SEMANTIC_SCHOLAR_MAX_REFERENCES_PER_PAGE
S2_REQUEST_TIMEOUT = settings.S2_REQUEST_TIMEOUT
S2_CONN_LIMIT = settings.S2_CONN_LIMIT
S2_RETRY_COUNT = settings.S2_RETRY_COUNT
S2_BASE_RETRY_DELAY = settings.S2_BASE_RETRY_DELAY
S2_JITTER_FACTOR = settings.S2_JITTER_FACTOR
S2_RATE_LIMIT_WITH_KEY = settings.S2_RATE_LIMIT_WITH_KEY
S2_RATE_LIMIT_WITHOUT_KEY = settings.S2_RATE_LIMIT_WITHOUT_KEY
S2_RATE_LIMIT_BUFFER_FACTOR = settings.S2_RATE_LIMIT_BUFFER_FACTOR
S2_DEFAULT_FIELDS = settings.S2_DEFAULT_FIELDS
S2_REFERENCES_FIELDS = settings.S2_REFERENCES_FIELDS
S2_REFERENCES_LIMIT = settings.S2_REFERENCES_LIMIT
PDF_INPUT_DIR = settings.PDF_INPUT_DIR
DEFAULT_PDF_PATH = settings.DEFAULT_PDF_PATH
ARTICLE_DOI = settings.ARTICLE_DOI
OUTPUT_BASE_DIR = settings.OUTPUT_BASE_DIR
PDF_IMAGES_SUBDIR = settings.PDF_IMAGES_SUBDIR
CACHE_DIR = settings.CACHE_DIR
CACHE_EXPIRY_DAYS = settings.CACHE_EXPIRY_DAYS
LOG_LEVEL = settings.LOG_LEVEL
LOG_DIR = settings.LOG_DIR
LOG_FILE = settings.LOG_FILE
MAX_PAGES_TO_SCAN_FOR_DOI = settings.MAX_PAGES_TO_SCAN_FOR_DOI
MAX_QUESTIONS_TO_GENERATE = settings.MAX_QUESTIONS_TO_GENERATE
MAX_CONTENT_CHARS_FOR_LLM = settings.MAX_CONTENT_CHARS_FOR_LLM
