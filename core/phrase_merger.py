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
            # ==================== 商品词短语 ====================
            # 纸品/文具
            ("card", "stock"): ("商品词", 0.95),
            ("cardstock"): ("商品词", 0.95),
            ("sticky", "notes"): ("商品词", 0.95),
            ("index", "cards"): ("商品词", 0.95),
            ("flash", "cards"): ("商品词", 0.95),
            ("business", "cards"): ("商品词", 0.95),
            ("greeting", "cards"): ("商品词", 0.95),
            ("note", "cards"): ("商品词", 0.95),
            
            # 包袋
            ("duffle", "bag"): ("商品词", 0.95),
            ("duffel", "bag"): ("商品词", 0.95),
            ("tote", "bag"): ("商品词", 0.95),
            ("messenger", "bag"): ("商品词", 0.95),
            ("laptop", "bag"): ("商品词", 0.95),
            ("gym", "bag"): ("商品词", 0.95),
            ("travel", "bag"): ("商品词", 0.95),
            ("shoulder", "bag"): ("商品词", 0.95),
            ("crossbody", "bag"): ("商品词", 0.95),
            ("fanny", "pack"): ("商品词", 0.95),
            ("belt", "bag"): ("商品词", 0.95),
            ("sling", "bag"): ("商品词", 0.95),
            
            # 床品/家居
            ("bed", "sheets"): ("商品词", 0.95),
            ("sheet", "set"): ("商品词", 0.95),
            ("pillow", "case"): ("商品词", 0.95),
            ("pillow", "cases"): ("商品词", 0.95),
            ("mattress", "topper"): ("商品词", 0.95),
            ("mattress", "pad"): ("商品词", 0.95),
            ("mattress", "protector"): ("商品词", 0.95),
            ("comforter", "set"): ("商品词", 0.95),
            ("duvet", "cover"): ("商品词", 0.95),
            ("throw", "blanket"): ("商品词", 0.95),
            ("throw", "pillow"): ("商品词", 0.95),
            
            # 汽车配件
            ("roof", "sunshade"): ("商品词", 0.95),
            ("sun", "shade"): ("商品词", 0.95),
            ("car", "cover"): ("商品词", 0.95),
            ("seat", "cover"): ("商品词", 0.95),
            ("seat", "covers"): ("商品词", 0.95),
            ("floor", "mats"): ("商品词", 0.95),
            ("floor", "mat"): ("商品词", 0.95),
            ("steering", "wheel", "cover"): ("商品词", 0.95),
            ("phone", "holder"): ("商品词", 0.95),
            ("phone", "mount"): ("商品词", 0.95),
            ("dash", "cam"): ("商品词", 0.95),
            ("dash", "camera"): ("商品词", 0.95),
            
            # 电子产品
            ("power", "bank"): ("商品词", 0.95),
            ("charging", "cable"): ("商品词", 0.95),
            ("usb", "cable"): ("商品词", 0.95),
            ("mouse", "pad"): ("商品词", 0.95),
            ("keyboard", "cover"): ("商品词", 0.95),
            ("screen", "protector"): ("商品词", 0.95),
            ("phone", "case"): ("商品词", 0.95),
            ("tablet", "stand"): ("商品词", 0.95),
            ("laptop", "stand"): ("商品词", 0.95),
            ("monitor", "stand"): ("商品词", 0.95),
            ("ring", "light"): ("商品词", 0.95),
            ("led", "strip"): ("商品词", 0.95),
            ("led", "lights"): ("商品词", 0.95),
            ("fairy", "lights"): ("商品词", 0.95),
            ("string", "lights"): ("商品词", 0.95),
            
            # 运动用品
            ("yoga", "mat"): ("商品词", 0.95),
            ("yoga", "pants"): ("商品词", 0.95),
            ("yoga", "block"): ("商品词", 0.95),
            ("resistance", "bands"): ("商品词", 0.95),
            ("resistance", "band"): ("商品词", 0.95),
            ("jump", "rope"): ("商品词", 0.95),
            ("exercise", "ball"): ("商品词", 0.95),
            ("foam", "roller"): ("商品词", 0.95),
            ("pull", "up", "bar"): ("商品词", 0.95),
            ("ab", "roller"): ("商品词", 0.95),
            
            # 厨房用品
            ("cutting", "board"): ("商品词", 0.95),
            ("chopping", "board"): ("商品词", 0.95),
            ("water", "bottle"): ("商品词", 0.95),
            ("coffee", "mug"): ("商品词", 0.95),
            ("travel", "mug"): ("商品词", 0.95),
            ("lunch", "box"): ("商品词", 0.95),
            ("lunch", "bag"): ("商品词", 0.95),
            ("ice", "cube", "tray"): ("商品词", 0.95),
            ("storage", "container"): ("商品词", 0.95),
            ("storage", "containers"): ("商品词", 0.95),
            ("food", "storage"): ("商品词", 0.95),
            
            # 服装相关商品词
            ("t", "shirt"): ("商品词", 0.95),
            ("t-shirt"): ("商品词", 0.95),
            ("tank", "top"): ("商品词", 0.95),
            ("polo", "shirt"): ("商品词", 0.95),
            ("dress", "shirt"): ("商品词", 0.95),
            ("button", "down", "shirt"): ("商品词", 0.95),
            ("cargo", "pants"): ("商品词", 0.95),
            ("cargo", "shorts"): ("商品词", 0.95),
            ("sweat", "pants"): ("商品词", 0.95),
            ("sweatpants"): ("商品词", 0.95),
            ("sweat", "shirt"): ("商品词", 0.95),
            ("sweatshirt"): ("商品词", 0.95),
            ("rain", "jacket"): ("商品词", 0.95),
            ("rain", "coat"): ("商品词", 0.95),
            ("puffer", "jacket"): ("商品词", 0.95),
            ("bomber", "jacket"): ("商品词", 0.95),
            ("denim", "jacket"): ("商品词", 0.95),
            ("leather", "jacket"): ("商品词", 0.95),
            ("sports", "bra"): ("商品词", 0.95),
            ("running", "shoes"): ("商品词", 0.95),
            ("hiking", "boots"): ("商品词", 0.95),
            ("ankle", "boots"): ("商品词", 0.95),
            ("snow", "boots"): ("商品词", 0.95),
            ("rain", "boots"): ("商品词", 0.95),
            ("knee", "high", "boots"): ("商品词", 0.95),
            ("flip", "flops"): ("商品词", 0.95),
            
            # 德语商品词短语
            ("lauf", "schuhe"): ("商品词", 0.95),
            ("sport", "schuhe"): ("商品词", 0.95),
            ("regen", "jacke"): ("商品词", 0.95),
            ("schlaf", "anzug"): ("商品词", 0.95),
            ("bade", "anzug"): ("商品词", 0.95),
            
            # 法语商品词短语
            ("sac", "à", "dos"): ("商品词", 0.95),
            ("sac", "de", "voyage"): ("商品词", 0.95),
            ("sac", "à", "main"): ("商品词", 0.95),
            ("chaussures", "de", "course"): ("商品词", 0.95),
            ("tapis", "de", "yoga"): ("商品词", 0.95),
            
            # 西班牙语商品词短语
            ("bolsa", "de", "viaje"): ("商品词", 0.95),
            ("mochila", "escolar"): ("商品词", 0.95),
            ("funda", "de", "almohada"): ("商品词", 0.95),
            ("alfombrilla", "de", "ratón"): ("商品词", 0.95),
            ("cargador", "inalámbrico"): ("商品词", 0.95),
            
            # ==================== 属性词短语 ====================
            # 袖长/腰高等
            ("long", "sleeve"): ("属性词", 0.9),
            ("short", "sleeve"): ("属性词", 0.9),
            ("sleeveless"): ("属性词", 0.9),
            ("cap", "sleeve"): ("属性词", 0.9),
            ("3/4", "sleeve"): ("属性词", 0.9),
            ("high", "waist"): ("属性词", 0.9),
            ("low", "waist"): ("属性词", 0.9),
            ("mid", "waist"): ("属性词", 0.9),
            ("high", "rise"): ("属性词", 0.9),
            ("low", "rise"): ("属性词", 0.9),
            ("mid", "rise"): ("属性词", 0.9),
            ("slim", "fit"): ("属性词", 0.9),
            ("loose", "fit"): ("属性词", 0.9),
            ("regular", "fit"): ("属性词", 0.9),
            ("relaxed", "fit"): ("属性词", 0.9),
            ("oversized", "fit"): ("属性词", 0.9),
            ("v", "neck"): ("属性词", 0.9),
            ("crew", "neck"): ("属性词", 0.9),
            ("round", "neck"): ("属性词", 0.9),
            ("scoop", "neck"): ("属性词", 0.9),
            ("mock", "neck"): ("属性词", 0.9),
            ("turtle", "neck"): ("属性词", 0.9),
            ("hooded"): ("属性词", 0.9),
            ("zip", "up"): ("属性词", 0.9),
            ("button", "down"): ("属性词", 0.9),
            ("pull", "on"): ("属性词", 0.9),
            ("wide", "leg"): ("属性词", 0.9),
            ("straight", "leg"): ("属性词", 0.9),
            ("skinny", "leg"): ("属性词", 0.9),
            ("bootcut"): ("属性词", 0.9),
            ("full", "length"): ("属性词", 0.9),
            ("knee", "length"): ("属性词", 0.9),
            ("ankle", "length"): ("属性词", 0.9),
            
            # 材质
            ("stainless", "steel"): ("属性词", 0.9),
            ("memory", "foam"): ("属性词", 0.9),
            ("faux", "leather"): ("属性词", 0.9),
            ("genuine", "leather"): ("属性词", 0.9),
            ("real", "leather"): ("属性词", 0.9),
            ("pu", "leather"): ("属性词", 0.9),
            ("vegan", "leather"): ("属性词", 0.9),
            ("cotton", "blend"): ("属性词", 0.9),
            ("bamboo", "fiber"): ("属性词", 0.9),
            ("microfiber"): ("属性词", 0.9),
            ("fleece", "lined"): ("属性词", 0.9),
            ("sherpa", "lined"): ("属性词", 0.9),
            ("fur", "lined"): ("属性词", 0.9),
            
            # 技术/功能
            ("open", "ear"): ("属性词", 0.9),
            ("bone", "conduction"): ("属性词", 0.9),
            ("true", "wireless"): ("属性词", 0.9),
            ("touch", "screen"): ("属性词", 0.9),
            ("dual", "layer"): ("属性词", 0.9),
            ("double", "layer"): ("属性词", 0.9),
            ("single", "layer"): ("属性词", 0.9),
            
            # ==================== 卖点词短语 ====================
            ("quick", "dry"): ("卖点词", 0.9),
            ("fast", "dry"): ("卖点词", 0.9),
            ("quick", "drying"): ("卖点词", 0.9),
            ("water", "resistant"): ("卖点词", 0.9),
            ("water", "proof"): ("卖点词", 0.9),
            ("waterproof"): ("卖点词", 0.9),
            ("wind", "proof"): ("卖点词", 0.9),
            ("windproof"): ("卖点词", 0.9),
            ("breathable"): ("卖点词", 0.9),
            ("lightweight"): ("卖点词", 0.9),
            ("light", "weight"): ("卖点词", 0.9),
            ("ultra", "light"): ("卖点词", 0.9),
            ("noise", "cancelling"): ("卖点词", 0.9),
            ("noise", "canceling"): ("卖点词", 0.9),
            ("sweat", "proof"): ("卖点词", 0.9),
            ("sweat", "resistant"): ("卖点词", 0.9),
            ("anti", "slip"): ("卖点词", 0.9),
            ("non", "slip"): ("卖点词", 0.9),
            ("anti", "skid"): ("卖点词", 0.9),
            ("uv", "protection"): ("卖点词", 0.9),
            ("sun", "protection"): ("卖点词", 0.9),
            ("spf", "protection"): ("卖点词", 0.9),
            ("wrinkle", "free"): ("卖点词", 0.9),
            ("stain", "resistant"): ("卖点词", 0.9),
            ("odor", "resistant"): ("卖点词", 0.9),
            ("scratch", "resistant"): ("卖点词", 0.9),
            ("shock", "proof"): ("卖点词", 0.9),
            ("shockproof"): ("卖点词", 0.9),
            ("drop", "proof"): ("卖点词", 0.9),
            ("dust", "proof"): ("卖点词", 0.9),
            ("machine", "washable"): ("卖点词", 0.9),
            ("easy", "clean"): ("卖点词", 0.9),
            ("easy", "to", "clean"): ("卖点词", 0.9),
            ("heavy", "duty"): ("卖点词", 0.9),
            ("long", "lasting"): ("卖点词", 0.9),
            ("fast", "charging"): ("卖点词", 0.9),
            ("quick", "charge"): ("卖点词", 0.9),
            
            # ==================== 尺寸词短语 ====================
            ("king", "size"): ("尺寸词", 0.9),
            ("queen", "size"): ("尺寸词", 0.9),
            ("full", "size"): ("尺寸词", 0.9),
            ("twin", "size"): ("尺寸词", 0.9),
            ("extra", "large"): ("尺寸词", 0.9),
            ("extra", "small"): ("尺寸词", 0.9),
            ("plus", "size"): ("尺寸词", 0.9),
            ("one", "size"): ("尺寸词", 0.9),
            
            # ==================== 场景词短语 ====================
            ("work", "out"): ("场景词", 0.85),
            ("work", "from", "home"): ("场景词", 0.85),
            ("outdoor", "sports"): ("场景词", 0.85),
            ("outdoor", "activities"): ("场景词", 0.85),
            ("road", "trip"): ("场景词", 0.85),
            ("beach", "vacation"): ("场景词", 0.85),
            ("back", "to", "school"): ("场景词", 0.85),
            ("daily", "use"): ("场景词", 0.85),
            ("everyday", "use"): ("场景词", 0.85),
            
            # ==================== 人群词短语 ====================
            ("big", "and", "tall"): ("人群词", 0.9),
            ("petite", "women"): ("人群词", 0.9),
            ("plus", "size", "women"): ("人群词", 0.9),
            ("young", "adults"): ("人群词", 0.9),
            ("teen", "girls"): ("人群词", 0.9),
            ("teen", "boys"): ("人群词", 0.9),
            ("little", "girls"): ("人群词", 0.9),
            ("little", "boys"): ("人群词", 0.9),
            
            # ==================== 德语短语 ====================
            ("mit", "kapuze"): ("属性词", 0.9),
            ("mit", "taschen"): ("属性词", 0.9),
            ("mit", "reißverschluss"): ("属性词", 0.9),
            ("hohe", "taille"): ("属性词", 0.9),
            ("hoher", "bund"): ("属性词", 0.9),
            ("lange", "ärmel"): ("属性词", 0.9),
            ("kurze", "ärmel"): ("属性词", 0.9),
            ("ohne", "ärmel"): ("属性词", 0.9),
            ("schnell", "trocknend"): ("卖点词", 0.9),
            
            # ==================== 法语短语 ====================
            ("taille", "haute"): ("属性词", 0.9),
            ("taille", "basse"): ("属性词", 0.9),
            ("manches", "longues"): ("属性词", 0.9),
            ("manches", "courtes"): ("属性词", 0.9),
            ("sans", "manches"): ("属性词", 0.9),
            ("sous", "lit"): ("属性词", 0.9),
            ("à", "roulettes"): ("属性词", 0.9),
            ("pour", "femme"): ("人群词", 0.9),
            ("pour", "homme"): ("人群词", 0.9),
            ("pour", "enfant"): ("人群词", 0.9),
            
            # ==================== 西班牙语短语 ====================
            ("manga", "larga"): ("属性词", 0.9),
            ("manga", "corta"): ("属性词", 0.9),
            ("sin", "mangas"): ("属性词", 0.9),
            ("cintura", "alta"): ("属性词", 0.9),
            ("cintura", "baja"): ("属性词", 0.9),
            ("talla", "grande"): ("尺寸词", 0.9),
            ("para", "mujer"): ("人群词", 0.9),
            ("para", "hombre"): ("人群词", 0.9),
            ("para", "niños"): ("人群词", 0.9),
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
