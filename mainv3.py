import csv
import re
import time
import random
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

URL = "https://titv.vn"
RUN_CSV = "titv_courses_and_lessons.csv"
U_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

def dondep_price(price_str: str) -> int:
    if not price_str:
        return 0
    price_str = price_str.strip().lower()
    if "free" in price_str or price_str == "0":
        return 0
    digits = re.sub(r"[^\d]", "", price_str)
    return int(digits) if digits else 0

def Cào_titv_courses():
    courses_list = []
    final_data = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=U_AGENT)
        page = context.new_page()
        print("====== BƯỚC 1: Đang kết nối tới TITV.vn để lấy danh sách khóa học... ======")
        try:
            page.goto(URL, wait_until="networkidle", timeout=40000)
        except Exception as e:
            print(f"Không thể tải trang: {e}")
            browser.close()
            return

        print("Đang phân tích cấu trúc khóa học...")
        course_blocks = page.locator("h3").all()
        seen_titles = set()
        
        for block in course_blocks:
            title = block.inner_text().strip()
            if not title or title in seen_titles:
                continue
                
            if "[Video]" in title or "Toán rời rạc" in title or "Quản trị" in title:
                seen_titles.add(title)

                try:
                    parent = block.locator("xpath=./..")
                    parent_text = parent.inner_text()
                    price_match = re.search(r"(\d{1,3}(?:,\d{3})*\s*đ|Free)", parent_text, re.IGNORECASE)
                    raw_price = price_match.group(1) if price_match else "Free"
                except Exception:
                    raw_price = "Free"
                
                price_value = dondep_price(raw_price)

                course_url = URL
                try:
                    if block.get_attribute("href"):
                        course_url = urljoin(URL, block.get_attribute("href"))
                    elif parent.get_attribute("href"):
                        course_url = urljoin(URL, parent.get_attribute("href"))
                    else:
                        href_elem = block.locator("xpath=./ancestor::a").first
                        if href_elem.count() > 0:
                            course_url = urljoin(URL, href_elem.get_attribute("href"))
                except Exception:
                    pass

                courses_list.append({
                    "name": title,
                    "price": price_value,
                    "type": "Miễn phí" if price_value == 0 else "Có phí",
                    "url": course_url
                })
                print(f"Found: {title} -> {price_value:,}₫ (Link: {course_url})")

        print("\n====== BƯỚC 2: Tiến hành vào từng khóa học để cào bài học chi tiết... ======")
        
        for idx, course in enumerate(courses_list, 1):
            c_url = course["url"]
            print(f"[{idx}/{len(courses_list)}] Đang quét bài học khóa: {course['name']}")

            if c_url == URL or "/courses-page/" not in c_url:
                print("Không tìm thấy link bài học riêng, bỏ qua chi tiết.")
                final_data.append({
                    "Course Name": course["name"],
                    "Price": course["price"],
                    "Type": course["type"],
                    "Lesson Title": "Nội dung trọn gói tại trang chính",
                    "Lesson URL": c_url
                })
                continue
                
            try:
                page.goto(c_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(1000) 
                lesson_nodes = page.locator(f'a[href^="{c_url}"]').all()
                lessons_dict = {}
                
                for node in lesson_nodes:
                    l_href = node.get_attribute("href")
                    l_text = node.inner_text().strip()
                    
                    if l_href and l_text:
                        full_l_url = urljoin(c_url, l_href).split("?")[0].split("#")[0]
                        # Loại trừ link trùng với trang tổng khóa học
                        if full_l_url.strip("/") != c_url.strip("/"):
                            if full_l_url not in lessons_dict:
                                clean_text = " ".join(l_text.replace("\n", " ").split())
                                lessons_dict[full_l_url] = clean_text
                
                # Nếu tìm thấy danh sách bài học con
                if lessons_dict:
                    print(f"Tìm thấy {len(lessons_dict)} bài học.")
                    for l_url, l_title in lessons_dict.items():
                        final_data.append({
                            "Course Name": course["name"],
                            "Price": course["price"],
                            "Type": course["type"],
                            "Lesson Title": l_title,
                            "Lesson URL": l_url
                        })
                else:
                    print("Không tìm thấy danh sách bài học riêng lẻ.")
                    final_data.append({
                        "Course Name": course["name"],
                        "Price": course["price"],
                        "Type": course["type"],
                        "Lesson Title": "Trọn bộ nội dung",
                        "Lesson URL": c_url
                    })
                    
            except Exception as e:
                print(f"Lỗi khi tải chi tiết khóa học: {e}")
                final_data.append({
                    "Course Name": course["name"],
                    "Price": course["price"],
                    "Type": course["type"],
                    "Lesson Title": "Lỗi tải trang bài học",
                    "Lesson URL": c_url
                })
            time.sleep(random.uniform(1.0, 2.0))

        browser.close()

    if not final_data:
        print("Không thu thập được dữ liệu nào.")
        return

    fieldnames = ["Course Name", "Price", "Type", "Lesson Title", "Lesson URL"]
    with open(RUN_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(final_data)
        
    print(f"\n Đã lưu cấu trúc {len(final_data)} dòng dữ liệu khóa/bài học vào {RUN_CSV}")

if __name__ == "__main__":
    Cào_titv_courses()