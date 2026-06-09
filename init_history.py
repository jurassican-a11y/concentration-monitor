"""
init_history.py —— 在本地运行一次，生成完整历史数据
之后上传 docs/data.json 到 GitHub，后续由 Actions 每日增量更新

用法：
  pip install tushare akshare pandas
  python init_history.py --token 你的TUSHARE_TOKEN
"""

import argparse, sys, os

parser = argparse.ArgumentParser()
parser.add_argument("--token", required=True, help="Tushare token")
args = parser.parse_args()

os.environ["TUSHARE_TOKEN"] = args.token

# 切换到项目根目录
import pathlib
os.chdir(pathlib.Path(__file__).parent)

# 运行数据更新 + HTML生成
import importlib.util, sys

def run_script(path):
    spec = importlib.util.spec_from_file_location("mod", path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.main() if hasattr(mod, "main") else None

print("第一步：回溯历史数据（约需3-8分钟）...")
run_script("scripts/update_data.py")

print("\n第二步：生成 HTML...")
exec(open("scripts/build_html.py", encoding="utf-8").read())
build()

print("""
✅ 完成！接下来：

1. 将整个项目文件夹推送到 GitHub：
   git init
   git add .
   git commit -m "初始化集中度监控网站"
   git remote add origin https://github.com/你的用户名/concentration-monitor.git
   git push -u origin main

2. GitHub 仓库设置 → Pages → Source 选 main 分支 /docs 文件夹

3. 添加 Tushare Token 到 GitHub Secrets：
   仓库 → Settings → Secrets → New secret
   Name: TUSHARE_TOKEN
   Value: 你的token

4. 完成！网站地址：https://你的用户名.github.io/concentration-monitor/
   每个交易日15:35自动更新
""")
