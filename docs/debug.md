## 功能优化需求

1. **删除分析结果中的冗余信息**
    - 移除参考文献和相关文献的详细信息
    - 仅保留CSV导出功能的相关内容

2. **新增文献深度分析Agent**
    - 输入：解析后的MD文献文件
    - 输入：参考文献和相关文献信息
    - 功能：执行深入文献分析

3. **界面与交互优化**
    - 提升用户界面友好性，简化操作流程
    - 增加进度提示和错误反馈

4. **性能优化**
    - 优化大文件处理速度
    - 降低内存占用

5. **导出功能增强**
    - 支持多种导出格式（如Excel、JSON）
    - 增加导出字段自定义选项

## 近期调试与修复 (截至 2025-05-31)

1.  **LangChain 组件兼容性问题**
    *   **问题**: `agents/llm_analysis_agent.py` 中使用的 `LLMChain` 类在 LangChain 较新版本中已被弃用，导致 `LangChainDeprecationWarning`。
    *   **修复**: 已将所有 `LLMChain(llm=client, prompt=prompt)` 的用法更新为推荐的 `prompt | client` 语法，确保了与 LangChain 未来版本的兼容性。

2.  **元数据获取与缓存逻辑问题**
    *   **问题**: 当从缓存加载元数据时，由于 `MetadataFetchingAgent` 返回的扁平数据结构与 `app.py` 中期望的嵌套结构不一致，导致无法正确提取 `s2_paper_id` 和 `pubmed_pmid`，进而使得获取参考文献和相关文章的步骤被跳过，即使日志显示“使用完整元数据缓存”。
    *   **修复**: 修改了 `agents/metadata_fetching_agent.py` 中的 `fetch_metadata` 方法。当从缓存加载数据时，会将其转换为与API返回时一致的嵌套结构（包含 `pubmed_info` 和 `s2_info` 子字典），从而解决了 `app.py` 中的ID提取问题。

3.  **阶段性处理指标记录不完整**
    *   **问题**:
        *   "PDF内容解析" 阶段的指标被重复记录。
        *   其他主要处理阶段（如图片分析、元数据获取、LLM分析、问答生成、参考文献和相关文章获取）的耗时和状态未被记录到最终的汇总信息中。
        *   日志中 `stage_status` 的键名 "PDF内容 解析" 存在不必要的空格。
    *   **修复**:
        *   移除了 `app.py` 中对 "PDF内容解析" 阶段指标的重复记录逻辑。
        *   为所有主要处理阶段在 `app.py` 中添加了开始时间和 `record_stage` 调用，确保其耗时和状态（包括成功、失败或跳过）被正确记录和汇总。
        *   统一了 `record_stage` 调用时使用的阶段名称（无空格），确保了最终日志输出中键名的一致性。

4.  **PyTorch Flash Attention 警告** (已知未解决)
    *   **问题**: 日志中出现 `UserWarning: 1Torch was not compiled with flash attention.`
    *   **说明**: 此为 PyTorch 环境配置问题，可能影响性能，但未在本次代码修改范围内解决。
