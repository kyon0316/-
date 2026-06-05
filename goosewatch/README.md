# Goosewatch — 鹅产品市场调研系统

每日自动聚合鹅各部位产品的市场行情数据，写入飞书多维表格。

## 技术架构

```
互联网信息源（一亩田/1688/B2B平台）
         ↓
   aggregator.py（行情聚合 + baseline fallback）
         ↓
   processor.py（数据清洗 / 去重 / 异动检测）
         ↓
   writer.py（写入飞书 Bitable）
         ↓
   notifier.py（飞书群通知）
```

## 数据来源

- **在线源**：一亩田 (ymt.com)、1688 (1688.com)、百度爱采购 (b2b.baidu.com)
- **基线数据**：内置 2026 年 6 月调研的 13 个鹅产品行情基线，在线源不可用时自动 fallback

## 鹅产品覆盖

| 类别 | 产品 |
|------|------|
| 羽毛 | 鹅绒、刀翎鹅毛 |
| 内脏 | 鹅肥肝、鹅肠、鹅胗、鹅血 |
| 部位肉 | 鹅掌、鹅翅、鹅头、鹅脖 |
| 主体 | 鹅肉 |
| 副产品 | 鹅油、鹅胆 |

## 飞书多维表格字段

需要在飞书 Bitable 中创建以下字段：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 产品名称 | 文本 | 鹅各部位名称 |
| 产品类别 | 单选 | 羽毛/内脏/部位肉/主体/副产品 |
| 参考价格 | 文本 | 批发价格区间 |
| 市场需求 | 单选 | 极高/高/中 |
| 数据来源 | 文本 | 一亩田/1688/行情基线 |
| 备注 | 文本 | 补充说明 |
| 采集日期 | 日期 | YYYY-MM-DD |

## 调度

GitHub Actions，每日 08:00 CST（00:00 UTC）触发，15 分钟内完成。

## 环境变量（GitHub Secrets）

| Secret | 说明 |
|--------|------|
| FEISHU_APP_ID | 飞书应用 App ID |
| FEISHU_APP_SECRET | 飞书应用 App Secret |
| FEISHU_WEBHOOK_URL | 飞书群 Webhook 地址 |
| BITABLE_APP_TOKEN | 飞书多维表格 app_token |
| BITABLE_TABLE_ID | 飞书多维表格 table_id |

## 本地运行

```bash
pip install -r requirements.txt
python -m goosewatch.main
```
