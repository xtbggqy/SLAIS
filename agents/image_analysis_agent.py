from typing import List, Dict, Any, Optional
from pathlib import Path
import asyncio

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
            image_paths: 图片文件路径列表
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
            prompt = self._build_prompt(image_path, context)
            # 假设llm支持图片输入（如Qwen、GPT-4o等），否则可集成OCR/图像识别API
            try:
                # 修复：不再重复传递callbacks参数，而是传递到config
                response = await self.llm.ainvoke(
                    prompt, 
                    config={"callbacks": callbacks} if callbacks else None,
                    images=[image_path]
                )
                return {
                    "image_path": image_path,
                    "description": response if isinstance(response, str) else str(response)
                }
            except Exception as e:
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
        prompt = (
            "请对下列学术论文中的图片进行内容分析，简要描述图片展示的内容、类型（如图表、照片、流程图等）、主要发现或结论。"
            "如果有上下文信息，可结合上下文理解图片含义。\n"
        )
        if context:
            prompt += f"\n【上下文】\n{context}\n"
        prompt += f"\n【图片文件】{Path(image_path).name}\n"
        prompt += "请用简洁的学术语言输出结构化描述。"
        return prompt
