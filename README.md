# A股成交集中度监控网站

**完全免费 · 全自动 · 每日更新**

追踪A股前5%个股成交额集中度，历史警戒线45%。

---

## 部署步骤（约15分钟）

### 第一步：本地初始化历史数据

```bash
# 安装依赖
pip install akshare tushare pandas

# 回溯2007年至今历史（需要Tushare token，免费注册：tushare.pro）
python init_history.py --token 你的TUSHARE_TOKEN
```

执行完毕后，`docs/` 目录下会生成：
- `data.json`（约200KB，含全部历史数据）
- `index.html`（网站首页）

### 第二步：推送到 GitHub

```bash
git init
git add .
git commit -m "初始化集中度监控"
git branch -M main
git remote add origin https://github.com/你的用户名/concentration-monitor.git
git push -u origin main
```

### 第三步：开启 GitHub Pages

仓库页面 → **Settings** → **Pages**
- Source：`Deploy from a branch`
- Branch：`main`，文件夹选 `/docs`
- 保存

约1分钟后，网站上线：`https://你的用户名.github.io/concentration-monitor/`

### 第四步：配置自动更新密钥

仓库页面 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Name | Value |
|------|-------|
| `TUSHARE_TOKEN` | 你的Tushare token |

配置完成后，GitHub Actions 将在**每个交易日15:35（北京时间）**自动运行，
抓取当日数据，更新网站。

---

## 文件结构

```
concentration-monitor/
├── .github/
│   └── workflows/
│       └── daily_update.yml   # 自动化任务配置
├── scripts/
│   ├── update_data.py         # 数据抓取（Tushare + AKShare）
│   └── build_html.py          # 生成静态网页
├── docs/                      # GitHub Pages 根目录
│   ├── index.html             # 网站首页（自动生成）
│   └── data.json              # 历史数据（自动更新）
├── init_history.py            # 首次初始化脚本
├── requirements.txt
└── README.md
```

---

## 常见问题

**Q: GitHub Actions 没有自动运行？**
检查 Actions 是否被禁用：仓库 → Actions → 点击"启用 Workflows"

**Q: AKShare 字段报错？**
akshare 接口偶有变动，运行 `print(ak.stock_zh_a_spot_em().columns.tolist())` 查看实际字段名，在 `update_data.py` 中修改 `"成交额"` 为实际字段名。

**Q: 想手动触发更新？**
仓库 → Actions → daily_update → Run workflow

**Q: 历史数据精度？**
Tushare 免费账户 `daily` 接口数据与 Wind 同源，精度完全够用。

---

## 指标说明

| 指标 | 含义 |
|------|------|
| 前5%个股 | 全市场约270只成交额最高的股票 |
| 集中度 | 这270只股的成交额之和 / 全市场总成交额 |
| 警戒线45% | 历史上突破此线后均出现风格切换或市场回撤 |
