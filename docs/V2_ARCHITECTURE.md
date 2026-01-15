# V2 架构改进说明

## 一、核心改进点

### 1. 脚本分段处理混合语言 ✅

**问题**：电商标题常见混合语言，如 "New Balance 跑步鞋 メンズ 10.5cm"

**解决方案**：`ScriptSegmenter` 按字符类型（CJK、Latin、Kana）分段，每段用对应分词器处理

```python
from core.script_segmenter import ScriptSegmenter

segmenter = ScriptSegmenter()
segments = segmenter.segment("New Balance跑步鞋メンズ10.5cm")

# 输出:
# [
#   Segment("New Balance", LATIN, 0, 11),
#   Segment("跑步鞋", CJK, 11, 14),
#   Segment("メンズ", KANA, 14, 17),
#   Segment("10.5cm", LATIN, 17, 23)
# ]
```

### 2. 基于 Span 的固定短语提取 ✅

**问题**：`phrase in remaining + replace` 会误匹配子串（"one" 匹配 "someone"）

**解决方案**：`SpanPhraseExtractor` 使用 Trie + 边界感知匹配

```python
from core.span_extractor import create_span_extractor

extractor = create_span_extractor(dict_manager)
spans, locked_ranges = extractor.extract("New Balance running shoes")

# spans: [Span("New Balance", BRAND, "品牌词", 0.95)]
# locked_ranges: [(0, 11)]  # 后续分词跳过这些区间
```

### 3. 欧洲语言短语合并 ✅

**问题**：`long sleeve` 被拆成 `["long", "sleeve"]`

**解决方案**：`PhraseMerger` 在分词后识别并合并固定搭配

```python
from core.phrase_merger import PhraseMerger

merger = PhraseMerger()
tokens = ["long", "sleeve", "shirt", "for", "men"]
merged = merger.merge_to_strings(tokens)

# 输出: ["long sleeve", "shirt", "for", "men"]
```

### 4. 多标签 + 上下文推断 ✅

**问题**：只返回单标签；"14" 在不同上下文意义不同

**解决方案**：`EnhancedTagger` 支持多标签输出 + 上下文窗口推断

```python
from core.enhanced_tagger import EnhancedTagger

tagger = EnhancedTagger(dict_manager)
results = tagger.tag(["iPhone", "14", "Pro", "Max"])

# "14" 后面跟 "Pro" 和 "Max"，上下文推断为型号组成部分
```

### 5. AI 候选池机制 ✅

**问题**：AI 结果直接写入词典会导致错误自我强化

**解决方案**：`CandidatePool` 管理候选词条，满足条件才晋升

```python
from services.candidate_pool import CandidatePool

pool = CandidatePool("data/candidate_pool.json")

# AI 标注结果进入候选池
pool.add("thermo", "卖点词", 0.85, context="thermoleggings damen")

# 满足条件后晋升
if entry.confidence >= 0.75 and entry.seen_count >= 5:
    pool.promote("thermo", dict_manager)
```

---

## 二、新增文件清单

```
core/
├── script_segmenter.py    # 脚本分段器
├── span_extractor.py      # Span 固定短语提取器
├── phrase_merger.py       # 短语合并器
├── enhanced_tagger.py     # 增强版标签标注器
├── enhanced_pipeline.py   # 增强版处理流水线
└── __init__.py            # 更新，导出新模块

services/
└── candidate_pool.py      # AI 候选池
```

---

## 三、升级方法

### 方式一：渐进式升级（推荐）

新旧模块共存，可以逐步切换：

```python
# 使用旧版
from core import TokenizePipeline
pipeline = TokenizePipeline(dict_manager)

# 使用新版
from core import EnhancedPipeline
pipeline = EnhancedPipeline(dict_manager)
```

### 方式二：直接替换

修改 `api/routes/tokenize.py`：

```python
# 旧版
from core.pipeline import TokenizePipeline

# 新版
from core.enhanced_pipeline import EnhancedPipeline as TokenizePipeline
```

---

## 四、新处理流程

```
输入: "New Balance 跑步鞋 メンズ long sleeve"
                    │
                    ▼
            ┌─────────────┐
            │  预处理      │
            └─────────────┘
                    │
                    ▼
            ┌─────────────┐
            │ Span 提取    │  → 识别 "New Balance" (品牌词)
            └─────────────┘     锁定区间 (0, 11)
                    │
                    ▼
            ┌─────────────┐
            │  脚本分段    │  → [LATIN] [CJK] [KANA] [LATIN]
            └─────────────┘
                    │
                    ▼
        ┌───────────┴───────────┐
        │           │           │
        ▼           ▼           ▼
   跳过(已锁定)   jieba      sudachi
        │       "跑步鞋"    "メンズ"
        │           │           │
        └───────────┼───────────┘
                    │
                    ▼
            ┌─────────────┐
            │ 欧洲语言分词  │  → ["long", "sleeve"]
            └─────────────┘
                    │
                    ▼
            ┌─────────────┐
            │  短语合并    │  → ["long sleeve"]
            └─────────────┘
                    │
                    ▼
    合并所有 tokens: ["New Balance", "跑步鞋", "メンズ", "long sleeve"]
                    │
                    ▼
            ┌─────────────┐
            │ 增强版标注   │  → 多标签 + 上下文推断
            └─────────────┘
                    │
                    ▼
输出: {
  "tokens": ["New Balance", "跑步鞋", "メンズ", "long sleeve"],
  "tagged_tokens": [
    {"token": "New Balance", "tags": ["品牌词"], "confidence": 0.95},
    {"token": "跑步鞋", "tags": ["商品词"], "confidence": 0.95},
    {"token": "メンズ", "tags": ["人群词"], "confidence": 0.95},
    {"token": "long sleeve", "tags": ["属性词"], "confidence": 0.90}
  ]
}
```

---

## 五、置信度来源说明

| 来源 | 置信度范围 | 说明 |
|------|-----------|------|
| 词典匹配 | 0.9 - 1.0 | 词典中定义的值 |
| Span 提取 | 0.9 - 0.95 | 固定短语/品牌 |
| 短语合并 | 0.85 - 0.9 | 预设的固定搭配 |
| 正则模式 | 0.85 - 0.95 | 尺寸/颜色模式 |
| 规则推断 | 0.8 - 0.85 | 关键字匹配 |
| 上下文推断 | +0.02 - +0.05 | 上下文加分 |
| 启发式 | 0.65 - 0.8 | 词形特征 |
| 默认 | 0.5 | 未匹配到任何规则 |

---

## 六、后续改进方向

1. **日语分词优化**：调整 Sudachi 模式或添加用户词典
2. **复合词处理**：德语复合词分解（如 "thermoleggings"）
3. **评估系统**：按语言分 bucket 的 F1 评估
4. **性能优化**：LRU 缓存、并发处理
