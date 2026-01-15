"""
语言检测模块
"""
import re
from typing import List
from enum import Enum
from dataclasses import dataclass


class Language(Enum):
    """支持的语言"""
    CHINESE = "zh"
    JAPANESE = "ja"
    ENGLISH = "en"
    GERMAN = "de"
    FRENCH = "fr"
    SPANISH = "es"
    UNKNOWN = "unknown"
    MIXED = "mixed"


@dataclass
class LanguageSegment:
    """语言分段"""
    text: str
    language: Language


class LanguageDetector:
    """语言检测器"""
    
    def detect_char_script(self, char: str) -> str:
        """检测字符的文字系统"""
        code = ord(char)
        
        # CJK 统一汉字
        if 0x4E00 <= code <= 0x9FFF:
            return "han"
        # 平假名
        if 0x3040 <= code <= 0x309F:
            return "hiragana"
        # 片假名
        if 0x30A0 <= code <= 0x30FF:
            return "katakana"
        # 基础拉丁字母
        if 0x0041 <= code <= 0x007A:
            return "latin"
        # 拉丁扩展（德法西常用字符）
        if 0x00C0 <= code <= 0x00FF:
            return "latin_extended"
        # 数字
        if 0x0030 <= code <= 0x0039:
            return "digit"
        if char.isspace():
            return "space"
        return "other"
    
    def detect_language(self, text: str) -> Language:
        """检测文本主要语言"""
        if not text:
            return Language.UNKNOWN
        
        script_counts = {}
        for char in text:
            script = self.detect_char_script(char)
            if script not in ["space", "digit", "other"]:
                script_counts[script] = script_counts.get(script, 0) + 1
        
        if not script_counts:
            return Language.UNKNOWN
        
        has_hiragana = script_counts.get("hiragana", 0) > 0
        has_katakana = script_counts.get("katakana", 0) > 0
        has_han = script_counts.get("han", 0) > 0
        has_latin = script_counts.get("latin", 0) + script_counts.get("latin_extended", 0) > 0
        
        # 日语判断（有假名）
        if has_hiragana or has_katakana:
            return Language.JAPANESE
        # 纯中文
        if has_han and not has_latin:
            return Language.CHINESE
        # 纯拉丁文字
        if has_latin and not has_han:
            return self._detect_european_language(text)
        # 混合
        return Language.MIXED
    
    def _detect_european_language(self, text: str) -> Language:
        """区分欧洲语言"""
        text_lower = text.lower()
        
        # 德语特征字符
        if re.search(r'[äöüß]', text_lower):
            return Language.GERMAN
        # 法语特征字符
        if re.search(r'[çœæ]', text_lower):
            return Language.FRENCH
        # 西班牙语特征字符
        if re.search(r'[ñ¿¡]', text_lower):
            return Language.SPANISH
        # 默认英语
        return Language.ENGLISH
    
    def segment_by_language(self, text: str) -> List[LanguageSegment]:
        """按语言分段"""
        if not text:
            return []
        
        segments = []
        current_text = ""
        current_lang = None
        
        for char in text:
            script = self.detect_char_script(char)
            
            # 空格、数字、其他字符保持在当前段
            if script in ["space", "digit", "other"]:
                current_text += char
                continue
            
            # 确定字符语言
            if script in ["hiragana", "katakana"]:
                char_lang = Language.JAPANESE
            elif script == "han":
                char_lang = Language.CHINESE
            else:
                char_lang = Language.ENGLISH  # 拉丁字符暂时标记为英语
            
            # 开始新段或继续当前段
            if current_lang is None:
                current_lang = char_lang
            elif current_lang != char_lang:
                # 保存当前段，开始新段
                if current_text.strip():
                    segments.append(LanguageSegment(
                        text=current_text,
                        language=current_lang
                    ))
                current_text = ""
                current_lang = char_lang
            
            current_text += char
        
        # 保存最后一段
        if current_text.strip():
            segments.append(LanguageSegment(
                text=current_text,
                language=current_lang or Language.UNKNOWN
            ))
        
        return self._merge_segments(segments)
    
    def _merge_segments(self, segments: List[LanguageSegment]) -> List[LanguageSegment]:
        """合并相邻同语言段"""
        if not segments:
            return []
        
        merged = [segments[0]]
        for seg in segments[1:]:
            if seg.language == merged[-1].language:
                merged[-1] = LanguageSegment(
                    text=merged[-1].text + seg.text,
                    language=merged[-1].language
                )
            else:
                merged.append(seg)
        return merged


# 全局实例
language_detector = LanguageDetector()
