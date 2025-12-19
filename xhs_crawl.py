# crawl_xhs_univ.py
import os, re, time, csv, json, datetime, pathlib
from tqdm import tqdm
from playwright.sync_api import sync_playwright
from xhs import XhsClient, DataFetchError

# ---------- 全局配置 ----------
STEALTH_JS = "stealth.min.js"
COOKIE = (
    "a1=19b3550178fkwgeo0t7tl19f70ykjc7wfju47o1r150000173191;"               # <---- 按实际填写
    " web_session=040069b07bb8a0567dcd96b9713b4bfa3f0ca3;"
    " webId=411687a837778dde2e39d2931562a9ac"
)
MAX_PAGES   = 50    # 每所高校最多翻多少页
SLEEP_LIST  = 0.6    # 列表翻页限速(s)
SLEEP_DETAIL= 0.4    # 详情接口限速(s)
EXPORT_EXCEL= True   # 是否导出 Excel（多工作表）
EXPORT_CSV  = True   # 是否同时导出单独 CSV
BATCH_SIZE = 1      # 每处理 10 条保存一次

# 8 所高校映射  {学校中文名: user_id}
UNIVS = {
    "上海交通大学": "6391838f000000001f01882f",
    "清华大学":     "5e8ee437000000000100807e",
    "北京大学":     "5760cdcf6a6a696a7b9f2e32",
    "浙江大学":     "645b359d0000000029010db6",
    "复旦大学":     "5ef1a86f000000000101f473",
    "西安交通大学": "63c154990000000026012c81",
    "哈尔滨工业大学": "6699038d000000002401f004",
    "南京大学":     "654c3cb90000000004008c5b",
}

# ---------- 工具函数 ----------
def parse_cn_count(s: str | None) -> int:
    if not s:
        return 0
    s = s.strip().replace(",", "").rstrip("+")
    scale = 1
    if re.search(r"[万wW]", s):
        scale, s = 10_000, re.sub(r"[万wW]", "", s)
    elif "亿" in s:
        scale, s = 100_000_000, s.replace("亿", "")
    try:
        return int(float(s) * scale)
    except ValueError:
        return 0

def sign(uri, data=None, a1="", web_session=""):
    """调用浏览器执行 _webmsxyw 生成 x-s/x-t"""
    for _ in range(3):
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                ctx = browser.new_context()
                ctx.add_init_script(path=STEALTH_JS)
                page = ctx.new_page()
                page.goto("https://www.xiaohongshu.com")
                ctx.add_cookies([
                    {"name": "a1",          "value": a1,          "domain": ".xiaohongshu.com", "path": "/"},
                    {"name": "web_session", "value": web_session, "domain": ".xiaohongshu.com", "path": "/"},
                ])
                page.reload()
                time.sleep(1)
                sig = page.evaluate("([url, body]) => window._webmsxyw(url, body)", [uri, data])
                return {"x-s": sig["X-s"], "x-t": str(sig["X-t"])}
        except Exception:
            pass
    raise RuntimeError("sign failed after retries")

client = XhsClient(COOKIE, sign=sign)

# ---------- 保存已处理 ID ---------- 
def load_processed_ids(file_path="processed_ids.json"):
    """加载已爬取的笔记 ID 列表"""
    if pathlib.Path(file_path).exists():
        with open(file_path, "r", encoding="utf-8") as f:
            return set(json.load(f))  # 返回集合去重
    return set()

def save_processed_ids(ids, file_path="processed_ids.json"):
    """保存已爬取的笔记 ID 列表"""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(list(ids), f, ensure_ascii=False, indent=2)
        
# ---------- 核心爬取函数 ----------
def fetch_with_retry(client, note_id: str, xsec_token: str, retries=3):
    """
    尝试访问详情接口，如果返回 300013 错误（频次限制），等待并重试。
    """
    attempt = 0
    while attempt < retries:
        try:
            note = client.get_note_by_id(note_id, xsec_token)
            return note
        except DataFetchError as e:
            print(f"频次限制错误，正在重试...（尝试 {attempt + 1}/{retries}）")
            time.sleep(30)  # 等待 30 秒再重试
            attempt += 1
            continue
    raise RuntimeError("重试次数用尽，无法获取详情")

def crawl_user_notes(user_id: str, univ: str, max_pages=50, need_detail=True):
    cursor, rows = "", []
    processed_ids = load_processed_ids()  # 加载已爬取的 ID
    
    total = 500
    # 使用 tqdm 显示进度条，total 为预计爬取的总笔记数，dynamic_ncols 为自动调整进度条宽度
    with tqdm(total=total, dynamic_ncols=True, desc=f"Fetching notes for {univ}") as pbar:
        for _ in range(max_pages):
            res = client.get_user_notes(user_id=user_id, cursor=cursor)
            notes, cursor, has_more = res["notes"], res["cursor"], res["has_more"]

            for n in notes:
                note_id = n["note_id"]
                if note_id in processed_ids:  # 跳过已爬取的笔记
                    continue

                rows.append({
                    "note_id"      : note_id,
                    "xsec_token"   : n.get("xsec_token", ""),
                    "type"         : n.get("type", ""),
                    "title"        : n.get("display_title", ""),
                    "like_count"   : 0,
                    "collect_count": 0,
                    "share_count"  : 0,
                    "comment_count": 0,
                    "publish_time" : "",
                    "content"      : "",
                })

                r = rows[-1]
                try:
                    note = fetch_with_retry(client, r["note_id"], r["xsec_token"])  # 使用重试函数
                    inter = note.get("interact_info", {})
                    r["like_count"]    = parse_cn_count(inter.get("liked_count"))
                    r["collect_count"] = parse_cn_count(inter.get("collected_count"))
                    r["share_count"]   = parse_cn_count(inter.get("share_count"))
                    r["comment_count"] = parse_cn_count(inter.get("comment_count"))
                    r["content"]       = note.get("desc", "").replace("\n", " ").strip()

                    ts = note.get("time") or note.get("create_time") or note.get("last_update_time", 0)
                    if ts:
                        if len(str(ts)) > 10:  # 毫秒 -> 秒
                            ts = int(ts) / 1000
                        r["publish_time"] = datetime.datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
                except DataFetchError:
                    pass
                time.sleep(SLEEP_DETAIL)
                
                processed_ids.add(note_id)  # 加入已处理 ID 集合

                # 更新进度条
                pbar.update(1)

                if len(rows) % BATCH_SIZE == 0:  # 每 10 条保存一次
                    save_processed_ids(processed_ids)
                    # 导出到 CSV
                    if EXPORT_CSV:
                        save_to_csv(rows, univ)
                    rows.clear()  # 清空已爬取的记录

            if not has_more or not cursor:
                break
            time.sleep(SLEEP_LIST)

    return rows

def save_to_csv(rows, univ):
    """保存数据到 CSV，如果文件已存在，则追加数据"""
    if EXPORT_CSV:
        csv_path = pathlib.Path("output") / f"{univ}_notes.csv"

        # 如果文件已存在，设置 mode='a'（追加），如果文件不存在，则设置为 'w'（覆盖）
        file_exists = os.path.exists(csv_path)
        
        with csv_path.open("a" if file_exists else "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "note_id", "xsec_token", "type", "title", "content",
                "like_count", "collect_count", "share_count", "comment_count",
                "publish_time"
            ])
            
            # 如果文件不存在，则写入表头
            if not file_exists:
                writer.writeheader()

            # 写入数据行
            writer.writerows(rows)
        print(f"CSV saved → {csv_path}")
        
# ---------- 主流程 ----------
def main():
    pathlib.Path("output").mkdir(exist_ok=True)
    all_sheets = {}          # 用于 Excel 导出

    for univ, uid in UNIVS.items():
        print(f"\n=== {univ} ({uid}) ===")
        data = crawl_user_notes(uid, univ, max_pages=MAX_PAGES, need_detail=True)
        print(f"{univ}: fetched {len(data)} notes")

        # 用于 Excel
        all_sheets[univ] = data

    # --- 导出多工作表 Excel ---
    if EXPORT_EXCEL:
        import pandas as pd
        xlsx_path = pathlib.Path("output/xhs_univ_notes.xlsx")
        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
            for univ, rows in all_sheets.items():
                pd.DataFrame(rows).to_excel(writer, sheet_name=univ[:30], index=False)
        print(f"\nExcel saved → {xlsx_path}")

if __name__ == "__main__":
    main()
