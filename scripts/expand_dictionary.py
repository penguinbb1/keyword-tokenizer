#!/usr/bin/env python
"""
词典扩充脚本
从测试结果中提取低置信度词，使用 AI 批量标注，然后更新词典
"""
import json
import asyncio
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.dictionary_manager import DictionaryManager
from config import settings


def extract_low_confidence_words(results_file: str, threshold: float = 0.6) -> dict:
    """
    从测试结果中提取低置信度词
    
    Returns:
        {"日语": ["word1", "word2"], "德语": [...], ...}
    """
    with open(results_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    low_conf_words = defaultdict(set)
    
    for result in data.get('results', []):
        language = result.get('language', 'unknown')
        
        for tagged in result.get('tagged_tokens', []):
            if tagged.get('confidence', 0) <= threshold:
                word = tagged.get('token', '')
                # 过滤掉单字符和纯数字
                if len(word) > 1 and not word.isdigit():
                    low_conf_words[language].add(word)
    
    # 转换为 list
    return {lang: list(words) for lang, words in low_conf_words.items()}


def create_ai_prompt(words: list, language: str) -> str:
    """创建 AI 标注的 prompt"""
    
    tag_descriptions = """
- 品牌词: 商品品牌名称，如 Apple, Nike, 华为, Sony, Adidas
- 商品词: 商品品类名称，如 跑步鞋, 笔记本电脑, Tシャツ(T恤), leggings(打底裤), rucksack(背包)
- 人群词: 目标用户群体，如 男士, 女士, 儿童, メンズ(男性), damen(女士), femme(女性), herren(男士)
- 场景词: 使用场景，如 运动, 办公, ランニング(跑步), camping(露营), outdoor(户外), hiking(徒步)
- 颜色词: 颜色描述，如 黑色, 红色, schwarz(黑), noir(黑), black, blanco(白)
- 尺寸词: 尺寸规格，如 10.5码, 14寸, 256GB, 15L, XL, mini
- 卖点词: 产品卖点特性，如 防水, 轻量, wasserdicht(防水), imperméable(防水), lightweight
- 属性词: 产品属性特征，如 长袖, 材质, langarm(长袖), thermique(保暖), rechargeable(可充电)
"""
    
    # 每行一个词
    words_text = "\n".join([f"- {w}" for w in words[:50]])  # 最多50个
    
    prompt = f"""你是电商关键词分析专家。请为以下 {language} 词语判断最合适的标签类型。

## 可选标签类型：
{tag_descriptions}

## 待标注词语（{language}）：
{words_text}

## 输出要求：
请以 JSON 格式返回，每行一个词：
```json
{{
  "词语1": {{"tag": "商品词", "confidence": 0.9}},
  "词语2": {{"tag": "场景词", "confidence": 0.85}}
}}
```

注意：
1. confidence 范围 0.7-0.95，表示确信程度
2. 品牌词通常是专有名词
3. 如果词语明显是某个类别，confidence 给 0.9+
4. 请只输出 JSON，不要其他内容"""

    return prompt


def print_manual_prompt(language: str, words: list):
    """打印手动使用的 prompt（用于复制粘贴到 Claude）"""
    prompt = create_ai_prompt(words, language)
    
    print(f"\n{'='*60}")
    print(f"【{language}】词典扩充 - 共 {len(words)} 个词")
    print(f"{'='*60}")
    print("\n将以下内容复制到 Claude 对话框，获取标注结果：\n")
    print("-" * 40)
    print(prompt)
    print("-" * 40)


def parse_ai_response(response_text: str) -> dict:
    """解析 AI 返回的 JSON"""
    # 提取 JSON 部分
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0]
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0]
    
    return json.loads(response_text.strip())


def update_dictionaries(tagged_words: dict, language: str, dict_manager: DictionaryManager):
    """更新词典"""
    tag_to_dict = {
        "品牌词": "brands",
        "商品词": "products", 
        "人群词": "audiences",
        "场景词": "scenarios",
        "颜色词": "colors",
        "卖点词": "features",
        "属性词": "attributes",
        "尺寸词": "attributes",  # 尺寸词也放属性
    }
    
    added_count = 0
    
    for word, info in tagged_words.items():
        tag = info.get("tag", "属性词")
        confidence = info.get("confidence", 0.8)
        
        dict_name = tag_to_dict.get(tag, "attributes")
        
        # 品牌词需要区分语言
        if dict_name == "brands" and language != "英语":
            lang_code = {
                "日语": "ja",
                "德语": "de", 
                "法语": "fr",
                "西班牙语": "es",
                "中文": "zh"
            }.get(language, "global")
            
            if lang_code != "global":
                dict_name = f"brands_{lang_code}"
        
        dict_manager.add_entry(
            word=word,
            tag=tag,
            confidence=confidence,
            source="ai_generated"
        )
        added_count += 1
    
    return added_count


def interactive_mode():
    """交互模式：手动粘贴 AI 结果"""
    print("\n" + "=" * 60)
    print("交互模式 - 粘贴 AI 标注结果")
    print("=" * 60)
    
    dict_manager = DictionaryManager(settings.dictionary_path)
    dict_manager.load_all()
    
    while True:
        language = input("\n语言 (日语/德语/法语/英语/西班牙语/中文，输入 q 退出): ").strip()
        if language.lower() == 'q':
            break
        
        print("请粘贴 AI 返回的 JSON 结果（输入空行结束）：")
        lines = []
        while True:
            line = input()
            if not line:
                break
            lines.append(line)
        
        if not lines:
            continue
        
        try:
            response_text = "\n".join(lines)
            tagged_words = parse_ai_response(response_text)
            
            count = update_dictionaries(tagged_words, language, dict_manager)
            print(f"\n✅ 成功添加 {count} 个词条到词典！")
            
        except Exception as e:
            print(f"\n❌ 解析失败: {e}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='词典扩充工具')
    parser.add_argument('results_file', nargs='?', help='测试结果 JSON 文件')
    parser.add_argument('-t', '--threshold', type=float, default=0.6, 
                        help='置信度阈值，低于此值的词需要标注（默认 0.6）')
    parser.add_argument('-l', '--language', help='只处理指定语言')
    parser.add_argument('-i', '--interactive', action='store_true',
                        help='交互模式：手动粘贴 AI 结果')
    parser.add_argument('--apply', help='应用 AI 标注结果文件到词典')
    
    args = parser.parse_args()
    
    # 交互模式
    if args.interactive:
        interactive_mode()
        return
    
    # 应用结果文件
    if args.apply:
        print(f"📂 加载标注结果: {args.apply}")
        with open(args.apply, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        dict_manager = DictionaryManager(settings.dictionary_path)
        dict_manager.load_all()
        
        total = 0
        for language, tagged_words in data.items():
            if isinstance(tagged_words, dict):
                count = update_dictionaries(tagged_words, language, dict_manager)
                total += count
                print(f"   {language}: 添加 {count} 个")
        
        print(f"\n✅ 共添加 {total} 个词条")
        return
    
    # 从测试结果提取低置信度词
    if not args.results_file:
        parser.print_help()
        return
    
    if not Path(args.results_file).exists():
        print(f"❌ 文件不存在: {args.results_file}")
        return
    
    print(f"📂 分析测试结果: {args.results_file}")
    print(f"📊 置信度阈值: {args.threshold}")
    
    low_conf_words = extract_low_confidence_words(args.results_file, args.threshold)
    
    print(f"\n发现低置信度词：")
    total_words = 0
    for lang, words in sorted(low_conf_words.items()):
        print(f"   {lang}: {len(words)} 个")
        total_words += len(words)
    
    print(f"\n   总计: {total_words} 个词需要标注")
    
    # 过滤指定语言
    if args.language:
        if args.language in low_conf_words:
            low_conf_words = {args.language: low_conf_words[args.language]}
        else:
            print(f"❌ 未找到语言: {args.language}")
            return
    
    # 生成每种语言的 prompt
    print("\n" + "=" * 60)
    print("由于未配置 API Key，请手动复制以下 prompt 到 Claude 获取标注结果")
    print("然后使用 --interactive 模式粘贴结果")
    print("=" * 60)
    
    for language, words in sorted(low_conf_words.items()):
        if len(words) > 0:
            # 分批处理（每批50个）
            for i in range(0, min(len(words), 100), 50):  # 最多处理100个
                batch = words[i:i+50]
                print_manual_prompt(language, batch)
                
                if len(words) > 50:
                    print(f"\n⚠️ {language} 词太多，只显示前 {min(len(words), 100)} 个")
    
    print("\n" + "=" * 60)
    print("使用方法：")
    print("1. 复制上面的 prompt 到 Claude 对话框")
    print("2. 获取 JSON 结果后，运行: python scripts/expand_dictionary.py -i")
    print("3. 按提示粘贴结果，自动更新词典")
    print("=" * 60)


if __name__ == "__main__":
    main()
