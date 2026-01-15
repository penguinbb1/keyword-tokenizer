"""
分词相关 API 路由
"""
from fastapi import APIRouter, HTTPException
from typing import List

from api.models import (
    TokenizeRequest, 
    BatchTokenizeRequest,
    TokenizeResponse, 
    BatchTokenizeResponse
)
from core.enhanced_pipeline import EnhancedPipeline as TokenizePipeline

router = APIRouter(prefix="/api/v1", tags=["tokenize"])

# 全局 pipeline 实例（在 main.py 中初始化）
pipeline: TokenizePipeline = None


def set_pipeline(p: TokenizePipeline):
    """设置 pipeline 实例"""
    global pipeline
    pipeline = p


@router.post("/tokenize", response_model=TokenizeResponse)
async def tokenize_single(request: TokenizeRequest) -> TokenizeResponse:
    """
    处理单个关键词
    
    - 智能切词，保持固定搭配完整性
    - 标注8种标签类型
    - 返回置信度评分
    """
    if pipeline is None:
        raise HTTPException(status_code=500, detail="Pipeline not initialized")
    
    try:
        result = await pipeline.process(request.keyword)
        return TokenizeResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tokenize/batch", response_model=BatchTokenizeResponse)
async def tokenize_batch(request: BatchTokenizeRequest) -> BatchTokenizeResponse:
    """
    批量处理关键词
    
    - 支持最多100个关键词
    - 批量调用AI可节省token
    """
    if pipeline is None:
        raise HTTPException(status_code=500, detail="Pipeline not initialized")
    
    try:
        results = []
        success_count = 0
        
        for keyword in request.keywords:
            try:
                result = await pipeline.process(
                    keyword, 
                    use_ai=request.use_ai_enhancement
                )
                results.append(TokenizeResponse(**result))
                success_count += 1
            except Exception as e:
                # 单个失败不影响整体
                results.append(TokenizeResponse(
                    original_keyword=keyword,
                    tokens=[],
                    tagged_tokens=[],
                    tag_summary={}
                ))
        
        return BatchTokenizeResponse(
            results=results,
            total=len(request.keywords),
            success_count=success_count
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
