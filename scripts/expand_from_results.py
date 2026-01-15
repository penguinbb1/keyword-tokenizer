#!/usr/bin/env python3
"""
从测试结果中提取高频低置信度词，扩充词典

使用方法:
    python scripts/expand_from_results.py test_results.json
"""
import json
import sys
from pathlib import Path
from collections import Counter

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
DICT_PATH = PROJECT_ROOT / "dictionaries"


def load_results(filepath):
    """加载测试结果"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def collect_low_conf_words(data, min_count=3):
    """收集高频低置信度词"""
    by_language = {}
    
    for result in data.get('results', []):
        lang = result.get('language', 'unknown')
        if lang not in by_language:
            by_language[lang] = Counter()
        
        for token in result.get('tagged_tokens', []):
            if token.get('confidence', 0) <= 0.5:
                word = token.get('token', '')
                if len(word) > 1:
                    by_language[lang][word] += 1
    
    # 过滤低频词
    for lang in by_language:
        by_language[lang] = {
            w: c for w, c in by_language[lang].items() 
            if c >= min_count
        }
    
    return by_language


def categorize_japanese(words):
    """分类日语词"""
    categories = {
        'products': [],
        'scenarios': [],
        'features': [],
        'attributes': [],
    }
    
    product_suffixes = ['リュック', 'バッグ', 'シューズ', 'ベスト', 'パンツ', 
                        'ザック', 'ポーチ', 'ケース', 'ボトル', 'ジャケット',
                        'コート', 'シャツ']
    scenario_prefixes = ['ランニング', 'ハイキング', 'トレッキング', 'アウトドア',
                         'キャンプ', 'トレイル', 'マラソン', 'ジョギング', 'ウォーキング']
    
    for word, count in words.items():
        # 商品词（包含商品后缀）
        if any(suffix in word for suffix in product_suffixes):
            # 检查是否是复合商品词（场景+商品）
            categories['products'].append({
                'word': word,
                'count': count,
                'confidence': 0.85
            })
        # 跳过一些噪音词
        elif word in ['付き', 'れない', '多い', '通せる', '軽い']:
            categories['attributes'].append({
                'word': word,
                'count': count,
                'confidence': 0.7
            })
    
    return categories


def categorize_spanish(words):
    """分类西班牙语词"""
    categories = {
        'products': [],
        'scenarios': [],
        'features': [],
        'attributes': [],
        'colors': [],
    }
    
    # 预定义分类
    product_words = {'molde', 'estuche', 'coche', 'juego', 'bolsa', 'bocina'}
    material_words = {'madera', 'acero', 'silicona', 'agua'}
    feature_words = {'electrica', 'electrico', 'remoto', 'expandible', 
                     'muscular', 'interior', 'presion'}
    body_words = {'nariz', 'juanete', 'fascitis', 'cuello'}
    scenario_words = {'jardin', 'navidad', 'wc', 'emergencia'}
    
    for word, count in words.items():
        entry = {'word': word, 'count': count, 'confidence': 0.85}
        
        if word in product_words:
            categories['products'].append(entry)
        elif word in material_words:
            categories['attributes'].append(entry)
        elif word in feature_words:
            categories['features'].append(entry)
        elif word in body_words:
            categories['attributes'].append(entry)
        elif word in scenario_words:
            categories['scenarios'].append(entry)
        # 如果词以 -o/-a 结尾，可能是形容词
        elif word.endswith('o') or word.endswith('a'):
            categories['attributes'].append(entry)
    
    return categories


def categorize_german(words):
    """分类德语词"""
    categories = {
        'products': [],
        'features': [],
        'attributes': [],
    }
    
    feature_words = {'gefüttert', 'wasserdicht', 'atmungsaktiv'}
    
    for word, count in words.items():
        entry = {'word': word, 'count': count, 'confidence': 0.85}
        
        if word in feature_words:
            categories['features'].append(entry)
        else:
            # 德语复合词通常是商品或属性
            categories['attributes'].append(entry)
    
    return categories


def categorize_french(words):
    """分类法语词"""
    categories = {
        'products': [],
        'features': [],
        'attributes': [],
    }
    
    for word, count in words.items():
        entry = {'word': word, 'count': count, 'confidence': 0.85}
        categories['attributes'].append(entry)
    
    return categories


def update_dictionary(dict_name, new_entries, dry_run=True):
    """更新词典文件"""
    dict_file = DICT_PATH / f"{dict_name}.json"
    
    if not dict_file.exists():
        print(f"  ⚠️ 词典文件不存在: {dict_file}")
        return 0
    
    with open(dict_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    existing_words = {e.get('word', '').lower() for e in data.get('entries', [])}
    
    added = 0
    for entry in new_entries:
        word = entry['word']
        if word.lower() not in existing_words:
            data['entries'].append({
                'word': word,
                'confidence': entry.get('confidence', 0.85)
            })
            added += 1
            if not dry_run:
                existing_words.add(word.lower())
    
    if not dry_run and added > 0:
        with open(dict_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    return added


def main():
    if len(sys.argv) < 2:
        print("使用方法: python scripts/expand_from_results.py <results.json> [--apply]")
        sys.exit(1)
    
    results_file = sys.argv[1]
    dry_run = '--apply' not in sys.argv
    
    if dry_run:
        print("🔍 预览模式（添加 --apply 实际执行）\n")
    else:
        print("⚡ 执行模式\n")
    
    # 加载结果
    data = load_results(results_file)
    print(f"📂 已加载 {len(data.get('results', []))} 条结果\n")
    
    # 收集低置信度词
    by_language = collect_low_conf_words(data, min_count=3)
    
    # 按语言处理
    total_added = 0
    
    for lang, words in by_language.items():
        if not words:
            continue
        
        print(f"=== {lang} ({len(words)} 个高频低置信度词) ===")
        
        # 分类
        if lang == '日语':
            categories = categorize_japanese(words)
        elif lang == '西班牙语':
            categories = categorize_spanish(words)
        elif lang == '德语':
            categories = categorize_german(words)
        elif lang == '法语':
            categories = categorize_french(words)
        else:
            continue
        
        # 更新词典
        for cat, entries in categories.items():
            if not entries:
                continue
            
            count = update_dictionary(cat, entries, dry_run)
            if count > 0:
                print(f"  {cat}: +{count} 词")
                for e in entries[:5]:
                    print(f"    - {e['word']} ({e['count']}次)")
                if len(entries) > 5:
                    print(f"    ... 还有 {len(entries) - 5} 词")
            total_added += count
        
        print()
    
    print(f"{'预计' if dry_run else '已'}添加 {total_added} 个词")
    
    if dry_run:
        print("\n💡 使用 --apply 参数实际执行更新")


if __name__ == "__main__":
    main()
