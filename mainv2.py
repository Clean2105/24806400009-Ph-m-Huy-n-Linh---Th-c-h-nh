import csv
import random
import re
import time
import urllib.robotparser 
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

URL = "https://gochek.vn"
COLLECTION_TO_URL = f"{URL}/collections/all"
RUN_CSV = "gochek_product.csv"
U_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

def check_robots(url: str) -> bool:
    try:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url("https://gochek.vn") 
        rp.read()
        allow_url = rp.can_fetch("*", url)
        print(f"Robots.txt cho phép cào: '{url}': {allow_url}")
        return allow_url
    except Exception as e:
        print(f"Không thể kiểm tra file robots.txt ({e}), hãy cẩn trọng!")   
        return True  

def ketnoi_product(page) -> list[str]:
    "Lấy toàn bộ link sản phẩm trong danh mục"
    links = set()
    page_num = 1
    
    while True:
        url = COLLECTION_TO_URL if page_num == 1 else f"{COLLECTION_TO_URL}?page={page_num}"
        try:
            page.goto(url, wait_until="networkidle", timeout=40000)
            
            page.wait_for_timeout(1500) 
            locator = page.locator('a[href*="/products/"]')
            hrefs = locator.all_attribute_values("href")
            
            new_links = {urljoin(URL, h) for h in hrefs if h}
            before = len(links)
            links.update(new_links)
            
            print(f"Trang {page_num}: tìm thấy {len(new_links)} link, tổng cộng {len(links)}")
            
            if len(links) == before or page_num > 30:
                break
            page_num += 1
            
        except PWTimeout:
            print(f"Timeout tải trang {page_num}, dừng phân trang.")
            break
        except Exception as e:
            print(f"Gặp lỗi tại trang {page_num}: {e}. Đang thử tiếp tục...")
            page_num += 1
            if page_num > 30:
                break
        
    return sorted(links)

def price_text(text: str):
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None 

def scrape_product(page, url: str) -> dict:
    data = {"url": url}
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_selector("h1", timeout=10000)

        def meta(prop):
            try:
                return page.get_attribute(f'meta[property="{prop}"]', "content")
            except Exception:
                return None

        data["name"] = meta("og:title") or page.locator("h1").first.inner_text().strip()
        data["image"] = meta("og:image")
        price_amount = meta("og:price:amount")
        data["price"] = int(price_amount) if price_amount else None

        try:
            old_price_text = page.locator("s, del, .old-price, .price-old").first.inner_text(timeout=2000)
            data["old_price"] = price_text(old_price_text)
        except Exception:
            data["old_price"] = None

        page_text = page.locator("body").inner_text()
        data["in_stock"] = "Hết hàng" not in page_text[:3000]

        print(f"OK  - {data['name']} - {data['price']}₫")
    except Exception as e:
        print(f"BỊ LỖI THU THẬP - {url}: {e}")
        data["name"] = None
        data["price"] = None
        data["old_price"] = None
        data["in_stock"] = None

    return data

def main():
    check_robots(COLLECTION_TO_URL)
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(user_agent=U_AGENT)
        page = context.new_page()

        print("Đang thu thập danh sách link sản phẩm...")
        product_links = ketnoi_product(page)
        print(f"\nTổng cộng {len(product_links)} sản phẩm cần cào.\n")
        
        for i, url in enumerate(product_links, 1):
            print(f"[{i}/{len(product_links)}] {url}")
            results.append(scrape_product(page, url))
            time.sleep(random.uniform(1.0, 2.5)) 
       
        browser.close()

    if not results:
        print("Không thu thập được dữ liệu nào.")
        return

    fieldnames = ["name", "price", "old_price", "in_stock", "image", "url"]
    with open(RUN_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"\nĐã lưu {len(results)} sản phẩm vào {RUN_CSV}")
       
    # Phân tích số liệu nhanh
    valid = [r for r in results if r.get("price")]
    if valid:
        prices = [r["price"] for r in valid]
        in_stock_count = sum(1 for r in results if r.get("in_stock"))
        out_of_stock_count = sum(1 for r in results if r.get("in_stock") is False)
        on_sale_count = sum(1 for r in results if r.get("old_price"))
   
        print("\n--- PHÂN TÍCH NHANH ---")
        print(f"Tổng số sản phẩm thành công: {len(valid)}/{len(results)}")
        print(f"Còn hàng: {in_stock_count} | Hết hàng: {out_of_stock_count}")
        print(f"Đang giảm giá: {on_sale_count}")
        print(f"Giá thấp nhất: {min(prices):,}₫")
        print(f"Giá cao nhất: {max(prices):,}₫")
        print(f"Giá trung bình: {sum(prices)//len(prices):,}₫")
       
if __name__ == "__main__":
    main()