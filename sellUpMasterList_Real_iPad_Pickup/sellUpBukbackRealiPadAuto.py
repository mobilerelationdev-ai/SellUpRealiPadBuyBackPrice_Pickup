import requests
import time
import random
from datetime import datetime
from zoneinfo import ZoneInfo  # ✅ 用于设置 Asia/Singapore 时区
import json
import gspread
from google.oauth2.service_account import Credentials

# ---------- Google Sheets 配置 ----------
SERVICE_ACCOUNT_FILE = 'service_account.json'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = '1tKHZEiOve-MO8pOgfn9mHPf1e6SGbfJkx2hsGmd2ZWw'

credentials = Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
gc = gspread.authorize(credentials)
spreadsheet = gc.open_by_key(SPREADSHEET_ID)
worksheet = spreadsheet.worksheet('Used Buyback Prices - iPad')

# ---------- 数据抓取 ----------
with open('products.json', 'r') as f:
    products = json.load(f)

# ✅ 新加坡当前日期
current_date = datetime.now(ZoneInfo("Asia/Singapore")).strftime('%Y-%m-%d')

session = requests.Session()
all_results = []

request_counter = 0
max_retries = 3

for index, product in enumerate(products, start=1):
    retries = 0
    success = False

    print(f"\n🔍 处理商品: {product['product_name']} (ID: {product['goods_id']}) - 第 {index} 个")

    while retries < max_retries and not success:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
                'Referer': product['referer'],
                'Origin': 'https://sellup.com.sg',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest'
            }

            # Step 1: 获取 token
            payload_token = {
                'action': 'Calculate',
                'deviceType': '1',
                'goods_id': product['goods_id'],
                'seletedDate': current_date
            }
            payload_token['data[]'] = product['data']

            token_res = session.post('https://sellup.com.sg/ajax.php', headers=headers, data=payload_token)
            token_json = token_res.json()

            if token_json.get('errorCode') == 0 and token_json.get('data') is not None:
                token = token_json['data']['token']
                print(f"✅ Token 获取成功: {token}")
            else:
                print(f"❌ 获取 token 失败: {token_json.get('error')}, 重试中...")
                retries += 1
                time.sleep(5)
                continue

            # Step 2: 获取价格
            payload_price = {
                'action': 'onSite',
                'deviceType': '1',
                'goods_id': product['goods_id'],
                'token': token
            }
            payload_price['data[]'] = product['data']

            res = session.post('https://sellup.com.sg/ajax.php', headers=headers, data=payload_price)
            res_json = res.json()

            if res_json.get('errorCode') == 0 and res_json.get('data') is not None:
                dealer_prices = res_json['data']['dealerPrices']
                for dealer in dealer_prices:
                    result = {
                        'goods_id': product['goods_id'],
                        'product_name': product['product_name'],
                        'dealerId': dealer['dealerId'],
                        'dealerName': dealer['dealer']['name'],
                        'skuPrice': dealer['skuPrice'],
                        'totalPrice': dealer['totalPrice'],
                        'updated_at': datetime.now(ZoneInfo("Asia/Singapore")).strftime('%Y-%m-%d %H:%M:%S')  # ✅ 加入 SG 时间
                    }
                    all_results.append(result)
                print(f"✅ 商品 {product['product_name']} 价格抓取完成")
                success = True
            else:
                print(f"❌ 商品 {product['product_name']} 请求失败: {res_json.get('error')}, 重试中...")
                retries += 1
                time.sleep(5)

        except Exception as e:
            print(f"❌ 商品 {product['product_name']} 异常: {e}, 重试中...")
            retries += 1
            time.sleep(5)

    if not success:
        print(f"🚫 商品 {product['product_name']} 多次失败，跳过")

    request_counter += 1

    # 每 10 次停 60-120 秒
    if request_counter % 10 == 0:
        wait_time = random.uniform(60, 120)
        print(f"⏸️ 已处理 {request_counter} 个商品，休息 {int(wait_time)} 秒防封锁...")
        time.sleep(wait_time)
    else:
        time.sleep(random.uniform(5, 10))

# ---------- 写入 Google Sheets ----------
print("\n📤 正在同步到 Google Sheets...")

# 清空旧数据
worksheet.clear()
print("🚿 旧数据已清空")

# ✅ 表头加入 updated_at
header = ['goods_id', 'product_name', 'dealerId', 'dealerName', 'skuPrice', 'totalPrice', 'updated_at']
worksheet.update(values=[header], range_name='A1')
print("✅ 表头已写入")

# 准备批量数据
rows = []
for row in all_results:
    rows.append([
        row['goods_id'],
        row['product_name'],
        row['dealerId'],
        row['dealerName'],
        row['skuPrice'],
        row['totalPrice'],
        row['updated_at']  # ✅ 添加更新时间
    ])

# 写入数据
if rows:
    worksheet.update(values=rows, range_name='A2')
    print(f"✅ 共写入 {len(rows)} 行数据到 Google Sheets ✅")
else:
    print("⚠️ 没有数据可写入")

print("🎉 全部完成！")
