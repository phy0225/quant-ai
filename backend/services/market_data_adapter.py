"""
市场数据适配器层 — 统一接口，屏蔽底层数据源差异

Agent 只调用这里的函数，永远不直接 import akshare 或 tushare。
切换数据源时只需修改 DATA_PROVIDER 配置，或实现新的 provider。

支持的 provider：
  - akshare（默认，免费，无需注册）
  - tushare（稳定，需注册获取 token）
  - mock（开发测试用，返回随机数据）
"""
from __future__ import annotations
import json
from datetime import datetime, timedelta
from pathlib import Path
from config import settings

# ─── 统一数据结构（所有 provider 必须返回这个格式）──────────────────

class StockSnapshot:
    """行情快照 — 统一格式，与数据源无关"""
    def __init__(self, data: dict):
        self._d = data

    # 必须字段
    @property
    def symbol(self) -> str:           return self._d["symbol"]
    @property
    def current_price(self) -> float:  return float(self._d["current_price"])
    @property
    def change_pct(self) -> float:     return float(self._d.get("change_pct", 0))
    @property
    def rsi(self) -> float:            return float(self._d.get("rsi", 50))
    @property
    def macd(self) -> float:           return float(self._d.get("macd", 0))
    @property
    def macd_signal(self) -> float:    return float(self._d.get("macd_signal", 0))
    @property
    def ma5(self) -> float:            return float(self._d.get("ma5", self.current_price))
    @property
    def ma10(self) -> float:           return float(self._d.get("ma10", self.current_price))
    @property
    def ma20(self) -> float:           return float(self._d.get("ma20", self.current_price))
    @property
    def ma60(self) -> float:           return float(self._d.get("ma60", self.current_price))
    @property
    def bb_upper(self) -> float:       return float(self._d.get("bb_upper", self.current_price * 1.02))
    @property
    def bb_lower(self) -> float:       return float(self._d.get("bb_lower", self.current_price * 0.98))
    @property
    def volume_ratio(self) -> float:   return float(self._d.get("volume_ratio", 1.0))
    @property
    def trend(self) -> str:            return self._d.get("trend", "震荡")
    @property
    def high_52w(self) -> float:       return float(self._d.get("high_52w", self.current_price))
    @property
    def low_52w(self) -> float:        return float(self._d.get("low_52w", self.current_price))
    @property
    def fetched_at(self) -> str:       return self._d.get("fetched_at", datetime.now().isoformat())

    def to_dict(self) -> dict:
        return self._d


class FundamentalsData:
    """基本面数据 — 统一格式"""
    def __init__(self, data: dict):
        self._d = data

    @property
    def symbol(self) -> str:            return self._d["symbol"]
    @property
    def stock_name(self) -> str:        return self._d.get("stock_name", self._d["symbol"])
    @property
    def pe_ratio(self) -> float | None: return self._d.get("pe_ratio")
    @property
    def pb_ratio(self) -> float | None: return self._d.get("pb_ratio")
    @property
    def revenue_yoy(self) -> str:       return self._d.get("revenue_yoy", "")
    @property
    def net_profit_yoy(self) -> str:    return self._d.get("net_profit_yoy", "")
    @property
    def roe(self) -> str:               return self._d.get("roe", "")
    @property
    def gross_margin(self) -> str:      return self._d.get("gross_margin", "")
    @property
    def debt_ratio(self) -> str:        return self._d.get("debt_ratio", "")
    @property
    def total_mv(self) -> float | None: return self._d.get("total_mv")
    @property
    def report_period(self) -> str:     return self._d.get("report_period", "TTM")
    @property
    def data_source(self) -> str:       return self._d.get("data_source", "unknown")

    def to_dict(self) -> dict:
        return self._d

    def to_prompt_text(self) -> str:
        lines = [f"📊 {self.stock_name}（{self.symbol}）基本面数据（来源：{self.data_source}，报告期：{self.report_period}）"]
        if self.pe_ratio:    lines.append(f"• 市盈率（PE）：{self.pe_ratio}x")
        if self.pb_ratio:    lines.append(f"• 市净率（PB）：{self.pb_ratio}x")
        if self.total_mv:    lines.append(f"• 总市值：{self.total_mv} 亿元")
        if self.revenue_yoy: lines.append(f"• 营收同比增速：{self.revenue_yoy}")
        if self.net_profit_yoy: lines.append(f"• 净利润同比增速：{self.net_profit_yoy}")
        if self.roe:         lines.append(f"• ROE：{self.roe}")
        if self.gross_margin: lines.append(f"• 毛利率：{self.gross_margin}")
        if self.debt_ratio:  lines.append(f"• 资产负债率：{self.debt_ratio}")
        return "\n".join(lines)


class NewsItem:
    """新闻条目 — 统一格式"""
    def __init__(self, data: dict):
        self._d = data

    @property
    def title(self) -> str:     return self._d.get("title", "")
    @property
    def source(self) -> str:    return self._d.get("source", "")
    @property
    def published(self) -> str: return self._d.get("published", "")
    @property
    def content(self) -> str:   return self._d.get("content", "")

    def to_dict(self) -> dict:
        return self._d


class SentimentData:
    """情绪数据 — 统一格式"""
    def __init__(self, data: dict):
        self._d = data

    @property
    def score(self) -> float | None:        return self._d.get("score")
    @property
    def north_flow(self) -> float | None:   return self._d.get("north_flow")
    @property
    def limit_up_count(self) -> int:        return int(self._d.get("limit_up_count", 0))
    @property
    def limit_down_count(self) -> int:      return int(self._d.get("limit_down_count", 0))
    @property
    def sentiment_ratio(self) -> float:     return float(self._d.get("sentiment_ratio", 0.5))
    @property
    def data_source(self) -> str:           return self._d.get("data_source", "unknown")

    def to_dict(self) -> dict:
        return self._d


# ─── Provider 基类（接口契约）────────────────────────────────────────

class BaseDataProvider:
    """
    所有数据源 provider 必须实现这个接口。
    切换 Tushare / Wind 只需继承这个类，实现下面的方法。
    """
    provider_name: str = "base"

    async def get_snapshot(self, symbol: str) -> StockSnapshot | None:
        raise NotImplementedError

    async def get_fundamentals(self, symbol: str) -> FundamentalsData | None:
        raise NotImplementedError

    async def get_news(self, symbol: str, limit: int = 8) -> list[NewsItem]:
        raise NotImplementedError

    async def get_sentiment(self, symbol: str, rsi: float, vol_ratio: float) -> SentimentData:
        raise NotImplementedError

    async def get_market_telegraph(self) -> list[dict]:
        """宏观快讯（可选实现，不强制）"""
        return []


# ─── AKShare Provider ────────────────────────────────────────────────

class AKShareProvider(BaseDataProvider):
    provider_name = "akshare"

    async def get_snapshot(self, symbol: str) -> StockSnapshot | None:
        from services.cn_market_data import fetch_cn_snapshot
        data = await fetch_cn_snapshot(symbol)
        if not data:
            return None
        data["data_source"] = "AKShare"
        return StockSnapshot(data)

    async def get_fundamentals(self, symbol: str) -> FundamentalsData | None:
        from services.cn_fundamental_data import fetch_cn_fundamentals
        data = await fetch_cn_fundamentals(symbol)
        if not data:
            return None
        data["data_source"] = "AKShare"
        return FundamentalsData(data)

    async def get_news(self, symbol: str, limit: int = 8) -> list[NewsItem]:
        from services.cn_news_data import fetch_cn_news
        raw = await fetch_cn_news(symbol, limit)
        return [NewsItem(n) for n in raw]

    async def get_sentiment(self, symbol: str, rsi: float, vol_ratio: float) -> SentimentData:
        from services.cn_sentiment_data import (
            fetch_stock_comment, fetch_north_flow, fetch_market_breadth
        )
        comment = await fetch_stock_comment(symbol)
        north   = await fetch_north_flow()
        breadth = await fetch_market_breadth()
        return SentimentData({
            "score":             comment.get("score") if comment else None,
            "north_flow":        north.get("total_flow") if north else None,
            "limit_up_count":    breadth.get("limit_up_count", 0) if breadth else 0,
            "limit_down_count":  breadth.get("limit_down_count", 0) if breadth else 0,
            "sentiment_ratio":   breadth.get("sentiment_ratio", 0.5) if breadth else 0.5,
            "data_source":       "AKShare（东财评分+北向资金+涨跌停）",
        })

    async def get_market_telegraph(self) -> list[dict]:
        from services.cn_news_data import fetch_cls_telegraph
        return await fetch_cls_telegraph()


# ─── Tushare Provider（以后需要时填充实现）───────────────────────────

class TushareProvider(BaseDataProvider):
    """
    Tushare Pro 数据源。
    注册地址：https://tushare.pro
    .env 增加：TUSHARE_TOKEN=your_token
    
    接口文档：https://tushare.pro/document/2
    """
    provider_name = "tushare"

    def __init__(self):
        token = getattr(settings, "TUSHARE_TOKEN", "")
        if not token:
            raise ValueError("TUSHARE_TOKEN 未配置，请在 .env 中设置")
        import tushare as ts
        ts.set_token(token)
        self._pro = ts.pro_api()

    async def get_snapshot(self, symbol: str) -> StockSnapshot | None:
        """
        用 Tushare 实现行情快照
        Tushare 股票代码格式：000001.SZ / 600519.SH
        """
        ts_code = _to_tushare_code(symbol)
        try:
            # 日线行情
            df = self._pro.daily(ts_code=ts_code, limit=70)
            if df is None or df.empty:
                return None
            df = df.sort_values("trade_date")
            closes = df["close"].tolist()
            volumes = df["vol"].tolist()

            # TODO: 复用 cn_market_data 里的技术指标计算函数
            # 这里暂时返回基础字段，以后补充指标计算
            current_price = closes[-1]
            prev_close    = closes[-2] if len(closes) > 1 else current_price
            change_pct    = round((current_price - prev_close) / prev_close * 100, 2)

            return StockSnapshot({
                "symbol":        symbol,
                "current_price": current_price,
                "change_pct":    change_pct,
                "rsi":           50.0,   # TODO: 计算真实 RSI
                "macd":          0.0,    # TODO: 计算真实 MACD
                "macd_signal":   0.0,
                "ma20":          sum(closes[-20:]) / min(20, len(closes)),
                "ma60":          sum(closes[-60:]) / min(60, len(closes)),
                "volume_ratio":  1.0,    # TODO: 计算真实量比
                "trend":         "未知",
                "data_source":   "Tushare",
                "fetched_at":    datetime.now().isoformat(),
            })
        except Exception as e:
            print(f"[Tushare] get_snapshot failed for {symbol}: {e}")
            return None

    async def get_fundamentals(self, symbol: str) -> FundamentalsData | None:
        """
        用 Tushare 实现基本面数据
        参考接口：pro.daily_basic(), pro.income(), pro.balancesheet()
        """
        ts_code = _to_tushare_code(symbol)
        try:
            df = self._pro.daily_basic(ts_code=ts_code, limit=1,
                fields="ts_code,pe_ttm,pb,total_mv,circ_mv")
            if df is None or df.empty:
                return None
            r = df.iloc[0]
            return FundamentalsData({
                "symbol":      symbol,
                "pe_ratio":    round(float(r.get("pe_ttm") or 0), 2),
                "pb_ratio":    round(float(r.get("pb") or 0), 2),
                "total_mv":    round(float(r.get("total_mv") or 0) / 10000, 2),  # 万元→亿元
                "data_source": "Tushare Pro",
                "report_period": "TTM",
            })
        except Exception as e:
            print(f"[Tushare] get_fundamentals failed: {e}")
            return None

    async def get_news(self, symbol: str, limit: int = 8) -> list[NewsItem]:
        """Tushare 新闻接口（需积分）"""
        # TODO: 实现 self._pro.news() 调用
        # 参考：https://tushare.pro/document/2?doc_id=198
        return []

    async def get_sentiment(self, symbol: str, rsi: float, vol_ratio: float) -> SentimentData:
        """Tushare 暂无专门情绪接口，返回基础字段"""
        return SentimentData({
            "score": None,
            "north_flow": None,
            "limit_up_count": 0,
            "limit_down_count": 0,
            "sentiment_ratio": 0.5,
            "data_source": "Tushare（情绪数据待实现）",
        })


# ─── Mock Provider（开发测试用）──────────────────────────────────────

class MockProvider(BaseDataProvider):
    """返回随机但合理的模拟数据，用于开发和单元测试"""
    provider_name = "mock"

    async def get_snapshot(self, symbol: str) -> StockSnapshot | None:
        import random
        price = random.uniform(10, 200)
        return StockSnapshot({
            "symbol": symbol,
            "current_price": round(price, 2),
            "change_pct": round(random.uniform(-5, 5), 2),
            "rsi": round(random.uniform(25, 75), 1),
            "macd": round(random.uniform(-1, 1), 4),
            "macd_signal": round(random.uniform(-1, 1), 4),
            "ma5":  round(price * random.uniform(0.98, 1.02), 2),
            "ma10": round(price * random.uniform(0.97, 1.03), 2),
            "ma20": round(price * random.uniform(0.95, 1.05), 2),
            "ma60": round(price * random.uniform(0.90, 1.10), 2),
            "bb_upper": round(price * 1.05, 2),
            "bb_lower": round(price * 0.95, 2),
            "volume_ratio": round(random.uniform(0.5, 2.5), 2),
            "trend": random.choice(["多头", "空头", "震荡"]),
            "high_52w": round(price * 1.30, 2),
            "low_52w": round(price * 0.70, 2),
            "data_source": "Mock",
            "fetched_at": datetime.now().isoformat(),
        })

    async def get_fundamentals(self, symbol: str) -> FundamentalsData | None:
        import random
        return FundamentalsData({
            "symbol": symbol, "stock_name": f"模拟股票{symbol}",
            "pe_ratio": round(random.uniform(10, 50), 1),
            "pb_ratio": round(random.uniform(1, 5), 2),
            "total_mv": round(random.uniform(100, 5000), 1),
            "revenue_yoy": f"{random.uniform(-10, 30):.1f}%",
            "net_profit_yoy": f"{random.uniform(-20, 40):.1f}%",
            "roe": f"{random.uniform(5, 25):.1f}%",
            "gross_margin": f"{random.uniform(20, 60):.1f}%",
            "debt_ratio": f"{random.uniform(20, 70):.1f}%",
            "report_period": "2024-Q3", "data_source": "Mock",
        })

    async def get_news(self, symbol: str, limit: int = 8) -> list[NewsItem]:
        return [NewsItem({
            "title": f"{symbol} 模拟新闻标题 {i+1}",
            "source": "模拟数据", "published": datetime.now().strftime("%Y-%m-%d"),
            "content": "这是模拟新闻内容，实际接入数据源后会显示真实新闻。",
        }) for i in range(3)]

    async def get_sentiment(self, symbol: str, rsi: float, vol_ratio: float) -> SentimentData:
        import random
        return SentimentData({
            "score": round(random.uniform(40, 80), 1),
            "north_flow": round(random.uniform(-50, 80), 1),
            "limit_up_count": random.randint(20, 150),
            "limit_down_count": random.randint(5, 30),
            "sentiment_ratio": round(random.uniform(0.4, 0.8), 2),
            "data_source": "Mock",
        })


# ─── 工具函数 ─────────────────────────────────────────────────────────

def _to_tushare_code(symbol: str) -> str:
    """A 股代码转 Tushare 格式：000001 → 000001.SZ"""
    if symbol.startswith(("6", "9")):
        return f"{symbol}.SH"
    return f"{symbol}.SZ"


# ─── Provider 工厂（核心：改这里切换数据源）──────────────────────────

def _create_provider() -> BaseDataProvider:
    provider_name = getattr(settings, "DATA_PROVIDER", "akshare").lower()
    if provider_name == "tushare":
        return TushareProvider()
    if provider_name == "mock":
        return MockProvider()
    return AKShareProvider()  # 默认 AKShare


# 全局单例，整个应用只创建一次
_provider: BaseDataProvider | None = None

def get_provider() -> BaseDataProvider:
    global _provider
    if _provider is None:
        _provider = _create_provider()
        print(f"[data_adapter] 使用数据源：{_provider.provider_name}")
    return _provider


# ─── 对外暴露的统一接口（Agent 只调用这些）──────────────────────────

async def get_snapshot(symbol: str) -> StockSnapshot | None:
    return await get_provider().get_snapshot(symbol)

async def get_fundamentals(symbol: str) -> FundamentalsData | None:
    return await get_provider().get_fundamentals(symbol)

async def get_news(symbol: str, limit: int = 8) -> list[NewsItem]:
    return await get_provider().get_news(symbol, limit)

async def get_sentiment(symbol: str, rsi: float = 50, vol_ratio: float = 1.0) -> SentimentData:
    return await get_provider().get_sentiment(symbol, rsi, vol_ratio)

async def get_market_telegraph() -> list[dict]:
    return await get_provider().get_market_telegraph()
