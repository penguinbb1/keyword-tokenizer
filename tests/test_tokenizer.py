"""
分词功能测试
"""
import pytest
import sys
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.dictionary_manager import DictionaryManager
from core.preprocessor import preprocessor
from core.language_detector import language_detector, Language


class TestPreprocessor:
    """预处理器测试"""
    
    def test_fullwidth_to_halfwidth(self):
        """测试全角转半角"""
        text = "Ｈｅｌｌｏ　Ｗｏｒｌｄ"
        result, _ = preprocessor.process(text)
        assert "Hello" in result
    
    def test_normalize_whitespace(self):
        """测试空白字符规范化"""
        text = "Hello    World"
        result, _ = preprocessor.process(text)
        assert result == "Hello World"
    
    def test_preserve_special_chars(self):
        """测试保留特殊字符"""
        text = "Coca-Cola 10.5oz"
        result, _ = preprocessor.process(text)
        assert "-" in result
        assert "." in result


class TestLanguageDetector:
    """语言检测器测试"""
    
    def test_detect_chinese(self):
        """测试中文检测"""
        assert language_detector.detect("跑步鞋") == Language.CHINESE
    
    def test_detect_japanese(self):
        """测试日语检测（包含假名）"""
        assert language_detector.detect("ランニングシューズ") == Language.JAPANESE
    
    def test_detect_english(self):
        """测试英语检测"""
        assert language_detector.detect("running shoes") == Language.ENGLISH
    
    def test_detect_german(self):
        """测试德语检测"""
        assert language_detector.detect("Laufschuhe größe") == Language.GERMAN
    
    def test_detect_mixed(self):
        """测试混合语言分段"""
        text = "New Balance跑步鞋"
        segments = language_detector.segment_by_language(text)
        assert len(segments) >= 2


class TestDictionaryManager:
    """词典管理器测试"""
    
    @pytest.fixture
    def dict_manager(self):
        """创建测试用词典管理器"""
        dict_path = Path(__file__).parent.parent / "dictionaries"
        dm = DictionaryManager(dict_path)
        dm.load_all()
        return dm
    
    def test_load_dictionaries(self, dict_manager):
        """测试词典加载"""
        assert dict_manager.is_loaded()
        stats = dict_manager.get_stats()
        assert len(stats) > 0
    
    def test_contains_brand(self, dict_manager):
        """测试品牌词匹配"""
        assert dict_manager.contains("brands", "apple")
        assert dict_manager.contains("brands", "Nike")
    
    def test_contains_chinese_brand(self, dict_manager):
        """测试中文品牌词匹配"""
        assert dict_manager.contains("brands", "华为")
        assert dict_manager.contains("brands", "小米")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
