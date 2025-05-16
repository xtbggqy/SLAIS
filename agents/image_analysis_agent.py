import asyncio
import base64
from pathlib import Path
from typing import List, Dict, Any, Optional

from slais.utils.logging_utils import logger # 导入 logger
from langchain_core.messages import HumanMessage # 导入 HumanMessage
from agents.prompts import IMAGE_ANALYSIS_BASE_PROMPT # 导入图片分析基础提示词

class ImageAnalysisAgent:
    """
    智能体：分析PDF转化后提取的图片，输出结构化描述。
    """

    def __init__(self, llm_client):
        self.llm = llm_client

    async def analyze_images(self, image_paths: List[str], context: Optional[str] = None, callbacks=None) -> List[Dict[str, Any]]:
        """
        对图片列表进行内容分析，返回结构化描述。
        Args:
            image_paths: 图片文件路径列表 (应为绝对路径或LLM可访问的URL)
            context: 可选，图片所在文档的上下文文本
            callbacks: LLM回调
        Returns:
            每张图片的结构化描述列表
        """
        results = []
        if not image_paths:
            return results

        # 可选：分批并发处理，避免LLM API超载
        async def analyze_single_image(image_path):
            try:
                # 尝试读取图片并转换为 base64
                try:
                    with open(image_path, "rb") as f:
                        image_base64 = base64.b64encode(f.read()).decode("utf-8")
                    # 假设图片是JPEG格式，如果需要支持其他格式，需要检测文件类型
                    image_url = f"data:image/jpeg;base64,{image_base64}"
                except Exception as e:
                    logger.error(f"读取或编码图片文件失败: {image_path} - {e}")
                    return {
                        "image_path": image_path,
                        "description": f"图片读取或编码失败: {e}"
                    }

                # 构建符合 LangChain HumanMessage 多模态输入格式的 content
                message_content = [
                    {
                        "type": "text",
                        "text": self._build_prompt(image_path, context)
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url
                        }
                    }
                ]

                # 创建 HumanMessage 对象
                human_message = HumanMessage(content=message_content)

                # 调用 LLM
                logger.debug(f"调用 LLM 分析图片: {image_path}")
                response = await self.llm.ainvoke(
                    [human_message], # ainvoke 期望一个消息列表
                    config={"callbacks": callbacks} if callbacks else None
                )

                # 提取响应文本
                response_text = response.content if hasattr(response, 'content') else str(response)

                return {
                    "image_path": image_path,
                    "description": response_text
                }
            except Exception as e:
                logger.error(f"分析图片时发生错误: {image_path} - {e}")
                import traceback
                logger.debug(f"错误详情 (Traceback): {traceback.format_exc()}")
                return {
                    "image_path": image_path,
                    "description": f"图片解析失败: {e}"
                }

        tasks = [analyze_single_image(img) for img in image_paths]
        results = await asyncio.gather(*tasks)
        return results

    def _build_prompt(self, image_path: str, context: Optional[str]) -> str:
        """
        构建图片内容分析的提示词。
        """
        prompt = IMAGE_ANALYSIS_BASE_PROMPT # 使用导入的基础提示词

        if context:
            # 截断上下文以避免过长的提示
            max_context_chars = 2000 # 限制上下文长度
            truncated_context = context[:max_context_chars] + "..." if len(context) > max_context_chars else context
            prompt += f"\n【上下文】\n{truncated_context}\n"

        # 移除图片文件名，因为图片本身已作为输入
        # prompt += f"\n【图片文件】{Path(image_path).name}\n"

        # 基础提示词已经包含了结尾部分，无需再次添加
        # prompt += "请用简洁的学术语言输出结构化描述。"
        return prompt
