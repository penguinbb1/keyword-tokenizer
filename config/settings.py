"""
项目配置管理
"""
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""
    
    # API配置
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True
    
    # AI服务配置
    anthropic_api_key: Optional[str] = None
    ai_timeout_seconds: int = 60  # AI API 超时时间
    
    # 路径配置
    base_path: Path = Path(__file__).parent.parent
    dictionary_path: Path = base_path / "dictionaries"
    
    # 性能配置
    max_batch_size: int = 100
    ai_confidence_threshold: float = 0.6  # 低于此值触发AI
    
    # 日志配置
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 全局配置实例
settings = Settings()
