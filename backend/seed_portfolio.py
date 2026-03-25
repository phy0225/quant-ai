"""
持仓演示数据生成脚本
运行方式：python seed_portfolio.py（后端需要在运行中）
"""
import requests
import json

BASE = "http://localhost:8000/api/v1/portfolio"

holdings = [
    {"symbol": "600519", "symbol_name": "贵州茅台", "weight": 0.18, "cost_price": 1680.0,  "quantity": 100,  "note": "核心仓位，长期持有"},
    {"symbol": "000858", "symbol_name": "五 粮 液", "weight": 0.12, "cost_price": 128.5,   "quantity": 800,  "note": "白酒板块配置"},
    {"symbol": "300750", "symbol_name": "宁德时代", "weight": 0.15, "cost_price": 195.0,   "quantity": 600,  "note": "新能源核心标的"},
    {"symbol": "601318", "symbol_name": "中国平安", "weight": 0.10, "cost_price": 42.8,    "quantity": 2000, "note": "金融板块压舱石"},
    {"symbol": "002594", "symbol_name": "比亚迪",   "weight": 0.13, "cost_price": 238.0,   "quantity": 400,  "note": "新能源整车龙头"},
    {"symbol": "688111", "symbol_name": "金山办公", "weight": 0.08, "cost_price": 58.5,    "quantity": 1000, "note": "国产软件赛道"},
    {"symbol": "000333", "symbol_name": "美的集团", "weight": 0.09, "cost_price": 52.3,    "quantity": 1500, "note": "家电龙头，稳定分红"},
    {"symbol": "600036", "symbol_name": "招商银行", "weight": 0.08, "cost_price": 31.6,    "quantity": 2000, "note": "优质银行，ROE稳定"},
    {"symbol": "002415", "symbol_name": "海康威视", "weight": 0.07, "cost_price": 26.8,    "quantity": 2000, "note": "安防龙头"},
]

print("开始写入持仓数据...")
success = 0
for h in holdings:
    try:
        r = requests.post(BASE + "/", json=h, timeout=10)
        if r.status_code in (200, 201):
            data = r.json()
            print(f"  ✓ {h['symbol_name']}（{h['symbol']}）权重 {h['weight']*100:.0f}%")
            success += 1
        else:
            print(f"  ✗ {h['symbol_name']} 失败: {r.status_code} {r.text[:80]}")
    except Exception as e:
        print(f"  ✗ {h['symbol_name']} 异常: {e}")

print(f"\n完成：{success}/{len(holdings)} 条持仓写入成功")
print("总权重：{:.0f}%".format(sum(h['weight'] for h in holdings[:success]) * 100))

if success > 0:
    print("\n正在刷新实时价格...")
    try:
        r = requests.post(BASE + "/refresh-prices", timeout=60)
        if r.status_code == 200:
            print(f"  价格刷新成功: {r.json()}")
        else:
            print(f"  价格刷新失败: {r.status_code}")
    except Exception as e:
        print(f"  价格刷新异常: {e}")
