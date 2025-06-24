"""
This module provides a factory function to create and configure LLM clients
based on the selected API provider. It uses a centralized configuration
from slais.config to manage API keys, base URLs, and model settings.
"""

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from slais.config import (
    settings,
    API_PROVIDER_CONFIGS,
    DEFAULT_API_PROVIDER,
    DEFAULT_TEXT_MODEL_FOR_API,
    OPENAI_TEMPERATURE
)
from slais.utils.logging_utils import logger

# 将API提供商名称映射到其相应的LangChain客户端类
# 对于所有兼容OpenAI API的提供商（如阿里云、DeepSeek、OpenRouter），我们都可以使用ChatOpenAI
LLM_PROVIDER_CLIENT_MAP = {
    "OpenAI": ChatOpenAI,
    "阿里云": ChatOpenAI,
    "Gemini": ChatGoogleGenerativeAI,
    "xAI": ChatOpenAI,
    "DeepSeek": ChatOpenAI,
    "OpenRouter": ChatOpenAI,
}

def get_llm_client(
    provider: str = None,
    model_name: str = None,
    temperature: float = None,
    api_key: str = None,
    base_url: str = None,
):
    """
    Creates and returns a LangChain LLM client for the specified provider.

    This function centralizes client creation, using configurations from the
    global `settings` object. It automatically handles API keys, base URLs,
    and default models for each provider.

    Args:
        provider (str, optional): The name of the API provider (e.g., "阿里云", "OpenAI").
                                  If None, defaults to `DEFAULT_API_PROVIDER`.
        model_name (str, optional): The specific model to use. If None, the default
                                    model for the provider is used.
        temperature (float, optional): The model temperature. If None, defaults to
                                       `OPENAI_TEMPERATURE`.
        api_key (str, optional): The API key. If None, it's retrieved from config.
        base_url (str, optional): The API base URL. If None, it's retrieved from config.

    Returns:
        A configured instance of a LangChain chat model client (e.g., ChatOpenAI),
        or None if the provider is not supported or configured.
    """
    provider = provider or DEFAULT_API_PROVIDER
    logger.debug(f"开始创建LLM客户端，服务商: {provider}")

    provider_config = API_PROVIDER_CONFIGS.get(provider)
    if not provider_config:
        logger.error(f"未找到服务商 '{provider}' 的配置信息。")
        return None

    # 确定API密钥和基础URL
    final_api_key = api_key or provider_config.get("api_key")
    final_base_url = base_url or provider_config.get("base_url")

    if not final_api_key:
        logger.warning(f"服务商 '{provider}' 的API密钥未设置。")
        # 允许在某些情况下（例如使用本地模型或特定代理）没有API密钥
        # return None 

    # 确定模型名称和温度
    final_model_name = model_name or DEFAULT_TEXT_MODEL_FOR_API.get(provider)
    final_temperature = temperature if temperature is not None else OPENAI_TEMPERATURE

    # 获取客户端类
    client_class = LLM_PROVIDER_CLIENT_MAP.get(provider)
    if not client_class:
        logger.error(f"不支持的服务商: {provider}")
        return None

    logger.debug(f"使用模型 '{final_model_name}' 和温度 {final_temperature}")

    try:
        # 根据客户端类型进行实例化
        if client_class == ChatOpenAI:
            logger.debug(f"创建 ChatOpenAI 客户端，Base URL: {final_base_url}")
            return ChatOpenAI(
                model=final_model_name,
                temperature=final_temperature,
                api_key=final_api_key,
                base_url=final_base_url,
            )
        elif client_class == ChatGoogleGenerativeAI:
            logger.debug("创建 ChatGoogleGenerativeAI 客户端")
            return ChatGoogleGenerativeAI(
                model=final_model_name,
                temperature=final_temperature,
                google_api_key=final_api_key,
                # Gemini不需要base_url
            )
        else:
            # 为未来可能添加的其他客户端保留扩展点
            logger.error(f"未知的客户端类型: {client_class.__name__}")
            return None
            
    except Exception as e:
        logger.error(f"创建服务商 '{provider}' 的客户端时出错: {e}", exc_info=True)
        return None

# 示例：创建一个默认客户端
# default_client = get_llm_client()
