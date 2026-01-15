"""
增强版处理流水线

整合改进：
1. 脚本分段处理混合语言
2. 基于 span 的固定短语提取
3. 欧洲语言短语合并
4. 增强版标签标注
5. AI 自动标注（低置信度词）

处理流程：
输入 → 预处理 → 脚本分段 → 固定短语提取(span) → 
各段分词 → 短语合并 → 标签标注 → [AI增强] → 输出
"""
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from core.preprocessor import Preprocessor
from core.script_segmenter import ScriptSegmenter, ScriptType, Segment
from core.span_extractor import SpanPhraseExtractor, Span, create_span_extractor
from core.phrase_merger import PhraseMerger, get_default_merger
from core.enhanced_tagger import EnhancedTagger, TagResult
from core.tokenizers import ChineseTokenizer, JapaneseTokenizer, EuropeanTokenizer


@dataclass
class ProcessedToken:
    """处理后的 token"""
    text: str
    tag: str
    tags: List[str]  # 多标签
    confidence: float
    method: str
    source_segment: Optional[str] = None  # 来源段类型


class EnhancedPipeline:
    """增强版处理流水线"""
    
    def __init__(self, dictionary_manager, enable_ai: bool = True):
        """
        Args:
            dictionary_manager: 词典管理器
            enable_ai: 是否启用 AI 增强（需要配置 ANTHROPIC_API_KEY）
        """
        self.dict_manager = dictionary_manager
        self.enable_ai = enable_ai
        
        # 初始化各模块
        self.preprocessor = Preprocessor()
        self.segmenter = ScriptSegmenter()
        self.span_extractor = create_span_extractor(dictionary_manager)
        self.phrase_merger = get_default_merger()
        self.tagger = EnhancedTagger(dictionary_manager)
        
        # 初始化分词器
        self.tokenizers = {
            'chinese': ChineseTokenizer(dictionary_manager),
            'japanese': JapaneseTokenizer(dictionary_manager),
            'european': EuropeanTokenizer(),
        }
        
        # AI 增强服务（延迟初始化）
        self.ai_enhancer = None
        self.candidate_pool = None
        
        if enable_ai:
            self._init_ai_services()
    
    def _init_ai_services(self):
        """初始化 AI 相关服务"""
        try:
            from services.ai_enhancer_v2 import AIEnhancer
            from services.candidate_pool import CandidatePool
            from pathlib import Path
            
            # 初始化候选池
            pool_path = self.dict_manager.dictionary_path.parent / "data" / "candidate_pool.json"
            self.candidate_pool = CandidatePool(pool_path)
            
            # 初始化 AI 增强服务
            self.ai_enhancer = AIEnhancer(self.candidate_pool)
            
            if self.ai_enhancer.is_enabled:
                print("  ✓ AI 增强服务已启用")
            else:
                print("  ⚠️ AI 增强服务未配置 (缺少 ANTHROPIC_API_KEY)")
        except ImportError as e:
            print(f"  ⚠️ AI 服务加载失败: {e}")
            self.ai_enhancer = None
            self.candidate_pool = None
    
    async def process(self, keyword: str, language: str = None) -> Dict:
        """
        处理单个关键词
        
        Args:
            keyword: 输入关键词
            language: 语言代码（可选，用于语言特定优化）
            
        Returns:
            处理结果字典
        """
        # 1. 预处理
        cleaned, _ = self.preprocessor.process(keyword)  # 返回 (text, record) 元组
        
        # 2. 提取固定短语（span 方式）
        spans, locked_ranges = self.span_extractor.extract(cleaned)
        
        # 3. 脚本分段
        segments = self.segmenter.segment(cleaned)
        
        # 4. 对每段进行分词，跳过已锁定的区间
        all_tokens = []
        
        # 先添加固定短语（按位置）
        span_tokens = [(span.start, span.text, span.tag, span.confidence) for span in spans]
        
        # 对未锁定的段进行分词
        for segment in segments:
            # 检查这段是否完全在锁定区间内
            if self._is_fully_locked(segment.start, segment.end, locked_ranges):
                continue
            
            # 获取这段中未锁定的部分
            unlocked_parts = self._get_unlocked_parts(
                segment.text, segment.start, locked_ranges
            )
            
            for part_start, part_end, part_text in unlocked_parts:
                if not part_text.strip():
                    continue
                
                # 选择分词器
                tokenizer_name = self.segmenter.get_tokenizer_for_script(segment.script)
                
                if tokenizer_name == 'passthrough':
                    # 直接使用，不分词
                    tokens = [part_text.strip()] if part_text.strip() else []
                elif tokenizer_name in self.tokenizers:
                    token_objs = self.tokenizers[tokenizer_name].tokenize(part_text)
                    # Token 对象转为字符串
                    tokens = [t.text if hasattr(t, 'text') else str(t) for t in token_objs]
                else:
                    token_objs = self.tokenizers['european'].tokenize(part_text)
                    tokens = [t.text if hasattr(t, 'text') else str(t) for t in token_objs]
                
                # 过滤空字符串
                tokens = [t for t in tokens if t and t.strip()]
                
                # 欧洲语言进行短语合并
                if tokenizer_name == 'european' and tokens:
                    merged = self.phrase_merger.merge(tokens)
                    
                    # 记录短语合并器的建议标签
                    for m in merged:
                        if m.suggested_tag:
                            all_tokens.append((
                                part_start, m.text, m.suggested_tag, m.confidence
                            ))
                        else:
                            all_tokens.append((part_start, m.text, None, 0.0))
                    
                    # 已添加，跳过后续
                    continue
                
                # 添加分词结果
                for token in tokens:
                    if token and token.strip():
                        all_tokens.append((part_start, token.strip(), None, 0.0))
        
        # 添加 span 提取的固定短语
        all_tokens.extend(span_tokens)
        
        # 按位置排序
        all_tokens.sort(key=lambda x: x[0])
        
        # 提取 token 列表和预设标签
        tokens = [t[1] for t in all_tokens]
        preset_tags = {t[1]: (t[2], t[3]) for t in all_tokens if t[2] is not None}
        
        # 5. 标签标注（传递语言参数用于优化）
        tag_results = self.tagger.tag(tokens, cleaned, language=language)
        
        # 6. 应用预设标签（来自 span 提取和短语合并）
        final_results = []
        for result in tag_results:
            if result.token in preset_tags:
                preset_tag, preset_conf = preset_tags[result.token]
                # 如果预设标签置信度更高，使用预设
                if preset_conf >= result.confidence:
                    result = TagResult(
                        token=result.token,
                        tags=[preset_tag],
                        primary_tag=preset_tag,
                        confidence=preset_conf,
                        method="preset",
                        all_candidates=result.all_candidates
                    )
            final_results.append(result)
        
        # 7. AI 增强（可选）- 对低置信度词调用 AI 标注
        if self.ai_enhancer and self.ai_enhancer.is_enabled:
            final_results = await self._apply_ai_enhancement(final_results, keyword)
        
        # 8. 格式化输出
        return self._format_output(keyword, tokens, final_results)
    
    async def _apply_ai_enhancement(
        self, 
        results: List[TagResult], 
        context: str
    ) -> List[TagResult]:
        """
        应用 AI 增强
        
        对低置信度的词调用 AI 进行标注
        """
        from config import settings
        
        # 筛选需要 AI 处理的词
        low_conf_words = []
        low_conf_indices = []
        
        for i, result in enumerate(results):
            if result.confidence <= settings.ai_confidence_threshold:
                # 跳过太短的词和虚词
                if len(result.token) > 1 and result.method != "stopword":
                    low_conf_words.append(result.token)
                    low_conf_indices.append(i)
        
        if not low_conf_words:
            return results
        
        # 调用 AI 标注
        try:
            ai_results = await self.ai_enhancer.process_batch(low_conf_words, context)
            
            # 更新结果
            for idx, word in zip(low_conf_indices, low_conf_words):
                if word in ai_results:
                    ai_tag = ai_results[word]
                    results[idx] = TagResult(
                        token=word,
                        tags=[ai_tag["tag"]],
                        primary_tag=ai_tag["tag"],
                        confidence=ai_tag["confidence"],
                        method="ai",
                        all_candidates=results[idx].all_candidates
                    )
        except Exception as e:
            print(f"  ⚠️ AI 增强失败: {e}")
        
        return results
    
    def _is_fully_locked(self, start: int, end: int, locked_ranges: List[Tuple[int, int]]) -> bool:
        """检查区间是否完全被锁定"""
        for lock_start, lock_end in locked_ranges:
            if lock_start <= start and end <= lock_end:
                return True
        return False
    
    def _get_unlocked_parts(
        self, 
        text: str, 
        text_start: int, 
        locked_ranges: List[Tuple[int, int]]
    ) -> List[Tuple[int, int, str]]:
        """获取文本中未锁定的部分"""
        # 转换锁定区间到相对于 text_start 的位置
        relative_locks = []
        for lock_start, lock_end in locked_ranges:
            # 计算与当前段的交集
            rel_start = max(0, lock_start - text_start)
            rel_end = min(len(text), lock_end - text_start)
            if rel_start < rel_end:
                relative_locks.append((rel_start, rel_end))
        
        if not relative_locks:
            return [(text_start, text_start + len(text), text)]
        
        # 合并重叠的锁定区间
        relative_locks.sort()
        merged_locks = [relative_locks[0]]
        for start, end in relative_locks[1:]:
            if start <= merged_locks[-1][1]:
                merged_locks[-1] = (merged_locks[-1][0], max(merged_locks[-1][1], end))
            else:
                merged_locks.append((start, end))
        
        # 获取未锁定部分
        parts = []
        prev_end = 0
        
        for lock_start, lock_end in merged_locks:
            if prev_end < lock_start:
                part_text = text[prev_end:lock_start]
                parts.append((text_start + prev_end, text_start + lock_start, part_text))
            prev_end = lock_end
        
        if prev_end < len(text):
            part_text = text[prev_end:]
            parts.append((text_start + prev_end, text_start + len(text), part_text))
        
        return parts
    
    def _format_output(self, original: str, tokens: List[str], tag_results: List[TagResult]) -> Dict:
        """格式化输出结果"""
        tagged_tokens = []
        tag_summary = {}
        
        for result in tag_results:
            tagged_tokens.append({
                "token": result.token,
                "tags": result.tags,
                "confidence": round(result.confidence, 2)
            })
            
            # 使用主标签做 summary
            primary = result.primary_tag
            if primary not in tag_summary:
                tag_summary[primary] = []
            tag_summary[primary].append(result.token)
        
        return {
            "original_keyword": original,
            "tokens": tokens,
            "tagged_tokens": tagged_tokens,
            "tag_summary": tag_summary
        }
    
    async def process_batch(self, keywords: List[str]) -> List[Dict]:
        """批量处理"""
        results = []
        for keyword in keywords:
            result = await self.process(keyword)
            results.append(result)
        return results


# 向后兼容的别名
TokenizePipeline = EnhancedPipeline


# 工厂函数
def create_pipeline(dictionary_manager) -> EnhancedPipeline:
    """创建处理流水线"""
    return EnhancedPipeline(dictionary_manager)
