"""
关键词切词与标签标注服务 - API 入口
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from api.routes import tokenize_router, dictionary_router, set_pipeline, set_dict_manager
from api.models import HealthResponse
from core.pipeline import TokenizePipeline
from services.dictionary_manager import DictionaryManager


# 全局实例
pipeline: TokenizePipeline = None
dict_manager: DictionaryManager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global pipeline, dict_manager
    
    # 启动时初始化
    print("🚀 正在初始化服务...")
    
    # 初始化词典管理器
    dict_manager = DictionaryManager(settings.dictionary_path)
    dict_manager.load_all()
    print(f"📚 词典加载完成: {dict_manager.get_stats()}")
    
    # 初始化处理流水线
    pipeline = TokenizePipeline(dict_manager)
    print("⚙️ 处理流水线初始化完成")
    
    # 设置路由依赖
    set_pipeline(pipeline)
    set_dict_manager(dict_manager)
    
    print("✅ 服务启动完成!")
    
    yield
    
    # 关闭时清理
    print("👋 服务关闭中...")


# 创建 FastAPI 应用
app = FastAPI(
    title="关键词切词与标签标注服务",
    description="""
    ## 功能
    - 智能切词：对输入的关键词进行分词，特别处理固定搭配
    - 标签标注：识别关键词中的各类词性并打上相应标签
    
    ## 支持的标签类型
    - 品牌词、商品词、人群词、场景词
    - 颜色词、尺寸词、卖点词、属性词
    
    ## 支持的语言
    中文、英语、日语、德语、法语、西班牙语
    """,
    version="1.0.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(tokenize_router)
app.include_router(dictionary_router)


@app.get("/", tags=["health"])
async def root():
    """根路径"""
    return {"message": "关键词切词与标签标注服务", "docs": "/docs"}


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    """健康检查"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        dictionaries_loaded=dict_manager is not None and dict_manager.is_loaded()
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )
