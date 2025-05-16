# SLAIS 项目进展文档

**版本：** 0.5 (更新于2025-05-16)
**上次更新日期：** 2025-05-16

## 如何运行 (调用方式)
# 推荐用法
streamlit run main.py -- --web
1.  **配置环境变量**:
    *   在项目根目录下创建或修改 `.env` 文件。
    *   必须设置以下变量：
        *   `ARTICLE_DOI="your_target_article_doi"`: 指定要分析的目标文献的DOI。
        *   `NCBI_EMAIL="your_email@example.com"`: 用于NCBI API请求的邮箱地址。
        *   `OPENAI_API_KEY="your_openai_key"`: OpenAI API密钥，用于AI分析功能。
    *   可选配置：
        *   `SEMANTIC_SCHOLAR_API_KEY="your_s2_api_key"`: Semantic Scholar API密钥（推荐，以获得更高的请求速率）。
        *   `RELATED_ARTICLES_YEARS_BACK="5"`: 从PubMed获取相关文献时回溯的年限（默认为5年）。
        *   `OPENAI_API_MODEL="gpt-4o"`: 指定使用的OpenAI模型（默认为gpt-4o）。
        *   `OPENAI_API_BASE_URL="your_api_url"`: 可选的OpenAI API基础URL，用于使用兼容的替代API。
        *   `OUTPUT_BASE_DIR="output"`: 输出目录的基础路径。
        *   `MAX_CONTENT_CHARS_FOR_LLM=60000`: 传递给LLM的最大文本字符数。
        *   `MAX_QUESTIONS_TO_GENERATE=30`: 生成的问题数量上限。
        *   其他API超时、重试次数等参数也可在 `slais/config.py` 中查看并按需在 `.env` 中覆盖。

2.  **运行主程序**:
    *   打开终端，导航到项目根目录 (`d:/C/Documents/Program/Python_file/article/ont_article`)。
    *   执行命令:
        ```bash
        python main.py
        ```
    *   如果需要处理特定的本地PDF文件（而不是依赖配置中的 `DEFAULT_PDF_PATH`），可以使用 `--pdf` 参数：
        ```bash
        python main.py --pdf path/to/your/document.pdf
        ```

3.  **查看输出**:
    *   程序的运行日志和主要信息会打印在控制台。
    *   生成的Markdown报告会保存在 `output/<pdf_name_without_extension>/` 目录下。
    *   参考文献和相关文章的CSV文件会保存在相同目录下。

---

## 目录
1.  项目结构与基本说明
2.  项目详细说明
    *   `main.py` - 主程序入口
    *   `agents/` - 智能代理模块
    *   `slais/` - 核心功能模块
3.  主要功能流程
4.  最新更新
5.  未来计划

---

## 1. 项目结构与基本说明

当前项目 (SLAIS) 已发展为一个完整的PDF文献智能分析与洞察系统。以下是当前已实现的核心文件和目录结构及其基本说明：

*   `main.py`: 项目的主程序入口，协调整个分析流程。
*   `agents/` - 智能代理模块。
    *   `base_agent.py`: 基础代理类定义，提供公共功能。
    *   `callbacks.py`: LLM调用的回调处理，用于追踪token使用和成本。
    *   `formatting_utils.py`: 输出格式化工具，用于美化报告和修复Mermaid代码。
    *   `llm_analysis_agent.py`: 多种LLM分析代理实现，包括方法学分析、创新点提取、问答生成等。
    *   `metadata_fetching_agent.py`: 元数据获取代理，从外部API获取文献相关信息。
    *   `pdf_parsing_agent.py`: PDF解析代理，负责从PDF文件提取结构化内容。
    *   `prompts.py`: LLM提示模板定义。
*   `slais/` - 核心功能模块。
    *   `__init__.py`: 包初始化。
    *   `config.py`: 配置管理，从.env文件加载环境变量。
    *   `utils/`: 工具函数集合。
        *   `logging_utils.py`: 日志工具，配置日志系统。
*   `.env`: 存储环境变量，如API密钥和特定配置。
*   `output/`: 输出目录，存放生成的报告和CSV文件。
*   `PROGRESS.md`: 本项目进展文档。

---

## 2. 项目详细说明

### `main.py` - 主程序入口

*   **当前状态：** 已实现完整功能。
*   **功能：**
    *   作为命令行应用程序的入口点 (使用 `argparse` 解析参数)。
    *   协调全文分析流水线的各个组件。
    *   从 `.env` 文件获取配置，包括 `ARTICLE_DOI`、`OPENAI_API_KEY` 等。
    *   管理异步工作流，使用 `asyncio` 并行处理各种任务。
    *   生成并保存格式化的分析报告和相关CSV数据。

### `agents/` - 智能代理模块

#### `base_agent.py` - 基础代理类

*   **当前状态：** 已实现。
*   **功能：**
    *   定义了 `ResearchAgent` 基类，为所有智能代理提供通用方法和属性。
    *   包括 LLM 初始化、内容截断、LLM 链创建等功能。
    *   提供统一的抽象接口，确保各个具体代理实现一致的行为模式。

#### `callbacks.py` - LLM回调处理

*   **当前状态：** 已实现。
*   **功能：**
    *   实现 `TokenUsageCallbackHandler`，用于追踪 LLM API 调用的 token 使用情况。
    *   计算各种 OpenAI 模型的 API 调用成本。
    *   提供详细的 token 消耗和成本日志。

#### `formatting_utils.py` - 输出格式化工具

*   **当前状态：** 已实现。
*   **功能：**
    *   提供 Mermaid 脑图代码的格式化和修复功能。
    *   实现高级 Markdown 报告生成器，支持折叠区域、表格和样式美化。
    *   包含问答对格式化、方法学分析格式化等专用函数。
    *   提供合理的错误处理和默认内容生成。

#### `llm_analysis_agent.py` - LLM分析代理

*   **当前状态：** 已实现多种具体代理。
*   **功能：**
    *   `MethodologyAnalysisAgent`: 分析研究方法、关键技术、优缺点等。
    *   `InnovationExtractionAgent`: 提取文献的核心创新点、解决的问题和应用前景。
    *   `QAGenerationAgent`: 生成与文献相关的问题，并批量提供详细答案。
    *   `StorytellingAgent`: 以叙事方式解释研究内容，使其更易理解。
    *   `MindMapAgent`: 生成文献内容的结构化思维导图。

#### `metadata_fetching_agent.py` - 元数据获取代理

*   **当前状态：** 已实现。
*   **功能：**
    *   封装与外部 API（如 PubMed、Semantic Scholar）的交互。
    *   获取文献的元数据，包括标题、作者、摘要等。
    *   获取文献的参考文献和相关文章。
    *   实现请求速率限制和错误处理。

#### `pdf_parsing_agent.py` - PDF解析代理

*   **当前状态：** 已实现。
*   **功能：**
    *   从PDF文件提取结构化文本内容。
    *   处理表格、图片等非文本元素。
    *   将提取的内容转换为 Markdown 格式，便于后续分析。

#### `prompts.py` - LLM提示模板

*   **当前状态：** 已实现。
*   **功能：**
    *   定义用于各种分析任务的 LLM 提示模板。
    *   包括方法学分析、创新点提取、问答生成、故事讲述和思维导图生成的模板。
    *   提供结构化的输出指导，确保 LLM 生成符合预期格式的内容。

### `slais/` - 核心功能模块

#### `config.py` - 配置管理

*   **当前状态：** 已实现。
*   **功能：**
    *   使用 `python-dotenv` 从 `.env` 文件加载环境变量。
    *   提供对项目所有配置参数的访问。
    *   确保必要的目录结构存在。

#### `pubmed_client.py` - PubMed API 客户端

*   **当前状态：** 已实现并优化
*   **功能：**
    *   实现与 PubMed API 的异步通信
    *   获取文献元数据和相关文章
    *   使用多种方法提取文献 DOI（通过 PubMed XML 和 CrossRef API）
    *   处理批量请求和并发操作
    *   实现智能错误处理和重试机制
    *   提供灵活的配置选项，如搜索年限和最大结果数

#### `utils/logging_utils.py` - 日志工具

*   **当前状态：** 已实现。
*   **功能：**
    *   配置统一的日志系统。
    *   提供不同级别的日志记录功能。
    *   设置日志格式和输出目的地。

---

## 3. 主要功能流程

当前版本的 SLAIS 系统实现了一个完整的文献分析流水线，包括以下主要步骤：

1. **PDF内容提取**：从指定的PDF文件中提取文本内容，转换为Markdown格式。
2. **元数据获取**：通过DOI从PubMed和Semantic Scholar获取文献的基本信息。
3. **方法学分析**：分析研究方法、关键技术、数据来源等，评估其优缺点和创新性。
4. **创新点提取**：识别并提取文献的核心创新贡献、解决的问题和潜在应用。
5. **问答生成**：根据文献内容生成一系列问题，并提供详细答案，帮助理解关键概念。
6. **参考文献获取**：获取文献引用的其他论文信息，构建知识网络。
7. **相关文章检索**：从PubMed获取与当前文献相关的其他研究。
8. **故事化讲述**：将技术内容以易于理解的叙事方式重新表述。
9. **思维导图生成**：创建可视化的结构图，展示文献的逻辑组织。
10. **报告生成**：将所有分析结果整合为一个美观、结构化的Markdown报告。

系统现已支持异步操作和并行处理，大大提高了处理效率，特别是在处理大型文献或批量获取参考文献信息时。

---

## 4. 最新更新

### 2025-05-16：报告美观性与交互性优化

*   **Markdown报告美化**:
    *   增强了报告的结构化，统一使用表格、折叠区域、分割线等元素。
    *   增加了目录锚点、LOGO、页眉页脚和自定义CSS样式，兼容Typora/Obsidian等主流Markdown阅读器。
    *   图片支持缩略图预览和点击放大，Mermaid脑图自动格式化。
    *   支持折叠/展开详情，提升交互体验。

*   **Token消耗与成本统计**:
    *   LLM调用支持token消耗和成本的自动统计与日志输出。
    *   计划支持token消耗的可视化统计和报告输出。

*   **缓存与性能**:
    *   优化了 `CacheManager`，支持API响应和LLM分析结果的持久化缓存。
    *   针对大文件和重复任务优化缓存命中率。

### 2025-05-15：增强 DOI 提取机制

*   **PubMed 客户端 DOI 提取改进**:
    *   增强了 `parse_pubmed_article` 函数以从多个 XML 元素位置提取 DOI:
        *   PubmedData/ArticleIdList
        *   Article/ELocationID
        *   Article/ArticleIdList
    *   添加了 `_get_doi_from_pmid_crossref` 异步方法作为备用 DOI 获取机制
    *   实现了批量并行 DOI 查询以提高效率
    
*   **CrossRef API 集成**:
    *   添加了与 CrossRef API 的集成，用作 PubMed 未提供 DOI 时的备用数据源
    *   使用 `httpx` 实现异步请求处理
    *   实现了智能错误处理和日志记录
    
*   **类型系统优化**:
    *   在 `ArticleDetails` TypedDict 中添加了 `doi` 字段
    *   改进了代码中的类型注解以增强类型安全性
    
*   **异步性能优化**:
    *   使用 `asyncio.gather` 实现批量并行 DOI 查询
    *   优化了异步上下文管理器的使用
    *   改进了请求流程以减少 API 调用次数

### 2025-05-10：配置扩展

*   **可配置问题生成**:
    *   在 QA_GENERATION_PROMPT 中使用 `{num_questions}` 占位符
    *   通过 `.env` 中的 MAX_QUESTIONS_TO_GENERATE 参数控制生成问题数量
    *   更新了相关代理以支持可配置的问题数量

---

## 5. 未来计划

1. **报告多格式导出与主题定制**:
   * 支持Markdown、HTML、PDF等多格式报告导出。
   * 输出结构与样式分离，便于主题切换和定制。
   * 支持多语言报告模板。

2. **数据整合增强**:
   * 整合更多学术数据源 (如 Dimensions, OpenAlex)
   * 实现引用网络分析和可视化
   * 添加引文指标分析功能

3. **用户界面改进**:
   * 开发简单的 Web 界面，使非技术用户更容易使用系统
   * 添加进度指示器和实时反馈
   * 提供可交互的报告查看体验

4. **分析能力增强**:
   * 实现跨文献比较分析
   * 添加时间趋势分析和研究热点识别
   * 引入文献质量评估标准

5. **批量处理能力**:
   * 支持一次分析多篇文献，生成综合报告
   * 实现定期自动分析特定领域的新发表文献
   * 添加基于主题的文献分组和归类

6. **多语言支持**:
   * 添加对非英语文献的支持
   * 提供多语言报告生成选项
   * 实现跨语言文献比较

7. **性能与可靠性优化**:
   * 改进缓存策略，减少重复 API 调用
   * 优化大型文献的处理效率
   * 增强错误恢复和断点续传能力
   * 添加分布式处理支持，提高大批量分析效率

8. **数据质量改进**:
   * 实现更智能的 DOI 和元数据补全算法
   * 添加文献数据清洗和规范化流程
   * 开发重复和冲突数据检测机制

---

*最后更新: 2025-05-16*
