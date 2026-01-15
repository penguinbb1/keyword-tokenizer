"""
基于 Span 的固定短语提取器

解决问题：
1. 子串误匹配（"one" 匹配到 "someone"，"cat" 匹配到 "catholic"）
2. 位置信息丢失（replace 会破坏上下文）
3. 重叠/包含关系处理（"new balance" vs "balance"）

实现方案：
- 使用 Trie 树做最长匹配
- 输出 span 列表而不是替换字符串
- 支持边界感知匹配（token boundary / word boundary）
"""
from typing import List, Dict, Set, Tuple, Optional, NamedTuple
from dataclasses import dataclass
from enum import Enum
import re


class SpanType(Enum):
    """Span 类型"""
    BRAND = "brand"
    MODEL = "model"
    FIXED_PHRASE = "fixed_phrase"
    NUMBER_UNIT = "number_unit"


@dataclass
class Span:
    """表示文本中的一个区间"""
    start: int
    end: int
    text: str
    span_type: SpanType
    tag: str  # 标签类型（品牌词、商品词等）
    confidence: float
    
    @property
    def length(self) -> int:
        return self.end - self.start


class TrieNode:
    """Trie 树节点"""
    def __init__(self):
        self.children: Dict[str, 'TrieNode'] = {}
        self.is_end: bool = False
        self.data: Optional[Dict] = None  # 存储匹配到的词条信息


class Trie:
    """Trie 树，用于高效的最长前缀匹配"""
    
    def __init__(self, case_sensitive: bool = False):
        self.root = TrieNode()
        self.case_sensitive = case_sensitive
    
    def _normalize(self, text: str) -> str:
        """标准化文本"""
        if not self.case_sensitive:
            return text.lower()
        return text
    
    def insert(self, word: str, data: Dict = None):
        """插入词条"""
        word = self._normalize(word)
        node = self.root
        
        for char in word:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        
        node.is_end = True
        node.data = data or {}
    
    def search_longest(self, text: str, start: int = 0) -> Optional[Tuple[str, int, Dict]]:
        """
        从指定位置开始，查找最长匹配
        
        Returns:
            (匹配的词, 结束位置, 词条数据) 或 None
        """
        text_normalized = self._normalize(text)
        node = self.root
        
        last_match = None
        last_match_pos = start
        last_match_data = None
        
        for i in range(start, len(text_normalized)):
            char = text_normalized[i]
            
            if char not in node.children:
                break
            
            node = node.children[char]
            
            if node.is_end:
                # 记录当前匹配
                last_match = text[start:i+1]
                last_match_pos = i + 1
                last_match_data = node.data
        
        if last_match:
            return (last_match, last_match_pos, last_match_data)
        return None


class SpanPhraseExtractor:
    """
    基于 Span 的固定短语提取器
    
    特点：
    1. 使用 Trie 树做最长匹配，避免短词误匹配长词的子串
    2. 支持边界感知（只在词边界匹配）
    3. 输出 span 列表，保留位置信息
    4. 不修改原文本，只标记区间
    """
    
    def __init__(self, dictionary_manager=None):
        self.dict_manager = dictionary_manager
        
        # 两种 Trie：一个用于 CJK（字符级匹配），一个用于 Latin（词级匹配）
        self.cjk_trie = Trie(case_sensitive=False)
        self.latin_trie = Trie(case_sensitive=False)
        
        # 编译正则模式：数字+单位
        self.number_unit_pattern = re.compile(
            r'(\d+\.?\d*)\s*'
            r'(码|寸|号|cm|mm|m|inch|英寸|厘米|'
            r'kg|g|lb|磅|克|千克|'
            r'ml|l|毫升|升|'
            r'GB|TB|MB|gb|tb|mb|'
            r'张|片|个|只|条|支|瓶|盒|包|袋|件|套|双|对)',
            re.IGNORECASE
        )
        
        if dictionary_manager:
            self._load_from_dictionary()
    
    def _load_from_dictionary(self):
        """从词典加载固定短语"""
        # 加载品牌词
        brands = self.dict_manager.get_entries("brands")
        for entry in brands:
            word = entry.get("word", "")
            if self._is_cjk_dominant(word):
                self.cjk_trie.insert(word, {
                    "tag": "品牌词",
                    "confidence": entry.get("confidence", 0.95),
                    "type": SpanType.BRAND
                })
            else:
                self.latin_trie.insert(word, {
                    "tag": "品牌词",
                    "confidence": entry.get("confidence", 0.95),
                    "type": SpanType.BRAND
                })
        
        # 可以加载更多类型的固定短语...
    
    def _is_cjk_dominant(self, text: str) -> bool:
        """判断文本是否以 CJK 字符为主"""
        cjk_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u30ff')
        return cjk_count > len(text) / 2
    
    def add_phrase(self, phrase: str, tag: str, confidence: float = 0.95, 
                   span_type: SpanType = SpanType.FIXED_PHRASE):
        """添加固定短语"""
        data = {
            "tag": tag,
            "confidence": confidence,
            "type": span_type
        }
        
        if self._is_cjk_dominant(phrase):
            self.cjk_trie.insert(phrase, data)
        else:
            self.latin_trie.insert(phrase, data)
    
    def extract(self, text: str, segments: List = None) -> Tuple[List[Span], List[Tuple[int, int]]]:
        """
        提取固定短语
        
        Args:
            text: 输入文本
            segments: 脚本分段结果（可选，用于优化匹配）
            
        Returns:
            (spans: 提取出的固定短语 span 列表,
             locked_ranges: 被锁定的区间列表，后续分词应跳过这些区间)
        """
        spans = []
        locked_ranges = []
        
        # 1. 提取数字+单位组合
        for match in self.number_unit_pattern.finditer(text):
            span = Span(
                start=match.start(),
                end=match.end(),
                text=match.group(),
                span_type=SpanType.NUMBER_UNIT,
                tag="尺寸词",
                confidence=0.95
            )
            spans.append(span)
            locked_ranges.append((match.start(), match.end()))
        
        # 2. 提取品牌和固定短语
        text_lower = text.lower()
        i = 0
        
        while i < len(text):
            # 检查是否在已锁定区间内
            if self._is_in_locked_range(i, locked_ranges):
                i += 1
                continue
            
            # 判断当前位置的字符类型
            char = text[i]
            
            if self._is_cjk_char(char):
                # CJK 字符：使用 CJK Trie 匹配
                result = self.cjk_trie.search_longest(text, i)
                if result:
                    matched_text, end_pos, data = result
                    span = Span(
                        start=i,
                        end=end_pos,
                        text=matched_text,
                        span_type=data.get("type", SpanType.FIXED_PHRASE),
                        tag=data.get("tag", "属性词"),
                        confidence=data.get("confidence", 0.9)
                    )
                    spans.append(span)
                    locked_ranges.append((i, end_pos))
                    i = end_pos
                    continue
            else:
                # Latin 字符：使用词边界匹配
                result = self._match_latin_with_boundary(text, text_lower, i)
                if result:
                    matched_text, end_pos, data = result
                    span = Span(
                        start=i,
                        end=end_pos,
                        text=matched_text,
                        span_type=data.get("type", SpanType.FIXED_PHRASE),
                        tag=data.get("tag", "属性词"),
                        confidence=data.get("confidence", 0.9)
                    )
                    spans.append(span)
                    locked_ranges.append((i, end_pos))
                    i = end_pos
                    continue
            
            i += 1
        
        # 3. 按位置排序
        spans.sort(key=lambda s: s.start)
        locked_ranges.sort(key=lambda r: r[0])
        
        return spans, locked_ranges
    
    def _match_latin_with_boundary(self, text: str, text_lower: str, start: int) -> Optional[Tuple[str, int, Dict]]:
        """
        在词边界处匹配 Latin 短语
        
        解决问题：避免 "one" 匹配到 "someone" 的子串
        """
        # 检查是否在词边界（只检查 Latin 字符，CJK 是天然边界）
        if start > 0:
            prev_char = text_lower[start-1]
            # 只有前一个字符是 Latin 字母或数字时才算"不在边界"
            if prev_char.isascii() and prev_char.isalnum():
                return None
        
        result = self.latin_trie.search_longest(text_lower, start)
        if result:
            matched_text, end_pos, data = result
            
            # 检查结束位置是否是词边界（只检查 Latin 字符）
            if end_pos < len(text):
                next_char = text_lower[end_pos]
                # 只有下一个字符是 Latin 字母或数字时才算"不在边界"
                if next_char.isascii() and next_char.isalnum():
                    return None
            
            # 返回原始大小写的文本
            return (text[start:end_pos], end_pos, data)
        
        return None
    
    def _is_in_locked_range(self, pos: int, locked_ranges: List[Tuple[int, int]]) -> bool:
        """检查位置是否在已锁定区间内"""
        for start, end in locked_ranges:
            if start <= pos < end:
                return True
        return False
    
    def _is_cjk_char(self, char: str) -> bool:
        """判断是否是 CJK 字符"""
        code = ord(char)
        return (
            0x4E00 <= code <= 0x9FFF or
            0x3040 <= code <= 0x309F or
            0x30A0 <= code <= 0x30FF
        )
    
    def get_remaining_text_segments(self, text: str, locked_ranges: List[Tuple[int, int]]) -> List[Tuple[int, int, str]]:
        """
        获取未被锁定的文本段
        
        Returns:
            [(start, end, text), ...]
        """
        if not locked_ranges:
            return [(0, len(text), text)]
        
        segments = []
        prev_end = 0
        
        for start, end in sorted(locked_ranges):
            if prev_end < start:
                segments.append((prev_end, start, text[prev_end:start]))
            prev_end = end
        
        if prev_end < len(text):
            segments.append((prev_end, len(text), text[prev_end:]))
        
        return segments


# 常用短语预设
COMMON_PHRASES = {
    # 英语
    "long sleeve": ("属性词", 0.9),
    "short sleeve": ("属性词", 0.9),
    "high waist": ("属性词", 0.9),
    "low waist": ("属性词", 0.9),
    "slim fit": ("属性词", 0.9),
    "loose fit": ("属性词", 0.9),
    "quick dry": ("卖点词", 0.9),
    "water resistant": ("卖点词", 0.9),
    "water proof": ("卖点词", 0.9),
    "open ear": ("属性词", 0.9),
    "noise cancelling": ("卖点词", 0.9),
    "memory foam": ("属性词", 0.9),
    "stainless steel": ("属性词", 0.9),
    
    # 德语
    "mit kapuze": ("属性词", 0.9),
    "hohe taille": ("属性词", 0.9),
    
    # 法语
    "taille haute": ("属性词", 0.9),
    "manches longues": ("属性词", 0.9),
    "manches courtes": ("属性词", 0.9),
    "sous lit": ("属性词", 0.9),
    "à roulettes": ("属性词", 0.9),
    
    # 西班牙语
    "manga larga": ("属性词", 0.9),
    "manga corta": ("属性词", 0.9),
    "cintura alta": ("属性词", 0.9),
}


def create_span_extractor(dictionary_manager=None) -> SpanPhraseExtractor:
    """工厂函数：创建预配置的 SpanPhraseExtractor"""
    extractor = SpanPhraseExtractor(dictionary_manager)
    
    # 添加常用短语
    for phrase, (tag, confidence) in COMMON_PHRASES.items():
        extractor.add_phrase(phrase, tag, confidence)
    
    return extractor


# 测试代码
if __name__ == "__main__":
    extractor = SpanPhraseExtractor()
    
    # 添加测试短语
    extractor.add_phrase("new balance", "品牌词", 0.95, SpanType.BRAND)
    extractor.add_phrase("nike", "品牌词", 0.95, SpanType.BRAND)
    extractor.add_phrase("long sleeve", "属性词", 0.9)
    extractor.add_phrase("high waist", "属性词", 0.9)
    
    test_cases = [
        "New Balance跑步鞋男士黑色10.5码",
        "someone bought a nike shirt",  # 测试边界匹配
        "long sleeve t-shirt for men",
        "high waist leggings damen",
    ]
    
    for text in test_cases:
        print(f"\n输入: {text}")
        spans, locked = extractor.extract(text)
        print(f"  提取的 spans:")
        for span in spans:
            print(f"    '{span.text}' [{span.tag}] ({span.start}:{span.end}) conf={span.confidence}")
        print(f"  锁定区间: {locked}")
