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
        # self.chain = self._build_chain() # Chain should be built per call or with specific prompt

    @abstractmethod
    def _build_chain(self, prompt_template_str: str) -> LLMChain:
        """
        构建并返回一个LLMChain。子类必须实现此方法以定义其特定的提示和链。
        Builds and returns an LLMChain. Subclasses must implement this to define their specific prompt and chain.
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
        return json.dumps(key_data, sort_keys=True, ensure_ascii=False)

    async def _analyze(
        self,
        prompt_template_str: str,
        content: str,
        prompt_vars: Optional[Dict[str, Any]] = None,
        max_content_chars: Optional[int] = None
    ) -> Any:
        """
        使用LLM分析内容。
        Analyzes content using the LLM.
        """
        if prompt_vars is None:
            prompt_vars = {}

        # 不截断内容，直接使用完整内容
        prompt_vars["content"] = content

        try:
            chain = self._build_chain(prompt_template_str) # Build chain with the specific prompt
            response = await chain.arun(**prompt_vars) # Use arun for async
            
            # 直接返回响应内容，不尝试解析为 JSON
            return response
        except Exception as e:
            logger.error(f"LLM分析过程中发生错误: {e}")
            # An error occurred during LLM analysis: {e}
            import traceback
            logger.debug(f"错误详情 (Traceback): {traceback.format_exc()}")
            return None # Or raise a custom exception

    async def analyze_with_prompt(
        self, 
        prompt_template_str: str, 
        content: str, 
        callbacks: Optional[List[BaseCallbackHandler]] = None, # 新增 callbacks 参数
        **kwargs
    ) -> Any:
        # Generate cache key
        cache_key = self._generate_cache_key(prompt_template_str, content, kwargs)

        # Check cache first
        cached_result = self.cache_manager.get(cache_key)
        if cached_result is not None:
            logger.debug(f"Cache hit for analysis with prompt: {prompt_template_str[:50]}...")
            return cached_result

        # If not in cache, proceed with LLM call
        truncated_content = self._truncate_content(content, config.settings.MAX_CONTENT_CHARS_FOR_LLM)
        chain = self._create_llm_chain(prompt_template_str)
        try:
            # 将 callbacks 传递给 arun
            response_text = await chain.arun(content=truncated_content, callbacks=callbacks, **kwargs)

            # Cache the result
            self.cache_manager.set(cache_key, response_text)
            logger.debug(f"Cached result for analysis with prompt: {prompt_template_str[:50]}...")

            return response_text
        except Exception as e:
            logger.error(f"LLM分析过程中发生错误: {e}")
            logger.debug(f"错误详情: {kwargs}, Prompt: {prompt_template_str[:100]}")
            return f"错误：LLM分析失败 ({e})"
