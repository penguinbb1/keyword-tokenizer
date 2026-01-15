"""
短语合并器

解决问题：欧洲语言按空格分词后，固定搭配被拆开
例如：
- "long sleeve" → ["long", "sleeve"] → 应该合并为 ["long sleeve"]
- "high waist" → ["high", "waist"] → 应该合并为 ["high waist"]

实现：在 token 序列上跑 phrase matcher，识别并合并固定搭配
"""
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass


@dataclass
class MergedToken:
    """合并后的 token"""
    text: str
    original_tokens: List[str]  # 原始 tokens
    start_idx: int  # 在原始 token 列表中的起始索引
    end_idx: int    # 在原始 token 列表中的结束索引（不含）
    is_merged: bool  # 是否是合并产生的
    suggested_tag: Optional[str] = None  # 建议的标签
    confidence: float = 0.0


class PhraseMerger:
    """
    短语合并器
    
    在分词结果上识别并合并固定搭配
    """
    
    def __init__(self):
        # 短语词典：{(token1, token2, ...): (tag, confidence)}
        self.phrases: Dict[Tuple[str, ...], Tuple[str, float]] = {}
        
        # 最大短语长度（用于优化搜索）
        self.max_phrase_len = 1
        
        # 加载预设短语
        self._load_default_phrases()
    
    def _load_default_phrases(self):
        """加载预设的固定搭配"""
        default_phrases = {
            # 属性词 - 袖长/腰高等
            ("long", "sleeve"): ("属性词", 0.9),
            ("short", "sleeve"): ("属性词", 0.9),
            ("sleeveless"): ("属性词", 0.9),
            ("high", "waist"): ("属性词", 0.9),
            ("low", "waist"): ("属性词", 0.9),
            ("mid", "waist"): ("属性词", 0.9),
            ("slim", "fit"): ("属性词", 0.9),
            ("loose", "fit"): ("属性词", 0.9),
            ("regular", "fit"): ("属性词", 0.9),
            ("oversized", "fit"): ("属性词", 0.9),
            ("v", "neck"): ("属性词", 0.9),
            ("crew", "neck"): ("属性词", 0.9),
            ("round", "neck"): ("属性词", 0.9),
            ("hooded"): ("属性词", 0.9),
            ("zip", "up"): ("属性词", 0.9),
            ("button", "down"): ("属性词", 0.9),
            ("pull", "on"): ("属性词", 0.9),
            
            # 卖点词 - 功能特性
            ("quick", "dry"): ("卖点词", 0.9),
            ("fast", "dry"): ("卖点词", 0.9),
            ("water", "resistant"): ("卖点词", 0.9),
            ("water", "proof"): ("卖点词", 0.9),
            ("waterproof"): ("卖点词", 0.9),
            ("wind", "proof"): ("卖点词", 0.9),
            ("windproof"): ("卖点词", 0.9),
            ("breathable"): ("卖点词", 0.9),
            ("lightweight"): ("卖点词", 0.9),
            ("light", "weight"): ("卖点词", 0.9),
            ("noise", "cancelling"): ("卖点词", 0.9),
            ("noise", "canceling"): ("卖点词", 0.9),
            ("sweat", "proof"): ("卖点词", 0.9),
            ("anti", "slip"): ("卖点词", 0.9),
            ("non", "slip"): ("卖点词", 0.9),
            ("uv", "protection"): ("卖点词", 0.9),
            ("sun", "protection"): ("卖点词", 0.9),
            
            # 属性词 - 材质
            ("stainless", "steel"): ("属性词", 0.9),
            ("memory", "foam"): ("属性词", 0.9),
            ("faux", "leather"): ("属性词", 0.9),
            ("genuine", "leather"): ("属性词", 0.9),
            ("real", "leather"): ("属性词", 0.9),
            ("cotton", "blend"): ("属性词", 0.9),
            
            # 属性词 - 技术/功能
            ("open", "ear"): ("属性词", 0.9),
            ("bone", "conduction"): ("属性词", 0.9),
            ("true", "wireless"): ("属性词", 0.9),
            ("touch", "screen"): ("属性词", 0.9),
            
            # 场景词
            ("work", "out"): ("场景词", 0.85),
            ("work", "from", "home"): ("场景词", 0.85),
            ("outdoor", "sports"): ("场景词", 0.85),
            
            # 德语常见搭配
            ("mit", "kapuze"): ("属性词", 0.9),
            ("hohe", "taille"): ("属性词", 0.9),
            ("lange", "ärmel"): ("属性词", 0.9),
            ("kurze", "ärmel"): ("属性词", 0.9),
            
            # 法语常见搭配
            ("taille", "haute"): ("属性词", 0.9),
            ("taille", "basse"): ("属性词", 0.9),
            ("manches", "longues"): ("属性词", 0.9),
            ("manches", "courtes"): ("属性词", 0.9),
            ("sans", "manches"): ("属性词", 0.9),
            ("sous", "lit"): ("属性词", 0.9),
            ("à", "roulettes"): ("属性词", 0.9),
            
            # 西班牙语常见搭配
            ("manga", "larga"): ("属性词", 0.9),
            ("manga", "corta"): ("属性词", 0.9),
            ("sin", "mangas"): ("属性词", 0.9),
            ("cintura", "alta"): ("属性词", 0.9),
            ("cintura", "baja"): ("属性词", 0.9),
        }
        
        for phrase_tuple, (tag, confidence) in default_phrases.items():
            self.add_phrase(phrase_tuple, tag, confidence)
    
    def add_phrase(self, tokens: Tuple[str, ...], tag: str, confidence: float = 0.9):
        """添加固定短语"""
        # 标准化为小写
        normalized = tuple(t.lower() for t in tokens)
        self.phrases[normalized] = (tag, confidence)
        
        # 更新最大长度
        if len(normalized) > self.max_phrase_len:
            self.max_phrase_len = len(normalized)
    
    def add_phrases_from_dict(self, phrases: Dict[str, Tuple[str, float]]):
        """从字典批量添加短语"""
        for phrase_str, (tag, confidence) in phrases.items():
            tokens = tuple(phrase_str.lower().split())
            self.add_phrase(tokens, tag, confidence)
    
    def merge(self, tokens: List[str]) -> List[MergedToken]:
        """
        对 token 列表进行短语合并
        
        Args:
            tokens: 原始 token 列表
            
        Returns:
            合并后的 MergedToken 列表
        """
        if not tokens:
            return []
        
        result = []
        i = 0
        n = len(tokens)
        
        while i < n:
            # 尝试匹配最长的短语
            matched = False
            
            # 从最长可能的短语长度开始尝试
            for phrase_len in range(min(self.max_phrase_len, n - i), 0, -1):
                candidate = tuple(t.lower() for t in tokens[i:i + phrase_len])
                
                if candidate in self.phrases:
                    tag, confidence = self.phrases[candidate]
                    
                    # 创建合并后的 token
                    merged_text = " ".join(tokens[i:i + phrase_len])
                    result.append(MergedToken(
                        text=merged_text,
                        original_tokens=tokens[i:i + phrase_len],
                        start_idx=i,
                        end_idx=i + phrase_len,
                        is_merged=(phrase_len > 1),
                        suggested_tag=tag,
                        confidence=confidence
                    ))
                    
                    i += phrase_len
                    matched = True
                    break
            
            if not matched:
                # 没有匹配到短语，保留原始 token
                result.append(MergedToken(
                    text=tokens[i],
                    original_tokens=[tokens[i]],
                    start_idx=i,
                    end_idx=i + 1,
                    is_merged=False
                ))
                i += 1
        
        return result
    
    def merge_to_strings(self, tokens: List[str]) -> List[str]:
        """便捷方法：直接返回合并后的字符串列表"""
        merged = self.merge(tokens)
        return [m.text for m in merged]
    
    def get_suggested_tags(self, tokens: List[str]) -> Dict[str, Tuple[str, float]]:
        """
        获取合并后每个 token 的建议标签
        
        Returns:
            {token: (tag, confidence)}
        """
        merged = self.merge(tokens)
        return {
            m.text: (m.suggested_tag, m.confidence)
            for m in merged
            if m.suggested_tag is not None
        }


class ContextAwarePhraseMerger(PhraseMerger):
    """
    上下文感知的短语合并器
    
    额外功能：
    - 考虑上下文决定是否合并
    - 处理歧义短语
    """
    
    def __init__(self):
        super().__init__()
        
        # 歧义短语：需要上下文判断
        self.ambiguous_phrases: Dict[Tuple[str, ...], List[Tuple[str, float, str]]] = {
            # (phrase): [(tag1, conf1, context_hint), (tag2, conf2, context_hint)]
            ("pro",): [
                ("属性词", 0.7, "standalone"),  # 单独出现时
                ("品牌词", 0.6, "after_brand"),  # 品牌后面
            ],
            ("max",): [
                ("属性词", 0.7, "standalone"),
                ("品牌词", 0.6, "after_brand"),
            ],
            ("plus",): [
                ("属性词", 0.7, "standalone"),
                ("品牌词", 0.6, "after_brand"),
            ],
        }
    
    def merge_with_context(self, tokens: List[str], context_hints: Dict[int, str] = None) -> List[MergedToken]:
        """
        带上下文的短语合并
        
        Args:
            tokens: token 列表
            context_hints: {token_idx: hint} 上下文提示
        """
        # 基础合并
        result = self.merge(tokens)
        
        # 根据上下文调整歧义 token
        if context_hints:
            for i, merged_token in enumerate(result):
                if merged_token.start_idx in context_hints:
                    hint = context_hints[merged_token.start_idx]
                    # 根据 hint 调整标签...
        
        return result


# 便捷函数
def merge_phrases(tokens: List[str]) -> List[str]:
    """便捷函数：合并固定短语"""
    merger = PhraseMerger()
    return merger.merge_to_strings(tokens)


# 单例实例
_default_merger = None

def get_default_merger() -> PhraseMerger:
    """获取默认的短语合并器实例"""
    global _default_merger
    if _default_merger is None:
        _default_merger = PhraseMerger()
    return _default_merger


# 测试代码
if __name__ == "__main__":
    merger = PhraseMerger()
    
    test_cases = [
        ["long", "sleeve", "shirt", "for", "men"],
        ["high", "waist", "leggings", "damen"],
        ["quick", "dry", "running", "shorts"],
        ["taille", "haute", "legging", "femme"],
        ["manga", "larga", "camiseta"],
        ["stainless", "steel", "water", "bottle"],
        ["true", "wireless", "earbuds", "noise", "cancelling"],
    ]
    
    for tokens in test_cases:
        print(f"\n输入: {tokens}")
        merged = merger.merge(tokens)
        print(f"输出: {[m.text for m in merged]}")
        for m in merged:
            if m.suggested_tag:
                print(f"  '{m.text}' -> {m.suggested_tag} ({m.confidence})")
