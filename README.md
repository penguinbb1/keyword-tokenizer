# 🏷️ Multilingual E-commerce Keyword Tokenizer

多语言电商关键词分词与语义标注系统

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ 功能特点

- 🌍 **多语言支持**：中文、日语、英语、德语、法语、西班牙语
- 🔀 **混合语言处理**：自动识别并分别处理 `Nike ランニングシューズ 26.5cm`
- 🏷️ **语义标注**：品牌词、商品词、人群词、场景词、颜色词、尺寸词、卖点词、属性词
- 📊 **置信度评估**：每个标注附带可信度分数
- 🤖 **AI 增强**：可选的 Claude API 补充标注

## 🚀 快速开始

### 安装

```bash
# 克隆项目
git clone https://github.com/yourusername/keyword-tokenizer.git
cd keyword-tokenizer

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 安装日语分词器（可选）
pip install sudachipy sudachidict_core
```

### 配置

```bash
# 复制环境变量示例
cp .env.example .env

# 编辑 .env，配置 API Key（可选，用于 AI 增强）
# ANTHROPIC_API_KEY=your-api-key-here
```

### 使用

#### 命令行测试

```bash
# 单条测试
python3 scripts/test_v2.py

# 批量测试（不使用 AI）
python3 scripts/batch_test_v2.py keywords.csv -o results.json --no-ai

# 批量测试（使用 AI 增强）
python3 scripts/batch_test_v2.py keywords.csv -o results.json
```

#### API 服务

```bash
# 启动服务
python3 run.py

# 调用接口
curl -X POST "http://localhost:8000/api/tokenize" \
  -H "Content-Type: application/json" \
  -d '{"keyword": "Nike ランニングシューズ メンズ"}'
```

#### Python 代码

```python
import asyncio
from pathlib import Path
from services.dictionary_manager import DictionaryManager
from core.enhanced_pipeline import EnhancedPipeline

# 初始化
dict_manager = DictionaryManager(Path("dictionaries"))
dict_manager.load_all()
pipeline = EnhancedPipeline(dict_manager, enable_ai=False)

# 处理关键词
async def main():
    result = await pipeline.process("Nike ランニングシューズ メンズ 26.5cm")
    print(result)

asyncio.run(main())
```

## 📖 输出示例

```json
{
  "original_keyword": "Nike ランニングシューズ メンズ 26.5cm",
  "tokens": ["Nike", "ランニングシューズ", "メンズ", "26.5cm"],
  "tagged_tokens": [
    {"token": "Nike", "tag": "品牌词", "confidence": 0.95},
    {"token": "ランニングシューズ", "tag": "商品词", "confidence": 0.90},
    {"token": "メンズ", "tag": "人群词", "confidence": 0.90},
    {"token": "26.5cm", "tag": "尺寸词", "confidence": 0.95}
  ],
  "tag_summary": {
    "品牌词": ["Nike"],
    "商品词": ["ランニングシューズ"],
    "人群词": ["メンズ"],
    "尺寸词": ["26.5cm"]
  }
}
```

## 🏷️ 标签类型

| 标签 | 说明 | 示例 |
|------|------|------|
| 品牌词 | 品牌名称 | Nike, Sony, ナイキ |
| 商品词 | 商品品类 | leggings, シューズ, 背包 |
| 人群词 | 目标人群 | damen, メンズ, kids |
| 场景词 | 使用场景 | running, アウトドア |
| 颜色词 | 颜色 | schwarz, 黒, blue |
| 尺寸词 | 尺寸规格 | 26.5cm, XL, 32GB |
| 卖点词 | 产品特性 | waterproof, 軽量 |
| 属性词 | 其他属性 | with, für, long |

## 📁 项目结构

```
keyword-tokenizer/
├── api/                    # API 服务
├── config/                 # 配置管理
├── core/                   # 核心处理模块
│   ├── enhanced_pipeline.py    # 主处理流水线
│   ├── enhanced_tagger.py      # 标签标注器
│   ├── phrase_merger.py        # 短语合并器
│   ├── script_segmenter.py     # 脚本分段
│   ├── japanese_compound_merger.py  # 日语复合词
│   ├── spanish_normalizer.py   # 西班牙语归一化
│   └── tokenizers/             # 分词器
├── services/               # 服务层
│   ├── dictionary_manager.py   # 词典管理
│   └── ai_enhancer_v2.py       # AI 增强
├── dictionaries/           # 词典数据（1,700+ 词条）
├── dict_expansion/         # 词典扩充工具
├── scripts/                # 工具脚本
│   ├── batch_test_v2.py        # 批量测试
│   ├── import_ai_tags.py       # 导入 AI 标注
│   └── import_google_taxonomy.py  # 导入 Google 商品分类
└── docs/                   # 文档
```

## 📚 词典管理

### 当前词典规模

| 词典 | 词条数 | 说明 |
|------|--------|------|
| products | 800+ | 商品词（多语言） |
| attributes | 350+ | 属性词 |
| scenarios | 145 | 场景词 |
| brands | 110+ | 品牌词 |
| features | 83 | 卖点词 |
| audiences | 81 | 人群词 |
| colors | 68 | 颜色词 |
| 短语词典 | 263 | 固定搭配（内置） |

### 词典格式

```json
{
  "name": "商品词典",
  "entries": [
    {"word": "leggings", "confidence": 0.95},
    {"word": "シューズ", "confidence": 0.95}
  ]
}
```

### 扩充词典

```bash
# 方式一：使用词典扩充模块
python3 dict_expansion/apply_expansion.py --dry-run  # 预览
python3 dict_expansion/apply_expansion.py            # 实际导入

# 方式二：导入 Google Product Taxonomy
python3 scripts/import_google_taxonomy.py --lang en --dry-run  # 预览
python3 scripts/import_google_taxonomy.py --lang en            # 导入英语
python3 scripts/import_google_taxonomy.py --lang de            # 导入德语

# 方式三：导入 AI 标注结果
python3 scripts/import_ai_tags.py results.json --dry-run
python3 scripts/import_ai_tags.py results.json
```

## ⚙️ 配置选项

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `ANTHROPIC_API_KEY` | Claude API Key（AI 增强用） | - |
| `API_HOST` | API 服务地址 | 0.0.0.0 |
| `API_PORT` | API 服务端口 | 8000 |
| `AI_CONFIDENCE_THRESHOLD` | 触发 AI 的置信度阈值 | 0.6 |

## 🔧 开发

详细开发文档请参阅 [docs/DEVELOPER.md](docs/DEVELOPER.md)

架构设计文档请参阅 [docs/V2_ARCHITECTURE.md](docs/V2_ARCHITECTURE.md)

```bash
# 运行测试
pytest3 tests/

# 代码格式化
black .
```

## 📊 性能指标

在 9,017 条多语言关键词测试中：

| 指标 | 数值 |
|------|------|
| 总 tokens | 29,745 |
| 低置信度词 (≤0.5) | 10.4% |
| 高置信度词 (≥0.85) | 78.1% |
| 处理速度 | ~1000 条/分钟 |

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 🙏 致谢

- [jieba](https://github.com/fxsjy/jieba) - 中文分词
- [SudachiPy](https://github.com/WorksApplications/SudachiPy) - 日语分词
- [Google Product Taxonomy](https://www.google.com/basepages/producttype/taxonomy.en-US.txt) - 商品分类数据
- [Anthropic Claude](https://www.anthropic.com/) - AI 增强
