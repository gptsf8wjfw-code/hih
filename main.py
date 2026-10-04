import os
import time
import requests
from flask import Flask

app = Flask(__name__)

# --- CẤU HÌNH THÔNG TIN ---
TELEGRAM_BOT_TOKEN = "8847660116:AAFkfEUug-7lJKuvLQv4KF8qI_atg71H8yY"
TELEGRAM_CHAT_ID = "8836493753"

THUEAPIBANK_API_KEY = "fdfe3b83d9001aa2cae3a18d6c76a105"
ZALOPAY_PHONE = "0961179716"

# Bộ nhớ tạm lưu các mã giao dịch đã xử lý (tránh báo trùng)
processed_trans = set()


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print("Lỗi gửi Telegram:", e)


@app.route("/cron-check", methods=["GET"])
def cron_check():
    """Hàm này sẽ được Cronjob gọi định kỳ để kiểm tra tiền vào"""
    try:
        # Gọi API thueapibank lấy lịch sử giao dịch ZaloPay
        # (Lưu ý: URL API bên dưới khớp với định dạng v1 trong tài liệu thueapibank của bạn)
        api_url = f"https://api.thueapibank.vn/v1/history/zalopay?token={THUEAPIBANK_API_KEY}&phone={ZALOPAY_PHONE}"
        response = requests.get(api_url, timeout=10)
        res_data = response.json()

        # Kiểm tra nếu lấy dữ liệu thành công
        if res_data.get("status") == True or res_data.get("code") == 200:
            transactions = res_data.get("data", [])

            for trans in transactions:
                trans_id = str(trans.get("trans_id") or trans.get("id"))
                amount = trans.get("amount", 0)
                comment = trans.get("comment") or trans.get("description") or ""

                # Chỉ xử lý giao dịch CỘNG TIỀN và CHƯA XỬ LÝ
                if amount > 0 and trans_id not in processed_trans:
                    processed_trans.add(trans_id)

                    # Tạo nội dung thông báo
                    msg = (
                        f"🎉 **CÓ GIAO DỊCH ZALOPAY MỚI!**\n\n"
                        f"💵 **Số tiền:** `+{amount:,.0f} VNĐ`\n"
                        f"📝 **Nội dung:** `{comment}`\n"
                        f"🆔 **Mã GD:** `{trans_id}`\n"
                        f"⏰ **Thời gian:** Vừa xong"
                    )

                    # Gửi tin nhắn về Telegram
                    send_telegram(msg)

            return "OK - Checked", 200
        else:
            return f"API Error: {res_data.get('message')}", 400

    except Exception as e:
        return f"Server Error: {str(e)}", 500


@app.route("/")
def home():
    return "Bot AutoBank đang hoạt động!", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)