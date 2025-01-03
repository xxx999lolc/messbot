import time
import requests
import sqlite3
import schedule
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from flask import Flask, request, jsonify
from threading import Thread

# Khai báo token và ID người dùng của Facebook
FB_PAGE_ACCESS_TOKEN = 'your_facebook_page_access_token'  # Token của bạn
FB_USER_ID = 'user_id_here'  # ID người dùng bạn muốn gửi ảnh vào Messenger

# Cấu hình trình duyệt Chrome để chạy Selenium mà không mở cửa sổ
chrome_options = Options()
chrome_options.add_argument("--headless")  # Chạy mà không mở cửa sổ trình duyệt

# Đảm bảo bạn đã tải và chỉ định đúng đường dẫn đến ChromeDriver
driver_service = Service("path/to/chromedriver")  # Thay bằng đường dẫn tới ChromeDriver của bạn

# Tạo ứng dụng Flask
app = Flask(__name__)

# Kết nối và tạo cơ sở dữ liệu SQLite
def init_db():
    conn = sqlite3.connect('web_capture_history.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS capture_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT,
        status TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    conn.commit()
    conn.close()

# Hàm thêm một bản ghi vào cơ sở dữ liệu
def insert_capture_history(url, status="Chưa xử lý"):
    conn = sqlite3.connect('web_capture_history.db')
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO capture_history (url, status)
    VALUES (?, ?)
    ''', (url, status))
    conn.commit()
    conn.close()

# Hàm cập nhật trạng thái công việc trong cơ sở dữ liệu
def update_capture_status(url, status):
    conn = sqlite3.connect('web_capture_history.db')
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE capture_history
    SET status = ?
    WHERE url = ?
    ''', (status, url))
    conn.commit()
    conn.close()

# Hàm chụp ảnh trang web
def capture_website(url, filename):
    driver = webdriver.Chrome(service=driver_service, options=chrome_options)
    driver.get(url)
    time.sleep(5)  # Đợi trang web tải xong
    driver.save_screenshot(filename)
    driver.quit()
    print(f"Screenshot saved as {filename}")

# Hàm gửi ảnh qua Messenger
def send_image_to_messenger(user_id, image_path, access_token):
    url = f"https://graph.facebook.com/v11.0/me/messages?access_token={access_token}"

    # Đọc ảnh
    with open(image_path, 'rb') as img:
        files = {
            'attachment': ('image.png', img, 'image/png')
        }
        payload = {
            "recipient": {"id": user_id},
            "message": {"attachment": {"type": "image", "payload": {}}}
        }

        response = requests.post(url, data=payload, files=files)
        print(response.text)

# Công việc chính: chụp ảnh và gửi sau 15 phút
def job(url):
    # Cập nhật trạng thái là "Đang xử lý"
    update_capture_status(url, "Đang xử lý")
    
    # Chụp ảnh và gửi ảnh
    capture_website(url, "screenshot.png")
    send_image_to_messenger(FB_USER_ID, "screenshot.png", FB_PAGE_ACCESS_TOKEN)
    
    # Cập nhật trạng thái là "Hoàn thành"
    update_capture_status(url, "Hoàn thành")

# Lên lịch công việc gửi ảnh sau 15 phút
def schedule_job(url):
    schedule.every(15).minutes.do(job, url=url)

# Tạo API nhận URL từ người dùng và bắt đầu bot
@app.route('/start-bot', methods=['POST'])
def start_bot():
    data = request.get_json()  # Nhận dữ liệu JSON từ yêu cầu POST
    url = data.get('url')  # Lấy URL từ yêu cầu JSON
    
    if not url:
        return jsonify({"error": "URL is required"}), 400
    
    # Lưu URL vào cơ sở dữ liệu với trạng thái "Chưa xử lý"
    insert_capture_history(url, status="Chưa xử lý")
    
    # Bắt đầu công việc chụp ảnh và gửi
    schedule_job(url)
    
    return jsonify({"message": f"Bot started for {url}"}), 200

# API để lấy lịch sử chụp ảnh
@app.route('/history', methods=['GET'])
def get_history():
    conn = sqlite3.connect('web_capture_history.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM capture_history ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for row in rows:
        history.append({
            "id": row[0],
            "url": row[1],
            "status": row[2],
            "timestamp": row[3]
        })
    
    return jsonify({"history": history})

# Hàm chạy Flask và lịch trình trong cùng một thời gian
def run_flask():
    app.run(debug=True, use_reloader=False, host="0.0.0.0", port=5000)

# Hàm chạy lịch trình
def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    # Khởi tạo cơ sở dữ liệu SQLite
    init_db()

    # Chạy Flask và lịch trình đồng thời
    thread1 = Thread(target=run_flask)
    thread2 = Thread(target=run_schedule)

    thread1.start()
    thread2.start()
