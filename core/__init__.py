"""
核心处理模块

v2 改进：
- ScriptSegmenter: 脚本分段器，处理混合语言
- SpanPhraseExtractor: 基于 span 的固定短语提取
- PhraseMerger: 短语合并器
- EnhancedTagger: 增强版标签标注器
- EnhancedPipeline: 增强版处理流水线
"""
# 原有模块（向后兼容）
from .pipeline import TokenizePipeline
from .preprocessor import Preprocessor
from .fixed_phrase_extractor import FixedPhraseExtractor
from .language_detector import LanguageDetector
from .tagger import Tagger

# v2 新增模块
try:
    from .script_segmenter import ScriptSegmenter, ScriptType, Segment
    from .span_extractor import SpanPhraseExtractor, Span, create_span_extractor
    from .phrase_merger import PhraseMerger, merge_phrases, get_default_merger
    from .enhanced_tagger import EnhancedTagger, TagResult, create_enhanced_tagger
    from .enhanced_pipeline import EnhancedPipeline, create_pipeline
    
    V2_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ v2 模块未完全加载: {e}")
    V2_AVAILABLE = False

__all__ = [
    # v1 模块
    "TokenizePipeline",
    "Preprocessor",
    "FixedPhraseExtractor",
    "LanguageDetector",
    "Tagger",
    # v2 模块
    "ScriptSegmenter",
    "ScriptType",
    "Segment",
    "SpanPhraseExtractor",
    "Span",
    "PhraseMerger",
    "EnhancedTagger",
    "TagResult",
    "EnhancedPipeline",
    # 工厂函数
    "create_span_extractor",
    "create_enhanced_tagger",
    "create_pipeline",
    "merge_phrases",
    "get_default_merger",
    # 版本标识
    "V2_AVAILABLE",
]
