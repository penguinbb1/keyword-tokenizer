#!/usr/bin/env python3

"""
启动服务
"""
import uvicorn
from config import settings

if __name__ == "__main__":
    print("🚀 启动关键词切词与标签标注服务...")
    print(f"📍 API文档: http://localhost:{settings.api_port}/docs")
    
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )
