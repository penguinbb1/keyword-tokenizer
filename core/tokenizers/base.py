"""
分词器基类
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class Token:
    """分词结果"""
    text: str
    start: int = 0
    end: int = 0
    pos: str = ""  # 词性


class BaseTokenizer(ABC):
    """分词器基类"""
    
    def __init__(self, dictionary_manager=None):
        self.dict_manager = dictionary_manager
    
    @abstractmethod
    def tokenize(self, text: str) -> List[Token]:
        """分词"""
        pass
    
    def add_word(self, word: str, freq: int = None):
        """添加词到分词器（可选实现）"""
        pass
