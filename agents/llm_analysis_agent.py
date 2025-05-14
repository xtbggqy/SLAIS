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
    BATCH_ANSWER_GENERATION_PROMPT
)
from slais import config

class MethodologyAnalysisAgent(BaseResearchAgent):
    def __init__(self, llm_client: Any):
        super().__init__(llm_client, provider_name="openai")

    def _build_chain(self, prompt_template_str: str) -> LLMChain:
        """构建并返回方法学分析的LLMChain。"""
        prompt = PromptTemplate(template=prompt_template_str, input_variables=["content"])
        return LLMChain(llm=self.llm_client, prompt=prompt)

    async def analyze_methodology(
        self, 
        content: str, 
        callbacks: Optional[List[BaseCallbackHandler]] = None
    ) -> Union[Dict[str, Any], str]:
        try:
            logger.info(f"分析文献方法，内容长度: {len(content)} 字符")
            truncated_content = self._truncate_content(content, max_chars=config.settings.MAX_CONTENT_CHARS_FOR_LLM)
            chain = self._build_chain(METHODOLOGY_ANALYSIS_PROMPT)
            response = await chain.ainvoke({"content": truncated_content}, config={"callbacks": callbacks})
            response_text = response.get("text", str(response))
            logger.debug(f"方法分析原始响应: {response_text[:200]}...")
            return response_text if isinstance(response_text, str) else str(response_text)
        except json.JSONDecodeError:
            logger.warning("方法学分析未能解析JSON，返回原始文本。")
            return response_text
        except Exception as e:
            logger.error(f"方法分析时发生错误: {str(e)}")
            return f"错误：方法学分析失败 ({e})"

    async def run(self, content: str, callbacks: Optional[List[BaseCallbackHandler]] = None) -> Dict[str, Any]:
        """实现抽象的run方法。"""
        return await self.analyze_methodology(content, callbacks)

class InnovationExtractionAgent(BaseResearchAgent):
    def __init__(self, llm_client: Any):
        super().__init__(llm_client, provider_name="openai")

    def _build_chain(self, prompt_template_str: str) -> LLMChain:
        """构建并返回创新点提取的LLMChain。"""
        prompt = PromptTemplate(template=prompt_template_str, input_variables=["content"])
        return LLMChain(llm=self.llm_client, prompt=prompt)

    async def extract_innovations(
        self, 
        content: str, 
        callbacks: Optional[List[BaseCallbackHandler]] = None
    ) -> Union[Dict[str, Any], str]:
        try:
            logger.info(f"提取创新点，内容长度: {len(content)} 字符")
            truncated_content = self._truncate_content(content, max_chars=config.settings.MAX_CONTENT_CHARS_FOR_LLM)
            chain = self._build_chain(INNOVATION_EXTRACTION_PROMPT)
            response = await chain.ainvoke({"content": truncated_content}, config={"callbacks": callbacks})
            response_text = response.get("text", str(response))
            logger.debug(f"创新点提取原始响应: {response_text[:200]}...")
            return response_text if isinstance(response_text, str) else str(response_text)
        except json.JSONDecodeError:
            logger.warning("创新点提取未能解析JSON，返回原始文本。")
            return response_text
        except Exception as e:
            logger.error(f"创新点提取时发生错误: {str(e)}")
            return f"错误：创新点提取失败 ({e})"

    async def run(self, content: str, callbacks: Optional[List[BaseCallbackHandler]] = None) -> Dict[str, Any]:
        """实现抽象的run方法。"""
        return await self.extract_innovations(content, callbacks)

class QAGenerationAgent(BaseResearchAgent):
    def __init__(self, llm_client: Any):
        super().__init__(llm_client, provider_name="openai")

    def _build_chain(self, prompt_template_str: str) -> LLMChain:
        """构建并返回问答生成的LLMChain。"""
        if prompt_template_str == QA_GENERATION_PROMPT:
            input_variables = ["content", "num_questions"]
        elif prompt_template_str == BATCH_ANSWER_GENERATION_PROMPT:
            input_variables = ["content", "questions_json_list_string"]
        else:
            input_variables = ["content"]

        prompt = PromptTemplate(template=prompt_template_str, input_variables=input_variables)
        return LLMChain(llm=self.llm_client, prompt=prompt)

    async def generate_questions(
        self, 
        content: str, 
        callbacks: Optional[List[BaseCallbackHandler]] = None
    ) -> List[str]:
        logger.info(f"生成问题，内容长度: {len(content)} 字符 (传递给分析前)")
        try:
            truncated_content = self._truncate_content(content, max_chars=config.settings.MAX_CONTENT_CHARS_FOR_LLM)
            chain = self._build_chain(QA_GENERATION_PROMPT)
            response = await chain.ainvoke({
                "content": truncated_content,
                "num_questions": config.settings.MAX_QUESTIONS_TO_GENERATE
            }, config={"callbacks": callbacks})
            response_text = response.get("text", str(response))
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
        callbacks: Optional[List[BaseCallbackHandler]] = None
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
            input_variables=["content", "questions_json_list_string"]
        )
        chain = self._create_llm_chain(prompt_template_obj=prompt_template)

        try:
            response = await chain.ainvoke({
                "content": truncated_content, 
                "questions_json_list_string": questions_json_list_string
            }, config={"callbacks": callbacks})
            response_text = response.get("text", str(response))
            
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

    async def run(self, content: str, callbacks: Optional[List[BaseCallbackHandler]] = None) -> List[Dict[str, str]]:
        return await self.generate_questions(content, callbacks)

class StorytellingAgent(BaseResearchAgent):
    def __init__(self, llm_client: Any):
        super().__init__(llm_client, provider_name="openai")

    def _build_chain(self, prompt_template_str: str) -> LLMChain:
        """构建并返回讲故事的LLMChain。"""
        prompt = PromptTemplate(template=prompt_template_str, input_variables=["content"])
        return LLMChain(llm=self.llm_client, prompt=prompt)

    async def tell_story(
        self, 
        content: str, 
        callbacks: Optional[List[BaseCallbackHandler]] = None
    ) -> str:
        logger.info(f"以讲故事的方式讲述文献，内容长度: {len(content)} 字符")
        truncated_content = self._truncate_content(content, max_chars=config.settings.MAX_CONTENT_CHARS_FOR_LLM)
        chain = self._build_chain(prompts.STORYTELLING_PROMPT)
        response = await chain.ainvoke({"content": truncated_content}, config={"callbacks": callbacks})
        response_text = response.get("text", str(response))
        logger.debug(f"讲故事原始响应: {response_text[:200]}...")
        return response_text if isinstance(response_text, str) else str(response_text)

    async def run(self, content: str, callbacks: Optional[List[BaseCallbackHandler]] = None) -> str:
        """实现抽象的run方法。"""
        return await self.tell_story(content, callbacks)

class MindMapAgent(BaseResearchAgent):
    def __init__(self, llm_client: Any):
        super().__init__(llm_client, provider_name="openai")

    def _build_chain(self, prompt_template_str: str) -> LLMChain:
        """构建并返回生成脑图的LLMChain。"""
        # 明确定义只使用"content"作为输入变量
        prompt = PromptTemplate(template=prompt_template_str, input_variables=["content"])
        
        # 添加诊断日志以便调试
        logger.debug(f"MindMapAgent._build_chain: PromptTemplate.input_variables = {prompt.input_variables}")
        
        return LLMChain(llm=self.llm_client, prompt=prompt)

    async def generate_mindmap(
        self, 
        content: str, 
        callbacks: Optional[List[BaseCallbackHandler]] = None
    ) -> str:
        logger.info(f"生成 Mermaid 脑图，内容长度: {len(content)} 字符")
        truncated_content = self._truncate_content(content, max_chars=config.settings.MAX_CONTENT_CHARS_FOR_LLM)
        
        try:
            # 完全硬编码脑图生成提示，避免任何依赖
            template_str = """请根据以下文献内容，生成一个概括全文逻辑结构的 Mermaid 格式的脑图（思维导图）。
脑图应清晰地展示文献的主要章节、关键概念、研究流程或论证结构。
请确保输出是有效的 Mermaid 语法代码块，例如：

```mermaid
graph TD
    A[文献标题] --> B(引言)
    B --> C[研究问题]
    C --> D[方法]
    D --> E[结果]
    E --> F[讨论]
    F --> G[结论]
```

文献内容：
{content}

请只返回 Mermaid 代码块，不要包含额外的解释文本。"""

            # 创建全新的提示和链，避免任何潜在的变量/缓存问题
            prompt = PromptTemplate(template=template_str, input_variables=["content"])
            chain = LLMChain(llm=self.llm_client, prompt=prompt)
            
            # 只传递content参数
            response = await chain.ainvoke({"content": truncated_content}, config={"callbacks": callbacks})
            response_text = response.get("text", str(response))
            
            # 确保响应是正确的Mermaid代码块，如果不是则格式化它
            if "```mermaid" not in response_text:
                # 尝试提取可能是未正确格式化的Mermaid代码
                if "graph" in response_text and "-->" in response_text:
                    response_text = f"```mermaid\n{response_text}\n```"
                else:
                    # 如果无法找到明显的Mermaid语法，添加警告
                    response_text = f"```mermaid\ngraph TD\n    A[警告] --> B[生成的脑图可能不符合Mermaid语法]\n    B --> C[原始输出已保留在下方]\n```\n\n原始LLM输出:\n{response_text}"
            
            logger.debug(f"生成脑图原始响应: {response_text[:200]}...")
            return response_text if isinstance(response_text, str) else str(response_text)
        except Exception as e:
            logger.error(f"MindMapAgent.generate_mindmap中的意外错误: {e}")
            # 返回一个可显示的默认脑图，表示生成失败
            return """```mermaid
graph TD
    A[生成失败] --> B[脑图生成过程中出错]
    B --> C1[可能原因1: LLM响应问题]
    B --> C2[可能原因2: 输入文本过长]
    B --> C3[可能原因3: 格式解析错误]
    C1 --> D[请查看日志获取详细错误信息]
```
"""

    async def run(self, content: str, callbacks: Optional[List[BaseCallbackHandler]] = None) -> str:
        """实现抽象的run方法。"""
        return await self.generate_mindmap(content, callbacks)
