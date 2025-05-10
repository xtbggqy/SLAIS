# SLAIS 项目进展文档

**版本：** 0.1 (初始文档)
**更新日期：** {{env:SYSTEM_DATE}}

## 如何运行 (调用方式)

1.  **配置环境变量**:
    *   在项目根目录下创建或修改 `.env` 文件。
    *   必须设置以下变量：
        *   `ARTICLE_DOI="your_target_article_doi"`: 指定要分析的目标文献的DOI。
        *   `NCBI_EMAIL="your_email@example.com"`: 用于NCBI API请求的邮箱地址。
    *   可选配置：
        *   `SEMANTIC_SCHOLAR_API_KEY="your_s2_api_key"`: Semantic Scholar API密钥（推荐，以获得更高的请求速率）。
        *   `RELATED_ARTICLES_YEARS_BACK="5"`: 从PubMed获取相关文献时回溯的年限（默认为5年）。
        *   其他API超时、重试次数等参数也可在 `slais/config.py` 中查看并按需在 `.env` 中覆盖。

2.  **运行主程序**:
    *   打开终端，导航到项目根目录 (`d:/C/Documents/Program/Python_file/article/ont_article`)。
    *   执行命令:
        ```bash
        python -m slais.main
        ```
    *   如果需要处理特定的本地PDF文件（而不是依赖配置中的 `DEFAULT_PDF_PATH`），可以使用 `-p` 或 `--pdf` 参数：
        ```bash
        python -m slais.main -p path/to/your/document.pdf
        ```

3.  **查看输出**:
    *   程序的运行日志和主要信息会打印在控制台。
    *   生成的Markdown文件会保存在 `output/<pdf_name_without_extension>/` 目录下。
    *   包含详细文献信息的CSV报告会保存在 `output/csv_reports/` 目录下。

---

## 目录
1.  项目结构与基本说明
2.  项目详细说明
    *   `main.py` - 主程序入口
    *   `config.py` - 配置管理
    *   `pdf_utils.py` - PDF处理工具
    *   `api_clients.py` - 外部API客户端
    *   未来计划模块

---

## 1. 项目结构与基本说明

当前项目 (SLAIS) 旨在构建一个PDF文献智能分析与洞察系统。以下是当前已建立或规划的核心文件和目录结构及其基本说明：

*   `slais/` - 项目核心代码目录。
    *   `__init__.py`: 标识 `slais` 目录为一个Python包。
    *   `main.py`: 项目的主程序入口，负责协调整个分析流程。
    *   `config.py`: 管理项目的所有配置项，如API密钥、文件路径、DOI等，主要从 `.env` 文件加载。
    *   `pdf_utils.py`: 包含PDF处理相关的工具函数，核心功能是使用 `magic_pdf` 库将PDF转换为Markdown，并计划支持表格、图像提取等。
    *   `api_clients.py`: 封装与外部API（如PubMed）交互的客户端。
    *   `utils/`: 存放通用工具模块。
        *   `logging_utils.py`: (已规划) 日志记录工具。
    *   `analyzer.py`: (已规划) 内容分析模块，将使用AI模型进行文本分析。
    *   `report_builder.py`: (已规划) 报告生成模块。
    *   `cache_manager.py`: (已规划) 缓存管理模块。
    *   `error_handler.py`: (已规划) 统一错误处理模块。
*   `tests/`: (已规划) 存放单元测试和集成测试。
*   `.env`: (项目根目录) 存储环境变量，如API密钥和特定配置（例如 `ARTICLE_DOI`）。
*   `project.md`: 项目的综合设计与规范文档。
*   `PROGRESS.md`: 本项目进展文档。

---

## 2. 项目详细说明

### `main.py` - 主程序入口

*   **当前状态：** 已实现基本框架。
*   **功能：**
    *   作为命令行应用程序的入口点 (使用 `argparse` 解析参数)。
    *   从 `slais.config` 模块获取配置，特别是 `ARTICLE_DOI` 和 `DEFAULT_PDF_PATH`。
    *   **DOI处理**：直接从配置中读取 `ARTICLE_DOI`，不再从PDF中提取。
    *   调用 `api_clients.PubMedClient` 根据DOI获取文献的标题和摘要。
    *   调用 `pdf_utils.convert_pdf_to_markdown` 将指定的PDF文件转换为Markdown格式。
    *   管理输出目录结构，将处理结果（如Markdown文件）保存到基于PDF文件名和 `OUTPUT_BASE_DIR` 配置的子目录中。
    *   使用 `asyncio` 运行异步操作（如API调用）。

### `config.py` - 配置管理

*   **当前状态：** 已实现。
*   **功能：**
    *   使用 `python-dotenv` 从项目根目录下的 `.env` 文件加载环境变量。
    *   定义并提供对项目中所有配置参数的访问，例如：
        *   `PUBMED_API_BASE_URL`
        *   `OPENAI_API_KEY`, `OPENAI_API_MODEL` (已规划)
        *   `PDF_INPUT_DIR`, `DEFAULT_PDF_PATH`
        *   `ARTICLE_DOI` (核心配置，用于指定当前处理文献的DOI)
        *   `OUTPUT_BASE_DIR`
        *   `CACHE_DIR`, `CACHE_EXPIRY_DAYS` (已规划)
        *   `LOG_LEVEL`, `LOG_FILE` (已规划)
    *   包含 `ensure_directories()` 函数，用于在程序启动时创建必要的目录（如输出目录、缓存目录、日志目录）。

### `pdf_utils.py` - PDF处理工具

*   **当前状态：** 核心Markdown转换功能已实现，其他功能部分实现或规划中。
*   **功能：**
    *   **`convert_pdf_to_markdown(pdf_path, output_dir)`**:
        *   核心功能，使用 `magic_pdf` 库将PDF文件转换为Markdown。
        *   支持 `magic_pdf` 的文本和OCR模式。
        *   将生成的Markdown文件、图片（如果存在）、内容列表JSON和中间JSON保存到指定的输出目录。
        *   之前版本中的DOI提取逻辑已移除。
    *   **`extract_images(pdf_path, output_dir)`**:
        *   从PDF中提取图像。当前实现依赖 `magic_pdf` 在转换过程中的图像保存，并列出输出目录中的图像文件。
    *   **`extract_tables(pdf_path)`**:
        *   从PDF中提取表格。当前实现为占位符，依赖 `magic_pdf` 的 `infer_result` 是否提供直接的表格对象和Markdown转换方法。需要进一步验证 `magic_pdf` 的具体API。
    *   **公式识别 (`detect_equations`)**: (已规划，见 `project.md`) 计划使用 `magic_pdf` 识别和格式化公式。

### `api_clients.py` - 外部API客户端 (已分割和重构)

*   **当前状态：** 原 `api_clients.py` 已被分割为 `pubmed_client.py` 和 `semantic_scholar_client.py`。
*   旧的 `slais/api_clients.py` 文件已被清空并标记为弃用。

### `pubmed_client.py` - PubMed API 客户端

*   **当前状态：** 已实现。
*   **`PubMedClient`**:
    *   `get_article_details(doi, email)`: 异步方法，根据DOI获取单篇PubMed文章的详细信息（包括标题、作者、期刊、发表日期、PMID、PMCID、摘要等）。
    *   `get_article_details_by_pmid(pmid, email)`: 新增异步方法，根据PMID获取单篇PubMed文章的详细信息。
    *   `get_related_articles(initial_pmid, email)`: 异步方法，获取与指定PMID文章相关的文献列表。相关文献的回溯年限可通过 `.env` 文件配置 (`RELATED_ARTICLES_YEARS_BACK`)。
    *   `batch_get_article_details_by_dois(dois, email)`: 新增异步方法，通过一批DOI批量获取文章详情。内部首先并发地将DOI转换为PMID（使用 `asyncio.Semaphore` 和延迟控制速率），然后批量通过PMID使用`efetch`获取详情。
    *   `batch_get_article_details_by_pmids(pmids, email)`: 新增异步方法，通过一批PMID批量获取文章详情。
    *   **速率控制与错误处理**:
        *   使用 `tenacity` 实现重试逻辑。
        *   在并发DOI到PMID转换时使用 `asyncio.Semaphore` 和固定延迟来控制请求速率，以减少HTTP 429错误。
        *   增加了 `httpx` 客户端的默认超时时间。

### `semantic_scholar_client.py` - Semantic Scholar API 客户端

*   **当前状态：** 已实现。
*   **`SemanticScholarClient`**:
    *   `get_paper_details_by_doi(doi)`: 异步方法，根据DOI获取单篇论文的Semantic Scholar详细信息（包括S2 PaperID、标题、作者、摘要、年份、引用数、参考文献数、`externalIds`等）。
    *   `batch_get_paper_details_by_dois(dois)`: 新增异步方法，通过一批DOI批量从Semantic Scholar获取论文的详细信息，使用 `/paper/batch` 端点。
    *   `get_references_by_paper_id(paper_id)`: 异步方法，根据S2 PaperID获取该论文的参考文献DOI列表（目前获取第一页，最多1000条）。
    *   **速率控制与错误处理**:
        *   集成了令牌桶 (`TokenBucket`) 机制，根据是否有API Key（`SEMANTIC_SCHOLAR_API_KEY`）调整请求速率。
        *   包含重试和指数退避逻辑。
        *   使用 `aiohttp` 进行异步HTTP请求。

### `main.py` - 主程序入口 (已更新)

*   **当前状态：** 功能大幅扩展。
*   **核心数据获取流程：**
    1.  **原始文章信息**：
        *   优先从 `SemanticScholarClient` 获取原始文章的详细信息。
        *   如果S2返回PMID，则调用 `PubMedClient` 通过PMID补充或核实信息。若S2无PMID，则尝试用DOI从PubMed获取。
    2.  **PubMed 相关文献**：
        *   如果获取到原始文章的PMID，则调用 `PubMedClient` 获取PubMed计算的相关文献列表。
    3.  **Semantic Scholar 参考文献**：
        *   如果获取到原始文章的S2 PaperID，则调用 `SemanticScholarClient` 获取参考文献的DOI列表。
        *   使用这些DOI，批量调用 `SemanticScholarClient` 获取这些参考文献的S2详细信息。
        *   从S2参考文献详情中提取PMID，然后批量调用 `PubMedClient` 获取这些参考文献的PubMed补充信息。
*   **CSV 输出**：
    *   将收集到的所有信息（原始文章的S2和PubMed信息、PubMed相关文献、S2参考文献的S2和PubMed信息）输出到一个统一的CSV文件 (`*_full_report.csv`)。
    *   CSV文件包含详细字段，并有 "DataSource" 列标明信息来源。
*   **配置**：
    *   从 `config.py`（进而从 `.env`）读取 `ARTICLE_DOI`, `NCBI_EMAIL`, `RELATED_ARTICLES_YEARS_BACK`, `SEMANTIC_SCHOLAR_API_KEY` 等配置。
*   **错误修复**：
    *   已修复之前日志中报告的 `TypeError` (处理作者列表时) 和缩进问题。

### 未来计划模块

根据 `project.md`，以下模块是项目后续开发的核心组成部分：

*   **`analyzer.py` (内容分析器):**
    *   利用 `OpenAIClient` 对从PDF提取的Markdown内容和PubMed摘要进行深度分析。
    *   提取核心信息（研究目的、方法、创新点等）。
    *   生成问答对。
    *   分析创新点与不足。
    *   计划使用 `pydantic` 定义数据结构，使用NLP库（如`spacy`, `nltk`）进行预处理，并可能生成可视化内容。

*   **`report_builder.py` (报告生成器):**
    *   根据分析结果生成多种格式的报告。
    *   HTML报告 (使用 `Jinja2`，可能集成CSS框架如Tailwind CSS和交互库如Alpine.js)。
    *   PDF报告 (可能使用 `weasyprint`)。
    *   演示文稿 (可能使用 `python-pptx`)。
    *   JSON数据导出。

*   **`cache_manager.py` (缓存管理器):**
    *   实现API响应和分析结果的缓存，以提高性能和减少外部调用。
    *   计划使用 `diskcache` 或 `joblib` 进行持久化缓存。

*   **`error_handler.py` (错误处理器):**
    *   集中管理错误处理逻辑。
    *   配置高级日志系统 (如 `loguru`)。

*   **`utils/logging_utils.py` 和 `utils/file_utils.py`:**
    *   提供通用的日志和文件操作辅助函数。

*   **`tests/` (测试套件):**
    *   全面的单元测试和集成测试，使用 `pytest`。
    *   模拟外部依赖，确保测试的可靠性和速度。

该文档将随着项目的进展定期更新。

Python -m slais.main
