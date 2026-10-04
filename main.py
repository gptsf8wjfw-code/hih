import os
import random
import requests
from flask import Flask, request

app = Flask(__name__)

# --- CẤU HÌNH THÔNG TIN BẠN CẦN ĐIỀN ---
TELEGRAM_BOT_TOKEN = "8847660116:AAFkfEUug-7lJKuvLQv4KF8qI_atg71H8yY"
THUEAPIBANK_API_KEY = "fdfe3b83d9001aa2cae3a18d6c76a105"
ACCOUNT_ID = "467"  # ID tài khoản ZaloPay trên Thueapibank của bạn

# --- CẤU HÌNH NHẬN TIỀN (ZALOPAY / BANK) ---
BANK_ID = "MB"            # Mã ngân hàng (VD: MB, VCB, ZALOPAY)
ACCOUNT_NO = "0987654321" # Số tài khoản/SĐT nhận tiền
ACCOUNT_NAME = "NGUYEN VAN A" # Tên chủ tài khoản

# Lưu trữ hóa đơn tạm thời (Trong thực tế nên lưu vào Database/File)
# Cấu trúc: { "NỘI_DUNG_NAP": {"chat_id": 12345, "amount": 2000, "status": "pending"} }
pending_orders = {}
processed_trans = set()

# --- HÀM GỬI ANH/TIN NHẮN TELEGRAM ---
def send_telegram_photo(chat_id, photo_url, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": chat_id,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Lỗi gửi ảnh Telegram:", e)

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print("Lỗi gửi tin nhắn Telegram:", e)

# --- WEBHOOK NHẬN LỆNH TỪ TELEGRAM (/nap 2000) ---
@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    if not data or "message" not in data:
        return "OK", 200

    message = data["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    # Xử lý lệnh /nap <số_tiền>
    if text.startswith("/nap"):
        parts = text.split()
        if len(parts) >= 2 and parts[1].isdigit():
            amount = int(parts[1])
            
            if amount < 1000:
                send_telegram_message(chat_id, "❌ Số tiền nạp tối thiểu là 1,000 VNĐ!")
                return "OK", 200

            # Tạo nội dung nạp ngẫu nhiên để không bị trùng (VD: NAP8392)
            rand_code = random.randint(1000, 9999)
            memo = f"NAP{rand_code}"

            # Lưu đơn hàng chờ thanh toán
            pending_orders[memo] = {
                "chat_id": chat_id,
                "amount": amount,
                "status": "pending"
            }

            # Tạo link ảnh VietQR tự động điền sẵn thông tin
            qr_url = f"https://img.vietqr.io/image/{BANK_ID}-{ACCOUNT_NO}-compact2.png?amount={amount}&addInfo={memo}&accountName={ACCOUNT_NAME}"

            caption = (
                f"💳 **YÊU CẦU NẠP TIỀN**\n\n"
                f"💵 **Số tiền:** `{amount:,.0f} VNĐ`\n"
                f"📝 **Nội dung CK:** `{memo}` (BẮT BUỘC KHÔNG SỬA)\n\n"
                f"📌 *Vui lòng quét mã QR trên để chuyển khoản. Hệ thống sẽ tự động xác nhận khi nhận được tiền!*"
            )

            send_telegram_photo(chat_id, qr_url, caption)
        else:
            send_telegram_message(chat_id, "⚠️ Cú pháp không đúng! Vui lòng gõ: `/nap <số_tiền>`\n\nVí dụ: `/nap 2000`")

    return "OK", 200

# --- CRON CHECK KIỂM TRA LỊCH SỬ GIAO DỊCH ---
@app.route('/cron-check', methods=['GET'])
def cron_check():
    try:
        api_url = f"https://thueapibank.vn/api/zalopay/history/{ACCOUNT_ID}?token={THUEAPIBANK_API_KEY}"
        response = requests.get(api_url, timeout=10)
        
        if response.status_code != 200:
            return f"Error HTTP {response.status_code}", 200

        res_data = response.json()
        transactions = res_data.get('data') or res_data.get('history') or []

        for trans in transactions:
            trans_id = str(trans.get('trans_id') or trans.get('tranId') or trans.get('id'))
            amount = trans.get('amount', 0)
            comment = str(trans.get('comment') or trans.get('description') or trans.get('content') or "").upper()

            if amount > 0 and trans_id not in processed_trans:
                # Kiểm tra xem nội dung chuyển khoản có trùng với đơn hàng nào đang chờ không
                for memo, order in list(pending_orders.items()):
                    if memo in comment and amount >= order["amount"] and order["status"] == "pending":
                        # Đánh dấu đã xử lý
                        processed_trans.add(trans_id)
                        order["status"] = "done"

                        # Gửi thông báo DONE cho người dùng
                        success_msg = (
                            f"✅ **THANH TOÁN THÀNH CÔNG! (DONE)**\n\n"
                            f"💵 **Số tiền đã nhận:** `+{amount:,.0f} VNĐ`\n"
                            f"📝 **Nội dung:** `{memo}`\n"
                            f"🆔 **Mã GD:** `{trans_id}`\n\n"
                            f"🎉 Cảm ơn bạn, tài khoản đã được xử lý!"
                        )
                        send_telegram_message(order["chat_id"], success_msg)
                        
                        # Xóa đơn hàng khỏi danh sách chờ
                        del pending_orders[memo]
                        break

        return "OK - Checked", 200

    except Exception as e:
        print("Lỗi Python Server:", str(e))
        return f"Python Exception: {str(e)}", 200

@app.route('/')
def home():
    return "Bot Telegram Auto QR đang hoạt động!", 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
