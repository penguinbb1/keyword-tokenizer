"""
脚本分段器
将混合语言文本按字符类型（脚本）分段，每段用对应的分词器处理

解决问题：电商标题常见混合语言，如 "New Balance 跑步鞋 メンズ 10.5cm"
传统做法（整句语言检测）会导致某些部分被错误分词
"""
import re
import unicodedata
from typing import List, Tuple, NamedTuple
from enum import Enum


class ScriptType(Enum):
    """脚本类型"""
    CJK = "cjk"           # 中文汉字
    KANA = "kana"         # 日语假名（平假名+片假名）
    HANGUL = "hangul"     # 韩语
    LATIN = "latin"       # 拉丁字母（英语、德语、法语、西班牙语等）
    NUMBER = "number"     # 数字
    SPACE = "space"       # 空格
    PUNCT = "punct"       # 标点符号
    OTHER = "other"       # 其他


class Segment(NamedTuple):
    """分段结果"""
    text: str
    script: ScriptType
    start: int
    end: int


class ScriptSegmenter:
    """
    脚本分段器
    
    将文本按字符类型分段，便于后续用不同分词器处理每一段
    
    示例：
    输入: "New Balance跑步鞋メンズ10.5cm"
    输出: [
        Segment("New Balance", LATIN, 0, 11),
        Segment("跑步鞋", CJK, 11, 14),
        Segment("メンズ", KANA, 14, 17),
        Segment("10.5", NUMBER, 17, 21),
        Segment("cm", LATIN, 21, 23)
    ]
    """
    
    def __init__(self, merge_adjacent_latin: bool = True):
        """
        Args:
            merge_adjacent_latin: 是否合并相邻的 Latin 和数字段
                                  （如 "10.5cm" 保持完整）
        """
        self.merge_adjacent_latin = merge_adjacent_latin
    
    def segment(self, text: str) -> List[Segment]:
        """
        对文本进行脚本分段
        
        Args:
            text: 输入文本
            
        Returns:
            分段列表，每段包含文本、脚本类型、起止位置
        """
        if not text:
            return []
        
        segments = []
        current_text = ""
        current_script = None
        current_start = 0
        
        for i, char in enumerate(text):
            char_script = self._get_script_type(char)
            
            # 空格特殊处理：根据上下文决定归属
            if char_script == ScriptType.SPACE:
                # 如果当前有累积的段，先保存
                if current_text.strip():
                    segments.append(Segment(
                        text=current_text,
                        script=current_script,
                        start=current_start,
                        end=i
                    ))
                    current_text = ""
                    current_script = None
                # 跳过空格，重置起始位置
                current_start = i + 1
                continue
            
            # 脚本类型变化，保存当前段
            if current_script is not None and char_script != current_script:
                # 检查是否应该合并（Latin + Number 或 Number + Latin）
                should_merge = (
                    self.merge_adjacent_latin and
                    self._can_merge(current_script, char_script)
                )
                
                if not should_merge:
                    if current_text.strip():
                        segments.append(Segment(
                            text=current_text,
                            script=current_script,
                            start=current_start,
                            end=i
                        ))
                    current_text = char
                    current_script = char_script
                    current_start = i
                else:
                    # 合并，保持 Latin 类型
                    current_text += char
                    if current_script == ScriptType.NUMBER:
                        current_script = ScriptType.LATIN
            else:
                current_text += char
                if current_script is None:
                    current_script = char_script
        
        # 保存最后一段
        if current_text.strip():
            segments.append(Segment(
                text=current_text,
                script=current_script,
                start=current_start,
                end=len(text)
            ))
        
        # 后处理：合并可以合并的段
        segments = self._post_merge(segments)
        
        return segments
    
    def _get_script_type(self, char: str) -> ScriptType:
        """判断单个字符的脚本类型"""
        if not char:
            return ScriptType.OTHER
        
        code = ord(char)
        
        # 空格
        if char.isspace():
            return ScriptType.SPACE
        
        # 数字（包括全角数字）
        if char.isdigit():
            return ScriptType.NUMBER
        
        # CJK 汉字
        if self._is_cjk(code):
            return ScriptType.CJK
        
        # 日语假名
        if self._is_kana(code):
            return ScriptType.KANA
        
        # 韩语
        if self._is_hangul(code):
            return ScriptType.HANGUL
        
        # Latin 字母（包括扩展拉丁）
        if self._is_latin(code):
            return ScriptType.LATIN
        
        # 标点符号
        if unicodedata.category(char).startswith('P'):
            return ScriptType.PUNCT
        
        return ScriptType.OTHER
    
    def _is_cjk(self, code: int) -> bool:
        """判断是否是 CJK 汉字"""
        return (
            0x4E00 <= code <= 0x9FFF or      # CJK Unified Ideographs
            0x3400 <= code <= 0x4DBF or      # CJK Unified Ideographs Extension A
            0x20000 <= code <= 0x2A6DF or    # CJK Unified Ideographs Extension B
            0x2A700 <= code <= 0x2B73F or    # CJK Unified Ideographs Extension C
            0x2B740 <= code <= 0x2B81F or    # CJK Unified Ideographs Extension D
            0xF900 <= code <= 0xFAFF or      # CJK Compatibility Ideographs
            0x2F00 <= code <= 0x2FDF         # Kangxi Radicals
        )
    
    def _is_kana(self, code: int) -> bool:
        """判断是否是日语假名"""
        return (
            0x3040 <= code <= 0x309F or      # Hiragana
            0x30A0 <= code <= 0x30FF or      # Katakana
            0x31F0 <= code <= 0x31FF or      # Katakana Phonetic Extensions
            0xFF65 <= code <= 0xFF9F         # Halfwidth Katakana
        )
    
    def _is_hangul(self, code: int) -> bool:
        """判断是否是韩语"""
        return (
            0xAC00 <= code <= 0xD7AF or      # Hangul Syllables
            0x1100 <= code <= 0x11FF or      # Hangul Jamo
            0x3130 <= code <= 0x318F         # Hangul Compatibility Jamo
        )
    
    def _is_latin(self, code: int) -> bool:
        """判断是否是拉丁字母"""
        return (
            0x0041 <= code <= 0x005A or      # A-Z
            0x0061 <= code <= 0x007A or      # a-z
            0x00C0 <= code <= 0x00FF or      # Latin-1 Supplement (带重音的字母)
            0x0100 <= code <= 0x017F or      # Latin Extended-A
            0x0180 <= code <= 0x024F or      # Latin Extended-B
            0x1E00 <= code <= 0x1EFF or      # Latin Extended Additional
            0xFF21 <= code <= 0xFF3A or      # Fullwidth A-Z
            0xFF41 <= code <= 0xFF5A         # Fullwidth a-z
        )
    
    def _can_merge(self, script1: ScriptType, script2: ScriptType) -> bool:
        """判断两种脚本类型是否可以合并"""
        mergeable = {ScriptType.LATIN, ScriptType.NUMBER, ScriptType.PUNCT}
        return script1 in mergeable and script2 in mergeable
    
    def _post_merge(self, segments: List[Segment]) -> List[Segment]:
        """后处理：合并相邻的可合并段"""
        if not segments:
            return segments
        
        merged = []
        current = segments[0]
        
        for next_seg in segments[1:]:
            # 检查是否可以合并
            if self._can_merge(current.script, next_seg.script):
                # 检查是否相邻（允许小间隔）
                gap = next_seg.start - current.end
                if gap <= 1:
                    # 合并
                    current = Segment(
                        text=current.text + (" " * gap) + next_seg.text,
                        script=ScriptType.LATIN,  # 合并后统一为 LATIN
                        start=current.start,
                        end=next_seg.end
                    )
                    continue
            
            merged.append(current)
            current = next_seg
        
        merged.append(current)
        return merged
    
    def get_tokenizer_for_script(self, script: ScriptType) -> str:
        """
        根据脚本类型返回推荐的分词器
        
        Returns:
            分词器标识: 'chinese', 'japanese', 'european', 'passthrough'
        """
        mapping = {
            ScriptType.CJK: 'chinese',
            ScriptType.KANA: 'japanese',
            ScriptType.HANGUL: 'korean',
            ScriptType.LATIN: 'european',
            ScriptType.NUMBER: 'passthrough',
            ScriptType.PUNCT: 'passthrough',
            ScriptType.OTHER: 'passthrough',
        }
        return mapping.get(script, 'european')


# 便捷函数
def segment_by_script(text: str) -> List[Segment]:
    """便捷函数：对文本进行脚本分段"""
    segmenter = ScriptSegmenter()
    return segmenter.segment(text)


# 测试代码
if __name__ == "__main__":
    segmenter = ScriptSegmenter()
    
    test_cases = [
        "New Balance跑步鞋男士黑色10.5码",
        "ランニングベスト メンズ 軽量",
        "iPhone 14 Pro Max 256GB",
        "Adidas Ultraboost 22 ランニングシューズ",
        "thermoleggings damen winter",
        "登山 リュック レディース 15L",
    ]
    
    for text in test_cases:
        print(f"\n输入: {text}")
        segments = segmenter.segment(text)
        for seg in segments:
            print(f"  [{seg.script.value}] '{seg.text}' ({seg.start}:{seg.end})")
