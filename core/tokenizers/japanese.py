"""
日语分词器
"""
import re
from typing import List
from core.tokenizers.base import BaseTokenizer, Token

_sudachi_tokenizer = None


def get_sudachi():
    global _sudachi_tokenizer
    if _sudachi_tokenizer is None:
        try:
            from sudachipy import dictionary
            _sudachi_tokenizer = dictionary.Dictionary().create()
        except ImportError:
            print("警告: sudachipy未安装，将使用简单分词")
            _sudachi_tokenizer = "fallback"
    return _sudachi_tokenizer


class JapaneseTokenizer(BaseTokenizer):
    """日语分词器"""
    
    def __init__(self, dictionary_manager=None):
        super().__init__(dictionary_manager)
        self.tokenizer = get_sudachi()
    
    def tokenize(self, text: str) -> List[Token]:
        """日语分词"""
        if not text:
            return []
        
        if self.tokenizer == "fallback":
            return self._simple_tokenize(text)
        
        try:
            from sudachipy import tokenizer as sudachi_tokenizer
            morphemes = self.tokenizer.tokenize(text, sudachi_tokenizer.Tokenizer.SplitMode.C)
            tokens = []
            for m in morphemes:
                surface = m.surface().strip()
                if surface:
                    tokens.append(Token(text=surface))
            return tokens
        except Exception:
            return self._simple_tokenize(text)
    
    def _simple_tokenize(self, text: str) -> List[Token]:
        """简单分词（fallback）"""
        words = re.split(r'[\s、。，．・]+', text)
        return [Token(text=w) for w in words if w]
    
    def add_word(self, word: str, freq: int = None):
        """sudachi不支持动态添加"""
        pass
