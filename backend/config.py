from typing import List

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./quant_ai.db"
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "quant_user"
    DB_PASSWORD: str = ""
    DB_NAME: str = "quant_ai"
    FEATURE_PLATFORM_MODE: str = "api"
    FEATURE_PLATFORM_API_URL: str = ""
    FEATURE_PLATFORM_API_KEY: str = ""
    FEATURE_PLATFORM_DB_URL: str = ""
    TRADING_CALENDAR_CACHE_DAYS: int = 30
    APSCHEDULER_ENABLED: bool = False

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
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def use_mock(self) -> bool:
        return not bool(self.LLM_API_KEY.strip())

    @property
    def mysql_dsn(self) -> str:
        password = f":{self.DB_PASSWORD}" if self.DB_PASSWORD else ""
        return f"mysql+asyncmy://{self.DB_USER}{password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
