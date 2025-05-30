import re
from pathlib import Path
from slais.utils.logging_utils import logger

def load_models_from_config_file(config_path: str):
    """
    从config.txt文件中加载API接口及其对应的模型列表。
    """
    models_data = {}
    current_api = None
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # 匹配API接口名称，例如 "OpenAI:"
                api_match = re.match(r"^(.*?):$", line)
                if api_match:
                    current_api = api_match.group(1).strip()
                    models_data[current_api] = []
                elif current_api and line.startswith("-"):
                    # 匹配模型名称，例如 "- gpt-3.5-turbo"
                    model_name = line[1:].strip()
                    if model_name:
                        models_data[current_api].append(model_name)
    except FileNotFoundError:
        logger.error(f"配置文件未找到: {config_path}")
    except Exception as e:
        logger.error(f"解析配置文件时发生错误: {e}")
    return models_data

def get_model_choices(api_name: str, all_models: dict, default_model: str):
    """
    根据API名称从加载的模型数据中获取模型列表。
    """
    return all_models.get(api_name, [default_model])
