import json
import re
import logging
from typing import Dict, Any, List, Optional, Union
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_core.exceptions import OutputParserException
from langchain_core.callbacks.base import BaseCallbackHandler

from agents.base_agent import ResearchAgent as BaseResearchAgent
from slais.utils.logging_utils import logger
import agents.prompts as prompts
from agents.prompts import (
    METHODOLOGY_ANALYSIS_PROMPT,
    INNOVATION_EXTRACTION_PROMPT,
    QA_GENERATION_PROMPT,
    BATCH_ANSWER_GENERATION_PROMPT,
    STORYTELLING_PROMPT, # 导入 STORYTELLING_PROMPT
    MINDMAP_PROMPT, # 导入 MINDMAP_PROMPT
    DEEP_ANALYSIS_PROMPT # 导入 DEEP_ANALYSIS_PROMPT
)
from slais import config

# 辅助函数，用于在MindMapAgent生成失败时提供默认的Mermaid图
def generate_default_mindmap_on_error(error_message: str) -> str:
    """生成一个默认的脑图，显示错误信息。"""
    return f"""```mermaid
graph TD
    A[生成失败] --> B[脑图生成过程中出错]
    B --> C["{error_message}"]
    C --> D1[可能原因1: LLM响应问题]
    C --> D2[可能原因2: 输入文本过长]
    C --> D3[可能原因3: 格式解析错误]
    D1 --> E[请查看日志获取详细错误信息]
```
"""

class MethodologyAnalysisAgent(BaseResearchAgent):
    def __init__(self, llm_client: Any):
        super().__init__(llm_client, provider_name="openai")

    def _build_chain(self, prompt_template_str: str):
        """构建并返回方法学分析的链。"""
        prompt = PromptTemplate(template=prompt_template_str, input_variables=["content", "image_analysis"])
        return prompt | self.llm_client

    async def analyze_methodology(
        self, 
        content: str, 
        callbacks: Optional[List[BaseCallbackHandler]] = None,
        image_analysis: str = ""  # 添加图像分析参数，默认为空字符串
    ) -> Union[Dict[str, Any], str]:
        try:
            logger.info(f"分析文献方法，内容长度: {len(content)} 字符")
            truncated_content = self._truncate_content(content, max_chars=config.settings.MAX_CONTENT_CHARS_FOR_LLM)
            chain = self._build_chain(METHODOLOGY_ANALYSIS_PROMPT)
            # 传递图像分析内容
            input_data = {
                "content": truncated_content,
                "image_analysis": image_analysis
            }
            response_text = await super()._invoke_llm_analysis(
                METHODOLOGY_ANALYSIS_PROMPT,
                input_data,
                callbacks
            )
            # _invoke_llm_analysis 已经处理了 .content 和基本错误
            # 此处可以添加特定于此 Agent 的后处理或错误处理
            if response_text.startswith("错误："): # 基类方法返回的错误信息
                return response_text # 直接返回错误信息
            
            logger.debug(f"方法分析原始响应: {response_text[:200]}...")
            # 尝试解析JSON的逻辑可以保留，如果提示要求JSON输出的话，但当前提示是Markdown
            # try:
            #     # parsed_response = json.loads(response_text)
            #     # return parsed_response
            # except json.JSONDecodeError:
            #     logger.warning("方法学分析未能解析JSON（如果预期是JSON的话），返回原始文本。")
            return response_text
        except Exception as e: # 捕获在准备输入或调用基类方法之前可能发生的其他错误
            logger.error(f"准备或执行方法学分析时发生意外错误: {str(e)}")
            return f"错误：方法学分析准备失败 ({e})"

    async def run(self, content: str, image_analysis: str = "", callbacks: Optional[List[BaseCallbackHandler]] = None) -> Dict[str, Any]:
        """实现抽象的run方法。"""
        return await self.analyze_methodology(content, callbacks, image_analysis)

class InnovationExtractionAgent(BaseResearchAgent):
    def __init__(self, llm_client: Any):
        super().__init__(llm_client, provider_name="openai")

    def _build_chain(self, prompt_template_str: str):
        """构建并返回创新点提取的链。"""
        prompt = PromptTemplate(template=prompt_template_str, input_variables=["content", "image_analysis"])
        return prompt | self.llm_client

    async def extract_innovations(
        self, 
        content: str, 
        callbacks: Optional[List[BaseCallbackHandler]] = None,
        image_analysis: str = ""  # 添加图像分析参数，默认为空字符串
    ) -> Union[Dict[str, Any], str]:
        try:
            logger.info(f"提取创新点，内容长度: {len(content)} 字符")
            truncated_content = self._truncate_content(content, max_chars=config.settings.MAX_CONTENT_CHARS_FOR_LLM)
            chain = self._build_chain(INNOVATION_EXTRACTION_PROMPT)
            # 传递图像分析内容
            input_data = {
                "content": truncated_content,
                "image_analysis": image_analysis
            }
            response_text = await super()._invoke_llm_analysis(
                INNOVATION_EXTRACTION_PROMPT,
                input_data,
                callbacks
            )
            if response_text.startswith("错误："):
                return response_text
                
            logger.debug(f"创新点提取原始响应: {response_text[:200]}...")
            # try:
            #     # parsed_response = json.loads(response_text)
            #     # return parsed_response
            # except json.JSONDecodeError:
            #     logger.warning("创新点提取未能解析JSON（如果预期是JSON的话），返回原始文本。")
            return response_text
        except Exception as e:
            logger.error(f"准备或执行创新点提取时发生意外错误: {str(e)}")
            return f"错误：创新点提取准备失败 ({e})"

    async def run(self, content: str, image_analysis: str = "", callbacks: Optional[List[BaseCallbackHandler]] = None) -> Dict[str, Any]:
        """实现抽象的run方法。"""
        return await self.extract_innovations(content, callbacks, image_analysis)

class QAGenerationAgent(BaseResearchAgent):
    def __init__(self, llm_client: Any):
        super().__init__(llm_client, provider_name="openai")

    def _build_chain(self, prompt_template_str: str):
        """构建并返回问答生成的链。"""
        if prompt_template_str == QA_GENERATION_PROMPT:
            input_variables = ["content", "num_questions", "image_analysis"]
            prompt = PromptTemplate(template=prompt_template_str, input_variables=input_variables)
        elif prompt_template_str == BATCH_ANSWER_GENERATION_PROMPT:
            input_variables = ["content", "questions_json_list_string", "image_analysis"]
            # 移除 validate_template=False，让其默认为 True，以便在初始化时进行验证
            prompt = PromptTemplate(template=prompt_template_str, input_variables=input_variables)
        else:
            # 理论上这个分支不应该被 QAGenerationAgent 触及，因为其主要处理 QA_GENERATION_PROMPT 和 BATCH_ANSWER_GENERATION_PROMPT
            # 但为了健壮性，可以保留或抛出错误
            input_variables = ["content", "image_analysis"] # 假设一个通用情况
            prompt = PromptTemplate(template=prompt_template_str, input_variables=input_variables)
        return prompt | self.llm_client

    async def generate_questions(
        self, 
        content: str, 
        callbacks: Optional[List[BaseCallbackHandler]] = None,
        image_analysis: str = ""  # 添加图像分析参数，默认为空字符串
    ) -> List[str]:
        logger.info(f"生成问题，内容长度: {len(content)} 字符 (传递给分析前)")
        try:
            truncated_content = self._truncate_content(content, max_chars=config.settings.MAX_CONTENT_CHARS_FOR_LLM)
            input_data = {
                "content": truncated_content,
                "num_questions": config.settings.MAX_QUESTIONS_TO_GENERATE,
                "image_analysis": image_analysis
            }
            response_text = await super()._invoke_llm_analysis(
                QA_GENERATION_PROMPT,
                input_data,
                callbacks,
                cache_content_key="content" # 明确用于缓存哈希的内容字段
            )
            if response_text.startswith("错误："):
                # 如果基类方法返回错误，则直接返回空列表或错误信息
                logger.error(f"问题生成失败: {response_text}")
                return []
                
            logger.debug(f"问题生成原始响应: {response_text[:200]}...")
            questions = self._extract_questions_from_text(response_text)
            return questions
        except Exception as e:
            logger.error(f"问题生成时发生错误: {e}")
            import traceback
            logger.debug(f"错误详情: {traceback.format_exc()}")
            return []

    async def generate_answers_batch(
        self, 
        questions: List[str], 
        content: str, 
        callbacks: Optional[List[BaseCallbackHandler]] = None,
        image_analysis: str = ""  # 添加图像分析参数，默认为空字符串
    ) -> List[Dict[str, str]]:
        """
        根据文献内容和问题列表批量生成答案。
        """
        if not questions:
            logger.info("没有问题需要回答。")
            return []

        logger.info(f"批量生成答案，共 {len(questions)} 个问题。内容长度: {len(content)} 字符 (传递给分析前)")
        truncated_content = self._truncate_content(content, max_chars=config.settings.MAX_CONTENT_CHARS_FOR_LLM)
        questions_json_list_string = json.dumps(questions, ensure_ascii=False)

        # 显式定义输入变量以避免解析错误
        prompt_template = PromptTemplate(
            template=BATCH_ANSWER_GENERATION_PROMPT,
            input_variables=["content", "questions_json_list_string", "image_analysis"]
        )

        try:
            input_data = {
                "content": truncated_content,
                "questions_json_list_string": questions_json_list_string,
                "image_analysis": image_analysis
            }
            response_text = await super()._invoke_llm_analysis(
                BATCH_ANSWER_GENERATION_PROMPT,
                input_data,
                callbacks,
                cache_content_key="content" # 或者更复杂的键，如 content + questions_json_list_string
            )

            if response_text.startswith("错误："):
                logger.error(f"批量生成答案失败: {response_text}")
                return [{"question": q, "answer": response_text} for q in questions]

            # 清理LLM响应，移除Markdown代码块标记
            cleaned_response_text = response_text.strip()
            if cleaned_response_text.startswith("```json"):
                cleaned_response_text = cleaned_response_text[7:] # 移除 ```json\n
            elif cleaned_response_text.startswith("```"):
                cleaned_response_text = cleaned_response_text[3:] # 移除 ```\n
            
            if cleaned_response_text.endswith("```"):
                cleaned_response_text = cleaned_response_text[:-3] # 移除 ```
            
            cleaned_response_text = cleaned_response_text.strip()

            try:
                # 使用清理后的文本进行JSON解析
                qa_pairs_from_llm = json.loads(cleaned_response_text)
                
                # 确保返回的是列表，并且列表中的元素是字典
                if not isinstance(qa_pairs_from_llm, list) or \
                   not all(isinstance(item, dict) and "question" in item and "answer" in item for item in qa_pairs_from_llm):
                    logger.error(f"LLM返回的JSON结构不符合预期 (不是字典列表或缺少键)。原始文本: {response_text[:500]}")
                    # 为每个原始问题生成一个包含错误信息的答案条目
                    return [{"question": q, "answer": f"错误：LLM返回的JSON结构不符合预期。原始响应: {response_text[:200]}"} for q in questions]

                # 将LLM生成的答案与原始问题列表对齐 (以原始问题列表为准)
                # 这是一个简单的对齐，假设LLM返回的顺序和问题数量与输入一致
                # 更健壮的实现可能需要基于问题文本进行匹配
                aligned_qa_pairs = []
                llm_answers_map = {item.get("question", "").strip(): item.get("answer", "未能生成答案。") for item in qa_pairs_from_llm}

                for original_question_text in questions:
                    # 尝试精确匹配
                    answer = llm_answers_map.get(original_question_text.strip())
                    if answer is None:
                        # 如果精确匹配失败，可以尝试模糊匹配或记录错误
                        logger.warning(f"未能从LLM的响应中为问题 '{original_question_text}' 找到精确匹配的答案。")
                        answer = f"错误：未能从LLM响应中找到此问题的答案。LLM可能未按预期格式返回。"
                    
                    aligned_qa_pairs.append({
                        "question": original_question_text,
                        "answer": answer
                    })
                
                logger.info(f"成功解析并对齐了 {len(aligned_qa_pairs)} 个问答对。")
                return aligned_qa_pairs

            except json.JSONDecodeError as e:
                logger.error(f"批量生成答案时解析JSON失败: {e}")
                logger.error(f"LLM响应文本 (导致JSON解析失败): {response_text[:1000]}") # 记录更长的文本以便调试
                # 为每个原始问题生成一个包含错误信息的答案条目
                return [{"question": q, "answer": f"错误：未能从LLM响应中解析答案 ({e})"} for q in questions]
        
        except Exception as e:
            logger.error(f"批量生成答案时发生意外错误: {e}")
            logger.debug(f"错误详情: questions_json_list_string: {questions_json_list_string[:100]}, content_len: {len(truncated_content)}")
            # 为每个原始问题生成一个包含错误信息的答案条目
            return [{"question": q, "answer": f"错误：生成答案时发生意外 ({e})"} for q in questions]

    def _extract_questions_from_text(self, text: str) -> List[str]:
        logger.info("尝试提取问题...")
        questions = []
        matches = re.findall(r'(?:^|\n)\s*(?:-?\s*问题\s*\d+\s*[:：.]?\s*(.*?)$|^\s*\d+\.\s*(.*?)$|^\s*-\s*(.*?)$)', text, re.MULTILINE | re.DOTALL)
        
        for match in matches:
            question_text = next((item for item in match if item), None)
            if question_text:
                cleaned_question = question_text.strip()
                cleaned_question = re.sub(r'^-?\s*', '', cleaned_question)
                cleaned_question = re.sub(r'^\s*\d+\s*[:：：.]?\s*', '', cleaned_question)
                
                if cleaned_question:
                    questions.append(cleaned_question)

        if not questions:
            logger.warning("未能从文本中提取到任何问题。")
            logger.debug(f"尝试提取问题的原始文本:\n{text[:500]}...")
        else:
            logger.info(f"成功提取到 {len(questions)} 个问题。")

        return questions[:config.settings.MAX_QUESTIONS_TO_GENERATE]

    async def run(self, content: str, image_analysis: str = "", callbacks: Optional[List[BaseCallbackHandler]] = None) -> List[Dict[str, str]]:
        return await self.generate_questions(content, callbacks, image_analysis)

class StorytellingAgent(BaseResearchAgent):
    def __init__(self, llm_client: Any):
        super().__init__(llm_client, provider_name="openai")

    def _build_chain(self, prompt_template_str: str):
        """构建并返回讲故事的链。"""
        prompt = PromptTemplate(template=prompt_template_str, input_variables=["content", "image_analysis"])
        return prompt | self.llm_client

    async def tell_story(
        self, 
        content: str, 
        callbacks: Optional[List[BaseCallbackHandler]] = None,
        image_analysis: str = ""  # 添加图像分析参数，默认为空字符串
    ) -> str:
        logger.info(f"以讲故事的方式讲述文献，内容长度: {len(content)} 字符")
        truncated_content = self._truncate_content(content, max_chars=config.settings.MAX_CONTENT_CHARS_FOR_LLM)
        input_data = {
            "content": truncated_content,
            "image_analysis": image_analysis
        }
        response_text = await super()._invoke_llm_analysis(
            STORYTELLING_PROMPT, # 使用 prompts.STORYTELLING_PROMPT
            input_data,
            callbacks
        )
        if response_text.startswith("错误："):
            return response_text
            
        logger.debug(f"讲故事原始响应: {response_text[:200]}...")
        return response_text

    async def run(self, content: str, image_analysis: str = "", callbacks: Optional[List[BaseCallbackHandler]] = None) -> str:
        """实现抽象的run方法。"""
        return await self.tell_story(content, callbacks, image_analysis)

class MindMapAgent(BaseResearchAgent):
    def __init__(self, llm_client: Any):
        super().__init__(llm_client, provider_name="openai")

    def _build_chain(self, prompt_template_str: str):
        """构建并返回生成脑图的链。"""
        # 提示模板的输入变量已在 prompts.py 中定义，此处无需重复明确
        prompt = PromptTemplate(template=prompt_template_str, input_variables=["content", "image_analysis"])
        
        # 添加诊断日志以便调试
        logger.debug(f"MindMapAgent._build_chain: PromptTemplate.input_variables = {prompt.input_variables}")
        
        return prompt | self.llm_client

    async def generate_mindmap(
        self, 
        content: str, 
        callbacks: Optional[List[BaseCallbackHandler]] = None,
        image_analysis: str = ""  # 添加图像分析参数，默认为空字符串
    ) -> str:
        logger.info(f"生成 Mermaid 脑图，内容长度: {len(content)} 字符")
        truncated_content = self._truncate_content(content, max_chars=config.settings.MAX_CONTENT_CHARS_FOR_LLM)
        
        try:
            input_data = {
                "content": truncated_content,
                "image_analysis": image_analysis
            }
            response_text = await super()._invoke_llm_analysis(
                MINDMAP_PROMPT,
                input_data,
                callbacks
            )

            if response_text.startswith("错误："):
                # 返回一个可显示的默认脑图，表示生成失败
                return generate_default_mindmap_on_error(response_text)

            # 使用formatting_utils中的格式化函数，避免重复逻辑
            from agents.formatting_utils import format_mermaid_code
            response_text = format_mermaid_code(response_text)
            
            logger.debug(f"生成脑图原始响应: {response_text[:200]}...")
            return response_text if isinstance(response_text, str) else str(response_text)
        except Exception as e:
            logger.error(f"MindMapAgent.generate_mindmap中的意外错误: {e}")
            # 返回一个可显示的默认脑图，表示生成失败
            return generate_default_mindmap_on_error(f"MindMapAgent.generate_mindmap中的意外错误: {e}")

    async def run(self, content: str, image_analysis: str = "", callbacks: Optional[List[BaseCallbackHandler]] = None) -> str:
        """实现抽象的run方法。"""
        return await self.generate_mindmap(content, callbacks, image_analysis)

class DeepAnalysisAgent(BaseResearchAgent):
    def __init__(self, llm_client: Any):
        super().__init__(llm_client, provider_name="openai")

    def _build_chain(self, prompt_template_str: str):
        """构建并返回深度分析的链。"""
        # DEEP_ANALYSIS_PROMPT 需要 content, image_analysis, references_summary, related_articles_summary
        prompt = PromptTemplate(
            template=prompt_template_str, 
            input_variables=["content", "image_analysis", "references_summary", "related_articles_summary"]
        )
        return prompt | self.llm_client

    async def analyze_deeply(
        self, 
        content: str,
        image_analysis: str = "",
        references_summary: str = "无参考文献信息。", # 提供默认值
        related_articles_summary: str = "无相关文献信息。", # 提供默认值
        callbacks: Optional[List[BaseCallbackHandler]] = None
    ) -> str:
        """
        执行深度文献分析。
        
        Args:
            content: 主要文献的Markdown内容。
            image_analysis: 主要文献的图片分析结果。
            references_summary: 主要文献的参考文献摘要信息。
            related_articles_summary: 相关文献的摘要信息。
            callbacks: LangChain回调处理器列表。
            
        Returns:
            Markdown格式的深度分析报告。
        """
        logger.info(f"开始深度文献分析，主文献内容长度: {len(content)} 字符")
        
        # 截断各个输入部分以适应LLM的上下文窗口限制
        # 注意：这里的截断策略可能需要根据实际最大Token数和各部分重要性进行调整
        # 假设总字符数限制为 MAX_CONTENT_CHARS_FOR_LLM，按比例分配
        # 例如：主内容占60%，图片分析10%，参考文献15%，相关文献15%
        # 这是一个简化的分配，实际可能需要更复杂的策略
        
        total_limit = config.settings.MAX_CONTENT_CHARS_FOR_LLM
        
        # 为了简单起见，我们先对每个部分进行单独截断，并记录日志
        # 更好的做法是动态计算各部分长度，然后按比例或优先级截断
        
        truncated_content = self._truncate_content(content, max_chars=int(total_limit * 0.5)) # 主内容占50%
        truncated_image_analysis = self._truncate_content(image_analysis, max_chars=int(total_limit * 0.1)) # 图片分析10%
        truncated_references_summary = self._truncate_content(references_summary, max_chars=int(total_limit * 0.2)) # 参考文献20%
        truncated_related_articles_summary = self._truncate_content(related_articles_summary, max_chars=int(total_limit * 0.2)) # 相关文献20%

        logger.debug(f"深度分析输入截断后长度：主内容 {len(truncated_content)}, 图片分析 {len(truncated_image_analysis)}, 参考文献 {len(truncated_references_summary)}, 相关文献 {len(truncated_related_articles_summary)}")

        # chain = self._build_chain(DEEP_ANALYSIS_PROMPT) # _invoke_llm_analysis 会处理
        
        try:
            input_data = {
                "content": truncated_content,
                "image_analysis": truncated_image_analysis,
                "references_summary": truncated_references_summary,
                "related_articles_summary": truncated_related_articles_summary
            }
            response_text = await super()._invoke_llm_analysis(
                DEEP_ANALYSIS_PROMPT,
                input_data,
                callbacks,
                # 对于深度分析，可能需要更复杂的缓存键，例如基于所有输入部分的哈希
                # 但为简单起见，仍使用 "content" (主文献内容) 作为主要哈希依据
                cache_content_key="content" 
            )

            if response_text.startswith("错误："):
                return response_text
                
            logger.debug(f"深度分析原始响应: {response_text[:200]}...")
            return response_text
        except Exception as e: # 捕获在准备输入或调用基类方法之前可能发生的其他错误
            logger.error(f"准备或执行深度分析时发生意外错误: {str(e)}")
            return f"错误：深度分析准备失败 ({e})"

    async def run(
        self, 
        content: str, 
        image_analysis: str = "", 
        references_summary: str = "", 
        related_articles_summary: str = "", 
        callbacks: Optional[List[BaseCallbackHandler]] = None
    ) -> str:
        """实现抽象的run方法。"""
        return await self.analyze_deeply(
            content, 
            image_analysis, 
            references_summary, 
            related_articles_summary, 
            callbacks
        )
