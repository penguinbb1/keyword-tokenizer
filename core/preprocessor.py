"""
文本预处理模块
- 统一大小写
- 全角半角转换
- 特殊字符处理
"""
import re
import unicodedata
from typing import Tuple


class Preprocessor:
    """文本预处理器"""
    
    def __init__(self):
        # 需要保留的特殊字符（在商品标题中有意义）
        self.preserve_chars = set(['-', '/', '.', '+', '&', "'"])
    
    def process(self, text: str) -> Tuple[str, dict]:
        """
        预处理文本
        
        Args:
            text: 原始文本
            
        Returns:
            (处理后的文本, 处理记录)
        """
        original = text
        record = {"original": original, "steps": []}
        
        # Step 1: Unicode 规范化
        text = unicodedata.normalize("NFKC", text)
        record["steps"].append("unicode_normalize")
        
        # Step 2: 全角转半角
        text = self._fullwidth_to_halfwidth(text)
        record["steps"].append("fullwidth_to_halfwidth")
        
        # Step 3: 统一空白字符
        text = self._normalize_whitespace(text)
        record["steps"].append("normalize_whitespace")
        
        # Step 4: 清理无意义字符（保留有意义的特殊字符）
        text = self._clean_special_chars(text)
        record["steps"].append("clean_special_chars")
        
        record["processed"] = text
        return text, record
    
    def _fullwidth_to_halfwidth(self, text: str) -> str:
        """全角转半角"""
        result = []
        for char in text:
            code = ord(char)
            # 全角空格
            if code == 0x3000:
                result.append(' ')
            # 全角字符范围
            elif 0xFF01 <= code <= 0xFF5E:
                result.append(chr(code - 0xFEE0))
            else:
                result.append(char)
        return ''.join(result)
    
    def _normalize_whitespace(self, text: str) -> str:
        """统一空白字符"""
        # 多个空白变成单个空格
        text = re.sub(r'\s+', ' ', text)
        # 去除首尾空白
        text = text.strip()
        return text
    
    def _clean_special_chars(self, text: str) -> str:
        """清理特殊字符，保留有意义的"""
        result = []
        for char in text:
            if char.isalnum() or char.isspace():
                result.append(char)
            elif char in self.preserve_chars:
                result.append(char)
            # 保留 CJK 字符
            elif '\u4e00' <= char <= '\u9fff':  # 中文
                result.append(char)
            elif '\u3040' <= char <= '\u30ff':  # 日文假名
                result.append(char)
            elif '\u3400' <= char <= '\u4dbf':  # CJK扩展A
                result.append(char)
            # 其他字符用空格替代
            else:
                result.append(' ')
        
        # 再次清理多余空格
        return re.sub(r'\s+', ' ', ''.join(result)).strip()


# 单例
preprocessor = Preprocessor()
