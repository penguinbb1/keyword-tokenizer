"""
分词与标注处理流水线
整合所有模块，实现完整的处理流程
"""
from typing import Dict, List, Optional
from collections import defaultdict

from .preprocessor import preprocessor
from .fixed_phrase_extractor import FixedPhraseExtractor
from .language_detector import language_detector, Language
from .tokenizers import ChineseTokenizer, JapaneseTokenizer, EuropeanTokenizer
from .tagger import Tagger


class TokenizePipeline:
    """分词与标注处理流水线"""
    
    def __init__(self, dictionary_manager):
        self.dict_manager = dictionary_manager
        
        # 初始化各组件
        self.fixed_phrase_extractor = FixedPhraseExtractor(dictionary_manager)
        self.tagger = Tagger(dictionary_manager)
        
        # 初始化各语言分词器
        self.tokenizers = {
            Language.CHINESE: ChineseTokenizer(dictionary_manager),
            Language.JAPANESE: JapaneseTokenizer(dictionary_manager),
            Language.ENGLISH: EuropeanTokenizer(dictionary_manager, Language.ENGLISH),
            Language.GERMAN: EuropeanTokenizer(dictionary_manager, Language.GERMAN),
            Language.FRENCH: EuropeanTokenizer(dictionary_manager, Language.FRENCH),
            Language.SPANISH: EuropeanTokenizer(dictionary_manager, Language.SPANISH),
        }
    
    async def process(self, keyword: str, use_ai: bool = True) -> Dict:
        """
        处理单个关键词
        
        Args:
            keyword: 输入关键词
            use_ai: 是否使用AI增强
            
        Returns:
            处理结果字典
        """
        # Step 1: 预处理
        processed_text, preprocess_record = preprocessor.process(keyword)
        
        # Step 2: 提取固定搭配
        fixed_phrases, remaining_text = self.fixed_phrase_extractor.extract(processed_text)
        
        # Step 3: 对剩余文本进行语言分段和分词
        other_tokens = []
        if remaining_text.strip():
            segments = language_detector.segment_by_language(remaining_text)
            
            for segment in segments:
                tokenizer = self._get_tokenizer(segment.language)
                tokens = tokenizer.tokenize(segment.text)
                other_tokens.extend([t.text for t in tokens])
        
        # Step 4: 合并所有 tokens（保持原始顺序）
        all_tokens = self._merge_tokens(
            keyword, 
            fixed_phrases, 
            other_tokens
        )
        
        # Step 5: 标签标注
        tag_results = self.tagger.tag(all_tokens, context=keyword)
        
        # Step 6: 格式化输出
        return self._format_output(keyword, all_tokens, tag_results)
    
    def _get_tokenizer(self, language: Language):
        """获取对应语言的分词器"""
        if language in self.tokenizers:
            return self.tokenizers[language]
        # 默认使用英语分词器
        return self.tokenizers[Language.ENGLISH]
    
    def _merge_tokens(
        self, 
        original: str,
        fixed_phrases: List,
        other_tokens: List[str]
    ) -> List[str]:
        """
        合并固定搭配和其他分词结果
        尽量保持原始顺序
        """
        result = []
        
        # 将固定搭配添加到结果
        for phrase in fixed_phrases:
            result.append(phrase.text)
        
        # 添加其他tokens（去重）
        existing = set(t.lower() for t in result)
        for token in other_tokens:
            if token.lower() not in existing and token.strip():
                result.append(token)
                existing.add(token.lower())
        
        # TODO: 更智能的排序，基于在原文中的位置
        
        return result
    
    def _format_output(
        self, 
        original: str,
        tokens: List[str],
        tag_results: List
    ) -> Dict:
        """格式化输出为 API 要求的格式"""
        
        # 构建 tagged_tokens
        tagged_tokens = []
        for i, tag_result in enumerate(tag_results):
            tagged_tokens.append({
                "token": tag_result.token,
                "tags": tag_result.tags,
                "confidence": tag_result.confidence
            })
        
        # 构建 tag_summary
        tag_summary = defaultdict(list)
        for tag_result in tag_results:
            for tag in tag_result.tags:
                if tag_result.token not in tag_summary[tag]:
                    tag_summary[tag].append(tag_result.token)
        
        return {
            "original_keyword": original,
            "tokens": tokens,
            "tagged_tokens": tagged_tokens,
            "tag_summary": dict(tag_summary)
        }
