# goosewatch —— 鹅产品多平台监控

每天自动搜索淘宝、京东、拼多多、抖音上的鹅相关产品，汇总写入飞书多维表格，并推送价格异动通知。

---

## 目录结构

```
goosewatch/
├── __init__.py
├── config.py          # 全局配置（关键词、飞书凭证、反爬参数）
├── main.py            # 主入口
├── processor.py       # 数据清洗 / 去重 / 价格异动检测
├── writer.py          # 飞书多维表格写入
├── notifier.py        # 飞书群 Webhook 通知
├── requirements.txt
└── fetchers/
    ├── __init__.py
    ├── jd.py          # 京东（requests + BeautifulSoup）
    ├── taobao.py      # 淘宝（requests + h5api / HTML fallback）
    ├── pdd.py         # 拼多多（playwright 无头浏览器）
    └── douyin.py      # 抖音电商（playwright 无头浏览器）
```

---

## 飞书多维表格字段

在飞书多维表格中**提前创建**以下字段（字段名需和代码一致）：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 平台 | 单行文本 | 淘宝 / 京东 / 拼多多 / 抖音 |
| 搜索词 | 单行文本 | 触发该条数据的关键词 |
| 商品名称 | 单行文本 | 商品标题 |
| 价格 | 数字 | 当前到手价（元） |
| 原价 | 数字 | 划线价 |
| 月销量 | 数字 | 近30天销量 |
| 店铺名称 | 单行文本 | 卖家店铺 |
| 评分 | 数字 | 综合评分（0-5） |
| 商品链接 | 超链接 | 原始商品 URL |
| 商品ID | 单行文本 | 平台 SKU ID |
| 采集日期 | 单行文本 | YYYY-MM-DD |
| 价格变化(%) | 数字 | 与昨日对比，正数=涨价 |

---

## GitHub Secrets 配置

在仓库 Settings → Secrets and variables → Actions 中添加：

| Secret 名称 | 说明 |
|-------------|------|
| FEISHU_APP_ID | 飞书应用 App ID |
| FEISHU_APP_SECRET | 飞书应用 App Secret |
| FEISHU_WEBHOOK_URL | 飞书群机器人 Webhook URL |
| BITABLE_APP_TOKEN | 多维表格的 app_token（URL 中的参数） |
| BITABLE_TABLE_ID | 表格的 table_id |
| TAOBAO_COOKIE | 淘宝登录 Cookie（浏览器 DevTools → Network 复制） |
| DOUYIN_COOKIE | 抖音登录 Cookie（同上） |

---

## 本地运行

```bash
pip install -r goosewatch/requirements.txt
playwright install chromium

# 设置环境变量后运行
export FEISHU_APP_ID=xxx
export FEISHU_APP_SECRET=xxx
# ...
python -m goosewatch.main
```

---

## 搜索词配置

编辑 `goosewatch/config.py` 中的 `KEYWORDS` 列表即可：

```python
KEYWORDS = ["鹅绒被", "鹅肝", "鹅掌", "鹅肉", "鹅玩具", "鹅周边"]
```

---

## 注意事项

1. **Cookie 维护**：淘宝和抖音 Cookie 有效期约 7-30 天，失效后需手动更新 Secret
2. **反爬限制**：`REQUEST_DELAY` 默认 2 秒，不建议改小
3. **playwright 在 GitHub Actions**：已在 workflow 中配置安装 Chromium，首次运行较慢（约3分钟）
4. **抖音爬取**：反爬最强，如果持续失败可以先关闭，只用三个平台
