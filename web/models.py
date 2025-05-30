import re
from pathlib import Path
from slais.utils.logging_utils import logger
from slais import config # 导入 slais.config

# 移除 load_models_from_config_file 函数，因为模型选择将直接从 slais.config 获取

def get_model_choices(api_name: str, default_model: str):
    """
    根据API名称从 slais.config.settings.LLM_MODEL_CHOICES 中获取模型列表。
    
    Args:
        api_name: API接口的名称 (e.g., "OpenAI", "阿里云")
        default_model: 如果指定API没有对应的模型列表，则返回的默认模型名称
        
    Returns:
        该API接口下的模型列表，如果不存在则返回包含 default_model 的列表
    """
    # 直接从 slais.config.settings 获取模型选择
    return config.settings.LLM_MODEL_CHOICES.get(api_name, [default_model])
