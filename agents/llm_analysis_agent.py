import json
import re
import logging
from typing import Dict, Any, List, Optional

from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_core.exceptions import OutputParserException

from agents.base_agent import ResearchAgent as BaseResearchAgent
from slais.utils.logging_utils import logger
from agents.prompts import (
    METHODOLOGY_ANALYSIS_PROMPT,
    INNOVATION_EXTRACTION_PROMPT,
    QA_GENERATION_PROMPT
)
from slais import config

class MethodologyAnalysisAgent(BaseResearchAgent):
    def __init__(self, llm_client: Any):
        super().__init__(llm_client, provider_name="openai")

    def _build_chain(self, prompt_template_str: str) -> LLMChain:
        """构建并返回方法学分析的LLMChain。"""
        prompt = PromptTemplate(template=prompt_template_str, input_variables=["content"])
        return LLMChain(llm=self.llm_client, prompt=prompt)

    async def analyze_methodology(self, content: str) -> Dict[str, Any]:
        try:
            logger.info(f"分析文献方法，内容长度: {len(content)} 字符")
            analysis_result = await self._analyze(
                prompt_template_str=METHODOLOGY_ANALYSIS_PROMPT,
                content=content
            )
            response_text = analysis_result if isinstance(analysis_result, str) else json.dumps(analysis_result)
            logger.debug(f"方法分析原始响应: {response_text[:200]}...")
            
            if isinstance(analysis_result, dict):
                return analysis_result

            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                try:
                    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                    if json_match:
                        cleaned_json = json_match.group(0)
                        return json.loads(cleaned_json)
                    else:
                        raise ValueError("无法提取JSON格式内容")
                except Exception as inner_e:
                    logger.error(f"JSON清理后仍无法解析: {inner_e}. 原始响应: {response_text[:200]}...")
                    return {"error": f"无法解析响应: {str(inner_e)}", "方法类型": "未知", "关键技术": "未知", "创新方法": "未知"}
        except Exception as e:
            logger.error(f"方法分析时发生错误: {str(e)}")
            return {"error": str(e), "方法类型": "未知", "关键技术": "未知", "创新方法": "未知"}

    async def run(self, content: str) -> Dict[str, Any]:
        """实现抽象的run方法。"""
        return await self.analyze_methodology(content)

class InnovationExtractionAgent(BaseResearchAgent):
    def __init__(self, llm_client: Any):
        super().__init__(llm_client, provider_name="openai")

    def _build_chain(self, prompt_template_str: str) -> LLMChain:
        """构建并返回创新点提取的LLMChain。"""
        prompt = PromptTemplate(template=prompt_template_str, input_variables=["content"])
        return LLMChain(llm=self.llm_client, prompt=prompt)

    async def extract_innovations(self, content: str) -> Dict[str, Any]:
        try:
            logger.info(f"提取创新点，内容长度: {len(content)} 字符")
            analysis_result = await self._analyze(
                prompt_template_str=INNOVATION_EXTRACTION_PROMPT,
                content=content
            )
            response_text = analysis_result if isinstance(analysis_result, str) else json.dumps(analysis_result)
            logger.debug(f"创新点提取原始响应: {response_text[:200]}...")

            if isinstance(analysis_result, dict):
                return analysis_result
            
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                try:
                    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                    if json_match:
                        cleaned_json = json_match.group(0)
                        return json.loads(cleaned_json)
                    else:
                        raise ValueError("无法提取JSON格式内容")
                except Exception as inner_e:
                    logger.error(f"JSON清理后仍无法解析: {inner_e}. 原始响应: {response_text[:200]}...")
                    return {"error": f"无法解析响应: {str(inner_e)}", "核心创新": "未知", "潜在应用": "未知"}
        except Exception as e:
            logger.error(f"创新点提取时发生错误: {str(e)}")
            return {"error": str(e), "核心创新": "未知", "潜在应用": "未知"}

    async def run(self, content: str) -> Dict[str, Any]:
        """实现抽象的run方法。"""
        return await self.extract_innovations(content)

class QAGenerationAgent(BaseResearchAgent):
    def __init__(self, llm_client: Any):
        super().__init__(llm_client, provider_name="openai")

    def _build_chain(self, prompt_template_str: str) -> LLMChain:
        """构建并返回问答生成的LLMChain。"""
        prompt = PromptTemplate(template=prompt_template_str, input_variables=["content"])
        return LLMChain(llm=self.llm_client, prompt=prompt)

    async def generate_qa(self, content: str) -> List[Dict[str, str]]:
        logger.info(f"生成问答，内容长度: {len(content)} 字符 (传递给分析前)")
        try:
            analysis_result = await self._analyze(
                prompt_template_str=QA_GENERATION_PROMPT,
                content=content
            )
            
            parsed_json = None
            if isinstance(analysis_result, dict):
                parsed_json = analysis_result
            elif isinstance(analysis_result, str):
                try:
                    cleaned_result_str = re.sub(r"```json\n(.*?)\n```", r"\1", analysis_result, flags=re.DOTALL)
                    cleaned_result_str = re.sub(r"```(.*?)\n```", r"\1", cleaned_result_str, flags=re.DOTALL)
                    cleaned_result_str = re.sub(r",\s*(\]|\})", r"\1", cleaned_result_str)
                    parsed_json = json.loads(cleaned_result_str)
                except json.JSONDecodeError as e:
                    logger.error(f"无法将LLM的字符串输出解析为JSON: {e}")
                    logger.debug(f"原始LLM输出 (字符串): {analysis_result}")
                    return self._extract_qa_from_text_fallback(analysis_result)
            else:
                logger.error(f"LLM返回了意外的类型: {type(analysis_result)}")
                return self._extract_qa_from_text_fallback(str(analysis_result))

            qa_pairs = parsed_json.get("qa_pairs", []) if parsed_json else []
            if not isinstance(qa_pairs, list) or not all(isinstance(pair, dict) and "question" in pair and "answer" in pair for pair in qa_pairs):
                logger.warning(f"LLM返回的QA对格式不正确: {qa_pairs}")
                return self._extract_qa_from_text_fallback(str(analysis_result))

            return qa_pairs[:config.MAX_QUESTIONS_TO_GENERATE]

        except OutputParserException as e:
            logger.error(f"问答生成时输出解析错误: {e}")
            logger.debug(f"原始LLM输出 (导致解析错误): {e.llm_output if hasattr(e, 'llm_output') else 'N/A'}")
            return self._extract_qa_from_text_fallback(e.llm_output if hasattr(e, 'llm_output') else content)
        except Exception as e:
            logger.error(f"问答生成时发生错误: {e}")
            import traceback
            logger.debug(f"错误详情: {traceback.format_exc()}")
            return []

    def _extract_qa_from_text_fallback(self, text: str) -> List[Dict[str, str]]:
        logger.warning("尝试使用正则表达式回退提取QA对。")
        pairs = []
        matches = re.findall(r'"question":\s*"(.*?)",\s*"answer":\s*"(.*?)"', text, re.IGNORECASE | re.DOTALL)
        for q, a in matches:
            pairs.append({"question": q.strip(), "answer": a.strip()})
        
        if not pairs:
            logger.warning("正则表达式回退未能提取任何QA对。")
        else:
            logger.info(f"通过正则表达式回退提取了 {len(pairs)} 个QA对。")
        return pairs[:config.MAX_QUESTIONS_TO_GENERATE]

    async def run(self, content: str) -> List[Dict[str, str]]:
        """实现抽象的run方法。"""
        return await self.generate_qa(content)
