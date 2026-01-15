"""
标签标注模块
识别8种标签类型：品牌词、商品词、人群词、场景词、颜色词、尺寸词、卖点词、属性词
"""
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


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
class TagResult:
    """标注结果"""
    token: str
    tags: List[str]
    confidence: float
    method: str  # 标注方法：dict/pattern/inference


class Tagger:
    """标签标注器"""
    
    def __init__(self, dictionary_manager):
        self.dict_manager = dictionary_manager
        self._build_patterns()
        self._build_inference_rules()
    
    def _build_patterns(self):
        """构建正则模式"""
        # 颜色词模式
        self.color_patterns = [
            r'.+[色系]$',  # 以"色"或"色系"结尾
            r'^(深|浅|亮|暗|淡).+色$',  # 深X色、浅X色
        ]
        
        # 尺寸词模式
        self.size_patterns = [
            r'^\d+\.?\d*\s*(码|寸|号|cm|mm|m|inch|英寸|厘米)$',
            r'^\d+\.?\d*\s*(kg|g|lb|磅|克|千克)$',
            r'^\d+\.?\d*\s*(ml|l|毫升|升)$',
            r'^\d+\.?\d*\s*(GB|TB|MB|gb|tb|mb)$',
            r'^(S|M|L|XL|XXL|XXXL|XS)$',
            r'^\d+\.?\d*\s*(张|片|个|只|条|支|瓶|盒|包|袋|件|套|双|对)$',
            r'^\d+x\d+$',  # 9x12 等尺寸
            r'^\d+l$',  # 15l 等容量
        ]
        
        # 编译正则
        self.compiled_color_patterns = [re.compile(p, re.IGNORECASE) for p in self.color_patterns]
        self.compiled_size_patterns = [re.compile(p, re.IGNORECASE) for p in self.size_patterns]
    
    def _build_inference_rules(self):
        """构建推断规则 - 多语言支持"""
        
        # 商品词后缀（各语言）
        self.product_suffixes = {
            # 日语
            'シャツ', 'パンツ', 'スカート', 'ドレス', 'コート', 'ジャケット',
            'バッグ', 'ポーチ', 'リュック', 'シューズ', 'ブーツ', 'サンダル',
            'ケース', 'カバー', 'ホルダー', 'スタンド', 'ラック', 'ボックス',
            # 德语
            'hose', 'jacke', 'mantel', 'hemd', 'bluse', 'rock', 'kleid',
            'tasche', 'rucksack', 'schuhe', 'stiefel', 'mütze', 'gürtel',
            'halter', 'ständer', 'box', 'case',
            # 法语
            'pantalon', 'veste', 'manteau', 'chemise', 'robe', 'jupe',
            'sac', 'chaussures', 'bottes', 'chapeau', 'ceinture',
            'support', 'boîte', 'étui', 'housse',
            # 西班牙语
            'pantalón', 'chaqueta', 'abrigo', 'camisa', 'vestido', 'falda',
            'bolso', 'mochila', 'zapatos', 'botas', 'sombrero', 'cinturón',
            'soporte', 'caja', 'funda', 'estuche',
            # 英语
            'shirt', 'pants', 'jacket', 'coat', 'dress', 'skirt',
            'bag', 'backpack', 'shoes', 'boots', 'hat', 'belt',
            'case', 'cover', 'holder', 'stand', 'rack', 'box',
            'legging', 'leggings', 'shorts', 'top', 'tops',
        }
        
        # 人群词关键字
        self.audience_keywords = {
            # 日语
            'メンズ', 'レディース', 'キッズ', 'ベビー', 'ジュニア',
            '男性', '女性', '子供', '大人',
            # 德语
            'damen', 'herren', 'kinder', 'baby', 'mädchen', 'jungen',
            # 法语
            'femme', 'homme', 'enfant', 'bébé', 'fille', 'garçon',
            # 西班牙语
            'mujer', 'hombre', 'niño', 'niña', 'bebé', 'niños',
            # 英语
            'men', 'women', 'mens', 'womens', "men's", "women's",
            'kids', 'boys', 'girls', 'baby', 'unisex', 'adult',
        }
        
        # 场景词关键字
        self.scenario_keywords = {
            # 日语
            'ランニング', 'トレーニング', 'ヨガ', 'スポーツ', 'アウトドア',
            'キャンプ', '登山', 'ハイキング', 'トレッキング', 'オフィス',
            # 德语
            'sport', 'fitness', 'yoga', 'outdoor', 'camping', 'wandern',
            'laufen', 'büro', 'reise', 'fahrrad',
            # 法语
            'sport', 'fitness', 'yoga', 'outdoor', 'camping', 'randonnée',
            'course', 'bureau', 'voyage', 'plage',
            # 西班牙语
            'deporte', 'fitness', 'yoga', 'outdoor', 'camping', 'senderismo',
            'correr', 'oficina', 'viaje', 'gym', 'playa',
            # 英语
            'running', 'training', 'yoga', 'sports', 'outdoor', 'camping',
            'hiking', 'office', 'travel', 'gym', 'beach',
        }
        
        # 卖点词/属性词关键字
        self.feature_keywords = {
            # 日语
            '軽量', '防水', '撥水', '速乾', '保温', '通気', 'ストレッチ',
            '伸縮', '抗菌', '消臭', 'コンパクト', '折りたたみ', '大容量',
            # 德语
            'wasserdicht', 'atmungsaktiv', 'leicht', 'warm', 'elastisch',
            'gepolstert', 'schnelltrocknend', 'kompakt', 'faltbar', 'thermo',
            # 法语
            'imperméable', 'respirant', 'léger', 'chaud', 'élastique',
            'pliable', 'rechargeable', 'compact', 'thermique',
            # 西班牙语
            'impermeable', 'transpirable', 'ligero', 'cálido', 'elástico',
            'plegable', 'recargable', 'compacto',
            # 英语
            'waterproof', 'breathable', 'lightweight', 'warm', 'padded',
            'elastic', 'quick-dry', 'compact', 'foldable', 'thermal',
            'compression', 'stretchy', 'slim', 'fitted',
        }
        
        # 属性词关键字（描述性词汇）
        self.attribute_keywords = {
            # 日语
            '半袖', '長袖', 'ノースリーブ', 'フード付き', 'ポケット付き',
            '裏起毛', 'タイプ', 'セット', 'サイズ',
            # 德语
            'langarm', 'kurzarm', 'ärmellos', 'mit kapuze', 'gefüttert',
            'hoch', 'tief', 'lang', 'kurz', 'mini', 'maxi',
            # 法语
            'manches longues', 'manches courtes', 'sans manches', 'à capuche',
            'haut', 'haute', 'taille', 'long', 'court',
            # 西班牙语
            'manga larga', 'manga corta', 'sin mangas', 'con capucha',
            'alto', 'alta', 'largo', 'corto', 'externo',
            # 英语
            'long sleeve', 'short sleeve', 'sleeveless', 'hooded',
            'high', 'low', 'waist', 'long', 'short', 'slim', 'wide',
            'open ear', 'wireless', 'bluetooth',
        }
    
    def tag(self, tokens: List[str], context: Optional[str] = None) -> List[TagResult]:
        """
        对 tokens 进行标签标注
        
        Args:
            tokens: 分词结果
            context: 上下文（完整标题）
            
        Returns:
            标注结果列表
        """
        results = []
        
        for i, token in enumerate(tokens):
            # 传入位置信息用于推断
            tag_result = self._tag_single(token, tokens, context, position=i)
            results.append(tag_result)
        
        return results
    
    def _tag_single(
        self, 
        token: str, 
        all_tokens: List[str],
        context: Optional[str],
        position: int = 0
    ) -> TagResult:
        """标注单个 token"""
        
        candidates = []
        
        # 1. 词典匹配（最高优先级）
        dict_result = self._match_dictionary(token)
        if dict_result:
            candidates.extend(dict_result)
        
        # 2. 正则模式匹配
        pattern_result = self._match_patterns(token)
        if pattern_result:
            candidates.extend(pattern_result)
        
        # 3. 规则推断（基于关键字匹配）
        if not candidates or all(c["confidence"] < 0.8 for c in candidates):
            infer_result = self._infer_by_rules(token, all_tokens, position)
            if infer_result:
                candidates.extend(infer_result)
        
        # 4. 启发式推断（基于词形特征）
        if not candidates:
            heuristic_result = self._infer_heuristic(token, all_tokens, context, position)
            if heuristic_result:
                candidates.extend(heuristic_result)
        
        # 合并结果
        if not candidates:
            return TagResult(
                token=token,
                tags=["属性词"],  # 默认标签
                confidence=0.5,
                method="default"
            )
        
        # 按置信度排序，取最高的
        candidates.sort(key=lambda x: x["confidence"], reverse=True)
        
        # 取置信度最高的标签
        top_tags = []
        top_confidence = candidates[0]["confidence"]
        
        for c in candidates:
            if c["confidence"] >= top_confidence - 0.1:
                if c["tag"] not in top_tags:
                    top_tags.append(c["tag"])
        
        return TagResult(
            token=token,
            tags=top_tags[:2],
            confidence=top_confidence,
            method=candidates[0]["method"]
        )
    
    def _match_dictionary(self, token: str) -> List[Dict]:
        """从词典匹配"""
        results = []
        token_lower = token.lower()
        
        tag_dict_mapping = {
            "brands": TagType.BRAND.value,
            "products": TagType.PRODUCT.value,
            "audiences": TagType.AUDIENCE.value,
            "scenarios": TagType.SCENARIO.value,
            "colors": TagType.COLOR.value,
            "features": TagType.FEATURE.value,
            "attributes": TagType.ATTRIBUTE.value,
        }
        
        for dict_name, tag_type in tag_dict_mapping.items():
            if self.dict_manager.contains(dict_name, token_lower):
                entry = self.dict_manager.get_entry(dict_name, token_lower)
                confidence = entry.get("confidence", 0.9) if entry else 0.9
                results.append({
                    "tag": tag_type,
                    "confidence": confidence,
                    "method": "dict"
                })
        
        return results
    
    def _match_patterns(self, token: str) -> List[Dict]:
        """正则模式匹配"""
        results = []
        
        # 颜色词模式
        for pattern in self.compiled_color_patterns:
            if pattern.match(token):
                results.append({
                    "tag": TagType.COLOR.value,
                    "confidence": 0.85,
                    "method": "pattern"
                })
                break
        
        # 尺寸词模式
        for pattern in self.compiled_size_patterns:
            if pattern.match(token):
                results.append({
                    "tag": TagType.SIZE.value,
                    "confidence": 0.95,
                    "method": "pattern"
                })
                break
        
        return results
    
    def _infer_by_rules(self, token: str, all_tokens: List[str], position: int) -> List[Dict]:
        """基于规则推断"""
        results = []
        token_lower = token.lower()
        
        # 检查是否是商品词
        if token_lower in self.product_suffixes or token in self.product_suffixes:
            results.append({
                "tag": TagType.PRODUCT.value,
                "confidence": 0.85,
                "method": "rule_inference"
            })
        
        # 检查是否是人群词
        if token_lower in self.audience_keywords or token in self.audience_keywords:
            results.append({
                "tag": TagType.AUDIENCE.value,
                "confidence": 0.85,
                "method": "rule_inference"
            })
        
        # 检查是否是场景词
        if token_lower in self.scenario_keywords or token in self.scenario_keywords:
            results.append({
                "tag": TagType.SCENARIO.value,
                "confidence": 0.85,
                "method": "rule_inference"
            })
        
        # 检查是否是卖点词
        if token_lower in self.feature_keywords or token in self.feature_keywords:
            results.append({
                "tag": TagType.FEATURE.value,
                "confidence": 0.85,
                "method": "rule_inference"
            })
        
        # 检查是否是属性词
        if token_lower in self.attribute_keywords or token in self.attribute_keywords:
            results.append({
                "tag": TagType.ATTRIBUTE.value,
                "confidence": 0.8,
                "method": "rule_inference"
            })
        
        return results
    
    def _infer_heuristic(
        self, 
        token: str, 
        all_tokens: List[str],
        context: Optional[str],
        position: int
    ) -> List[Dict]:
        """启发式推断"""
        results = []
        token_lower = token.lower()
        
        # 规则1: 首字母大写的英文词可能是品牌（但排除常见词）
        common_words = {'the', 'a', 'an', 'and', 'or', 'for', 'with', 'new', 'pro', 'max', 'mini'}
        if (token[0].isupper() and token.isalpha() and len(token) > 2 
            and token_lower not in common_words
            and position == 0):  # 通常品牌在开头
            results.append({
                "tag": TagType.BRAND.value,
                "confidence": 0.65,
                "method": "heuristic"
            })
        
        # 规则2: 包含数字的可能是规格/尺寸
        if any(c.isdigit() for c in token):
            results.append({
                "tag": TagType.SIZE.value,
                "confidence": 0.7,
                "method": "heuristic"
            })
        
        # 规则3: 位置在末尾且是形容词形式可能是属性词
        if position == len(all_tokens) - 1:
            # 检查是否像形容词（如 slim, wide, high 等）
            adj_patterns = ['slim', 'wide', 'high', 'low', 'long', 'short', 'mini', 'maxi']
            if token_lower in adj_patterns:
                results.append({
                    "tag": TagType.ATTRIBUTE.value,
                    "confidence": 0.75,
                    "method": "heuristic"
                })
        
        # 规则4: 检查词尾特征
        # 日语商品词后缀
        ja_product_endings = ['ケース', 'カバー', 'ホルダー', 'スタンド', 'ラック', 'ボックス', 'バッグ']
        for ending in ja_product_endings:
            if token.endswith(ending):
                results.append({
                    "tag": TagType.PRODUCT.value,
                    "confidence": 0.8,
                    "method": "heuristic"
                })
                break
        
        return results


# 工厂函数
def create_tagger(dictionary_manager) -> Tagger:
    """创建 Tagger 实例"""
    return Tagger(dictionary_manager)
