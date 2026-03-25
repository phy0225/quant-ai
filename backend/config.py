from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./quant_ai.db"

    # LLM 配置
    LLM_API_URL: str = ""
    LLM_API_KEY: str = ""
    LLM_MODEL:   str = "gpt-4o"

    # 数据源选择（切换数据源只改这一行）
    # 可选值：akshare（默认）| tushare | mock
    DATA_PROVIDER: str = "akshare"

    # Tushare Token（DATA_PROVIDER=tushare 时必填）
    # 注册地址：https://tushare.pro
    TUSHARE_TOKEN: str = ""

    CORS_ORIGINS: str = "http://localhost:5173"
    APP_ENV: str = "development"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    @property
    def use_mock(self) -> bool:
        return not bool(self.LLM_API_KEY.strip())

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
