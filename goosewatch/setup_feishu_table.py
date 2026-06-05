"""
一键在飞书 Bitable 创建鹅产品调研字段 + 写入数据
"""
import json, time, requests

APP_ID = "cli_a8d935e5cf26501c"
APP_SECRET = "4z0HCbjReCzzbcv0kMGm7bR1rBMT1xaI"
BITABLE_APP_TOKEN = "CZf5bAQt0aJgW0suvo0cslyHnKe"
TABLE_ID = "tblJADDS7nA9fUBn"

# ── 1. 获取 token ──
def get_token():
    r = requests.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                      json={"app_id": APP_ID, "app_secret": APP_SECRET})
    return r.json()["tenant_access_token"]

TOKEN = get_token()
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# ── 2. 需要创建的字段 ──
FIELDS = [
    {"field_name": "产品名称", "type": 1},           # 文本
    {"field_name": "产品类别", "type": 3},           # 单选
    {"field_name": "参考价格", "type": 1},           # 文本
    {"field_name": "市场需求", "type": 1},            # 文本
    {"field_name": "利润评级", "type": 3},           # 单选
    {"field_name": "数据来源", "type": 1},            # 文本
    {"field_name": "备注", "type": 1},               # 多行文本(飞书type=1)
    {"field_name": "采集日期", "type": 5},            # 日期 (type=5 = DateTime)
]

# ── 3. 创建字段 ──
print("=== 创建字段 ===")
created_fields = {}
for f in FIELDS:
    name = f["field_name"]
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BITABLE_APP_TOKEN}/tables/{TABLE_ID}/fields"
    body = {"field_name": name, "type": f["type"]}
    r = requests.post(url, headers=HEADERS, json=body)
    result = r.json()
    if result["code"] == 0:
        fid = result["data"]["field"]["field_id"]
        created_fields[name] = fid
        print(f"  ✅ {name} ({fid})")
    else:
        print(f"  ❌ {name}: {result}")
    time.sleep(0.3)

# ── 4. 更新主列名称 ──
print("\n=== 更新主列名称 ===")
url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BITABLE_APP_TOKEN}/tables/{TABLE_ID}/fields/fldInSe4kU"
r = requests.put(url, headers=HEADERS, json={"field_name": "序号"})
print(f"  主列: {r.json()}")

# ── 5. 写入鹅产品调研数据 ──
print("\n=== 写入数据 ===")
DATA = [
    {"产品名称": "鹅肥肝",      "产品类别": "内脏",   "参考价格": "55-240元/斤",     "市场需求": "高(出口增速10%+)",   "利润评级": "S", "数据来源": "行业报告/一亩田",  "备注": "中国占全球20%市场，深加工溢价40%+。鹅肝酱/鲜肝双路线", "采集日期": "2026-06-03"},
    {"产品名称": "刀翎鹅毛",    "产品类别": "羽毛",   "参考价格": "280-450元/斤",    "市场需求": "高(羽毛球刚需)",     "利润评级": "S", "数据来源": "行业报告/1688", "备注": "单根0.7-0.8元，羽毛球核心原料。一斤毛比一只活鹅还贵", "采集日期": "2026-06-03"},
    {"产品名称": "鹅绒",        "产品类别": "羽毛",   "参考价格": "94万元/吨(90%白)", "市场需求": "高(全球2000亿市场)", "利润评级": "S", "数据来源": "行业报告/一亩田",  "备注": "90%白鹅绒94.3万/吨，羽绒服/羽绒被刚需。按克计价利润极高", "采集日期": "2026-06-03"},
    {"产品名称": "鹅掌",        "产品类别": "部位肉", "参考价格": "30-33元/斤",      "市场需求": "高(火锅/卤味/粤菜)", "利润评级": "A", "数据来源": "一亩田/1688",  "备注": "火锅食材+卤味加工+粤菜鲍汁鹅掌。电商零售价更高", "采集日期": "2026-06-03"},
    {"产品名称": "鹅翅",        "产品类别": "部位肉", "参考价格": "31-35元/斤",      "市场需求": "中高(烧烤/卤味)",    "利润评级": "A", "数据来源": "一亩田/1688",  "备注": "烧烤+卤味需求稳定，深加工（卤鹅翅）溢价明显", "采集日期": "2026-06-03"},
    {"产品名称": "鹅肠",        "产品类别": "内脏",   "参考价格": "15-26元/斤",      "市场需求": "高(火锅刚需)",       "利润评级": "A", "数据来源": "一亩田/1688",  "备注": "火锅店刚需品，川渝地区需求极大。新鲜鹅肠溢价更高", "采集日期": "2026-06-03"},
    {"产品名称": "鹅胗",        "产品类别": "内脏",   "参考价格": "16-18元/斤",      "市场需求": "中(卤味加工)",       "利润评级": "B", "数据来源": "一亩田/1688",  "备注": "卤味加工稳定需求，可做鹅胗干零食", "采集日期": "2026-06-03"},
    {"产品名称": "鹅肉",        "产品类别": "主体",   "参考价格": "8-20元/斤",       "市场需求": "中(深加工溢价)",     "利润评级": "B", "数据来源": "一亩田/1688",  "备注": "白条鹅8-12元/斤，分割肉15-20元/斤。深加工（酱鹅/风干鹅）溢价40%+", "采集日期": "2026-06-03"},
    {"产品名称": "鹅血",        "产品类别": "内脏",   "参考价格": "2-5元/斤",        "市场需求": "低(深加工潜力大)",   "利润评级": "C", "数据来源": "行业报告",      "备注": "鲜食价值低，但深加工（血红素/饲料蛋白）前景好", "采集日期": "2026-06-03"},
    {"产品名称": "鹅头",        "产品类别": "部位肉", "参考价格": "15-25元/斤",      "市场需求": "中(卤味)",           "利润评级": "B", "数据来源": "一亩田/1688",  "备注": "卤鹅头受欢迎，但单品价值不如鹅掌/鹅翅", "采集日期": "2026-06-03"},
    {"产品名称": "鹅脖",        "产品类别": "部位肉", "参考价格": "12-18元/斤",      "市场需求": "中(卤味/零食)",      "利润评级": "B", "数据来源": "一亩田/1688",  "备注": "卤鹅脖+真空零食包装可提升附加值", "采集日期": "2026-06-03"},
    {"产品名称": "鹅油",        "产品类别": "副产品", "参考价格": "20-40元/斤",      "市场需求": "中(精油/化妆品)",    "利润评级": "B", "数据来源": "行业报告",      "备注": "鹅油提炼精油，化妆品原料。深加工后价值翻5-10倍", "采集日期": "2026-06-03"},
    {"产品名称": "鹅胆",        "产品类别": "副产品", "参考价格": "50-100元/个",     "市场需求": "中(药用)",           "利润评级": "B", "数据来源": "行业报告",      "备注": "鹅去氧胆酸药用价值高，提取后大幅增值", "采集日期": "2026-06-03"},
]

records = []
for item in DATA:
    fields = {}
    for name, value in item.items():
        if name in created_fields:
            fields[created_fields[name]] = value
    records.append({"fields": fields})

# 批量写入（每次最多500条）
url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BITABLE_APP_TOKEN}/tables/{TABLE_ID}/records/batch_create"
r = requests.post(url, headers=HEADERS, json={"records": records})
result = r.json()
if result["code"] == 0:
    print(f"  ✅ 成功写入 {len(result['data']['records'])} 条记录")
else:
    print(f"  ❌ 写入失败: {result}")

print("\n=== 全部完成 ===")
print(f"表格链接: https://twu4v2385kc.feishu.cn/base/{BITABLE_APP_TOKEN}?table={TABLE_ID}")
