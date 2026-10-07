"""
build_html.py
从 docs/data.json 生成 docs/index.html
"""

import json
from datetime import date
from html import escape
from pathlib import Path

DATA_PATH = Path("docs/data.json")
HTML_PATH = Path("docs/index.html")


def event_metrics(records, event, warning):
    """First threshold observation in the event year, through the event date."""
    event_date = date.fromisoformat(event["date"])
    year_start = f"{event_date.year}-01-01"
    window = sorted(
        (r for r in records if year_start <= r["date"] <= event["date"]),
        key=lambda r: r["date"],
    )
    first = next((r for r in window if r["value"] >= warning), None)
    at_top = next((r for r in window if r["date"] == event["date"]), None)
    return {
        **event,
        "value": at_top["value"] if at_top else None,
        "warning_start": first["date"] if first else None,
        "days_to_top": (event_date - date.fromisoformat(first["date"])).days if first else None,
    }


def build():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    records     = data["records"]
    warning     = data["warning_line"]
    updated_at  = data["updated_at"]
    key_events  = data.get("key_events", [])

    if not records:
        print("无数据，跳过生成")
        return

    latest      = records[-1]
    latest_val  = latest["value"]
    latest_date = latest["date"]
    all_vals    = [r["value"] for r in records]
    pct_rank    = sum(v < latest_val for v in all_vals) / len(all_vals)
    above_warn  = latest_val >= warning

    event_cards = []
    for event in key_events:
        metric = event_metrics(records, event, warning)
        value_text = f"{metric['value']:.1%}" if metric["value"] is not None else "当日无数据"
        if metric["warning_start"] is not None:
            timing = (
                f'<div class="ev-duration">达警戒线至顶 <strong>{metric["days_to_top"]} 天</strong></div>'
                f'<div class="ev-start">首次达线：{metric["warning_start"]}</div>'
            )
        else:
            timing = '<div class="ev-start">当年截至事件日无达线记录</div>'
        event_cards.append(
            '<div class="event-card">'
            f'<div class="ev-date">{escape(event["date"])}</div>'
            f'<div class="ev-label">{escape(event["label"])}</div>'
            f'<div class="ev-val">集中度：{value_text}</div>'
            f'{timing}</div>'
        )
    event_cards_html = "\n".join(event_cards)

    # 序列化为 JS 数组
    dates_js  = json.dumps([r["date"]  for r in records])
    values_js = json.dumps([r["value"] for r in records])
    events_js = json.dumps(key_events)

    gauge_pct    = min(latest_val / 0.60, 1.0)  # 0-60%映射到0-100%
    gauge_deg    = int(gauge_pct * 180)           # 半圆0-180度
    gauge_color  = "#FF6B6B" if above_warn else "#4FC3F7"
    status_text  = "极度拥挤 ⚠" if latest_val >= 0.48 else \
                   "高度集中 ⚠" if latest_val >= 0.45 else \
                   "偏高"       if latest_val >= 0.40 else "正常"
    status_color = "#FF6B6B" if latest_val >= 0.45 else \
                   "#FFB347"  if latest_val >= 0.40 else "#4FC3F7"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>A股成交集中度监控</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Noto+Serif+SC:wght@400;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3.0.1/dist/chartjs-plugin-annotation.min.js"></script>
<style>
  :root {{
    --bg:       #0D1117;
    --surface:  #161B22;
    --border:   #21262D;
    --blue:     #4FC3F7;
    --amber:    #FFB347;
    --red:      #FF6B6B;
    --green:    #56D364;
    --text:     #E6EDF3;
    --muted:    #8B949E;
    --mono:     'JetBrains Mono', monospace;
    --serif:    'Noto Serif SC', serif;
  }}
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html {{ scroll-behavior: smooth; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: var(--mono);
    min-height: 100vh;
    padding: 0 0 60px;
  }}

  /* ── Header ── */
  header {{
    border-bottom: 1px solid var(--border);
    padding: 20px 40px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 12px;
  }}
  .site-title {{
    font-family: var(--serif);
    font-size: 1.1rem;
    letter-spacing: 0.05em;
    color: var(--text);
  }}
  .update-tag {{
    font-size: 0.72rem;
    color: var(--muted);
    background: var(--surface);
    border: 1px solid var(--border);
    padding: 4px 12px;
    border-radius: 20px;
  }}
  .update-tag span {{ color: var(--blue); }}

  /* ── Main layout ── */
  main {{
    max-width: 1100px;
    margin: 0 auto;
    padding: 0 24px;
  }}

  /* ── Gauge section ── */
  .gauge-section {{
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 48px 0 36px;
    position: relative;
  }}
  .gauge-label-top {{
    font-family: var(--serif);
    font-size: 0.85rem;
    color: var(--muted);
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 28px;
  }}

  /* SVG gauge */
  .gauge-wrap {{ position: relative; width: 280px; height: 150px; }}
  .gauge-wrap svg {{ width: 100%; height: auto; }}
  .gauge-number {{
    position: absolute;
    bottom: 0; left: 50%;
    transform: translateX(-50%);
    text-align: center;
  }}
  .gauge-number .big {{
    font-size: 3.2rem;
    font-weight: 600;
    color: {gauge_color};
    line-height: 1;
    letter-spacing: -0.02em;
  }}
  .gauge-number .unit {{
    font-size: 1rem;
    color: var(--muted);
    margin-left: 2px;
  }}

  .gauge-meta {{
    display: flex;
    gap: 36px;
    margin-top: 28px;
    flex-wrap: wrap;
    justify-content: center;
  }}
  .meta-item {{ text-align: center; }}
  .meta-item .label {{
    font-size: 0.68rem;
    color: var(--muted);
    letter-spacing: 0.1em;
    text-transform: uppercase;
    display: block;
    margin-bottom: 4px;
  }}
  .meta-item .value {{
    font-size: 1.05rem;
    font-weight: 600;
  }}
  .status-badge {{
    display: inline-block;
    padding: 6px 18px;
    border-radius: 4px;
    font-size: 0.9rem;
    font-weight: 600;
    border: 1px solid;
    margin-top: 24px;
    color: {status_color};
    border-color: {status_color};
    background: {status_color}18;
  }}

  /* ── Divider ── */
  .divider {{
    border: none;
    border-top: 1px solid var(--border);
    margin: 0;
  }}

  /* ── Chart section ── */
  .chart-section {{
    padding: 40px 0;
  }}
  .section-eyebrow {{
    font-size: 0.7rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 8px;
  }}
  .section-title {{
    font-family: var(--serif);
    font-size: 1.15rem;
    margin-bottom: 24px;
  }}
  .chart-container {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 24px 20px 16px;
    position: relative;
  }}
  canvas {{ width: 100% !important; }}

  /* ── Events table ── */
  .events-section {{ padding: 0 0 20px; }}
  .events-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 12px;
    margin-top: 20px;
  }}
  .event-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 3px solid var(--red);
    border-radius: 6px;
    padding: 14px 16px;
  }}
  .event-card .ev-date {{
    font-size: 0.72rem;
    color: var(--muted);
    margin-bottom: 4px;
  }}
  .event-card .ev-label {{
    font-size: 0.85rem;
    color: var(--text);
    font-family: var(--serif);
  }}
  .event-card .ev-val {{
    font-size: 0.8rem;
    color: var(--red);
    margin-top: 6px;
    font-weight: 600;
  }}
  .event-card .ev-duration {{ font-size: 0.8rem; margin-top: 12px; color: var(--text); }}
  .event-card .ev-duration strong {{ color: var(--amber); }}
  .event-card .ev-start {{ font-size: 0.72rem; margin-top: 6px; color: var(--muted); line-height: 1.6; }}
  .events-note {{ font-size: 0.75rem; color: var(--muted); line-height: 1.8; }}

  /* ── Explainer ── */
  .explainer {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 24px 28px;
    margin-top: 32px;
    font-size: 0.82rem;
    line-height: 1.8;
    color: var(--muted);
  }}
  .explainer strong {{ color: var(--text); }}
  .explainer .warn {{ color: var(--amber); }}

  /* ── Footer ── */
  footer {{
    text-align: center;
    font-size: 0.7rem;
    color: var(--muted);
    margin-top: 48px;
    border-top: 1px solid var(--border);
    padding-top: 24px;
  }}
  footer a {{ color: var(--blue); text-decoration: none; }}

  @media (max-width: 600px) {{
    header {{ padding: 16px 20px; }}
    main {{ padding: 0 16px; }}
    .gauge-number .big {{ font-size: 2.6rem; }}
    .gauge-wrap {{ width: 220px; height: 118px; }}
  }}
</style>
</head>
<body>

<header>
  <span class="site-title">A股成交集中度监控</span>
  <span class="update-tag">最后更新 <span>{updated_at}</span></span>
</header>

<main>

  <!-- ── 仪表盘 ── -->
  <section class="gauge-section">
    <p class="gauge-label-top">前 5% 个股成交额集中度</p>

    <div class="gauge-wrap">
      <svg viewBox="0 0 280 150" xmlns="http://www.w3.org/2000/svg">
        <!-- 背景轨道 -->
        <path d="M 20 140 A 120 120 0 0 1 260 140"
              fill="none" stroke="#21262D" stroke-width="18" stroke-linecap="round"/>
        <!-- 警戒区（45%-60%范围 = 135°-180° of arc） -->
        <path d="M 20 140 A 120 120 0 0 1 260 140"
              fill="none" stroke="#FF6B6B22" stroke-width="18" stroke-linecap="round"
              stroke-dasharray="188 377" stroke-dashoffset="-188"/>
        <!-- 进度弧 -->
        <path id="gauge-arc" d="M 20 140 A 120 120 0 0 1 260 140"
              fill="none" stroke="{gauge_color}" stroke-width="18" stroke-linecap="round"
              stroke-dasharray="{int(gauge_pct * 377)} 377"
              style="transition: stroke-dasharray 1.2s cubic-bezier(.4,0,.2,1)"/>
        <!-- 刻度标签 -->
        <text x="14"  y="158" fill="#8B949E" font-size="11" font-family="JetBrains Mono">20%</text>
        <text x="114" y="24"  fill="#8B949E" font-size="11" font-family="JetBrains Mono" text-anchor="middle">40%</text>
        <text x="243" y="158" fill="#8B949E" font-size="11" font-family="JetBrains Mono">60%</text>
        <!-- 警戒线刻度 -->
        <text x="195" y="54" fill="#FF6B6B" font-size="10" font-family="JetBrains Mono">45%⚑</text>
      </svg>
      <div class="gauge-number">
        <span class="big">{latest_val:.1%}</span>
      </div>
    </div>

    <div class="gauge-meta">
      <div class="meta-item">
        <span class="label">最新日期</span>
        <span class="value" style="color:var(--muted); font-size:0.9rem">{latest_date}</span>
      </div>
      <div class="meta-item">
        <span class="label">历史分位</span>
        <span class="value" style="color:var(--amber)">{pct_rank:.1%}</span>
      </div>
      <div class="meta-item">
        <span class="label">警戒线</span>
        <span class="value" style="color:var(--red)">45.0%</span>
      </div>
      <div class="meta-item">
        <span class="label">历史最高</span>
        <span class="value" style="color:var(--muted)">{max(all_vals):.1%}</span>
      </div>
    </div>

    <div class="status-badge">{status_text}</div>
  </section>

  <hr class="divider">

  <!-- ── 折线图 ── -->
  <section class="chart-section">
    <p class="section-eyebrow">历史走势</p>
    <h2 class="section-title">2007年以来完整序列</h2>
    <div class="chart-container">
      <canvas id="mainChart" height="320"></canvas>
    </div>
  </section>

  <!-- ── 关键事件 ── -->
  <section class="events-section">
    <p class="section-eyebrow">历史参照</p>
    <h2 class="section-title">集中度峰值与市场事件</h2>
    <p class="events-note">按现有序列，取事件当年首次达到 {warning:.0%} 的日期，计算至事件日的自然日差（起算当天为 0 天）。历史数据来源仍待核查。</p>
    <div class="events-grid" id="events-grid">{event_cards_html}</div>
  </section>

  <!-- ── 说明 ── -->
  <div class="explainer">
    <strong>指标说明：</strong>每个交易日，将全市场个股按成交额从高到低排序，前 5%（约270只）的合计成交额占全市场总成交额的比例，即为本指标。<br>
    <strong>历史警戒线 <span class="warn">45%</span>：</strong>
    图中标注 6 个市场事件：2007年牛市顶部、2009年反弹高点、2015年杠杆牛顶部、2018年初价值抱团、2021年初"茅指数"抱团顶，以及2026年7月1日科创AI硬件顶。事件用于历史参照。<br>
    <strong>数据来源：</strong>Tushare（历史）/ AKShare（每日更新），Wind同口径。
  </div>

</main>

<footer>
  <p>数据仅供参考，不构成投资建议 · 
     <a href="https://github.com" target="_blank">GitHub</a> · 
     每个交易日 15:35 自动更新
  </p>
</footer>

<script>
const dates   = {dates_js};
const values  = {values_js};
const events  = {events_js};
const WARNING = {warning};

// ── 图表 ──────────────────────────────────────────────────
Chart.register(window['chartjs-plugin-annotation']);

const ctx = document.getElementById('mainChart').getContext('2d');

// 渐变填充
const grad = ctx.createLinearGradient(0, 0, 0, 320);
grad.addColorStop(0,   'rgba(79,195,247,0.18)');
grad.addColorStop(1,   'rgba(79,195,247,0.00)');

// 峰值点（>45%）
const pointColors = values.map(v =>
  v >= 0.50 ? '#FFB347' : v >= WARNING ? '#FF6B6B' : 'transparent'
);
const pointRadius = values.map(v => v >= WARNING ? 4 : 0);

// 稀疏标签（只显示每年1月）
const labelDates = dates.map((d, i) => {{
  if (d.slice(5) === '01-01' || (i === 0) || (i === dates.length - 1)) return d.slice(0, 7);
  return '';
}});

// 事件标注
const annotations = {{}};
events.forEach((ev, i) => {{
  const idx = dates.indexOf(ev.date);
  if (idx < 0) return;
  annotations[`event${{i}}`] = {{
    type: 'line',
    xMin: idx, xMax: idx,
    borderColor: 'rgba(255,107,107,0.45)',
    borderWidth: 1,
    borderDash: [4, 3],
    label: {{
      display: true,
      content: ev.label,
      position: 'start',
      color: '#FF6B6B',
      backgroundColor: '#0D1117',
      font: {{ size: 10, family: 'JetBrains Mono' }},
      padding: 4,
    }}
  }};
}});

// 警戒线标注
annotations['warningLine'] = {{
  type: 'line',
  yMin: WARNING, yMax: WARNING,
  borderColor: 'rgba(255,107,107,0.55)',
  borderWidth: 1.5,
  borderDash: [6, 4],
  label: {{
    display: true,
    content: '警戒线 45%',
    position: 'end',
    color: '#FF6B6B',
    backgroundColor: '#0D1117',
    font: {{ size: 10, family: 'JetBrains Mono' }},
  }}
}};

new Chart(ctx, {{
  type: 'line',
  data: {{
    labels: labelDates,
    datasets: [{{
      data: values,
      borderColor: '#4FC3F7',
      borderWidth: 1.5,
      backgroundColor: grad,
      fill: true,
      tension: 0.2,
      pointBackgroundColor: pointColors,
      pointRadius: pointRadius,
      pointHoverRadius: 5,
    }}]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    interaction: {{ mode: 'index', intersect: false }},
    plugins: {{
      legend: {{ display: false }},
      tooltip: {{
        backgroundColor: '#161B22',
        borderColor: '#21262D',
        borderWidth: 1,
        titleColor: '#8B949E',
        bodyColor: '#E6EDF3',
        titleFont: {{ family: 'JetBrains Mono', size: 11 }},
        bodyFont:  {{ family: 'JetBrains Mono', size: 13 }},
        callbacks: {{
          title: items => dates[items[0].dataIndex],
          label: item  => ` 集中度: ${{(item.raw * 100).toFixed(2)}}%`,
        }}
      }},
      annotation: {{ annotations }}
    }},
    scales: {{
      x: {{
        grid:  {{ color: '#21262D', drawTicks: false }},
        ticks: {{ color: '#8B949E', font: {{ size: 10, family: 'JetBrains Mono' }},
                  maxRotation: 0, autoSkip: true, maxTicksLimit: 12 }},
        border: {{ color: '#21262D' }},
      }},
      y: {{
        min: 0.18, max: 0.58,
        grid:  {{ color: '#21262D' }},
        ticks: {{
          color: '#8B949E',
          font: {{ size: 10, family: 'JetBrains Mono' }},
          callback: v => (v * 100).toFixed(0) + '%',
        }},
        border: {{ color: '#21262D' }},
      }}
    }},
    animation: {{ duration: 800 }}
  }}
}});

</script>
</body>
</html>"""

    HTML_PATH.parent.mkdir(parents=True, exist_ok=True)
    HTML_PATH.write_text(html, encoding="utf-8")
    print(f"✅ HTML 已生成：{HTML_PATH}")


if __name__ == "__main__":
    build()
