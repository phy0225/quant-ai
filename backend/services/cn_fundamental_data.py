"""
A股基本面数据 — AKShare
financial_abstract 返回格式：列=[选项, 指标, 20250930, 20250630...]
需要转置后按指标名提取数据
"""
from __future__ import annotations
import json
from datetime import datetime, timedelta
from pathlib import Path
from services.cn_market_data import _normalize_symbol

CACHE_DIR = Path(__file__).parent.parent / ".cn_fundamental_cache"
CACHE_TTL_DAYS = 7


def _cache_path(symbol: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / f"{symbol}_fundamental.json"


def _is_cache_valid(symbol: str) -> bool:
    p = _cache_path(symbol)
    if not p.exists():
        return False
    return datetime.now() - datetime.fromtimestamp(p.stat().st_mtime) < timedelta(days=CACHE_TTL_DAYS)


def _safe_float(val) -> float | None:
    try:
        v = float(str(val).replace("%", "").replace(",", "").replace(" ", "").strip())
        return None if v != v else round(v, 4)
    except (TypeError, ValueError):
        return None


def _find_value_in_transposed(df, keyword: str) -> str | None:
    """
    financial_abstract 格式：
      列 = ['选项', '指标', '20250930', '20250630', ...]
      每行的 '指标' 列是指标名，后面的日期列是值
    找到包含 keyword 的指标行，返回最新期（第一个日期列）的值
    """
    import pandas as pd

    # 找到指标名所在列
    name_col = next((c for c in df.columns if "指标" in str(c) or "项目" in str(c)), None)
    if name_col is None and len(df.columns) >= 2:
        name_col = df.columns[1]  # fallback 第2列
    if name_col is None:
        return None

    # 找日期列（8位数字）
    date_cols = [c for c in df.columns if str(c).isdigit() and len(str(c)) == 8]
    if not date_cols:
        # 尝试找其他数值列
        date_cols = [c for c in df.columns if c not in ("选项", "指标", "项目", name_col)]

    if not date_cols:
        return None

    # 找包含 keyword 的行
    for _, row in df.iterrows():
        indicator_name = str(row.get(name_col, ""))
        if keyword in indicator_name:
            # 取最新期（date_cols 已按降序排列，取第一个有效值）
            for dc in date_cols[:3]:
                v = str(row.get(dc, "")).strip()
                if v and v not in ("nan", "None", "--", ""):
                    return v
    return None


def _fetch_fundamentals_sync(symbol: str) -> dict | None:
    symbol = _normalize_symbol(symbol)

    if _is_cache_valid(symbol):
        try:
            data = json.loads(_cache_path(symbol).read_text())
            print(f"[cn_fundamental] cache hit: {symbol}")
            return data
        except Exception:
            pass

    try:
        import akshare as ak
    except ImportError:
        print("[cn_fundamental] akshare 未安装")
        return None

    data = {"symbol": symbol, "fetched_at": datetime.now().isoformat()}

    # ── 1. 实时估值（PE / PB / 市值）最稳定 ──────────────────────────
    try:
        spot = ak.stock_zh_a_spot_em()
        row = spot[spot["代码"] == symbol]
        if not row.empty:
            r = row.iloc[0]
            for col in r.index:
                v = r[col]
                if "名称" in col:                           data["stock_name"] = str(v)
                elif "市盈率" in col and "动" in col:       data["pe_ratio"] = _safe_float(v)
                elif "市盈率" in col and not data.get("pe_ratio"): data["pe_ratio"] = _safe_float(v)
                elif "市净率" in col:                       data["pb_ratio"] = _safe_float(v)
                elif "总市值" in col:
                    f = _safe_float(v)
                    data["total_mv"] = round(f / 1e8, 2) if f else None
                elif "换手率" in col:                       data["turnover_rate"] = _safe_float(v)
            print(f"[cn_fundamental] 估值 OK: PE={data.get('pe_ratio')} PB={data.get('pb_ratio')}")
    except Exception as e:
        print(f"[cn_fundamental] 实时估值失败: {e}")

    # ── 2. 财务摘要（转置格式处理）────────────────────────────────────
    for kwargs in [{"symbol": symbol}, {"stock": symbol}]:
        try:
            df = ak.stock_financial_abstract(**kwargs)
            if df is None or df.empty:
                continue

            # 提取各指标（模糊关键词匹配）
            mappings = [
                ("revenue_yoy",    ["营业总收入同比", "营业收入同比", "收入增长"]),
                ("net_profit_yoy", ["净利润同比", "归母净利润增长", "净利润增长"]),
                ("roe",            ["净资产收益率", "ROE"]),
                ("gross_margin",   ["销售毛利率", "毛利率"]),
                ("net_margin",     ["销售净利率", "净利率"]),
                ("debt_ratio",     ["资产负债率"]),
                ("eps",            ["基本每股收益", "每股收益"]),
                ("report_period",  ["报告期", "报告日期"]),
            ]

            for key, keywords in mappings:
                for kw in keywords:
                    v = _find_value_in_transposed(df, kw)
                    if v:
                        data[key] = v
                        break

            got = [k for k, _ in mappings if data.get(k)]
            print(f"[cn_fundamental] financial_abstract OK, 提取: {got}")
            break

        except Exception as e:
            print(f"[cn_fundamental] financial_abstract{kwargs}: {type(e).__name__}: {str(e)[:80]}")

    # ── 3. 补充资产负债率（stock_zh_a_indicator）──────────────────────
    if not data.get("debt_ratio"):
        try:
            for kw in [{"symbol": symbol, "timeframe": "全部"}, {"symbol": symbol}]:
                try:
                    df = ak.stock_zh_a_indicator(**kw)
                    if df is None or df.empty:
                        continue
                    # 这个接口是正常宽表，每列是一个指标
                    row = df.iloc[0]
                    for col in row.index:
                        v = str(row[col]).strip()
                        if not v or v in ("nan", "None"):
                            continue
                        if "资产负债率" in str(col):
                            data["debt_ratio"] = v
                        elif ("每股收益" in str(col) or str(col) == "eps") and not data.get("eps"):
                            data["eps"] = v
                        elif "净资产收益率" in str(col) and not data.get("roe"):
                            data["roe"] = v
                    break
                except TypeError:
                    continue
        except Exception as e:
            print(f"[cn_fundamental] indicator 失败: {e}")

    # ── 最终检查 ────────────────────────────────────────────────────
    useful = ["pe_ratio", "pb_ratio", "total_mv",
              "revenue_yoy", "net_profit_yoy", "roe", "gross_margin", "debt_ratio"]
    if not any(data.get(k) for k in useful):
        print(f"[cn_fundamental] {symbol} 无任何有效财务数据")
        return None

    try:
        _cache_path(symbol).write_text(json.dumps(data, ensure_ascii=False))
    except Exception:
        pass

    got_keys = [k for k in useful if data.get(k)]
    print(f"[cn_fundamental] {symbol} 成功: {got_keys}")
    return data


async def fetch_cn_fundamentals(symbol: str) -> dict | None:
    import asyncio
    return await asyncio.to_thread(_fetch_fundamentals_sync, symbol)


def format_for_prompt(data: dict) -> str:
    name   = data.get("stock_name", data["symbol"])
    period = data.get("report_period", "TTM")
    lines  = [f"📊 {name}（{data['symbol']}）基本面数据（AKShare，报告期：{period}）"]
    if data.get("pe_ratio"):        lines.append(f"• 市盈率（PE动态）：{data['pe_ratio']}x")
    if data.get("pb_ratio"):        lines.append(f"• 市净率（PB）：{data['pb_ratio']}x")
    if data.get("total_mv"):        lines.append(f"• 总市值：{data['total_mv']} 亿元")
    if data.get("revenue_yoy"):     lines.append(f"• 营收同比增速：{data['revenue_yoy']}")
    if data.get("net_profit_yoy"):  lines.append(f"• 净利润同比增速：{data['net_profit_yoy']}")
    if data.get("roe"):             lines.append(f"• ROE：{data['roe']}")
    if data.get("gross_margin"):    lines.append(f"• 毛利率：{data['gross_margin']}")
    if data.get("net_margin"):      lines.append(f"• 净利率：{data['net_margin']}")
    if data.get("debt_ratio"):      lines.append(f"• 资产负债率：{data['debt_ratio']}")
    if data.get("eps"):             lines.append(f"• 每股收益（EPS）：{data['eps']} 元")
    return "\n".join(lines)