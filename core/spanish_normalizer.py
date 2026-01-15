"""
西班牙语词形归一化器

解决问题：西班牙语有复数和性别变化，导致同一个词有多种形式
例如：
- inalámbrico / inalámbricos / inalámbrica / inalámbricas → 都是 "无线"
- negro / negra / negros / negras → 都是 "黑色"

策略：
1. 复数还原：去掉 -s, -es
2. 性别归一：-a → -o（在词典有对应词的情况下）
3. 常见词尾变化规则
4. 不规则词特殊处理
"""
from typing import Dict, Set, Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class NormalizedWord:
    """归一化结果"""
    original: str
    normalized: str
    changes: List[str]  # 应用的变化规则
    confidence: float


class SpanishNormalizer:
    """
    西班牙语词形归一化器
    
    将复数、阴性形式归一化到基本形式，便于词典匹配
    """
    
    def __init__(self, dictionary: Set[str] = None):
        """
        Args:
            dictionary: 词典词集合，用于验证归一化结果
        """
        self.dictionary = dictionary or set()
        
        # 不规则复数词
        self.irregular_plurals = {
            'pies': 'pie',
            'luces': 'luz',
            'voces': 'voz',
            'peces': 'pez',
            'nueces': 'nuez',
            'raíces': 'raíz',
            'lápices': 'lápiz',
        }
        
        # 不应该归一化的词（本身就是有效词）
        self.no_normalize = {
            'plus', 'bus', 'gas', 'as', 'es', 'os',  # 非复数
            'menos', 'más', 'tras', 'antes',  # 副词/介词
            'dos', 'tres', 'seis', 'diez',  # 数词
            'lunes', 'martes', 'miércoles', 'jueves', 'viernes',  # 星期
            'crisis', 'análisis', 'énfasis', 'tesis', 'síntesis',  # -sis 结尾
            'virus', 'corpus', 'campus', 'bonus', 'status',  # 拉丁词
        }
        
        # 常见形容词的阳性形式（用于性别归一）
        self.adjective_masculine = {
            # -o/-a 形容词
            'negro', 'blanco', 'rojo', 'amarillo', 'azul',
            'largo', 'corto', 'alto', 'bajo', 'ancho', 'estrecho',
            'nuevo', 'viejo', 'bueno', 'malo', 'bonito', 'feo',
            'pequeño', 'grande', 'gordo', 'delgado', 'grueso', 'fino',
            'duro', 'blando', 'suave', 'áspero',
            'limpio', 'sucio', 'seco', 'mojado', 'húmedo',
            'frío', 'caliente', 'templado', 'tibio',
            'rápido', 'lento', 'ligero', 'pesado',
            'barato', 'caro', 'económico',
            'eléctrico', 'electrónico', 'digital', 'manual', 'automático',
            'portátil', 'plegable', 'ajustable', 'lavable', 'impermeable',
            'inalámbrico', 'bluetooth', 'recargable', 'desechable',
            'profesional', 'industrial', 'comercial', 'doméstico',
            'transparente', 'opaco', 'brillante', 'mate',
            'redondo', 'cuadrado', 'rectangular', 'ovalado',
            'plástico', 'metálico', 'cerámico', 'textil',
            'deportivo', 'casual', 'formal', 'elegante',
            'cómodo', 'ergonómico', 'práctico', 'funcional',
            'resistente', 'duradero', 'robusto', 'frágil',
            'moderno', 'clásico', 'vintage', 'retro',
            'inteligente', 'táctil',
        }
        
        # 词尾变化规则（从最特殊到最通用）
        self.plural_rules = [
            # -ces → -z
            (r'ces$', 'z', 3),
            # -ies → -í (raramente usado)
            # -es 后面是辅音 → 去 -es
            (r'([bcdfghjklmnpqrstvwxyz])es$', r'\1', 2),
            # -es 后面是元音 → 可能是 -e + s 或 -es
            # -s 一般情况
            (r's$', '', 1),
        ]
    
    def normalize(self, word: str) -> NormalizedWord:
        """
        归一化单个词
        
        Args:
            word: 输入词
            
        Returns:
            NormalizedWord 包含归一化结果
        """
        original = word
        changes = []
        confidence = 1.0
        
        # 转小写处理
        word_lower = word.lower()
        
        # 检查是否在不归一化列表
        if word_lower in self.no_normalize:
            return NormalizedWord(original, word, [], 1.0)
        
        # 检查不规则复数
        if word_lower in self.irregular_plurals:
            return NormalizedWord(
                original,
                self.irregular_plurals[word_lower],
                ['irregular_plural'],
                0.95
            )
        
        # 1. 复数还原
        word_singular, plural_change = self._depluralize(word_lower)
        if plural_change:
            changes.append(plural_change)
            confidence *= 0.9
            word_lower = word_singular
        
        # 2. 性别归一（-a → -o）
        word_masc, gender_change = self._to_masculine(word_lower)
        if gender_change:
            changes.append(gender_change)
            confidence *= 0.85
            word_lower = word_masc
        
        return NormalizedWord(original, word_lower, changes, confidence)
    
    def _depluralize(self, word: str) -> Tuple[str, Optional[str]]:
        """
        复数还原
        
        Returns:
            (还原后的词, 应用的规则名) 或 (原词, None)
        """
        if len(word) < 3:
            return word, None
        
        # 尝试各种复数规则
        
        # -ces → -z
        if word.endswith('ces') and len(word) > 3:
            singular = word[:-3] + 'z'
            if self._is_valid_word(singular):
                return singular, 'ces→z'
        
        # -iones → -ión
        if word.endswith('iones') and len(word) > 5:
            singular = word[:-5] + 'ión'
            if self._is_valid_word(singular):
                return singular, 'iones→ión'
        
        # -es 辅音结尾
        if word.endswith('es') and len(word) > 3:
            if word[-3] in 'bcdfghjklmnpqrstvwxyz':
                singular = word[:-2]
                if self._is_valid_word(singular):
                    return singular, 'es→∅'
        
        # -s 一般情况（元音+s）
        if word.endswith('s') and len(word) > 2:
            if word[-2] in 'aeiouáéíóú':
                singular = word[:-1]
                if self._is_valid_word(singular):
                    return singular, 's→∅'
        
        # 即使词典没有，也尝试基本的 -s 去除
        if word.endswith('s') and len(word) > 2 and word[-2] in 'aeiouáéíóú':
            return word[:-1], 's→∅(unverified)'
        
        if word.endswith('es') and len(word) > 3 and word[-3] in 'bcdfghjklmnpqrstvwxyz':
            return word[:-2], 'es→∅(unverified)'
        
        return word, None
    
    def _to_masculine(self, word: str) -> Tuple[str, Optional[str]]:
        """
        阴性转阳性
        
        Returns:
            (阳性形式, 应用的规则名) 或 (原词, None)
        """
        if len(word) < 2:
            return word, None
        
        # -a → -o
        if word.endswith('a'):
            masculine = word[:-1] + 'o'
            # 检查阳性形式是否在词典或已知形容词中
            if masculine in self.adjective_masculine or self._is_valid_word(masculine):
                return masculine, 'a→o'
        
        # -as → -os (复数阴性 → 复数阳性)
        if word.endswith('as') and len(word) > 2:
            masculine = word[:-2] + 'os'
            if self._is_valid_word(masculine):
                return masculine, 'as→os'
        
        # -ora → -or
        if word.endswith('ora') and len(word) > 3:
            masculine = word[:-3] + 'or'
            if self._is_valid_word(masculine):
                return masculine, 'ora→or'
        
        # -esa/-isa → -és/-ís (国籍等)
        if word.endswith('esa') and len(word) > 3:
            masculine = word[:-3] + 'és'
            if self._is_valid_word(masculine):
                return masculine, 'esa→és'
        
        return word, None
    
    def _is_valid_word(self, word: str) -> bool:
        """检查词是否有效（在词典中或符合常见模式）"""
        if word in self.dictionary:
            return True
        if word in self.adjective_masculine:
            return True
        # 可以添加更多验证规则
        return False
    
    def set_dictionary(self, dictionary: Set[str]):
        """设置词典"""
        self.dictionary = dictionary
    
    def add_to_dictionary(self, words: List[str]):
        """添加词到词典"""
        self.dictionary.update(w.lower() for w in words)
    
    def normalize_batch(self, words: List[str]) -> Dict[str, str]:
        """
        批量归一化
        
        Returns:
            {original: normalized}
        """
        result = {}
        for word in words:
            normalized = self.normalize(word)
            if normalized.normalized != word.lower():
                result[word] = normalized.normalized
        return result


# 单例
_es_normalizer = None

def get_spanish_normalizer() -> SpanishNormalizer:
    """获取单例实例"""
    global _es_normalizer
    if _es_normalizer is None:
        _es_normalizer = SpanishNormalizer()
    return _es_normalizer


def normalize_spanish(word: str) -> str:
    """便捷函数：归一化单个词"""
    result = get_spanish_normalizer().normalize(word)
    return result.normalized


def normalize_spanish_tokens(tokens: List[str]) -> List[str]:
    """便捷函数：归一化 token 列表"""
    normalizer = get_spanish_normalizer()
    return [normalizer.normalize(t).normalized for t in tokens]


# 测试
if __name__ == "__main__":
    normalizer = SpanishNormalizer()
    
    # 添加一些测试词典
    normalizer.add_to_dictionary([
        'negro', 'rojo', 'azul', 'verde', 'blanco',
        'largo', 'corto', 'grande', 'pequeño',
        'inalámbrico', 'eléctrico', 'portátil',
        'pantalón', 'camiseta', 'vestido',
        'ratón', 'teclado', 'auricular',
    ])
    
    test_words = [
        # 复数
        'negros', 'rojos', 'azules',
        'pantalones', 'camisetas', 'vestidos',
        'auriculares', 'ratones', 'teclados',
        # 阴性
        'negra', 'roja', 'blanca',
        'larga', 'corta', 'grande',
        'inalámbrica', 'eléctrica', 'portátil',
        # 复数阴性
        'negras', 'rojas', 'blancas',
        'inalámbricas', 'eléctricas',
        # 不应该变化
        'plus', 'bus', 'gas',
        'lunes', 'crisis',
    ]
    
    print("=== 西班牙语词形归一化测试 ===\n")
    for word in test_words:
        result = normalizer.normalize(word)
        if result.changes:
            print(f"{word:20} → {result.normalized:20} ({', '.join(result.changes)}) conf={result.confidence:.2f}")
        else:
            print(f"{word:20} → (no change)")
