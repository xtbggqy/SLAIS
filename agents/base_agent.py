from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from slais.utils.logging_utils import logger
from slais import config # For MAX_CONTENT_CHARS_FOR_LLM

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

        current_max_chars = max_content_chars if max_content_chars is not None else config.MAX_CONTENT_CHARS_FOR_LLM
        
        truncated_content = self._truncate_content(content, max_chars=current_max_chars)
        
        prompt_vars["content"] = truncated_content

        try:
            chain = self._build_chain(prompt_template_str) # Build chain with the specific prompt
            response = await chain.arun(**prompt_vars) # Use arun for async
            
            # Attempt to parse JSON if response is a string
            if isinstance(response, str):
                try:
                    # Basic cleaning for common markdown code block fences
                    cleaned_response = response.strip()
                    if cleaned_response.startswith("```json"):
                        cleaned_response = cleaned_response[7:]
                    if cleaned_response.startswith("```"):
                         cleaned_response = cleaned_response[3:]
                    if cleaned_response.endswith("```"):
                        cleaned_response = cleaned_response[:-3]
                    
                    # Remove trailing commas before closing brackets/braces
                    cleaned_response = cleaned_response.replace(r',\s*]', ']').replace(r',\s*}', '}')

                    return json.loads(cleaned_response.strip())
                except json.JSONDecodeError:
                    logger.warning(f"LLM响应不是有效的JSON格式，将按原样返回字符串。响应: {response[:200]}...")
                    # LLM response is not valid JSON, returning string as is. Response: {response[:200]}...
                    return response # Return as string if not parsable
            return response # If already a dict (e.g. from a PydanticOutputParser)
        except Exception as e:
            logger.error(f"LLM分析过程中发生错误: {e}")
            # An error occurred during LLM analysis: {e}
            import traceback
            logger.debug(f"错误详情 (Traceback): {traceback.format_exc()}")
            return None # Or raise a custom exception
