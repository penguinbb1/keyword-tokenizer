"""
API 请求模型定义
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class TokenizeRequest(BaseModel):
    """单条分词请求"""
    keyword: str = Field(..., description="待处理的关键词/标题", min_length=1, max_length=500)
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {"keyword": "New Balance跑步鞋男士黑色10.5码"}
            ]
        }
    }


class BatchTokenizeRequest(BaseModel):
    """批量分词请求"""
    keywords: List[str] = Field(
        ..., 
        description="待处理的关键词列表",
        min_length=1,
        max_length=100
    )
    use_ai_enhancement: bool = Field(
        default=True,
        description="是否启用AI增强处理未知词"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "keywords": [
                        "New Balance跑步鞋男士黑色10.5码",
                        "Apple iPhone 15 Pro 256GB 深空黑"
                    ],
                    "use_ai_enhancement": True
                }
            ]
        }
    }


class DictionaryEntryRequest(BaseModel):
    """添加词典条目请求"""
    word: str = Field(..., description="词语", min_length=1)
    tag: str = Field(..., description="标签类型")
    language: str = Field(default="global", description="语言代码")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="置信度")
