#!/usr/bin/env python
"""
导入 Google Product Taxonomy 到词典

Google Product Taxonomy 是 Google 官方的商品分类体系，
包含 5000+ 商品类目，支持 20+ 语言。

用法:
    python scripts/import_google_taxonomy.py [--dry-run] [--lang en-US]
    
支持的语言:
    en-US (英语), de-DE (德语), fr-FR (法语), 
    es-ES (西班牙语), ja-JP (日语), zh-CN (中文)
"""
import json
import re
import sys
import requests
from pathlib import Path
from collections import defaultdict

# 语言代码映射
LANGUAGE_CODES = {
    'en': 'en-US',
    'de': 'de-DE', 
    'fr': 'fr-FR',
    'es': 'es-ES',
    'ja': 'ja-JP',
    'zh': 'zh-CN',
    'it': 'it-IT',
    'pt': 'pt-BR',
    'nl': 'nl-NL',
    'pl': 'pl-PL',
}

# 场景词关键字（用于分类）
SCENARIO_KEYWORDS = {
    'en': {'outdoor', 'indoor', 'sports', 'fitness', 'camping', 'hiking', 
           'swimming', 'running', 'cycling', 'fishing', 'hunting', 'golf',
           'yoga', 'gym', 'travel', 'office', 'home', 'garden', 'kitchen',
           'bathroom', 'bedroom', 'wedding', 'party', 'christmas', 'halloween'},
    'de': {'outdoor', 'indoor', 'sport', 'fitness', 'camping', 'wandern',
           'schwimmen', 'laufen', 'radfahren', 'angeln', 'jagd', 'golf',
           'yoga', 'reise', 'büro', 'haus', 'garten', 'küche', 'bad'},
    'fr': {'outdoor', 'intérieur', 'sport', 'fitness', 'camping', 'randonnée',
           'natation', 'course', 'cyclisme', 'pêche', 'chasse', 'golf',
           'yoga', 'voyage', 'bureau', 'maison', 'jardin', 'cuisine'},
    'es': {'exterior', 'interior', 'deporte', 'fitness', 'camping', 'senderismo',
           'natación', 'correr', 'ciclismo', 'pesca', 'caza', 'golf',
           'yoga', 'viaje', 'oficina', 'hogar', 'jardín', 'cocina'},
    'ja': {'アウトドア', 'インドア', 'スポーツ', 'フィットネス', 'キャンプ',
           'ハイキング', 'ランニング', 'サイクリング', '釣り', 'ゴルフ',
           'ヨガ', '旅行', 'オフィス', 'ホーム', 'ガーデン', 'キッチン'},
}

# 要跳过的通用词
SKIP_WORDS = {
    'en': {'&', 'and', 'or', 'the', 'a', 'an', 'for', 'with', 'by', 'to', 'of',
           'in', 'on', 'at', 'as', 'is', 'it', 'be', 'are', 'was', 'were',
           'other', 'all', 'new', 'used', 'general', 'special', 'custom'},
    'de': {'&', 'und', 'oder', 'der', 'die', 'das', 'für', 'mit', 'von', 'zu',
           'in', 'auf', 'an', 'als', 'ist', 'sind', 'war', 'waren',
           'andere', 'alle', 'neu', 'gebraucht', 'allgemein', 'spezial'},
    'fr': {'&', 'et', 'ou', 'le', 'la', 'les', 'pour', 'avec', 'de', 'à',
           'en', 'sur', 'dans', 'comme', 'est', 'sont', 'était', 'étaient',
           'autre', 'tous', 'nouveau', 'général', 'spécial'},
    'es': {'&', 'y', 'o', 'el', 'la', 'los', 'las', 'para', 'con', 'de', 'a',
           'en', 'sobre', 'como', 'es', 'son', 'era', 'eran',
           'otro', 'todos', 'nuevo', 'general', 'especial'},
    'ja': {'&', 'と', 'や', 'の', 'を', 'に', 'は', 'が', 'で', 'へ',
           'その他', 'すべて', '新品', '中古', '一般', '特殊'},
}


def download_taxonomy(lang_code: str, local_file: str = None) -> list:
    """下载或从本地加载 Google Product Taxonomy"""
    
    # 优先使用本地文件
    if local_file:
        local_path = Path(local_file)
        if local_path.exists():
            print(f"📂 从本地文件加载: {local_file}")
            return parse_taxonomy_file(local_path)
        else:
            print(f"   ❌ 本地文件不存在: {local_file}")
            return []
    
    # 检查默认本地文件位置
    script_dir = Path(__file__).parent
    default_local = script_dir / "taxonomy_data" / f"taxonomy.{lang_code}.txt"
    if default_local.exists():
        print(f"📂 从本地文件加载: {default_local}")
        return parse_taxonomy_file(default_local)
    
    # 尝试网络下载
    url = f"https://www.google.com/basepages/producttype/taxonomy-with-ids.{lang_code}.txt"
    
    print(f"📥 下载 Google Taxonomy ({lang_code})...")
    print(f"   URL: {url}")
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        categories = parse_taxonomy_content(response.text)
        print(f"   ✓ 下载成功，共 {len(categories)} 个分类")
        return categories
        
    except requests.exceptions.RequestException as e:
        print(f"   ❌ 下载失败: {e}")
        print(f"\n💡 请手动下载文件:")
        print(f"   1. 访问: {url}")
        print(f"   2. 保存到: {default_local}")
        print(f"   3. 重新运行此脚本")
        return []


def parse_taxonomy_file(file_path: Path) -> list:
    """解析本地 Taxonomy 文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return parse_taxonomy_content(content)


def parse_taxonomy_content(content: str) -> list:
    """解析 Taxonomy 内容"""
    lines = content.strip().split('\n')
    categories = []
    
    for line in lines[1:]:  # 跳过第一行注释
        line = line.strip()
        if not line:
            continue
        
        # 格式1: "1 - Animals & Pet Supplies" (with IDs)
        if ' - ' in line and line.split(' - ')[0].strip().isdigit():
            parts = line.split(' - ', 1)
            if len(parts) == 2:
                categories.append(parts[1].strip())
        # 格式2: "Animals & Pet Supplies" (without IDs)
        elif ' > ' in line or (line and not line[0].isdigit()):
            categories.append(line)
    
    return categories


def extract_words(categories: list, lang: str) -> dict:
    """从分类中提取词汇"""
    product_words = defaultdict(lambda: {'count': 0, 'sources': []})
    scenario_words = defaultdict(lambda: {'count': 0, 'sources': []})
    
    skip = SKIP_WORDS.get(lang, SKIP_WORDS['en'])
    scenarios = SCENARIO_KEYWORDS.get(lang, SCENARIO_KEYWORDS['en'])
    
    for cat in categories:
        # 分割层级
        levels = cat.split(' > ')
        
        for level in levels:
            # 提取单词
            if lang == 'ja':
                # 日语：按原样保留
                words = [level]
            else:
                # 其他语言：分词
                words = re.findall(r'\b\w+\b', level.lower())
            
            for word in words:
                # 跳过条件
                if word in skip:
                    continue
                if len(word) < 2:
                    continue
                if word.isdigit():
                    continue
                
                # 分类：场景词 or 商品词
                if word in scenarios:
                    scenario_words[word]['count'] += 1
                    if cat not in scenario_words[word]['sources']:
                        scenario_words[word]['sources'].append(cat)
                else:
                    product_words[word]['count'] += 1
                    if cat not in product_words[word]['sources']:
                        product_words[word]['sources'].append(cat)
    
    return {
        'products': dict(product_words),
        'scenarios': dict(scenario_words)
    }


def load_existing_dict(dict_path: Path) -> set:
    """加载现有词典，获取已有词汇"""
    existing = set()
    
    if dict_path.exists():
        with open(dict_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for entry in data.get('entries', []):
            word = entry.get('word', '').lower()
            if word:
                existing.add(word)
    
    return existing


def merge_to_dict(dict_path: Path, new_words: dict, dry_run: bool = False) -> int:
    """合并新词到词典"""
    # 加载现有词典
    if dict_path.exists():
        with open(dict_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {'entries': []}
    
    existing = {e.get('word', '').lower() for e in data.get('entries', [])}
    
    # 添加新词
    added = 0
    for word, info in new_words.items():
        if word.lower() not in existing:
            entry = {
                'word': word,
                'confidence': 0.85,  # Google Taxonomy 来源给 0.85
                'source': 'google_taxonomy',
            }
            data['entries'].append(entry)
            existing.add(word.lower())
            added += 1
    
    # 保存
    if not dry_run and added > 0:
        with open(dict_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    return added


def main():
    print("=" * 60)
    print("📦 Google Product Taxonomy 导入工具")
    print("=" * 60)
    
    # 解析参数
    dry_run = '--dry-run' in sys.argv or '-n' in sys.argv
    
    # 获取语言参数
    lang = 'en'
    for i, arg in enumerate(sys.argv):
        if arg == '--lang' and i + 1 < len(sys.argv):
            lang = sys.argv[i + 1]
            break
    
    # 获取本地文件参数
    local_file = None
    for i, arg in enumerate(sys.argv):
        if arg == '--file' and i + 1 < len(sys.argv):
            local_file = sys.argv[i + 1]
            break
    
    lang_code = LANGUAGE_CODES.get(lang, lang)
    
    if dry_run:
        print("\n*** 预览模式 - 不会实际修改文件 ***")
    
    print(f"\n语言: {lang} ({lang_code})")
    
    # 词典目录
    script_dir = Path(__file__).parent
    dict_base = script_dir.parent / "dictionaries"
    
    print(f"词典目录: {dict_base}")
    
    # 下载或加载分类
    categories = download_taxonomy(lang_code, local_file)
    if not categories:
        print("❌ 无法获取分类数据")
        sys.exit(1)
    
    # 提取词汇
    print(f"\n🔍 提取词汇...")
    extracted = extract_words(categories, lang)
    
    product_count = len(extracted['products'])
    scenario_count = len(extracted['scenarios'])
    
    print(f"   商品词: {product_count} 个")
    print(f"   场景词: {scenario_count} 个")
    
    # 显示高频词示例
    print(f"\n📊 高频商品词 Top 20:")
    sorted_products = sorted(
        extracted['products'].items(), 
        key=lambda x: x[1]['count'], 
        reverse=True
    )[:20]
    for word, info in sorted_products:
        print(f"   {word}: {info['count']}次")
    
    print(f"\n📊 场景词示例:")
    for word in list(extracted['scenarios'].keys())[:10]:
        print(f"   {word}")
    
    # 合并到词典
    print(f"\n📝 合并到词典...")
    
    # 商品词
    products_path = dict_base / "products.json"
    products_added = merge_to_dict(products_path, extracted['products'], dry_run)
    action = "将添加" if dry_run else "已添加"
    print(f"   products.json: {action} {products_added} 个新词")
    
    # 场景词
    scenarios_path = dict_base / "scenarios.json"
    scenarios_added = merge_to_dict(scenarios_path, extracted['scenarios'], dry_run)
    print(f"   scenarios.json: {action} {scenarios_added} 个新词")
    
    # 总结
    total_added = products_added + scenarios_added
    print(f"\n{'=' * 60}")
    print(f"总计: {action} {total_added} 个词到词典")
    
    if dry_run:
        print("\n要实际导入，请去掉 --dry-run 参数重新运行:")
        print(f"  python scripts/import_google_taxonomy.py --lang {lang}")
    else:
        print("\n✅ 导入完成！重新运行测试查看效果。")
    
    # 显示支持的语言
    print(f"\n💡 支持的语言:")
    for code, full in LANGUAGE_CODES.items():
        print(f"   --lang {code}  ({full})")


if __name__ == "__main__":
    main()
