"""
持仓上下文生成器 — 为各 Agent 提供持仓相关的分析背景

从 context["current_portfolio"] 里提取完整持仓信息，
格式化成自然语言供 LLM 分析时参考。
"""
from __future__ import annotations


def get_holding(context: dict, symbol: str) -> dict | None:
    """获取指定标的的持仓信息，兼容旧格式（只有 weight）和新格式（完整字段）"""
    portfolio = context.get("current_portfolio") or {}
    holding = portfolio.get(symbol)
    if holding is None:
        return None
    # 旧格式：直接是 float
    if isinstance(holding, (int, float)):
        return {"weight": float(holding)}
    return holding


def format_holding_context(holding: dict | None, symbol: str) -> str:
    """把持仓信息格式化为 LLM 可读的文字"""
    if not holding:
        return f"当前未持有 {symbol}。"

    weight = holding.get("weight", 0)
    cost   = holding.get("cost_price")
    curr   = holding.get("current_price")
    pnl    = holding.get("pnl_pct")
    qty    = holding.get("quantity")
    mv     = holding.get("market_value")
    name   = holding.get("symbol_name", symbol)

    lines = [f"📋 {name}（{symbol}）当前持仓情况："]
    lines.append(f"• 仓位权重：{weight*100:.1f}%")
    if cost:
        lines.append(f"• 持仓成本价：¥{cost:.2f}")
    if curr:
        lines.append(f"• 最新价格：¥{curr:.2f}")
    if pnl is not None:
        pnl_pct = pnl * 100 if abs(pnl) < 1 else pnl  # 兼容小数和百分比两种格式
        emoji = "📈" if pnl_pct > 0 else "📉"
        lines.append(f"• 浮动盈亏：{emoji} {pnl_pct:+.2f}%")
        # 盈亏判断提示
        if pnl_pct >= 50:
            lines.append("  → 大幅浮盈，需考虑止盈风险")
        elif pnl_pct >= 20:
            lines.append("  → 有较大浮盈，注意保护利润")
        elif pnl_pct <= -30:
            lines.append("  → 大幅亏损，需重点评估是否止损")
        elif pnl_pct <= -15:
            lines.append("  → 有较大浮亏，需审慎评估后续策略")
    if qty:
        lines.append(f"• 持股数量：{qty:,} 股")
    if mv:
        lines.append(f"• 持仓市值：¥{mv/10000:.1f} 万元")

    return "\n".join(lines)


def format_portfolio_summary(context: dict) -> str:
    """格式化整个投资组合的摘要，供需要全局视角的分析使用"""
    portfolio = context.get("current_portfolio") or {}
    if not portfolio:
        return "当前无持仓记录。"

    lines = ["📊 当前投资组合概况："]
    total_weight = 0.0
    pnl_list = []

    for sym, h in portfolio.items():
        if isinstance(h, (int, float)):
            w = float(h)
            lines.append(f"• {sym}：{w*100:.1f}%")
            total_weight += w
        else:
            w   = h.get("weight", 0)
            pnl = h.get("pnl_pct")
            name = h.get("symbol_name", sym)
            total_weight += w
            if pnl is not None:
                pnl_pct = pnl * 100 if abs(pnl) < 1 else pnl
                pnl_list.append(pnl_pct * w)
                pnl_str = f"{pnl_pct:+.1f}%"
            else:
                pnl_str = "未知"
            lines.append(f"• {name}（{sym}）：{w*100:.1f}% / 盈亏 {pnl_str}")

    lines.append(f"总仓位：{total_weight*100:.1f}%")
    if pnl_list:
        weighted_pnl = sum(pnl_list) / total_weight if total_weight > 0 else 0
        lines.append(f"组合加权浮盈：{weighted_pnl:+.2f}%")

    return "\n".join(lines)
