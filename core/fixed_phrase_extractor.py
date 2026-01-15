"""
固定搭配提取模块
负责识别并保持品牌、型号、规格等固定搭配的完整性
"""
import re
from typing import List, Tuple
from dataclasses import dataclass


@dataclass
class FixedPhrase:
    """固定搭配"""
    text: str
    normalized: str
    start: int
    end: int
    phrase_type: str
    confidence: float


class FixedPhraseExtractor:
    """固定搭配提取器"""
    
    def __init__(self, dictionary_manager):
        self.dict_manager = dictionary_manager
        
        # 规格模式（数字+单位）
        self.spec_patterns = [
            (r'\d+\.?\d*\s*(码|寸|cm|inch|英寸|サイズ)', '尺寸词'),
            (r'\d+\.?\d*\s*(GB|MB|TB|gb|mb|tb)', '属性词'),
            (r'\d+\.?\d*\s*(kg|g|lb|oz|克|千克|磅)', '尺寸词'),
            (r'\d+\.?\d*\s*(张|片|支|个|包|盒|瓶|罐)', '尺寸词'),
            (r'\d+\.?\d*\s*(ml|ML|L|升|毫升)', '尺寸词'),
        ]
        
        # 型号模式
        self.model_patterns = [
            (r'iPhone\s*\d+\s*(Pro\s*Max|Pro|Plus|mini)?', '商品型号'),
            (r'Galaxy\s*[A-Z]?\d+\s*(Ultra|Plus|\+)?', '商品型号'),
            (r'MacBook\s*(Pro|Air)?\s*\d*', '商品型号'),
            (r'MateBook\s*\d+\s*(Pro)?', '商品型号'),
            (r'iPad\s*(Pro|Air|mini)?\s*\d*', '商品型号'),
        ]
    
    def extract(self, text: str) -> Tuple[List[FixedPhrase], str]:
        """
        提取固定搭配
        
        Returns:
            (固定搭配列表, 剩余待分词的文本)
        """
        matches = []
        remaining = text
        
        # 1. 先提取品牌词（最长匹配优先）
        brand_matches, remaining = self._extract_from_dict(remaining, "brands")
        matches.extend(brand_matches)
        
        # 2. 提取型号
        model_matches, remaining = self._extract_patterns(remaining, self.model_patterns)
        matches.extend(model_matches)
        
        # 3. 提取规格（数字+单位）
        spec_matches, remaining = self._extract_patterns(remaining, self.spec_patterns)
        matches.extend(spec_matches)
        
        return matches, remaining
    
    def _extract_from_dict(self, text: str, dict_name: str) -> Tuple[List[FixedPhrase], str]:
        """从词典中提取固定搭配"""
        matches = []
        text_lower = text.lower()
        
        # 获取词典条目，按长度降序排列（最长匹配优先）
        entries = self.dict_manager.get_entries(dict_name)
        entries = sorted(entries, key=lambda x: len(x.get("word", "")), reverse=True)
        
        for entry in entries:
            word = entry.get("word", "")
            if not word:
                continue
                
            word_lower = word.lower()
            if word_lower in text_lower:
                start = text_lower.find(word_lower)
                end = start + len(word)
                original = text[start:end]
                
                matches.append(FixedPhrase(
                    text=original,
                    normalized=word_lower,
                    start=start,
                    end=end,
                    phrase_type="品牌词",
                    confidence=entry.get("confidence", 0.95)
                ))
                
                # 用占位符替换，避免被后续处理拆分
                placeholder = '\x00' * len(word)
                text = text[:start] + placeholder + text[end:]
                text_lower = text.lower()
        
        # 清理占位符
        remaining = text.replace('\x00', ' ')
        remaining = re.sub(r'\s+', ' ', remaining).strip()
        
        return matches, remaining
    
    def _extract_patterns(self, text: str, patterns: List[Tuple[str, str]]) -> Tuple[List[FixedPhrase], str]:
        """使用正则模式提取"""
        matches = []
        remaining = text
        
        for pattern, phrase_type in patterns:
            for match in re.finditer(pattern, remaining, re.IGNORECASE):
                matches.append(FixedPhrase(
                    text=match.group(),
                    normalized=match.group().lower(),
                    start=match.start(),
                    end=match.end(),
                    phrase_type=phrase_type,
                    confidence=0.95
                ))
                
                # 用占位符替换
                placeholder = '\x00' * (match.end() - match.start())
                remaining = remaining[:match.start()] + placeholder + remaining[match.end():]
        
        # 清理占位符
        remaining = remaining.replace('\x00', ' ')
        remaining = re.sub(r'\s+', ' ', remaining).strip()
        
        return matches, remaining
