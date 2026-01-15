"""
基础测试
"""
import pytest
from core.preprocessor import Preprocessor
from core.language_detector import LanguageDetector
from core.tokenizers import get_tokenizer


class TestPreprocessor:
    """预处理器测试"""
    
    def setup_method(self):
        self.preprocessor = Preprocessor()
    
    def test_normalize_fullwidth(self):
        """测试全角转半角"""
        text = "Ｈｅｌｌｏ　Ｗｏｒｌｄ"
        result = self.preprocessor.normalize(text)
        assert result == "Hello World"
    
    def test_normalize_whitespace(self):
        """测试空白处理"""
        text = "Hello    World   "
        result = self.preprocessor.normalize(text)
        assert result == "Hello World"
    
    def test_normalize_chinese(self):
        """测试中文不变"""
        text = "华为手机"
        result = self.preprocessor.normalize(text)
        assert result == "华为手机"


class TestLanguageDetector:
    """语言检测器测试"""
    
    def setup_method(self):
        self.detector = LanguageDetector()
    
    def test_detect_chinese(self):
        """测试中文检测"""
        assert self.detector.detect_language("华为手机") == "zh"
    
    def test_detect_japanese(self):
        """测试日语检测"""
        assert self.detector.detect_language("ケース") == "ja"
        assert self.detector.detect_language("こんにちは") == "ja"
    
    def test_detect_english(self):
        """测试英语检测"""
        assert self.detector.detect_language("running shoes") == "en"
    
    def test_detect_german(self):
        """测试德语检测"""
        assert self.detector.detect_language("Laufschuhe für Herren") == "de"
    
    def test_segment_mixed(self):
        """测试混合语言分段"""
        text = "New Balance跑步鞋"
        segments = self.detector.segment_by_language(text)
        assert len(segments) >= 2


class TestTokenizers:
    """分词器测试"""
    
    def test_chinese_tokenizer(self):
        """测试中文分词"""
        tokenizer = get_tokenizer("zh")
        tokens = tokenizer.tokenize("跑步鞋男士黑色")
        assert len(tokens) > 0
        assert "跑步鞋" in tokens or "跑步" in tokens
    
    def test_english_tokenizer(self):
        """测试英文分词"""
        tokenizer = get_tokenizer("en")
        tokens = tokenizer.tokenize("running shoes for men")
        assert "running" in tokens
        assert "shoes" in tokens
    
    def test_european_tokenizer_hyphen(self):
        """测试连字符处理"""
        tokenizer = get_tokenizer("en")
        tokens = tokenizer.tokenize("high-quality shoes")
        # 短连字符词应该保持
        assert "high-quality" in tokens or "high" in tokens


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
