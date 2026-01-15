#!/usr/bin/env python
"""
从 AI 标注结果导入词典

将 test_results_ai.json 中 AI 标注的高质量词汇导入到词典中，
这样下次处理时就不需要再调用 AI。

用法:
    python scripts/import_ai_tags.py test_results_ai.json [--dry-run]
"""
import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 标签到词典文件的映射
TAG_TO_DICT = {
    "品牌词": "brands/global.json",
    "商品词": "products.json",
    "人群词": "audiences.json",
    "场景词": "scenarios.json",
    "颜色词": "colors.json",
    "尺寸词": "attributes.json",  # 尺寸词放 attributes
    "卖点词": "features.json",
    "属性词": "attributes.json",
    "材质词": "attributes.json",
    "数量词": "attributes.json",
    "时间词": "attributes.json",
    "季节词": "scenarios.json",
    "动作词": "attributes.json",
}

# 要过滤的词（虚词碎片、太短、或明显错误）
SKIP_WORDS = {
    # 虚词碎片（西班牙语/法语）
    'ni', 'as', 'os', 'ba', 'en', 'es', 'de', 'le', 'la', 'et', 'un', 'une',
    # 德语碎片
    'gr', 'rer', 'wei', 'gro',
    # 日语碎片
    'さめ', 'きめ', 'たたみ', 'せる', 'つける', 'きい', 'ける', 'ない',
    # 太短或无意义
    'up', 'to', 'in', 'on', 'an', 'or', 'at', 'by', 'so', 'do', 'go', 'if',
}

# 最低置信度要求
MIN_CONFIDENCE = 0.75

# 最低出现次数要求
MIN_COUNT = 2


def load_results(json_path: str) -> Tuple[Dict[str, List[Tuple[str, float]]], Dict[str, int]]:
    """
    从测试结果中提取 AI 标注的词
    
    Returns:
        ai_tagged: {tag: [(word, confidence), ...]}
        word_counts: {word: count}
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    ai_tagged = defaultdict(list)
    word_counts = defaultdict(int)
    seen_words = set()
    
    for result in data.get('results', []):
        for token in result.get('tagged_tokens', []):
            if token.get('method') == 'ai':
                word = token.get('token', '').strip()
                tag = token.get('tags', ['属性词'])[0]
                conf = token.get('confidence', 0.7)
                
                word_counts[word] += 1
                
                # 只记录第一次出现
                if word not in seen_words:
                    ai_tagged[tag].append((word, conf))
                    seen_words.add(word)
    
    return dict(ai_tagged), dict(word_counts)


def filter_words(
    ai_tagged: Dict[str, List[Tuple[str, float]]],
    word_counts: Dict[str, int]
) -> Dict[str, List[Tuple[str, float]]]:
    """过滤掉低质量的词"""
    filtered = {}
    
    for tag, words in ai_tagged.items():
        good_words = []
        for word, conf in words:
            # 跳过条件
            if word.lower() in SKIP_WORDS:
                continue
            if len(word) < 2:
                continue
            if conf < MIN_CONFIDENCE:
                continue
            if word_counts.get(word, 0) < MIN_COUNT:
                continue
            
            good_words.append((word, conf))
        
        if good_words:
            filtered[tag] = good_words
    
    return filtered


def load_existing_dict(dict_path: Path) -> Tuple[dict, set]:
    """加载现有词典"""
    if dict_path.exists():
        with open(dict_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        existing_words = {e.get('word', '').lower() for e in data.get('entries', [])}
        return data, existing_words
    return {"entries": []}, set()


def save_dict(dict_path: Path, data: dict):
    """保存词典"""
    dict_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dict_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def import_to_dicts(
    filtered: Dict[str, List[Tuple[str, float]]],
    dict_base: Path,
    dry_run: bool = False
) -> Dict[str, int]:
    """导入到词典"""
    stats = defaultdict(int)
    
    # 按目标词典分组
    by_dict = defaultdict(list)
    for tag, words in filtered.items():
        dict_file = TAG_TO_DICT.get(tag, "attributes.json")
        for word, conf in words:
            by_dict[dict_file].append({
                "word": word,
                "confidence": round(conf, 2),
                "source": "ai_generated",
                "original_tag": tag
            })
    
    # 导入各词典
    for dict_file, new_entries in by_dict.items():
        dict_path = dict_base / dict_file
        data, existing_words = load_existing_dict(dict_path)
        
        added = 0
        for entry in new_entries:
            word = entry["word"]
            if word.lower() not in existing_words:
                # 简化 entry，只保留必要字段
                clean_entry = {
                    "word": word,
                    "confidence": entry["confidence"]
                }
                data["entries"].append(clean_entry)
                existing_words.add(word.lower())
                added += 1
        
        if added > 0:
            if not dry_run:
                save_dict(dict_path, data)
                print(f"  ✓ {dict_file}: 添加 {added} 条")
            else:
                print(f"  [预览] {dict_file}: 将添加 {added} 条")
            
            stats[dict_file] = added
    
    return dict(stats)


def main():
    if len(sys.argv) < 2:
        print("用法: python import_ai_tags.py <test_results.json> [--dry-run]")
        print("示例: python import_ai_tags.py test_results_ai.json --dry-run")
        sys.exit(1)
    
    json_path = sys.argv[1]
    dry_run = '--dry-run' in sys.argv or '-n' in sys.argv
    
    print("=" * 60)
    print("从 AI 标注结果导入词典")
    print("=" * 60)
    
    if dry_run:
        print("\n*** 预览模式 - 不会实际修改文件 ***\n")
    
    # 词典目录
    dict_base = Path(__file__).parent.parent / "dictionaries"
    print(f"词典目录: {dict_base}")
    
    # 加载 AI 标注结果
    print(f"\n📂 加载 AI 标注结果: {json_path}")
    ai_tagged, word_counts = load_results(json_path)
    
    total_words = sum(len(v) for v in ai_tagged.values())
    print(f"   AI 标注词总数: {total_words}")
    
    # 按标签统计
    print(f"\n📊 各标签词数:")
    for tag in sorted(ai_tagged.keys()):
        print(f"   {tag}: {len(ai_tagged[tag])} 词")
    
    # 过滤
    print(f"\n🔍 过滤低质量词...")
    print(f"   最低置信度: {MIN_CONFIDENCE}")
    print(f"   最低出现次数: {MIN_COUNT}")
    print(f"   跳过词数: {len(SKIP_WORDS)}")
    
    filtered = filter_words(ai_tagged, word_counts)
    filtered_total = sum(len(v) for v in filtered.values())
    print(f"   过滤后剩余: {filtered_total} 词")
    
    # 显示过滤后各标签
    print(f"\n📋 过滤后各标签词数:")
    for tag in sorted(filtered.keys()):
        words = filtered[tag]
        print(f"   {tag}: {len(words)} 词")
        # 显示前 5 个
        for word, conf in words[:5]:
            count = word_counts.get(word, 0)
            print(f"      - {word} ({conf}, {count}次)")
    
    # 导入
    print(f"\n📝 导入词典...")
    stats = import_to_dicts(filtered, dict_base, dry_run)
    
    # 总结
    total_added = sum(stats.values())
    print(f"\n" + "=" * 60)
    print(f"总计: {'将添加' if dry_run else '已添加'} {total_added} 个词到词典")
    
    if dry_run:
        print("\n要实际导入，请去掉 --dry-run 参数重新运行")
    else:
        print("\n✅ 导入完成！下次运行测试时将不需要 AI 标注这些词。")


if __name__ == "__main__":
    main()
