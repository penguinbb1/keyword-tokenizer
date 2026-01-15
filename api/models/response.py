"""
API 响应模型定义
"""
from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class TagInfo(BaseModel):
    """标签信息"""
    tag: str = Field(..., description="标签类型")
    confidence: float = Field(..., description="置信度", ge=0.0, le=1.0)


class TokenInfo(BaseModel):
    """分词结果中的单个token"""
    token: str = Field(..., description="词语")
    tags: List[str] = Field(..., description="标签列表")
    confidence: float = Field(..., description="置信度")


class TokenizeResponse(BaseModel):
    """分词响应"""
    original_keyword: str = Field(..., description="原始关键词")
    tokens: List[str] = Field(..., description="分词结果列表")
    tagged_tokens: List[TokenInfo] = Field(..., description="带标签的分词结果")
    tag_summary: Dict[str, List[str]] = Field(..., description="按标签分类汇总")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "original_keyword": "New Balance跑步鞋男士黑色10.5码",
                    "tokens": ["new balance", "跑步鞋", "男士", "黑色", "10.5码"],
                    "tagged_tokens": [
                        {"token": "new balance", "tags": ["品牌词"], "confidence": 0.95},
                        {"token": "跑步鞋", "tags": ["商品词"], "confidence": 0.90},
                        {"token": "男士", "tags": ["人群词"], "confidence": 0.95},
                        {"token": "黑色", "tags": ["颜色词"], "confidence": 0.98},
                        {"token": "10.5码", "tags": ["尺寸词"], "confidence": 0.99}
                    ],
                    "tag_summary": {
                        "品牌词": ["new balance"],
                        "商品词": ["跑步鞋"],
                        "人群词": ["男士"],
                        "颜色词": ["黑色"],
                        "尺寸词": ["10.5码"]
                    }
                }
            ]
        }
    }


class BatchTokenizeResponse(BaseModel):
    """批量分词响应"""
    results: List[TokenizeResponse] = Field(..., description="分词结果列表")
    total: int = Field(..., description="处理总数")
    success_count: int = Field(..., description="成功数量")


class ErrorResponse(BaseModel):
    """错误响应"""
    error: str = Field(..., description="错误信息")
    detail: Optional[str] = Field(None, description="详细信息")


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="版本号")
    dictionaries_loaded: bool = Field(..., description="词典是否加载")
