#!/usr/bin/env python
"""
批量测试脚本 V2 - 优化 AI 调用

两阶段处理：
1. 第一阶段：不用 AI，处理所有关键词，收集低置信度词
2. 第二阶段：批量调用 AI 标注低置信度词
3. 第三阶段：合并结果

这样可以大大减少 API 调用次数（从数千次减少到几十次）
"""
import csv
import json
import asyncio
import sys
from pathlib import Path
from datetime import datetime
from collections import Counter

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.enhanced_pipeline import EnhancedPipeline
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
    return 'utf-8'


def load_keywords_from_csv(csv_path: str) -> list:
    """从 CSV 文件加载关键词"""
    keywords = []
    encoding = detect_encoding(csv_path)
    print(f"   检测到文件编码: {encoding}")
    
    with open(csv_path, 'r', encoding=encoding) as f:
        sample = f.read(1024)
        f.seek(0)
        delimiter = '\t' if '\t' in sample else ','
        print(f"   检测到分隔符: {'TAB' if delimiter == '\t' else 'COMMA'}")
        
        reader = csv.DictReader(f, delimiter=delimiter)
        
        # 打印列名帮助调试
        first_row = next(reader, None)
        if first_row:
            print(f"   CSV 列名: {list(first_row.keys())}")
            f.seek(0)
            reader = csv.DictReader(f, delimiter=delimiter)
        
        for row in reader:
            # 支持多种列名
            keyword = (row.get('search_term') or row.get('keyword') or 
                      row.get('Keyword') or row.get('关键词') or '')
            language = (row.get('language') or row.get('Language') or 
                       row.get('语言') or 'unknown')
            
            if keyword:
                keywords.append({
                    'keyword': keyword.strip(),
                    'language': language.strip()
                })
    
    return keywords


async def phase1_collect_low_conf(pipeline, keywords):
    """
    第一阶段：处理所有关键词，收集低置信度词
    """
    results = []
    low_conf_words = Counter()  # 统计低置信度词出现次数
    
    # 语言名称映射
    lang_map = {
        '日语': 'ja', '日本語': 'ja', 'japanese': 'ja',
        '西班牙语': 'es', 'spanish': 'es', 'español': 'es',
        '德语': 'de', 'german': 'de', 'deutsch': 'de',
        '法语': 'fr', 'french': 'fr', 'français': 'fr',
        '英语': 'en', 'english': 'en',
    }
    
    total = len(keywords)
    
    for i, item in enumerate(keywords):
        if (i + 1) % 500 == 0:
            print(f"   阶段1进度: {i+1}/{total} ({(i+1)/total*100:.1f}%)")
        
        keyword = item['keyword']
        language = item['language']
        
        # 转换语言代码
        lang_code = lang_map.get(language.lower(), language.lower()) if language else None
        
        try:
            result = await pipeline.process(keyword, language=lang_code)
            result['language'] = language
            results.append(result)
            
            # 收集低置信度词
            for token in result.get('tagged_tokens', []):
                if token.get('confidence', 0) <= 0.5:
                    word = token.get('token', '')
                    if len(word) > 1:  # 跳过单字符
                        low_conf_words[word] += 1
                        
        except Exception as e:
            print(f"   ⚠️ 处理失败 [{keyword}]: {e}")
            results.append({
                'keyword': keyword,
                'language': language,
                'tokens': [],
                'tagged_tokens': [],
                'error': str(e)
            })
    
    return results, low_conf_words


async def phase2_ai_batch_tagging(low_conf_words, min_count=2):
    """
    第二阶段：批量调用 AI 标注低置信度词
    
    只处理出现次数 >= min_count 的词（减少噪音）
    """
    from services.ai_enhancer_v2 import AIEnhancer
    
    enhancer = AIEnhancer()
    
    if not enhancer.is_enabled:
        print("   ⚠️ AI 服务未启用，跳过 AI 标注")
        return {}
    
    # 筛选高频低置信度词
    words_to_tag = [word for word, count in low_conf_words.items() if count >= min_count]
    
    print(f"   共 {len(words_to_tag)} 个高频低置信度词需要 AI 标注")
    
    if not words_to_tag:
        return {}
    
    # 分批处理（每批 50 个词）
    batch_size = 50
    all_results = {}
    
    for i in range(0, len(words_to_tag), batch_size):
        batch = words_to_tag[i:i + batch_size]
        print(f"   AI 标注批次 {i//batch_size + 1}/{(len(words_to_tag) + batch_size - 1)//batch_size}: {len(batch)} 词")
        
        try:
            results = await enhancer.process_batch(batch, context="电商关键词")
            all_results.update(results)
            
            # 避免 API 限流
            await asyncio.sleep(1)
        except Exception as e:
            print(f"   ⚠️ AI 批量标注失败: {e}")
    
    return all_results


def phase3_merge_results(results, ai_tags):
    """
    第三阶段：合并 AI 标注结果
    """
    if not ai_tags:
        return results
    
    updated_count = 0
    
    for result in results:
        for token in result.get('tagged_tokens', []):
            word = token.get('token', '')
            if word in ai_tags:
                ai_result = ai_tags[word]
                token['tags'] = [ai_result['tag']]
                token['confidence'] = ai_result['confidence']
                token['method'] = 'ai'
                updated_count += 1
    
    print(f"   已更新 {updated_count} 个 token 的标注")
    return results


def compute_statistics(results):
    """计算统计信息"""
    stats = {
        'total': len(results),
        'success': sum(1 for r in results if 'error' not in r),
        'language_distribution': Counter(),
        'tag_distribution': {},
        'confidence_distribution': Counter(),
    }
    
    for result in results:
        lang = result.get('language', 'unknown')
        stats['language_distribution'][lang] += 1
        
        if lang not in stats['tag_distribution']:
            stats['tag_distribution'][lang] = Counter()
        
        for token in result.get('tagged_tokens', []):
            tag = token.get('tags', ['未知'])[0]
            conf = round(token.get('confidence', 0), 2)
            
            stats['tag_distribution'][lang][tag] += 1
            stats['confidence_distribution'][conf] += 1
    
    stats['success_rate'] = stats['success'] / stats['total'] if stats['total'] > 0 else 0
    
    # 转换 Counter 为普通 dict
    stats['language_distribution'] = dict(stats['language_distribution'])
    stats['tag_distribution'] = {k: dict(v) for k, v in stats['tag_distribution'].items()}
    stats['confidence_distribution'] = dict(stats['confidence_distribution'])
    
    return stats


async def main():
    print("=" * 60)
    print("关键词切词与标签标注 - 批量测试 V2 (AI 优化版)")
    print("=" * 60)
    
    # 解析参数
    if len(sys.argv) < 2:
        print("用法: python batch_test_v2.py <csv_file> [-o output.json] [--no-ai]")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    output_path = None
    use_ai = True
    
    for i, arg in enumerate(sys.argv):
        if arg == '-o' and i + 1 < len(sys.argv):
            output_path = sys.argv[i + 1]
        if arg == '--no-ai':
            use_ai = False
    
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"test_results_{timestamp}.json"
    
    # 加载关键词
    print(f"\n📂 加载关键词文件: {csv_path}")
    keywords = load_keywords_from_csv(csv_path)
    print(f"   共 {len(keywords)} 条关键词")
    
    # 语言分布
    lang_dist = Counter(k['language'] for k in keywords)
    print(f"\n📊 语言分布:")
    for lang, count in lang_dist.most_common():
        print(f"   {lang}: {count} 条")
    
    # 初始化 pipeline（禁用实时 AI，后面批量处理）
    print(f"\n⚙️ 初始化处理管道...")
    dict_manager = DictionaryManager(settings.dictionary_path)
    dict_manager.load_all()
    pipeline = EnhancedPipeline(dict_manager, enable_ai=False)  # 禁用实时 AI
    
    # 阶段1：处理所有关键词
    print(f"\n🔄 阶段1: 处理关键词（不使用 AI）...")
    results, low_conf_words = await phase1_collect_low_conf(pipeline, keywords)
    
    print(f"   处理完成，共发现 {len(low_conf_words)} 个不同的低置信度词")
    print(f"   高频低置信度词 (Top 10):")
    for word, count in low_conf_words.most_common(10):
        print(f"      {word}: {count}次")
    
    # 阶段2：AI 批量标注
    ai_tags = {}
    if use_ai:
        print(f"\n🤖 阶段2: AI 批量标注...")
        ai_tags = await phase2_ai_batch_tagging(low_conf_words, min_count=2)
        print(f"   AI 标注完成，共 {len(ai_tags)} 个词")
    else:
        print(f"\n⏭️ 跳过 AI 标注 (--no-ai)")
    
    # 阶段3：合并结果
    print(f"\n📝 阶段3: 合并结果...")
    results = phase3_merge_results(results, ai_tags)
    
    # 计算统计
    print(f"\n📊 计算统计信息...")
    stats = compute_statistics(results)
    
    # 置信度统计
    total_tokens = sum(stats['confidence_distribution'].values())
    low_conf = sum(c for conf, c in stats['confidence_distribution'].items() if conf <= 0.5)
    high_conf = sum(c for conf, c in stats['confidence_distribution'].items() if conf >= 0.85)
    
    print(f"\n📈 置信度分布:")
    print(f"   总 tokens: {total_tokens}")
    if total_tokens > 0:
        print(f"   低置信度 (≤0.5): {low_conf} ({low_conf/total_tokens*100:.1f}%)")
        print(f"   高置信度 (≥0.85): {high_conf} ({high_conf/total_tokens*100:.1f}%)")
    else:
        print(f"   ⚠️ 无数据")
    
    # 保存结果
    output = {
        'summary': stats,
        'ai_tags_count': len(ai_tags),
        'results': results
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 结果已保存到: {output_path}")
    
    # 示例结果
    print(f"\n" + "=" * 60)
    print("示例结果")
    print("=" * 60)
    
    for lang in ['日语', '德语', '法语', '英语', '西班牙语']:
        samples = [r for r in results if r.get('language') == lang][:2]
        for s in samples:
            # 从 tokens 或 original 获取关键词
            kw = s.get('original', '')
            if not kw and s.get('tokens'):
                kw = ' '.join(s.get('tokens', []))
            
            tokens_str = ' | '.join([
                f"{t['token']}({t['tags'][0]})" 
                for t in s.get('tagged_tokens', [])[:5]
            ])
            print(f"【{lang}】{kw}")
            print(f"   {tokens_str}")


if __name__ == "__main__":
    asyncio.run(main())
