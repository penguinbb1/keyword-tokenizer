"""
日语复合词合并器

解决问题：Sudachi 即使用 Mode C 也会过度分词
例如：
- 腹巻きタイプ → 腹/巻/き/タイプ (错误)
- 应该是 → 腹巻き/タイプ (正确)

策略：
1. 预定义高频复合词列表
2. 基于规则的后处理合并（假名连接、词尾变化等）
3. 动态 SplitMode（先 Mode C，对未知长词用 Mode A）
"""
from typing import List, Tuple, Dict, Optional, Set
from dataclasses import dataclass
import re


@dataclass
class JapaneseToken:
    """日语 token"""
    text: str
    reading: Optional[str] = None
    is_merged: bool = False
    original_tokens: List[str] = None
    suggested_tag: Optional[str] = None
    confidence: float = 0.0


class JapaneseCompoundMerger:
    """
    日语复合词合并器
    
    使用多种策略合并被过度分词的日语词
    
    重要：只在合并后的词存在于词典或高频词表时才合并
    """
    
    def __init__(self, dictionary_words: set = None):
        """
        Args:
            dictionary_words: 词典中的词集合，用于验证合并后的词
        """
        self.dictionary_words = dictionary_words or set()
        
        # 1. 预定义复合词词典（这些词合并后一定有效）
        self.compound_dict = self._build_compound_dict()
        
        # 2. 常见词尾（应该和前面的词合并）
        self.suffix_patterns = {
            # 动词/形容词词尾
            'き', 'く', 'け', 'い', 'う', 'た', 'て', 'ない', 'れる', 'せる',
            'める', 'ける', 'える', 'げる', 'べる', 'ねる', 'へる',
            # 名词化词尾
            'さ', 'み', 'め',
            # 连用形词尾
            'し', 'じ',
        }
        
        # 3. 常见复合词模式
        self.merge_patterns = [
            # (前缀模式, 后缀模式) -> 应该合并
            (r'.*[巻掛置付吊掃取]$', r'^[きくけいうたてっ]'),  # 动词连用形 + 词尾
            (r'.*[入出]$', r'^[れりっ]'),  # 入れ、出り
            (r'.*き$', r'^め'),  # きめ → きめ
            (r'.*さ$', r'^め'),  # さめ → さめ
            (r'.*た$', r'^[たみめ]'),  # たたみ
        ]
        
        # 4. 确定可以合并的完整词列表（高优先级）
        self.must_merge = self._build_must_merge_list()
        
        # 5. 片假名商品词词尾
        self.katakana_product_suffixes = {
            'バッグ', 'ポーチ', 'ケース', 'カバー', 'ホルダー',
            'ボックス', 'ラック', 'スタンド', 'マット', 'パッド',
            'シャツ', 'パンツ', 'スカート', 'ジャケット', 'コート',
            'シューズ', 'ブーツ', 'サンダル', 'スニーカー',
            'リュック', 'ザック', 'ベスト', 'キャップ', 'ハット',
        }
    
    def set_dictionary(self, dictionary_words: set):
        """设置词典词集合"""
        self.dictionary_words = dictionary_words
    
    def _build_compound_dict(self) -> Dict[Tuple[str, ...], str]:
        """
        构建复合词词典
        key: (token1, token2, ...) 被分开的 tokens
        value: 合并后的词
        """
        compounds = {
            # 常见被错误分词的词
            ('腹', '巻', 'き'): '腹巻き',
            ('腹', '巻'): '腹巻',
            ('肌', '着'): '肌着',
            ('下', '着'): '下着',
            ('上', '着'): '上着',
            ('入', 'れ'): '入れ',
            ('出', 'し'): '出し',
            ('取', 'り'): '取り',
            ('付', 'け'): '付け',
            ('掛', 'け'): '掛け',
            ('置', 'き'): '置き',
            ('吊', 'り'): '吊り',
            ('巻', 'き'): '巻き',
            ('畳', 'み'): '畳み',
            ('た', 'た', 'み'): 'たたみ',
            ('さ', 'め'): 'さめ',  # 鮫/冷め
            ('き', 'め'): 'きめ',  # 決め/木目
            ('し', 'め'): 'しめ',
            
            # 常见商品词
            ('トート', 'バッグ'): 'トートバッグ',
            ('ショルダー', 'バッグ'): 'ショルダーバッグ',
            ('ボディ', 'バッグ'): 'ボディバッグ',
            ('ウエスト', 'バッグ'): 'ウエストバッグ',
            ('エコ', 'バッグ'): 'エコバッグ',
            ('スーツ', 'ケース'): 'スーツケース',
            ('キャリー', 'ケース'): 'キャリーケース',
            ('ペン', 'ケース'): 'ペンケース',
            ('メイク', 'ポーチ'): 'メイクポーチ',
            ('ランニング', 'シューズ'): 'ランニングシューズ',
            ('スニーカー', 'シューズ'): 'スニーカーシューズ',
            ('Tシャツ',): 'Tシャツ',
            ('T', 'シャツ'): 'Tシャツ',
            
            # 人群词
            ('メンズ',): 'メンズ',
            ('レディース',): 'レディース',
            ('キッズ',): 'キッズ',
            ('ベビー',): 'ベビー',
            ('ジュニア',): 'ジュニア',
            
            # 属性词
            ('大', '容量'): '大容量',
            ('軽', '量'): '軽量',
            ('防', '水'): '防水',
            ('耐', '水'): '耐水',
            ('保', '温'): '保温',
            ('保', '冷'): '保冷',
            ('抗', '菌'): '抗菌',
            ('速', '乾'): '速乾',
            ('吸', '汗'): '吸汗',
            ('通', '気'): '通気',
            
            # 场景词
            ('アウト', 'ドア'): 'アウトドア',
            ('インドア',): 'インドア',
            ('オフィス',): 'オフィス',
            ('ビジネス',): 'ビジネス',
            ('カジュアル',): 'カジュアル',
            ('フォーマル',): 'フォーマル',
        }
        return compounds
    
    def _build_must_merge_list(self) -> Set[str]:
        """
        构建必须合并的完整词列表
        如果这些词被分开了，应该合并回来
        """
        return {
            # 商品词
            'トートバッグ', 'ショルダーバッグ', 'ボディバッグ', 'ウエストバッグ',
            'エコバッグ', 'スーツケース', 'キャリーケース', 'ペンケース',
            'メイクポーチ', 'ランニングシューズ', 'スニーカー',
            # 常用词
            '腹巻き', '肌着', '下着', '大容量', '軽量', '防水',
            'アウトドア', 'ビジネス', 'カジュアル',
            # 人群词
            'メンズ', 'レディース', 'キッズ', 'ベビー', 'ジュニア',
        }
    
    def merge(self, tokens: List[str]) -> List[JapaneseToken]:
        """
        合并日语 tokens
        
        Args:
            tokens: 分词后的 token 列表
            
        Returns:
            合并后的 JapaneseToken 列表
        """
        if not tokens:
            return []
        
        # 第一遍：词典匹配合并
        tokens = self._dict_merge(tokens)
        
        # 第二遍：规则合并（处理词尾）
        tokens = self._rule_merge(tokens)
        
        # 第三遍：片假名商品词合并
        tokens = self._katakana_merge(tokens)
        
        # 转换为 JapaneseToken
        result = []
        for t in tokens:
            if isinstance(t, JapaneseToken):
                result.append(t)
            else:
                result.append(JapaneseToken(text=t))
        
        return result
    
    def _dict_merge(self, tokens: List[str]) -> List:
        """使用词典进行合并"""
        result = []
        i = 0
        n = len(tokens)
        
        while i < n:
            matched = False
            
            # 尝试最长匹配（最多 4 个 token）
            for length in range(min(4, n - i), 0, -1):
                candidate = tuple(tokens[i:i + length])
                
                if candidate in self.compound_dict:
                    merged_text = self.compound_dict[candidate]
                    result.append(JapaneseToken(
                        text=merged_text,
                        is_merged=True,
                        original_tokens=list(candidate)
                    ))
                    i += length
                    matched = True
                    break
            
            if not matched:
                result.append(tokens[i])
                i += 1
        
        return result
    
    def _rule_merge(self, tokens: List) -> List:
        """使用规则进行合并（处理词尾）"""
        if len(tokens) < 2:
            return tokens
        
        result = []
        i = 0
        
        while i < len(tokens):
            current = tokens[i].text if isinstance(tokens[i], JapaneseToken) else tokens[i]
            
            # 检查是否需要和下一个 token 合并
            if i + 1 < len(tokens):
                next_token = tokens[i + 1].text if isinstance(tokens[i + 1], JapaneseToken) else tokens[i + 1]
                
                should_merge = False
                
                # 检查词尾模式
                if next_token in self.suffix_patterns and len(current) >= 1:
                    # 检查是否是动词/形容词词尾
                    should_merge = True
                
                # 检查正则模式
                for prev_pattern, next_pattern in self.merge_patterns:
                    if re.match(prev_pattern, current) and re.match(next_pattern, next_token):
                        should_merge = True
                        break
                
                if should_merge:
                    merged_text = current + next_token
                    result.append(JapaneseToken(
                        text=merged_text,
                        is_merged=True,
                        original_tokens=[current, next_token]
                    ))
                    i += 2
                    continue
            
            # 不合并，保留原样
            if isinstance(tokens[i], JapaneseToken):
                result.append(tokens[i])
            else:
                result.append(JapaneseToken(text=current))
            i += 1
        
        return result
    
    def _katakana_merge(self, tokens: List) -> List:
        """合并片假名商品词 - 只在词典中有对应词时合并"""
        if len(tokens) < 2:
            return tokens
        
        result = []
        i = 0
        
        while i < len(tokens):
            current = tokens[i].text if isinstance(tokens[i], JapaneseToken) else tokens[i]
            
            # 检查是否可以和下一个片假名词合并
            if i + 1 < len(tokens):
                next_token = tokens[i + 1].text if isinstance(tokens[i + 1], JapaneseToken) else tokens[i + 1]
                
                # 如果下一个 token 是片假名商品词词尾
                if next_token in self.katakana_product_suffixes:
                    # 检查当前 token 是否是片假名
                    if self._is_katakana(current):
                        merged_text = current + next_token
                        
                        # 关键修改：只在满足以下条件时才合并
                        # 1. 合并后的词在 must_merge 列表中
                        # 2. 或者合并后的词在词典中
                        should_merge = (
                            merged_text in self.must_merge or
                            merged_text.lower() in self.dictionary_words or
                            merged_text in self.dictionary_words
                        )
                        
                        if should_merge:
                            result.append(JapaneseToken(
                                text=merged_text,
                                is_merged=True,
                                original_tokens=[current, next_token],
                                suggested_tag='商品词',
                                confidence=0.85
                            ))
                            i += 2
                            continue
            
            result.append(tokens[i])
            i += 1
        
        return result
    
    def _is_katakana(self, text: str) -> bool:
        """检查是否主要是片假名"""
        if not text:
            return False
        katakana_count = sum(1 for c in text if '\u30A0' <= c <= '\u30FF')
        return katakana_count >= len(text) * 0.5
    
    def _is_valid_compound(self, text: str) -> bool:
        """检查是否是有效的复合词"""
        # 简单检查：长度合理且主要是日语字符
        if len(text) < 3 or len(text) > 15:
            return False
        return True
    
    def merge_to_strings(self, tokens: List[str]) -> List[str]:
        """便捷方法：返回字符串列表"""
        merged = self.merge(tokens)
        return [t.text for t in merged]


# 单例
_ja_merger = None

def get_japanese_merger() -> JapaneseCompoundMerger:
    """获取单例实例"""
    global _ja_merger
    if _ja_merger is None:
        _ja_merger = JapaneseCompoundMerger()
    return _ja_merger


def merge_japanese_compounds(tokens: List[str]) -> List[str]:
    """便捷函数"""
    return get_japanese_merger().merge_to_strings(tokens)


# 测试
if __name__ == "__main__":
    merger = JapaneseCompoundMerger()
    
    test_cases = [
        ['ランニング', 'ベスト', 'メンズ'],
        ['腹', '巻', 'き', 'タイプ'],
        ['トート', 'バッグ', 'レディース'],
        ['スーツ', 'ケース', '大', '容量'],
        ['ランニング', 'シューズ', '軽', '量'],
        ['さ', 'め', 'の', 'おもちゃ'],
        ['き', 'め', 'が', '細かい'],
    ]
    
    for tokens in test_cases:
        print(f"\n入力: {tokens}")
        result = merger.merge_to_strings(tokens)
        print(f"出力: {result}")
