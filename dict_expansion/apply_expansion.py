#!/usr/bin/env python
"""
词典扩充脚本

读取扩充文件，将词条添加到对应的词典文件中
"""
import json
import sys
from pathlib import Path

# 标签到词典文件的映射
TAG_TO_DICT = {
    "品牌词": "brands/global.json",
    "商品词": "products.json",
    "人群词": "audiences.json",
    "场景词": "scenarios.json",
    "颜色词": "colors.json",
    "尺寸词": "attributes.json",  # 尺寸词暂时放 attributes
    "卖点词": "features.json",
    "属性词": "attributes.json",
}


def load_json(path: Path) -> dict:
    """加载 JSON 文件"""
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"entries": []}


def save_json(path: Path, data: dict):
    """保存 JSON 文件"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_existing_words(data: dict) -> set:
    """获取已有词条"""
    return {entry.get("word", "").lower() for entry in data.get("entries", [])}


def apply_expansion(expansion_file: Path, dict_base: Path, dry_run: bool = False):
    """应用扩充文件"""
    print(f"\n处理: {expansion_file.name}")
    
    with open(expansion_file, 'r', encoding='utf-8') as f:
        expansion = json.load(f)
    
    language = expansion.get("language", "unknown")
    entries = expansion.get("entries", [])
    stopwords = set(expansion.get("stopwords", []))
    
    # 统计
    stats = {"added": 0, "skipped": 0, "stopword": 0}
    
    # 按目标词典分组
    by_dict = {}
    for entry in entries:
        word = entry.get("word", "")
        tag = entry.get("tag", "属性词")
        
        # 跳过虚词
        if word.lower() in stopwords:
            stats["stopword"] += 1
            continue
        
        dict_file = TAG_TO_DICT.get(tag, "attributes.json")
        if dict_file not in by_dict:
            by_dict[dict_file] = []
        by_dict[dict_file].append(entry)
    
    # 应用到各词典
    for dict_file, new_entries in by_dict.items():
        dict_path = dict_base / dict_file
        existing = load_json(dict_path)
        existing_words = get_existing_words(existing)
        
        added_count = 0
        for entry in new_entries:
            word = entry.get("word", "")
            if word.lower() not in existing_words:
                new_entry = {
                    "word": word,
                    "confidence": entry.get("confidence", 0.9),
                }
                if "note" in entry:
                    new_entry["note"] = entry["note"]
                
                existing["entries"].append(new_entry)
                existing_words.add(word.lower())
                added_count += 1
                stats["added"] += 1
            else:
                stats["skipped"] += 1
        
        if added_count > 0 and not dry_run:
            save_json(dict_path, existing)
            print(f"  ✓ {dict_file}: 添加 {added_count} 条")
        elif added_count > 0:
            print(f"  [预览] {dict_file}: 将添加 {added_count} 条")
    
    print(f"  统计: 添加 {stats['added']}, 跳过 {stats['skipped']}, 虚词 {stats['stopword']}")
    return stats


def main():
    # 确定路径
    script_dir = Path(__file__).parent
    
    # 扩充文件目录
    expansion_dir = script_dir / "dict_expansion"
    if not expansion_dir.exists():
        expansion_dir = Path("dict_expansion")
    
    # 词典目录
    dict_base = script_dir.parent / "dictionaries"
    if not dict_base.exists():
        dict_base = Path("dictionaries")
    
    print(f"扩充文件目录: {expansion_dir}")
    print(f"词典目录: {dict_base}")
    
    # 检查参数
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    if dry_run:
        print("\n*** 预览模式 - 不会实际修改文件 ***")
    
    # 处理所有扩充文件
    total_stats = {"added": 0, "skipped": 0, "stopword": 0}
    
    for exp_file in sorted(expansion_dir.glob("*.json")):
        stats = apply_expansion(exp_file, dict_base, dry_run)
        for k, v in stats.items():
            total_stats[k] += v
    
    print(f"\n{'='*50}")
    print(f"总计: 添加 {total_stats['added']} 条, 跳过 {total_stats['skipped']} 条")
    
    if dry_run:
        print("\n要实际应用更改，请去掉 --dry-run 参数重新运行")
    else:
        print("\n词典已更新！请重启服务后重新测试。")


if __name__ == "__main__":
    main()
