#!/usr/bin/env python
"""
批量测试脚本
从 CSV 文件读取关键词，调用 API 进行分词和标签标注测试
"""
import csv
import json
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.enhanced_pipeline import EnhancedPipeline as TokenizePipeline
from services.dictionary_manager import DictionaryManager
from config import settings


def detect_encoding(file_path: str) -> str:
    """检测文件编码"""
    encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'latin-1', 'shift-jis', 'cp1252']
    
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                f.read()
            return encoding
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    return 'utf-8'  # 默认


def load_keywords_from_csv(csv_path: str) -> list:
    """从 CSV 文件加载关键词"""
    keywords = []
    
    # 检测编码
    encoding = detect_encoding(csv_path)
    print(f"   检测到文件编码: {encoding}")
    
    with open(csv_path, 'r', encoding=encoding) as f:
        # 尝试检测分隔符
        sample = f.read(1024)
        f.seek(0)
        
        if '\t' in sample:
            delimiter = '\t'
        else:
            delimiter = ','
        
        print(f"   检测到分隔符: {'TAB' if delimiter == '\t' else 'COMMA'}")
        
        reader = csv.DictReader(f, delimiter=delimiter)
        
        for row in reader:
            # 支持不同的列名
            keyword = row.get('search_term') or row.get('keyword') or row.get('关键词')
            language = row.get('language') or row.get('语言') or 'unknown'
            
            if keyword:
                keywords.append({
                    'keyword': keyword.strip(),
                    'language': language.strip()
                })
    
    return keywords


async def test_single_keyword(pipeline: TokenizePipeline, keyword: str, language: str) -> dict:
    """测试单个关键词"""
    try:
        result = await pipeline.process(keyword)
        return {
            'keyword': keyword,
            'language': language,
            'success': True,
            'tokens': result.get('tokens', []),
            'tagged_tokens': result.get('tagged_tokens', []),
            'tag_summary': result.get('tag_summary', {})
        }
    except Exception as e:
        return {
            'keyword': keyword,
            'language': language,
            'success': False,
            'error': str(e)
        }


async def run_batch_test(csv_path: str, output_path: str = None):
    """运行批量测试"""
    print("=" * 60)
    print("关键词切词与标签标注 - 批量测试")
    print("=" * 60)
    
    # 加载关键词
    print(f"\n📂 加载关键词文件: {csv_path}")
    keywords = load_keywords_from_csv(csv_path)
    print(f"   共 {len(keywords)} 条关键词")
    
    # 按语言统计
    lang_counts = {}
    for kw in keywords:
        lang = kw['language']
        lang_counts[lang] = lang_counts.get(lang, 0) + 1
    
    print("\n📊 语言分布:")
    for lang, count in sorted(lang_counts.items()):
        print(f"   {lang}: {count} 条")
    
    # 初始化处理管道
    print("\n⚙️ 初始化处理管道...")
    dict_manager = DictionaryManager(settings.dictionary_path)
    dict_manager.load_all()
    pipeline = TokenizePipeline(dict_manager)
    
    # 执行测试
    print("\n🚀 开始测试...")
    results = []
    success_count = 0
    
    for i, kw in enumerate(keywords):
        result = await test_single_keyword(pipeline, kw['keyword'], kw['language'])
        results.append(result)
        
        if result['success']:
            success_count += 1
        
        # 打印进度
        if (i + 1) % 10 == 0 or i == len(keywords) - 1:
            print(f"   进度: {i + 1}/{len(keywords)} ({(i+1)/len(keywords)*100:.1f}%)")
    
    # 统计结果
    print("\n" + "=" * 60)
    print("测试结果统计")
    print("=" * 60)
    print(f"总数: {len(results)}")
    print(f"成功: {success_count}")
    print(f"失败: {len(results) - success_count}")
    print(f"成功率: {success_count/len(results)*100:.1f}%")
    
    # 按语言统计标签分布
    print("\n📊 各语言标签分布:")
    lang_tags = {}
    for result in results:
        if result['success']:
            lang = result['language']
            if lang not in lang_tags:
                lang_tags[lang] = {}
            
            for tag, tokens in result.get('tag_summary', {}).items():
                lang_tags[lang][tag] = lang_tags[lang].get(tag, 0) + len(tokens)
    
    for lang, tags in sorted(lang_tags.items()):
        print(f"\n   【{lang}】")
        for tag, count in sorted(tags.items(), key=lambda x: -x[1]):
            print(f"      {tag}: {count}")
    
    # 打印一些示例结果
    print("\n" + "=" * 60)
    print("示例结果（每种语言显示2个）")
    print("=" * 60)
    
    shown_langs = {}
    for result in results:
        if result['success']:
            lang = result['language']
            if lang not in shown_langs:
                shown_langs[lang] = 0
            
            if shown_langs[lang] < 2:
                print(f"\n【{lang}】{result['keyword']}")
                print(f"   分词: {result['tokens']}")
                print(f"   标签: ", end="")
                tag_parts = []
                for tt in result['tagged_tokens']:
                    tag_parts.append(f"{tt['token']}({','.join(tt['tags'])})")
                print(" | ".join(tag_parts))
                shown_langs[lang] += 1
    
    # 保存结果到文件
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"test_results_{timestamp}.json"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'summary': {
                'total': len(results),
                'success': success_count,
                'failed': len(results) - success_count,
                'success_rate': success_count / len(results),
                'language_distribution': lang_counts,
                'tag_distribution': lang_tags
            },
            'results': results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 详细结果已保存到: {output_path}")
    
    return results


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='批量测试关键词分词与标签标注')
    parser.add_argument('csv_file', help='CSV 文件路径')
    parser.add_argument('-o', '--output', help='输出文件路径', default=None)
    
    args = parser.parse_args()
    
    if not Path(args.csv_file).exists():
        print(f"❌ 文件不存在: {args.csv_file}")
        sys.exit(1)
    
    asyncio.run(run_batch_test(args.csv_file, args.output))


if __name__ == "__main__":
    main()
