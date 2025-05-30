from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import json
import hashlib # Import hashlib for cache key generation
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from slais.utils.logging_utils import logger
from slais import config # For MAX_CONTENT_CHARS_FOR_LLM
from langchain_core.callbacks.base import BaseCallbackHandler # 新增导入
from agents.cache.cache_manager import CacheManager # Import CacheManager

class BaseAgent(ABC):
    @abstractmethod
    async def run(self, *args, **kwargs) -> Any:
        """
        主运行方法，由子类实现。
        The main execution method to be implemented by subclasses.
        """
        pass

class ResearchAgent(BaseAgent):
    """
    研究智能体的基类，封装了与LLM交互的通用逻辑。
    Base class for research agents, encapsulating common logic for LLM interaction.
    """
    def __init__(self, llm_client: Any, provider_name: str = "unknown"): # provider_name can be used for specific logic if needed
        self.llm_client = llm_client
        self.provider_name = provider_name
        self.cache_manager = CacheManager() # Instantiate CacheManager

    @abstractmethod
    def _build_chain(self, prompt_template_str: str) -> Any: # 返回类型可以是 LCEL 链
        """
        构建并返回一个可执行的链 (例如 LangChain Expression Language runnable)。
        子类必须实现此方法以定义其特定的提示和链。
        Builds and returns an executable chain (e.g., a LangChain Expression Language runnable).
        Subclasses must implement this to define their specific prompt and chain.
        """
        pass

    def _truncate_content(self, text: str, max_chars: int) -> str:
        """
        截断内容到指定的字符数。
        Truncates content to a specified number of characters.
        """
        if len(text) > max_chars:
            logger.warning(f"内容过长 ({len(text)} 字符)，将截断为前 {max_chars} 字符。")
            # Content is too long ({len(text)} characters), truncating to the first {max_chars} characters.
            return text[:max_chars]
        return text

    def _create_llm_chain(self, prompt_template_str: Optional[str] = None, prompt_template_obj: Optional[PromptTemplate] = None):
        if prompt_template_obj:
            prompt = prompt_template_obj
        elif prompt_template_str:
            prompt = PromptTemplate.from_template(prompt_template_str)
        else:
            raise ValueError("Either prompt_template_str or prompt_template_obj must be provided.")
        
        logger.debug(f"Creating LLMChain with prompt. Input variables: {prompt.input_variables}") # Add this log
        return LLMChain(llm=self.llm_client, prompt=prompt)

    def _generate_cache_key(self, prompt_template_str: str, content: str, kwargs: Dict[str, Any]) -> str:
        """Generates a unique cache key based on prompt, content, and other kwargs."""
        # Include relevant kwargs in the key, excluding callbacks
        relevant_kwargs = {k: v for k, v in kwargs.items() if k != 'callbacks'}
        key_data = {
            "prompt_template": prompt_template_str,
            "content_hash": hashlib.sha256(content.encode('utf-8')).hexdigest(), # Use content hash to avoid large keys
            "kwargs": relevant_kwargs
        }
        # 将 kwargs 中的 content 移出，因为它用于生成哈希，其余的 kwargs 用于模板变量
        content_for_hash = kwargs.pop("content", "") # 假设 content 总是存在于 kwargs 中用于哈希
        key_data = {
            "prompt_template": prompt_template_str,
            "content_hash": hashlib.sha256(content_for_hash.encode('utf-8')).hexdigest(),
            "kwargs": kwargs # 剩余的 kwargs 是模板变量
        }
        return json.dumps(key_data, sort_keys=True, ensure_ascii=False)

    async def _invoke_llm_analysis(
        self,
        prompt_template_str: str,
        input_data: Dict[str, Any], # 包含所有模板变量的字典，包括截断后的内容
        callbacks: Optional[List[BaseCallbackHandler]] = None,
        cache_content_key: str = "content" # 指定用于生成缓存哈希的内容字段
    ) -> str:
        """
        通用的LLM分析执行方法，使用LCEL链并包含缓存逻辑。
        
        Args:
            prompt_template_str: 用于构建链和缓存键的提示模板字符串。
            input_data: 包含所有模板变量的字典。
            callbacks: LangChain回调处理器列表。
            cache_content_key: input_data 中用于生成缓存哈希的主要内容字段名。
                               默认为 "content"，但对于 DeepAnalysisAgent 可能需要传入多个字段的组合或特定字段。
                               为了简化，这里假设有一个主要的内容字段用于哈希。
                               更复杂的哈希可以基于整个 input_data (排除回调)。

        Returns:
            LLM生成的文本内容或错误信息字符串。
        """
        # 准备用于生成缓存键的 kwargs，这里我们传递整个 input_data
        # 但需要确保 content_for_hash 是从 input_data 中正确提取的
        content_for_hash = input_data.get(cache_content_key, "")
        
        # 从 input_data 复制一份用于缓存键，避免修改原始 input_data
        cache_key_kwargs = input_data.copy()
        # 将实际用于哈希的内容放入 cache_key_kwargs 以便 _generate_cache_key 使用
        cache_key_kwargs["content"] = content_for_hash 


        cache_key = self._generate_cache_key(prompt_template_str, "", cache_key_kwargs) # content 参数已包含在 cache_key_kwargs 中

        cached_result = self.cache_manager.get(cache_key)
        if cached_result is not None:
            logger.info(f"缓存命中，提示: {prompt_template_str[:50]}...")
            return cached_result

        logger.info(f"缓存未命中，执行LLM分析，提示: {prompt_template_str[:50]}...")
        chain = self._build_chain(prompt_template_str) # 子类实现此方法返回 LCEL 链

        try:
            response = await chain.ainvoke(
                input_data,
                config={"callbacks": callbacks}
            )
            
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            self.cache_manager.set(cache_key, response_text)
            logger.info(f"结果已缓存，提示: {prompt_template_str[:50]}...")
            return response_text
        except Exception as e:
            logger.error(f"LLM分析过程中发生错误: {e}")
            import traceback
            logger.debug(f"错误详情 (Traceback): {traceback.format_exc()}")
            logger.debug(f"输入数据: {input_data}")
            return f"错误：LLM分析失败 ({e})"
