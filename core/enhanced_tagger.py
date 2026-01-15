"""
增强版标签标注器

改进点：
1. 支持多标签输出（不只返回最高置信度的一个）
2. 上下文窗口推断（考虑前后 token 消解歧义）
3. 标签兼容矩阵（过滤不合理的标签组合）
4. 多层标注策略（词典→规则→启发式→默认）
5. 日语复合词合并（解决过度分词）
6. 西班牙语词形归一化（复数/性别）
"""
import re
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum

# 延迟导入优化模块
_japanese_merger = None
_spanish_normalizer = None

def get_japanese_merger():
    """延迟加载日语复合词合并器"""
    global _japanese_merger
    if _japanese_merger is None:
        try:
            from core.japanese_compound_merger import JapaneseCompoundMerger
            _japanese_merger = JapaneseCompoundMerger()
        except ImportError:
            _japanese_merger = "unavailable"
    return _japanese_merger

def get_spanish_normalizer():
    """延迟加载西班牙语归一化器"""
    global _spanish_normalizer
    if _spanish_normalizer is None:
        try:
            from core.spanish_normalizer import SpanishNormalizer
            _spanish_normalizer = SpanishNormalizer()
        except ImportError:
            _spanish_normalizer = "unavailable"
    return _spanish_normalizer


class TagType(Enum):
    """标签类型"""
    BRAND = "品牌词"
    PRODUCT = "商品词"
    AUDIENCE = "人群词"
    SCENARIO = "场景词"
    COLOR = "颜色词"
    SIZE = "尺寸词"
    FEATURE = "卖点词"
    ATTRIBUTE = "属性词"


@dataclass
class TagCandidate:
    """标签候选"""
    tag: str
    confidence: float
    method: str  # 标注方法：dict/pattern/rule/context/heuristic/default
    source: str = ""  # 来源详情


@dataclass
class TagResult:
    """标注结果"""
    token: str
    tags: List[str]  # 支持多标签
    primary_tag: str  # 主标签（用于 summary）
    confidence: float
    method: str
    all_candidates: List[TagCandidate] = field(default_factory=list)


# 标签兼容矩阵：定义哪些标签可以同时出现
# True = 兼容，False = 不兼容
TAG_COMPATIBILITY = {
    # 尺寸词通常不会和颜色词同时出现在同一个 token
    ("尺寸词", "颜色词"): False,
    ("尺寸词", "品牌词"): False,
    ("颜色词", "品牌词"): False,
    # 商品词和卖点词可以兼容（如 "防水背包"）
    ("商品词", "卖点词"): True,
    # 场景词和人群词可以兼容
    ("场景词", "人群词"): True,
    # 属性词比较通用，可以和大多数兼容
    ("属性词", "商品词"): True,
    ("属性词", "卖点词"): True,
}


def are_tags_compatible(tag1: str, tag2: str) -> bool:
    """检查两个标签是否兼容"""
    if tag1 == tag2:
        return True
    
    key = (tag1, tag2) if tag1 < tag2 else (tag2, tag1)
    
    # 如果在矩阵中定义了，使用定义的值
    if key in TAG_COMPATIBILITY:
        return TAG_COMPATIBILITY[key]
    
    # 默认兼容
    return True


class EnhancedTagger:
    """增强版标签标注器"""
    
    def __init__(self, dictionary_manager):
        self.dict_manager = dictionary_manager
        self._build_patterns()
        self._build_inference_rules()
        self._build_context_rules()
    
    def _build_patterns(self):
        """构建正则模式"""
        # 颜色词模式
        self.color_patterns = [
            re.compile(r'.+[色系]$'),
            re.compile(r'^(深|浅|亮|暗|淡).+色$'),
        ]
        
        # 尺寸词模式
        self.size_patterns = [
            re.compile(r'^\d+\.?\d*\s*(码|寸|号|cm|mm|m|inch|英寸|厘米)$', re.I),
            re.compile(r'^\d+\.?\d*\s*(kg|g|lb|磅|克|千克)$', re.I),
            re.compile(r'^\d+\.?\d*\s*(ml|l|毫升|升)$', re.I),
            re.compile(r'^\d+\.?\d*\s*(GB|TB|MB|gb|tb|mb)$', re.I),
            re.compile(r'^(S|M|L|XL|XXL|XXXL|XS|2XL|3XL|4XL)$', re.I),
            re.compile(r'^\d+x\d+$', re.I),
            re.compile(r'^\d+l$', re.I),
            re.compile(r'^\d+\.?\d*\s*(张|片|个|只|条|支|瓶|盒|包|袋|件|套|双|对)$'),
        ]
    
    def _build_inference_rules(self):
        """构建推断规则"""
        
        # 虚词列表（应该被忽略或特殊标记）
        self.stopwords = {
            # 英语
            'for', 'with', 'and', 'the', 'a', 'an', 'of', 'in', 'on', 'to', 'by',
            'or', 'at', 'as', 'if', 'so', 'up', 'it', 'is', 'be', 'do', 'no',
            # 德语
            'mit', 'für', 'und', 'der', 'die', 'das', 'ein', 'eine',
            'wei', 'gro', 'gr', 'rer',  # 德语碎片
            # 法语
            'de', 'pour', 'avec', 'sans', 'en', 'et', 'le', 'la', 'les', 'un', 'une',
            'du', 'au', 'aux', 'ce', 'se', 'ne', 'que', 'qui', 'ou', 'vue',
            # 西班牙语
            'para', 'de', 'con', 'en', 'y', 'el', 'la', 'los', 'las', 'un', 'una',
            'ni', 'as', 'os', 'ba', 'al', 'del', 'es', 'se', 'su', 'si', 'no',
            # 日语助词和碎片
            'の', 'を', 'に', 'は', 'が', 'で', 'と', 'も', 'や',
            'さめ', 'きめ', 'たたみ', 'せる', 'つける', 'きい', 'ける', 'ない',
        }
        
        # 商品词关键字（多语言）
        self.product_keywords = {
            # 日语
            'シャツ', 'Tシャツ', 'パンツ', 'ジャケット', 'コート', 'スカート',
            'バッグ', 'ポーチ', 'リュック', 'シューズ', 'ブーツ', 'ケース',
            'ベスト', 'ザック',
            # 德语
            'hose', 'jacke', 'mantel', 'hemd', 'bluse', 'rock', 'kleid',
            'tasche', 'rucksack', 'schuhe', 'stiefel',
            # 法语
            'pantalon', 'veste', 'manteau', 'chemise', 'robe', 'jupe',
            'sac', 'chaussures', 'bottes',
            # 西班牙语
            'pantalón', 'chaqueta', 'abrigo', 'camisa', 'vestido', 'falda',
            'bolso', 'mochila', 'zapatos', 'botas',
            # 英语
            'shirt', 'pants', 'jacket', 'coat', 'dress', 'skirt',
            'bag', 'backpack', 'shoes', 'boots', 'shorts', 'tops',
            'legging', 'leggings', 'belt', 'hat', 'cap',
        }
        
        # 人群词
        self.audience_keywords = {
            'メンズ', 'レディース', 'キッズ', 'ベビー',
            'damen', 'herren', 'kinder', 'baby',
            'femme', 'homme', 'enfant',
            'mujer', 'hombre', 'niño', 'niña', 'niños',
            'men', 'women', 'mens', 'womens', "men's", "women's",
            'kids', 'boys', 'girls', 'unisex', 'adult',
        }
        
        # 场景词
        self.scenario_keywords = {
            'ランニング', 'トレーニング', 'ヨガ', 'スポーツ', 'アウトドア',
            'キャンプ', '登山', 'ハイキング', 'トレッキング',
            'sport', 'fitness', 'yoga', 'outdoor', 'camping', 'wandern',
            'running', 'training', 'hiking', 'gym', 'travel',
        }
        
        # 卖点词
        self.feature_keywords = {
            '軽量', '防水', '撥水', '速乾', '保温', '通気', 'ストレッチ',
            'wasserdicht', 'atmungsaktiv', 'leicht', 'warm', 'elastisch', 'thermo',
            'imperméable', 'respirant', 'léger', 'rechargeable',
            'impermeable', 'transpirable', 'ligero',
            'waterproof', 'breathable', 'lightweight', 'compression',
            'quick-dry', 'thermal',
        }
        
        # 属性词
        self.attribute_keywords = {
            '半袖', '長袖', 'フード付き', 'タイプ',
            'langarm', 'kurzarm', 'mini',
            'haute', 'taille', 'long', 'court',
            'alta', 'largo', 'corto', 'externo',
            'long', 'short', 'high', 'low', 'waist', 'sleeve',
            'wireless', 'bluetooth',
        }
    
    def _build_context_rules(self):
        """构建上下文规则"""
        # 上下文加分规则：(前一个token类型, 当前猜测类型) -> 置信度加成
        self.context_boost = {
            # 品牌后面跟商品，两者都加分
            ("品牌词", "商品词"): 0.05,
            ("商品词", "品牌词"): -0.1,  # 商品后面跟品牌不太正常，减分
            # 颜色后面跟商品
            ("颜色词", "商品词"): 0.03,
            # 数字后面跟单位 = 强制尺寸词
            ("number", "unit"): 0.3,
            # 人群词后面跟商品
            ("人群词", "商品词"): 0.02,
            # 场景词后面跟商品
            ("场景词", "商品词"): 0.02,
        }
        
        # 单位词列表（用于 数字+单位 规则）
        self.unit_words = {
            '码', '寸', '号', 'cm', 'mm', 'm', 'inch', '英寸', '厘米',
            'kg', 'g', 'lb', '磅', '克', '千克',
            'ml', 'l', '毫升', '升',
            'gb', 'tb', 'mb',
        }
        
        # 型号后缀（Pro/Max/Plus 等）
        self.model_suffixes = {'pro', 'max', 'plus', 'mini', 'lite', 'ultra', 'se'}
    
    def tag(self, tokens: List[str], context: Optional[str] = None, language: str = None) -> List[TagResult]:
        """
        对 tokens 进行标签标注
        
        Args:
            tokens: 分词结果
            context: 上下文（完整标题）
            language: 语言代码（用于语言特定的优化）
            
        Returns:
            标注结果列表
        """
        # 日语复合词合并
        if language in ('ja', 'japanese', '日语', None):
            tokens = self._merge_japanese_compounds(tokens)
        
        results = []
        
        # 第一轮：独立标注每个 token
        for i, token in enumerate(tokens):
            candidates = self._get_candidates(token, tokens, i, language=language)
            results.append(self._create_result(token, candidates))
        
        # 第二轮：上下文调整
        results = self._apply_context_adjustments(results, tokens)
        
        return results
    
    def _merge_japanese_compounds(self, tokens: List[str]) -> List[str]:
        """合并日语复合词"""
        merger = get_japanese_merger()
        if merger == "unavailable" or merger is None:
            return tokens
        
        # 检查是否包含日语字符
        has_japanese = any(
            any('\u3040' <= c <= '\u309F' or  # Hiragana
                '\u30A0' <= c <= '\u30FF' or  # Katakana
                '\u4E00' <= c <= '\u9FFF'     # CJK
                for c in token)
            for token in tokens
        )
        
        if not has_japanese:
            return tokens
        
        # 从词典管理器获取所有词，传递给合并器
        # 这样只有词典中存在的复合词才会被合并
        try:
            all_dict_words = set()
            for dict_name in ['products', 'brands', 'scenarios', 'features', 'attributes', 'colors', 'audiences']:
                words = self.dict_manager.get_all_words(dict_name)
                if words:
                    all_dict_words.update(w.lower() for w in words)
                    all_dict_words.update(words)  # 保留原始大小写
            
            merger.set_dictionary(all_dict_words)
        except Exception:
            pass  # 如果获取失败，继续使用默认词典
        
        try:
            merged = merger.merge_to_strings(tokens)
            return merged
        except Exception:
            return tokens
    
    def _get_candidates(self, token: str, all_tokens: List[str], position: int, language: str = None) -> List[TagCandidate]:
        """获取所有候选标签"""
        candidates = []
        token_lower = token.lower()
        
        # 0. 虚词处理 - 给予较高置信度的"属性词"标签，避免干扰统计
        if token_lower in self.stopwords:
            return [TagCandidate(
                tag="属性词",
                confidence=0.85,  # 虚词给较高置信度，因为我们确定它是什么
                method="stopword",
                source="stopword_list"
            )]
        
        # 1. 词典匹配（包含西班牙语归一化）
        dict_candidates = self._match_dictionary(token, language=language)
        candidates.extend(dict_candidates)
        
        # 2. 正则模式匹配
        pattern_candidates = self._match_patterns(token)
        candidates.extend(pattern_candidates)
        
        # 3. 规则推断
        rule_candidates = self._infer_by_rules(token, all_tokens, position)
        candidates.extend(rule_candidates)
        
        # 4. 启发式推断
        if not candidates or max(c.confidence for c in candidates) < 0.7:
            heuristic_candidates = self._infer_heuristic(token, all_tokens, position)
            candidates.extend(heuristic_candidates)
        
        return candidates
    
    def _match_dictionary(self, token: str, language: str = None) -> List[TagCandidate]:
        """从词典匹配（支持西班牙语归一化）"""
        candidates = []
        token_lower = token.lower()
        
        # 西班牙语归一化
        normalized_token = None
        if language in ('es', 'spanish', '西班牙语', None):
            normalizer = get_spanish_normalizer()
            if normalizer != "unavailable" and normalizer is not None:
                try:
                    result = normalizer.normalize(token_lower)
                    if result.normalized != token_lower and result.changes:
                        normalized_token = result.normalized
                except Exception:
                    pass
        
        tag_dict_mapping = {
            "brands": "品牌词",
            "products": "商品词",
            "audiences": "人群词",
            "scenarios": "场景词",
            "colors": "颜色词",
            "features": "卖点词",
            "attributes": "属性词",
        }
        
        for dict_name, tag_type in tag_dict_mapping.items():
            # 先尝试原始词
            if self.dict_manager.contains(dict_name, token_lower):
                entry = self.dict_manager.get_entry(dict_name, token_lower)
                confidence = entry.get("confidence", 0.9) if entry else 0.9
                candidates.append(TagCandidate(
                    tag=tag_type,
                    confidence=confidence,
                    method="dict",
                    source=f"dict:{dict_name}"
                ))
            # 如果原始词没找到，尝试归一化后的词
            elif normalized_token and self.dict_manager.contains(dict_name, normalized_token):
                entry = self.dict_manager.get_entry(dict_name, normalized_token)
                # 归一化匹配的置信度稍低
                base_conf = entry.get("confidence", 0.9) if entry else 0.9
                confidence = base_conf * 0.95  # 稍微降低置信度
                candidates.append(TagCandidate(
                    tag=tag_type,
                    confidence=confidence,
                    method="dict_normalized",
                    source=f"dict:{dict_name}(normalized:{normalized_token})"
                ))
        
        return candidates
    
    def _match_patterns(self, token: str) -> List[TagCandidate]:
        """正则模式匹配"""
        candidates = []
        
        # 颜色词模式
        for pattern in self.color_patterns:
            if pattern.match(token):
                candidates.append(TagCandidate(
                    tag="颜色词",
                    confidence=0.85,
                    method="pattern",
                    source="color_pattern"
                ))
                break
        
        # 尺寸词模式
        for pattern in self.size_patterns:
            if pattern.match(token):
                candidates.append(TagCandidate(
                    tag="尺寸词",
                    confidence=0.95,
                    method="pattern",
                    source="size_pattern"
                ))
                break
        
        return candidates
    
    def _infer_by_rules(self, token: str, all_tokens: List[str], position: int) -> List[TagCandidate]:
        """基于规则推断"""
        candidates = []
        token_lower = token.lower()
        
        # 检查各类关键字
        if token_lower in self.product_keywords or token in self.product_keywords:
            candidates.append(TagCandidate(
                tag="商品词", confidence=0.85, method="rule", source="product_keywords"
            ))
        
        if token_lower in self.audience_keywords or token in self.audience_keywords:
            candidates.append(TagCandidate(
                tag="人群词", confidence=0.85, method="rule", source="audience_keywords"
            ))
        
        if token_lower in self.scenario_keywords or token in self.scenario_keywords:
            candidates.append(TagCandidate(
                tag="场景词", confidence=0.85, method="rule", source="scenario_keywords"
            ))
        
        if token_lower in self.feature_keywords or token in self.feature_keywords:
            candidates.append(TagCandidate(
                tag="卖点词", confidence=0.85, method="rule", source="feature_keywords"
            ))
        
        if token_lower in self.attribute_keywords or token in self.attribute_keywords:
            candidates.append(TagCandidate(
                tag="属性词", confidence=0.8, method="rule", source="attribute_keywords"
            ))
        
        return candidates
    
    def _infer_heuristic(self, token: str, all_tokens: List[str], position: int) -> List[TagCandidate]:
        """启发式推断"""
        candidates = []
        token_lower = token.lower()
        
        # 规则1: 首字母大写 + 开头位置 → 可能是品牌
        common_words = {'the', 'a', 'an', 'and', 'or', 'for', 'with', 'new', 'pro', 'max', 'mini'}
        if (len(token) > 2 and token[0].isupper() and token.isalpha() 
            and token_lower not in common_words and position == 0):
            candidates.append(TagCandidate(
                tag="品牌词", confidence=0.65, method="heuristic", source="capitalized_first"
            ))
        
        # 规则2: 包含数字 → 可能是尺寸/型号
        if any(c.isdigit() for c in token):
            candidates.append(TagCandidate(
                tag="尺寸词", confidence=0.7, method="heuristic", source="contains_digit"
            ))
        
        # 规则3: 型号后缀
        if token_lower in self.model_suffixes:
            # 检查前一个 token 是否可能是品牌/产品名
            if position > 0:
                candidates.append(TagCandidate(
                    tag="属性词", confidence=0.75, method="heuristic", source="model_suffix"
                ))
        
        return candidates
    
    def _apply_context_adjustments(self, results: List[TagResult], tokens: List[str]) -> List[TagResult]:
        """应用上下文调整"""
        if len(results) < 2:
            return results
        
        adjusted = []
        
        for i, result in enumerate(results):
            # 获取上下文窗口
            prev_tag = results[i-1].primary_tag if i > 0 else None
            next_tag = results[i+1].primary_tag if i < len(results)-1 else None
            
            # 检查是否需要调整
            adjustment = 0.0
            
            # 规则: 数字 + 单位词 → 强制尺寸词
            if i > 0:
                prev_token = tokens[i-1]
                curr_token = tokens[i].lower()
                
                if prev_token.replace('.', '').isdigit() and curr_token in self.unit_words:
                    # 当前 token 是单位，前一个是数字
                    result = TagResult(
                        token=result.token,
                        tags=["尺寸词"],
                        primary_tag="尺寸词",
                        confidence=0.95,
                        method="context",
                        all_candidates=result.all_candidates
                    )
            
            # 应用上下文加分
            if prev_tag:
                key = (prev_tag, result.primary_tag)
                if key in self.context_boost:
                    adjustment += self.context_boost[key]
            
            if adjustment != 0.0:
                new_confidence = min(1.0, max(0.0, result.confidence + adjustment))
                result = TagResult(
                    token=result.token,
                    tags=result.tags,
                    primary_tag=result.primary_tag,
                    confidence=new_confidence,
                    method=result.method,
                    all_candidates=result.all_candidates
                )
            
            adjusted.append(result)
        
        return adjusted
    
    def _create_result(self, token: str, candidates: List[TagCandidate]) -> TagResult:
        """从候选列表创建结果"""
        if not candidates:
            return TagResult(
                token=token,
                tags=["属性词"],
                primary_tag="属性词",
                confidence=0.5,
                method="default"
            )
        
        # 按置信度排序
        candidates.sort(key=lambda c: c.confidence, reverse=True)
        
        # 获取主标签
        primary = candidates[0]
        
        # 获取兼容的次级标签
        secondary_tags = []
        for c in candidates[1:]:
            if are_tags_compatible(primary.tag, c.tag) and c.confidence >= 0.7:
                secondary_tags.append(c.tag)
        
        # 构建标签列表（主标签 + 兼容的次级标签）
        all_tags = [primary.tag] + secondary_tags[:1]  # 最多2个标签
        
        return TagResult(
            token=token,
            tags=all_tags,
            primary_tag=primary.tag,
            confidence=primary.confidence,
            method=primary.method,
            all_candidates=candidates
        )


# 工厂函数
def create_enhanced_tagger(dictionary_manager) -> EnhancedTagger:
    """创建增强版 Tagger"""
    return EnhancedTagger(dictionary_manager)


# 向后兼容
Tagger = EnhancedTagger
create_tagger = create_enhanced_tagger
