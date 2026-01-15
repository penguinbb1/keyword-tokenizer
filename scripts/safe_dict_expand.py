#!/usr/bin/env python3
"""
安全的词典扩充脚本 - 只添加新词，不覆盖原有内容

使用方法:
    python scripts/safe_dict_expand.py [--apply]
    
    不加 --apply 只预览，加了才真正写入
"""
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DICT_PATH = PROJECT_ROOT / "dictionaries"


def safe_add_words(dict_file: Path, new_words: list, dry_run: bool = True) -> int:
    """
    安全地向词典添加新词
    
    Args:
        dict_file: 词典文件路径
        new_words: 要添加的词列表，每个元素是 dict，包含 word, confidence 等
        dry_run: True 只预览，False 实际写入
        
    Returns:
        添加的词数量
    """
    if not dict_file.exists():
        print(f"  ⚠️ 文件不存在: {dict_file}")
        return 0
    
    # 读取现有词典
    with open(dict_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 获取现有词（小写）
    existing = {entry.get('word', '').lower() for entry in data.get('entries', [])}
    
    # 筛选真正的新词
    to_add = []
    for word_entry in new_words:
        word = word_entry.get('word', '')
        if word.lower() not in existing:
            to_add.append(word_entry)
    
    if not to_add:
        return 0
    
    # 预览或写入
    if dry_run:
        print(f"  将添加 {len(to_add)} 个新词到 {dict_file.name}")
        for entry in to_add[:5]:
            print(f"    + {entry.get('word')}")
        if len(to_add) > 5:
            print(f"    ... 还有 {len(to_add) - 5} 个")
    else:
        # 添加到 entries 末尾
        data['entries'].extend(to_add)
        
        # 写回文件
        with open(dict_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"  ✅ 已添加 {len(to_add)} 个新词到 {dict_file.name}")
    
    return len(to_add)


def main():
    dry_run = '--apply' not in sys.argv
    
    if dry_run:
        print("🔍 预览模式（添加 --apply 实际执行）\n")
    else:
        print("⚡ 执行模式\n")
    
    total_added = 0
    
    # ==================== 日语复合商品词 ====================
    print("=== 添加日语复合商品词到 products.json ===")
    ja_products = [
        {"word": "ランニングリュック", "confidence": 0.9},
        {"word": "ハイキングリュック", "confidence": 0.9},
        {"word": "トレッキングリュック", "confidence": 0.9},
        {"word": "アウトドアリュック", "confidence": 0.9},
        {"word": "ウォーキングリュック", "confidence": 0.9},
        {"word": "ジョギングリュック", "confidence": 0.9},
        {"word": "マラソンリュック", "confidence": 0.9},
        {"word": "トレランザック", "confidence": 0.9},
        {"word": "ハイドレーションバッグ", "confidence": 0.9},
        {"word": "ランニングバッグ", "confidence": 0.9},
        {"word": "スーツケースバッグ", "confidence": 0.9},
        {"word": "トレッキングパンツ", "confidence": 0.9},
        {"word": "レディースパンツ", "confidence": 0.9},
        {"word": "マラソンベスト", "confidence": 0.9},
        {"word": "ジョギングベスト", "confidence": 0.9},
        {"word": "ランベスト", "confidence": 0.9},
        {"word": "ランニングベスト", "confidence": 0.9},
        {"word": "ランニングポーチ", "confidence": 0.9},
        {"word": "トートバッグ", "confidence": 0.9},
        {"word": "ショルダーバッグ", "confidence": 0.9},
        {"word": "ボディバッグ", "confidence": 0.9},
        {"word": "ウエストバッグ", "confidence": 0.9},
        {"word": "エコバッグ", "confidence": 0.9},
        {"word": "スーツケース", "confidence": 0.9},
        {"word": "キャリーケース", "confidence": 0.9},
        {"word": "ペンケース", "confidence": 0.9},
        {"word": "メイクポーチ", "confidence": 0.9},
        {"word": "ランニングシューズ", "confidence": 0.9},
    ]
    
    # 西班牙语商品词
    es_products = [
        {"word": "molde", "confidence": 0.85},
        {"word": "estuche", "confidence": 0.85},
        {"word": "coche", "confidence": 0.85},
        {"word": "juego", "confidence": 0.85},
        {"word": "bolsa", "confidence": 0.85},
        {"word": "bocina", "confidence": 0.85},
    ]
    
    total_added += safe_add_words(
        DICT_PATH / "products.json", 
        ja_products + es_products, 
        dry_run
    )
    
    # ==================== 属性词 ====================
    print("\n=== 添加属性词到 attributes.json ===")
    new_attributes = [
        # 西班牙语
        {"word": "madera", "confidence": 0.85},
        {"word": "acero", "confidence": 0.85},
        {"word": "silicona", "confidence": 0.85},
        {"word": "agua", "confidence": 0.85},
        {"word": "nariz", "confidence": 0.85},
        {"word": "juanete", "confidence": 0.85},
        {"word": "fascitis", "confidence": 0.85},
        {"word": "cuello", "confidence": 0.85},
        {"word": "interior", "confidence": 0.85},
        {"word": "burbujas", "confidence": 0.85},
        {"word": "estrellas", "confidence": 0.85},
        {"word": "presion", "confidence": 0.85},
        # 日语
        {"word": "腹巻き", "confidence": 0.9},
        {"word": "大容量", "confidence": 0.9},
        {"word": "軽量", "confidence": 0.9},
        {"word": "肩掛け", "confidence": 0.85},
        {"word": "小型", "confidence": 0.85},
        {"word": "畳み", "confidence": 0.85},
    ]
    
    total_added += safe_add_words(
        DICT_PATH / "attributes.json", 
        new_attributes, 
        dry_run
    )
    
    # ==================== 卖点词 ====================
    print("\n=== 添加卖点词到 features.json ===")
    new_features = [
        {"word": "electrico", "confidence": 0.85},
        {"word": "electrica", "confidence": 0.85},
        {"word": "remoto", "confidence": 0.85},
        {"word": "expandible", "confidence": 0.85},
        {"word": "muscular", "confidence": 0.85},
        {"word": "inalambrico", "confidence": 0.85},
        {"word": "gefüttert", "confidence": 0.85},
    ]
    
    total_added += safe_add_words(
        DICT_PATH / "features.json", 
        new_features, 
        dry_run
    )
    
    # ==================== 场景词 ====================
    print("\n=== 添加场景词到 scenarios.json ===")
    new_scenarios = [
        {"word": "jardin", "confidence": 0.85},
        {"word": "navidad", "confidence": 0.85},
        {"word": "wc", "confidence": 0.85},
        {"word": "emergencia", "confidence": 0.85},
        {"word": "d'appoint", "confidence": 0.85},
    ]
    
    total_added += safe_add_words(
        DICT_PATH / "scenarios.json", 
        new_scenarios, 
        dry_run
    )
    
    # ==================== 总结 ====================
    print(f"\n{'预计' if dry_run else '已'}添加 {total_added} 个词")
    
    if dry_run:
        print("\n💡 确认无误后，使用 --apply 参数实际执行")
        print("   python scripts/safe_dict_expand.py --apply")


if __name__ == "__main__":
    main()
