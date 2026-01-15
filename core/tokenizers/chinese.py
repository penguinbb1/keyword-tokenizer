"""
中文分词器
"""
from typing import List
from core.tokenizers.base import BaseTokenizer, Token

_jieba = None


def get_jieba():
    global _jieba
    if _jieba is None:
        import jieba
        jieba.setLogLevel(20)
        _jieba = jieba
    return _jieba


class ChineseTokenizer(BaseTokenizer):
    """中文分词器"""
    
    def __init__(self, dictionary_manager=None):
        super().__init__(dictionary_manager)
        self.jieba = get_jieba()
        
        # 将词典中的词添加到jieba
        if dictionary_manager:
            self._load_custom_words(dictionary_manager)
    
    def _load_custom_words(self, dict_manager):
        """从词典加载自定义词"""
        words = dict_manager.get_all_words_for_tokenizer("zh")
        for word in words:
            if len(word) > 1:  # 只添加多字词
                self.jieba.add_word(word)
    
    def tokenize(self, text: str) -> List[Token]:
        """中文分词"""
        if not text:
            return []
        words = self.jieba.lcut(text)
        tokens = []
        for word in words:
            word = word.strip()
            if word:
                tokens.append(Token(text=word))
        return tokens
    
    def add_word(self, word: str, freq: int = None):
        """添加词"""
        if freq:
            self.jieba.add_word(word, freq)
        else:
            self.jieba.add_word(word)
