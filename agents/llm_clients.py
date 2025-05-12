from langchain_openai import ChatOpenAI

# LLM_PROVIDER_CLIENTS 映射表
# 将配置中的提供商名称映射到相应的LangChain LLM类
LLM_PROVIDER_CLIENTS = {
    "openai": ChatOpenAI,
}
