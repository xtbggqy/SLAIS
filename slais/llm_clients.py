from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatTongyi

# 定义一个基础的LLM配置，以便不同客户端可以继承或使用
class BaseLLMConfig:
    def __init__(self, api_key: str, model: str, temperature: float = 0.1, api_base: str = None):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.api_base = api_base

class DashScopeLLM(ChatTongyi, BaseLLMConfig):
    def __init__(self, api_key: str, model: str, temperature: float = 0.1, api_base: str = None, **kwargs):
        BaseLLMConfig.__init__(self, api_key=api_key, model=model, temperature=temperature, api_base=api_base)
        # DashScope (Qwen) specific initialization using ChatTongyi
        # The 'api_key' for ChatTongyi is 'dashscope_api_key'
        # The 'model_name' for ChatTongyi is 'model'
        super().__init__(
            model_name=model, 
            dashscope_api_key=api_key, 
            temperature=temperature,
            **kwargs # Pass any other specific DashScope params
        )
        # api_base is not directly used by ChatTongyi in the same way as OpenAI

class OpenAICompatibleLLM(ChatOpenAI, BaseLLMConfig):
    def __init__(self, api_key: str, model: str, temperature: float = 0.1, api_base: str = None, **kwargs):
        BaseLLMConfig.__init__(self, api_key=api_key, model=model, temperature=temperature, api_base=api_base)
        # OpenAI specific initialization
        super().__init__(
            model_name=model, 
            openai_api_key=api_key, 
            openai_api_base=api_base, # Pass api_base if provided
            temperature=temperature,
            **kwargs # Pass any other specific OpenAI params
        )

# 可以根据需要添加更多LLM提供商的客户端类
# class AnthropicLLM(BaseLLMConfig): ...
# class GoogleLLM(BaseLLMConfig): ...

# 注意: 上述实现假设LangChain的ChatTongyi和ChatOpenAI接受这些参数。
# 您可能需要根据LangChain最新版本的API调整参数名称和初始化方式。
# 例如，ChatTongyi可能不直接使用api_base，而是通过环境变量或特定配置。
# ChatOpenAI的api_key参数是 openai_api_key, base_url参数是 openai_api_base。
