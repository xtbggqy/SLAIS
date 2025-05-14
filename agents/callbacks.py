from typing import Any, Dict, List, Optional, Union
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from slais.utils.logging_utils import logger
import tiktoken # 用于在API未提供token数时的备用计算

# 实际成本需要根据您使用的模型和API提供商的最新费率进行配置
# 以下为示例费率 (每1000个token的成本)
MODEL_COST_PER_TOKEN = {
    "qwen-turbo": {"prompt": 0.0003 / 1000, "completion": 0.0006 / 1000}, # 示例：通义千问Turbo
    "gpt-4": {"prompt": 0.03 / 1000, "completion": 0.06 / 1000},
    "gpt-3.5-turbo": {"prompt": 0.0015 / 1000, "completion": 0.002 / 1000},
    # 根据需要添加更多模型
}

class TokenUsageCallbackHandler(BaseCallbackHandler):
    """回调处理器，用于跟踪Token使用量和估算成本。"""

    def __init__(self, model_name: str):
        super().__init__()
        self.model_name = model_name
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost = 0.0
        self._current_tiktoken_prompt_tokens = 0 # 用于临时存储当前调用的tiktoken估算值
        try:
            # 尝试为指定模型获取tiktoken编码器
            self.tokenizer = tiktoken.encoding_for_model(self.model_name)
        except KeyError:
            # 尝试移除可能的后缀，如 -instruct 或 -preview
            base_model_name = self.model_name.split('-')[0]
            try:
                self.tokenizer = tiktoken.encoding_for_model(base_model_name)
                logger.warning(
                    f"模型 '{self.model_name}' 的Tiktoken编码器未找到，但找到了基础模型 '{base_model_name}' 的编码器。"
                )
            except KeyError:
                logger.warning(
                    f"模型 '{self.model_name}' 或基础模型 '{base_model_name}' 的Tiktoken编码器未找到。 "
                    f"将使用 'cl100k_base' 作为备用。Token数可能为近似值。"
                )
                self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        """LLM运行开始时调用。使用tiktoken估算并记录完整输入提示的Token数。
        'prompts' 参数列表中的字符串是已完全渲染的提示，包括所有替换的变量（如文献全文内容）。
        """
        if prompts:
            try:
                # prompts 列表包含了发送给LLM的完整请求字符串
                self._current_tiktoken_prompt_tokens = sum(len(self.tokenizer.encode(p)) for p in prompts)
                logger.info(
                    f"LLM调用开始。输入提示Token数 (tiktoken估算, 基于完整输入): "
                    f"{self._current_tiktoken_prompt_tokens} ({len(prompts)}个提示)."
                )
                # 可选：记录一小部分提示内容以供调试，确认完整性
                # logger.debug(f"第一个提示片段 (前200字符): {prompts[0][:200]}")
                # logger.debug(f"第一个提示片段 (后200字符): {prompts[0][-200:]}")
            except Exception as e:
                logger.warning(f"使用tiktoken估算提示Token时出错: {e}")
                self._current_tiktoken_prompt_tokens = 0
        else:
            self._current_tiktoken_prompt_tokens = 0
            logger.debug("LLM调用开始，但未提供提示内容给回调函数。")

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """LLM运行结束时调用，收集Token使用信息。"""
        prompt_tokens_api = 0
        completion_tokens_api = 0
        
        if response.llm_output and 'token_usage' in response.llm_output:
            token_usage = response.llm_output['token_usage']
            prompt_tokens_api = token_usage.get('prompt_tokens', 0)
            completion_tokens_api = token_usage.get('completion_tokens', 0)

            # 如果API未提供prompt_tokens，但我们通过tiktoken估算了，可以记录这一点
            if prompt_tokens_api == 0 and self._current_tiktoken_prompt_tokens > 0:
                logger.info(
                    f"API未报告提示Token数。使用tiktoken估算值: {self._current_tiktoken_prompt_tokens}"
                )
                # 在这种情况下，可以选择使用tiktoken的估算值，但这取决于您对估算的信任程度
                # prompt_tokens_api = self._current_tiktoken_prompt_tokens # 取消注释以使用tiktoken值

            self.total_prompt_tokens += prompt_tokens_api
            self.total_completion_tokens += completion_tokens_api
            
            cost = self._calculate_cost(prompt_tokens_api, completion_tokens_api)
            self.total_cost += cost
            
            logger.info(
                f"LLM调用完成。 "
                f"提示Token (API报告): {prompt_tokens_api}, "
                f"补全Token (API报告): {completion_tokens_api}, "
                f"本次调用成本: ￥{cost:.6f}"
            )
        else:
            # 如果API未提供token_usage，记录警告。
            # 此时，如果需要，可以使用tiktoken估算的输入和输出Token。
            logger.warning(
                "LLM响应中未包含 'token_usage'。Token统计和成本估算可能不完整。"
            )
            # 如果需要用tiktoken估算输出token（输入已在on_llm_start估算）
            # completion_text = ""
            # if response.generations and response.generations[0] and response.generations[0][0]:
            #     completion_text = response.generations[0][0].text
            #     try:
            #         completion_tokens_tiktoken = len(self.tokenizer.encode(completion_text))
            #         self.total_completion_tokens += completion_tokens_tiktoken
            #         # 如果API未提供prompt_tokens，也累加tiktoken估算的prompt_tokens
            #         if self._current_tiktoken_prompt_tokens > 0:
            #            self.total_prompt_tokens += self._current_tiktoken_prompt_tokens
            #            cost = self._calculate_cost(self._current_tiktoken_prompt_tokens, completion_tokens_tiktoken)
            #            self.total_cost += cost
            #            logger.info(
            #                f"LLM调用完成 (基于tiktoken估算)。 "
            #                f"提示Token: {self._current_tiktoken_prompt_tokens}, "
            #                f"补全Token: {completion_tokens_tiktoken}, "
            #                f"本次调用成本: ￥{cost:.6f}"
            #            )
            #     except Exception as e:
            #         logger.warning(f"使用tiktoken估算补全Token时出错: {e}")

        # 重置当前调用的tiktoken估算值
        self._current_tiktoken_prompt_tokens = 0

    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """根据模型和Token数量计算成本。"""
        cost_info = MODEL_COST_PER_TOKEN.get(self.model_name)
        
        # 如果精确模型名称未找到，尝试匹配基础模型 (例如 "gpt-4" 匹配 "gpt-4-turbo")
        if not cost_info:
            for model_key_prefix in MODEL_COST_PER_TOKEN:
                if self.model_name.startswith(model_key_prefix):
                    cost_info = MODEL_COST_PER_TOKEN[model_key_prefix]
                    logger.debug(f"未找到模型 '{self.model_name}' 的精确成本，使用前缀匹配 '{model_key_prefix}' 的成本。")
                    break
        
        if cost_info:
            prompt_cost = prompt_tokens * cost_info.get("prompt", 0)
            completion_cost = completion_tokens * cost_info.get("completion", 0)
            return prompt_cost + completion_cost
        else:
            logger.warning(f"模型 '{self.model_name}' 的成本信息未找到。成本将不会被计算。")
            return 0.0

    def get_total_usage_and_cost(self) -> Dict[str, Any]:
        """返回累计的Token使用量和成本。"""
        return {
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
            "total_cost": self.total_cost,
        }

    def log_total_usage(self) -> None:
        """记录总的Token使用量和估算成本。"""
        usage = self.get_total_usage_and_cost()
        logger.info(
            f"总Token使用情况: "
            f"提示Token: {usage['total_prompt_tokens']}, "
            f"补全Token: {usage['total_completion_tokens']}, "
            f"总Token: {usage['total_tokens']}. "
            f"估算总成本: ￥{usage['total_cost']:.6f}"
        )
