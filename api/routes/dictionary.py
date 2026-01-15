"""
词典管理 API 路由
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, List, Optional

from api.models import DictionaryEntryRequest
from services.dictionary_manager import DictionaryManager

router = APIRouter(prefix="/api/v1/dictionary", tags=["dictionary"])

# 全局词典管理器实例
dict_manager: DictionaryManager = None


def set_dict_manager(dm: DictionaryManager):
    """设置词典管理器实例"""
    global dict_manager
    dict_manager = dm


@router.get("/stats")
async def get_dictionary_stats() -> Dict:
    """获取词典统计信息"""
    if dict_manager is None:
        raise HTTPException(status_code=500, detail="Dictionary manager not initialized")
    
    return dict_manager.get_stats()


@router.get("/search")
async def search_dictionary(
    word: str,
    tag: Optional[str] = None,
    language: Optional[str] = None
) -> Dict:
    """搜索词典"""
    if dict_manager is None:
        raise HTTPException(status_code=500, detail="Dictionary manager not initialized")
    
    return dict_manager.search(word, tag=tag, language=language)


@router.post("/add")
async def add_dictionary_entry(request: DictionaryEntryRequest) -> Dict:
    """添加词典条目"""
    if dict_manager is None:
        raise HTTPException(status_code=500, detail="Dictionary manager not initialized")
    
    try:
        dict_manager.add_entry(
            word=request.word,
            tag=request.tag,
            language=request.language,
            confidence=request.confidence
        )
        return {"status": "success", "message": f"Added '{request.word}' to {request.tag}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/remove")
async def remove_dictionary_entry(word: str, tag: str) -> Dict:
    """删除词典条目"""
    if dict_manager is None:
        raise HTTPException(status_code=500, detail="Dictionary manager not initialized")
    
    try:
        dict_manager.remove_entry(word=word, tag=tag)
        return {"status": "success", "message": f"Removed '{word}' from {tag}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reload")
async def reload_dictionaries() -> Dict:
    """重新加载所有词典"""
    if dict_manager is None:
        raise HTTPException(status_code=500, detail="Dictionary manager not initialized")
    
    try:
        dict_manager.reload_all()
        return {"status": "success", "message": "All dictionaries reloaded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
