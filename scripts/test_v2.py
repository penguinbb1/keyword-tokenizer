#!/usr/bin/env python
"""
V2 测试脚本
对比旧版 pipeline 和新版 enhanced_pipeline 的效果
"""
import sys
import asyncio
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from services.dictionary_manager import DictionaryManager


def test_script_segmenter():
    """测试脚本分段器"""
    print("\n" + "="*60)
    print("测试 1: 脚本分段器 (ScriptSegmenter)")
    print("="*60)
    
    from core.script_segmenter import ScriptSegmenter
    
    segmenter = ScriptSegmenter()
    
    test_cases = [
        "New Balance跑步鞋メンズ10.5码",
        "Adidas Ultraboost ランニングシューズ",
        "thermoleggings damen winter warm",
        "iPhone 14 Pro Max 256GB",
    ]
    
    for text in test_cases:
        print(f"\n输入: {text}")
        segments = segmenter.segment(text)
        for seg in segments:
            print(f"  [{seg.script.value:6}] '{seg.text}'")


def test_phrase_merger():
    """测试短语合并器"""
    print("\n" + "="*60)
    print("测试 2: 短语合并器 (PhraseMerger)")
    print("="*60)
    
    from core.phrase_merger import PhraseMerger
    
    merger = PhraseMerger()
    
    test_cases = [
        ["long", "sleeve", "shirt", "for", "men"],
        ["high", "waist", "leggings", "damen"],
        ["quick", "dry", "running", "shorts"],
        ["noise", "cancelling", "earbuds"],
        ["taille", "haute", "legging", "femme"],
        ["manga", "larga", "camiseta"],
    ]
    
    for tokens in test_cases:
        merged = merger.merge(tokens)
        result = [m.text for m in merged]
        suggestions = {m.text: m.suggested_tag for m in merged if m.suggested_tag}
        
        print(f"\n输入: {tokens}")
        print(f"输出: {result}")
        if suggestions:
            print(f"建议标签: {suggestions}")


def test_span_extractor():
    """测试 Span 提取器"""
    print("\n" + "="*60)
    print("测试 3: Span 短语提取器 (SpanPhraseExtractor)")
    print("="*60)
    
    from core.span_extractor import SpanPhraseExtractor
    
    extractor = SpanPhraseExtractor()
    
    # 添加测试品牌
    extractor.add_phrase("new balance", "品牌词", 0.95)
    extractor.add_phrase("nike", "品牌词", 0.95)
    extractor.add_phrase("adidas", "品牌词", 0.95)
    
    test_cases = [
        "New Balance跑步鞋男士黑色10.5码",
        "someone bought a nike shirt",  # 测试边界匹配，不应匹配 "someone" 中的 "one"
        "nike air max running shoes",
        "adidas ultraboost 22",
    ]
    
    for text in test_cases:
        print(f"\n输入: {text}")
        spans, locked = extractor.extract(text)
        if spans:
            for span in spans:
                print(f"  提取: '{span.text}' -> {span.tag} (置信度: {span.confidence})")
        else:
            print("  无固定短语")


async def test_old_pipeline(dict_manager, test_cases):
    """测试旧版 pipeline"""
    print("\n" + "="*60)
    print("测试 4a: 旧版 Pipeline")
    print("="*60)
    
    from core.pipeline import TokenizePipeline
    
    pipeline = TokenizePipeline(dict_manager)
    
    for keyword in test_cases:
        print(f"\n输入: {keyword}")
        result = await pipeline.process(keyword)
        print(f"  tokens: {result['tokens']}")
        for t in result['tagged_tokens'][:5]:  # 只显示前5个
            print(f"    '{t['token']}' -> {t['tags']} ({t['confidence']})")


async def test_new_pipeline(dict_manager, test_cases):
    """测试新版 enhanced_pipeline"""
    print("\n" + "="*60)
    print("测试 4b: 新版 EnhancedPipeline")
    print("="*60)
    
    from core.enhanced_pipeline import EnhancedPipeline
    
    pipeline = EnhancedPipeline(dict_manager)
    
    for keyword in test_cases:
        print(f"\n输入: {keyword}")
        result = await pipeline.process(keyword)
        print(f"  tokens: {result['tokens']}")
        for t in result['tagged_tokens'][:5]:  # 只显示前5个
            print(f"    '{t['token']}' -> {t['tags']} ({t['confidence']})")


async def compare_pipelines():
    """对比新旧 pipeline"""
    print("\n" + "="*60)
    print("测试 5: 新旧 Pipeline 对比")
    print("="*60)
    
    # 初始化词典
    dict_manager = DictionaryManager(settings.dictionary_path)
    dict_manager.load_all()
    
    test_cases = [
        "long sleeve shirt for men",
        "high waist leggings damen",
        "New Balance跑步鞋メンズ",
        "ランニングベスト 軽量",
        "thermoleggings damen winter",
        "quick dry running shorts",
    ]
    
    from core.pipeline import TokenizePipeline
    from core.enhanced_pipeline import EnhancedPipeline
    
    old_pipeline = TokenizePipeline(dict_manager)
    new_pipeline = EnhancedPipeline(dict_manager)
    
    for keyword in test_cases:
        print(f"\n{'='*50}")
        print(f"关键词: {keyword}")
        print("-"*50)
        
        # 旧版结果
        old_result = await old_pipeline.process(keyword)
        print(f"旧版 tokens: {old_result['tokens']}")
        
        # 新版结果
        new_result = await new_pipeline.process(keyword)
        print(f"新版 tokens: {new_result['tokens']}")
        
        # 对比标注
        print("\n标注对比:")
        print(f"  {'Token':<20} {'旧版':<15} {'新版':<15}")
        print(f"  {'-'*50}")
        
        old_tags = {t['token']: (t['tags'][0], t['confidence']) for t in old_result['tagged_tokens']}
        new_tags = {t['token']: (t['tags'][0], t['confidence']) for t in new_result['tagged_tokens']}
        
        all_tokens = set(old_tags.keys()) | set(new_tags.keys())
        for token in sorted(all_tokens):
            old = old_tags.get(token, ("-", 0))
            new = new_tags.get(token, ("-", 0))
            
            old_str = f"{old[0]}({old[1]})"
            new_str = f"{new[0]}({new[1]})"
            
            marker = "  " if old[0] == new[0] else "* "  # 标记差异
            print(f"  {marker}{token:<18} {old_str:<15} {new_str:<15}")


def main():
    """主函数"""
    print("="*60)
    print("  V2 增强版测试")
    print("="*60)
    
    # 测试独立模块
    test_script_segmenter()
    test_phrase_merger()
    test_span_extractor()
    
    # 初始化词典
    print("\n\n加载词典...")
    dict_manager = DictionaryManager(settings.dictionary_path)
    dict_manager.load_all()
    
    # 测试用例
    test_cases = [
        "long sleeve shirt for men",
        "high waist leggings damen",
        "ランニングベスト 軽量",
    ]
    
    # 对比测试
    asyncio.run(compare_pipelines())
    
    print("\n" + "="*60)
    print("测试完成!")
    print("="*60)


if __name__ == "__main__":
    main()
