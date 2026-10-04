import os
import requests
from flask import Flask

app = Flask(__name__)

# --- CẤU HÌNH THÔNG TIN CỦA BẠN ---
TELEGRAM_BOT_TOKEN = "8847660116:AAFkfEUug-7lJKuvLQv4KF8qI_atg71H8yY"
TELEGRAM_CHAT_ID = "8836493753"

THUEAPIBANK_API_KEY = "ĐIỀN_API_KEY_THUEAPIBANK"
ZALOPAY_PHONE = "0961179716"

processed_trans = set()

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print("Lỗi gửi Telegram:", e)

@app.route('/cron-check', methods=['GET'])
def cron_check():
    try:
        # Gọi API thueapibank
        api_url = f"https://api.thueapibank.vn/v1/history/zalopay?token={THUEAPIBANK_API_KEY}&phone={ZALOPAY_PHONE}"
        response = requests.get(api_url, timeout=10)
        
        # Kiểm tra xem thueapibank có trả về 200 OK không
        if response.status_code != 200:
            print(f"Lỗi kết nối Thueapibank HTTP: {response.status_code} - {response.text}")
            return f"Error from Thueapibank HTTP {response.status_code}", 200

        res_data = response.json()

        # Kiểm tra dữ liệu trả về từ API
        if res_data.get('status') == True or res_data.get('code') == 200:
            transactions = res_data.get('data', [])

            for trans in transactions:
                trans_id = str(trans.get('trans_id') or trans.get('id') or trans.get('tranId'))
                amount = trans.get('amount', 0)
                comment = trans.get('comment') or trans.get('description') or ""

                if amount > 0 and trans_id not in processed_trans:
                    processed_trans.add(trans_id)

                    msg = (
                        f"🎉 **CÓ GIAO DỊCH ZALOPAY MỚI!**\n\n"
                        f"💵 **Số tiền:** `+{amount:,.0f} VNĐ`\n"
                        f"📝 **Nội dung:** `{comment}`\n"
                        f"🆔 **Mã GD:** `{trans_id}`"
                    )
                    send_telegram(msg)

            return "OK - Checked", 200
        else:
            print("API trả về lỗi:", res_data)
            return f"API Res Error: {res_data.get('message')}", 200

    except Exception as e:
        print("Lỗi Python Server:", str(e))
        # Trả về 200 để Cron không bị ngắt nhưng in lỗi ra log
        return f"Python Exception: {str(e)}", 200

@app.route('/')
def home():
    return "Bot AutoBank đang hoạt động!", 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
