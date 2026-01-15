"""
欧语分词器（英语、德语、法语、西班牙语）
"""
import re
from typing import List
from core.tokenizers.base import BaseTokenizer, Token
from core.language_detector import Language


class EuropeanTokenizer(BaseTokenizer):
    """欧语分词器"""
    
    def __init__(self, dictionary_manager=None, language: Language = Language.ENGLISH):
        super().__init__(dictionary_manager)
        self.language = language
        self.custom_words = set()
    
    def tokenize(self, text: str) -> List[Token]:
        """欧语分词"""
        if not text:
            return []
        
        # 基本分词：按空格和标点分割
        words = re.split(r'[\s,;:!?()[\]{}]+', text)
        words = [w for w in words if w]
        
        # 法语特殊处理（撇号）
        if self.language == Language.FRENCH:
            words = self._process_french(words)
        
        # 处理连字符
        words = self._handle_hyphens(words)
        
        return [Token(text=w) for w in words if w]
    
    def _process_french(self, words: List[str]) -> List[str]:
        """处理法语撇号缩写（如 l'eau -> l', eau）"""
        result = []
        for word in words:
            if "'" in word:
                parts = word.split("'")
                # 常见的法语冠词缩写：l', d', j', qu', n'
                if len(parts) == 2 and len(parts[0]) <= 2:
                    result.extend(parts)
                else:
                    result.append(word)
            else:
                result.append(word)
        return result
    
    def _handle_hyphens(self, words: List[str]) -> List[str]:
        """处理连字符复合词"""
        result = []
        for word in words:
            if '-' in word:
                parts = word.split('-')
                # 保留短的复合词（如 Coca-Cola, Mercedes-Benz）
                if all(len(p) <= 10 for p in parts) and len(parts) <= 3:
                    result.append(word)
                else:
                    result.extend(parts)
            else:
                result.append(word)
        return result
    
    def add_word(self, word: str, freq: int = None):
        """添加词"""
        self.custom_words.add(word.lower())
