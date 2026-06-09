"""
update_data.py
每日运行：追加当日集中度到 docs/data.json
首次运行（data.json不存在）：用Tushare回溯2007年至今完整历史
"""

import os
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

# ── 配置 ──────────────────────────────────────────────────
TOP_PCT      = 0.05
WARNING_LINE = 0.45
DATA_PATH    = Path("docs/data.json")
TUSHARE_TOKEN = os.environ.get("TUSHARE_TOKEN", "")

# 历史关键事件标注（显示在图表上）
KEY_EVENTS = [
    {"date": "2007-10-16", "label": "沪指6124点顶部"},
    {"date": "2009-08-04", "label": "4万亿后反弹顶"},
    {"date": "2015-06-12", "label": "杠杆牛顶部"},
    {"date": "2018-01-29", "label": "价值抱团崩盘前"},
    {"date": "2021-02-10", "label": "茅指数抱团顶"},
]


# ── 工具函数 ────────────────────────────────────────────────
def load_existing() -> dict:
    if DATA_PATH.exists():
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"records": [], "updated_at": ""}


def save_data(data: dict):
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    data["warning_line"] = WARNING_LINE
    data["key_events"] = KEY_EVENTS
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ 数据已保存至 {DATA_PATH}，共 {len(data['records'])} 条记录")


def is_trade_day(date_str: str) -> bool:
    """简单判断：周一至周五且不是明显节假日（GitHub Actions用，精度够用）"""
    try:
        import akshare as ak
        df = ak.tool_trade_date_hist_sina()
        dates = df["trade_date"].astype(str).tolist()
        return date_str in dates
    except Exception:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return d.weekday() < 5


# ── 今日数据（Tushare，支持境外IP）────────────────────────
def fetch_today_tushare(date_str: str) -> float | None:
    """用Tushare daily接口获取指定日期集中度，支持GitHub Actions境外服务器"""
    if not TUSHARE_TOKEN:
        print("⚠️  未设置 TUSHARE_TOKEN")
        return None
    try:
        import tushare as ts
        pro = ts.pro_api(TUSHARE_TOKEN)
        # 取当日及前后1天，防止节假日等边界问题
        d = datetime.strptime(date_str, "%Y-%m-%d")
        start = (d - timedelta(days=1)).strftime("%Y%m%d")
        end   = d.strftime("%Y%m%d")
        df = pro.daily(ts_code="", start_date=start, end_date=end,
                       fields="ts_code,trade_date,amount")
        if df is None or df.empty:
            print(f"  Tushare 返回空数据（{date_str} 可能非交易日）")
            return None
        # 只取目标日期
        target = date_str.replace("-", "")
        df = df[df["trade_date"] == target]
        if df.empty:
            print(f"  Tushare 无 {date_str} 数据（非交易日或数据延迟）")
            return None
        df = df[df["amount"] > 0]
        total = df["amount"].sum()
        if total == 0:
            return None
        n_top = max(1, int(len(df) * TOP_PCT))
        top_sum = df["amount"].nlargest(n_top).sum()
        val = round(top_sum / total, 6)
        print(f"  Tushare 今日集中度: {val:.2%}（{len(df)} 只个股）")
        return val
    except Exception as e:
        print(f"  Tushare 失败: {e}")
        return None


# ── 历史回溯（Tushare，首次运行）──────────────────────────
def fetch_history_tushare() -> list[dict]:
    if not TUSHARE_TOKEN:
        print("⚠️  未设置 TUSHARE_TOKEN，跳过历史回溯")
        return []

    try:
        import tushare as ts
        pro = ts.pro_api(TUSHARE_TOKEN)
        records = []

        for year in range(2007, datetime.today().year + 1):
            start = f"{year}0101"
            end   = f"{year}1231"
            try:
                df = pro.daily(
                    ts_code="",
                    start_date=start,
                    end_date=end,
                    fields="ts_code,trade_date,amount"
                )
                if df is None or df.empty:
                    continue
                df = df[df["amount"] > 0]

                for date, grp in df.groupby("trade_date"):
                    total = grp["amount"].sum()
                    if total == 0:
                        continue
                    n_top = max(1, int(len(grp) * TOP_PCT))
                    top_sum = grp["amount"].nlargest(n_top).sum()
                    records.append({
                        "date": f"{date[:4]}-{date[4:6]}-{date[6:]}",
                        "value": round(top_sum / total, 6),
                        "n_stocks": len(grp),
                    })

                print(f"  {year}: {df['trade_date'].nunique()} 个交易日 ✓")
                time.sleep(0.6)

            except Exception as e:
                print(f"  {year} 失败: {e}")
                time.sleep(2)

        records.sort(key=lambda x: x["date"])
        return records

    except Exception as e:
        print(f"Tushare 初始化失败: {e}")
        return []


# ── 主逻辑 ────────────────────────────────────────────────
def main():
    today = datetime.today().strftime("%Y-%m-%d")
    data  = load_existing()
    existing_dates = {r["date"] for r in data["records"]}

    # ── 情况1：首次运行，data.json 不存在 ─────────────────
    if not data["records"]:
        print("首次运行，开始 Tushare 历史回溯（约需2-5分钟）...")
        records = fetch_history_tushare()
        if records:
            data["records"] = records
            # 补上今日
            if today not in {r["date"] for r in records}:
                val = fetch_today_tushare(today)
                if val:
                    data["records"].append({"date": today, "value": val, "n_stocks": 0})
        save_data(data)
        return

    # ── 情况2：日常更新，追加今日数据 ─────────────────────
    if today in existing_dates:
        print(f"今日 {today} 数据已存在，无需更新")
        # 仍然重新生成 HTML（格式可能有变化）
        save_data(data)
        return

    if not is_trade_day(today):
        print(f"{today} 非交易日，跳过")
        return

    print(f"正在获取 {today} 数据...")
    val = fetch_today_tushare(today)
    if val is None:
        print("数据获取失败，可能市场未收盘或Tushare数据延迟，稍后重试")
        return

    # 补充近期遗漏的交易日（最多回溯5天）
    for i in range(1, 6):
        past = (datetime.today() - timedelta(days=i)).strftime("%Y-%m-%d")
        if past not in existing_dates and is_trade_day(past):
            print(f"  检测到遗漏日期 {past}，尝试补充...")
            past_val = fetch_today_tushare(past)
            if past_val:
                data["records"].append({"date": past, "value": past_val, "n_stocks": 0})
                print(f"  已补充 {past}: {past_val:.2%}")

    data["records"].append({
        "date": today,
        "value": val,
        "n_stocks": 0,  # AKShare实时不返回这个，留空
    })
    data["records"].sort(key=lambda x: x["date"])

    latest = data["records"][-1]
    flag = "⚠️  超过警戒线！" if val >= WARNING_LINE else "✅ 正常"
    all_vals = [r["value"] for r in data["records"]]
    pct_rank = sum(v < val for v in all_vals) / len(all_vals)
    print(f"\n{'='*45}")
    print(f"  {today}  集中度: {val:.2%}  {flag}")
    print(f"  历史分位: {pct_rank:.1%}（2007年以来）")
    print(f"{'='*45}\n")

    save_data(data)


if __name__ == "__main__":
    main()
