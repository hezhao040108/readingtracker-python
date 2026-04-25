# -*- coding: utf-8 -*-
"""
读书打卡系统 V3.1:单文件傻瓜式桌面版

核心升级：
1. 单一 GUI 主程序，不再把日常操作分散到多个脚本；
2. 支持 PyInstaller 打包为 exe;
3. 首次使用向导；
4. 简洁打卡 / 深度打卡；
5. 推迟、跳过、暂停、补读、临时加书；
6. 历史打卡查看、修改、删除；
7. 月历视图；
8. 一键备份与恢复；
9. 更友好的错误提示；
10. 系统建议：根据完成率、阅读速度、拖延情况给出调整建议。

依赖：
- Python 3.10+
- tkinter:Python 标准库，提供 GUI 支持
- matplotlib:用于统计图表显示

运行：
python reading_app_v3.py

打包：
pip install pyinstaller matplotlib
pyinstaller --onefile --noconsole --name 读书打卡系统 reading_app_v3.py
"""

import csv
import json
import os
import shutil
import smtplib
import ssl
import subprocess
import sys
import tempfile
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, scrolledtext


# =========================
# 一、路径与字段
# =========================

# 兼容源码运行与 PyInstaller 打包运行。
# 源码运行时：APP_DIR = .py 文件所在目录
# exe 运行时：APP_DIR = exe 文件所在目录
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
    APP_EXECUTABLE = Path(sys.executable).resolve()
else:
    APP_DIR = Path(__file__).resolve().parent
    APP_EXECUTABLE = Path(__file__).resolve()

DATA_DIR = APP_DIR / "data"
REPORT_DIR = APP_DIR / "reports"
FIG_DIR = APP_DIR / "figures"
BACKUP_DIR = APP_DIR / "backup"

BOOKS_FILE = DATA_DIR / "books.csv"
CONFIG_FILE = DATA_DIR / "config.json"
PLAN_FILE = DATA_DIR / "reading_plan.csv"
LOG_FILE = DATA_DIR / "reading_log.csv"
NOTES_FILE = DATA_DIR / "reading_notes.csv"
SUMMARY_FILE = DATA_DIR / "reading_summary.csv"

BOOK_FIELDS = [
    "书名", "作者", "总页数", "已读页数", "类别", "难度", "优先级",
    "是否必读", "状态", "备注"
]

PLAN_FIELDS = [
    "计划ID", "日期", "星期", "任务类型", "书名", "作者", "类别", "难度",
    "计划起始页", "计划结束页", "计划页数", "计划分钟", "完成状态", "是否复盘", "备注"
]

LOG_FIELDS = [
    "记录ID", "打卡时间", "日期", "计划ID", "书名", "计划起始页", "计划结束页",
    "实际起始页", "实际结束页", "实际页数", "阅读分钟", "完成状态",
    "理解程度", "论证拆解", "反驳质量", "现实迁移", "今日评分", "打卡模式", "一句话总结"
]

NOTE_FIELDS = [
    "记录ID", "记录时间", "日期", "书名", "阅读范围", "核心概念", "作者观点",
    "论证链", "关键证据", "隐含前提", "可反驳之处", "可迁移观点",
    "心理学或法学连接", "今日问题"
]

SUMMARY_FIELDS = [
    "记录ID", "记录时间", "日期", "类型", "本周完成", "三个概念",
    "最有说服力观点", "最可疑观点", "改变的看法", "下周调整"
]

INTENSITY_PRESETS = {
    "轻量": {"daily_minutes": 25, "base_pages": 20, "reading_weekdays": [1, 2, 3, 4, 5]},
    "标准": {"daily_minutes": 45, "base_pages": 35, "reading_weekdays": [1, 2, 3, 4, 5, 6]},
    "高强度": {"daily_minutes": 75, "base_pages": 60, "reading_weekdays": [1, 2, 3, 4, 5, 6]},
    "冲刺": {"daily_minutes": 120, "base_pages": 90, "reading_weekdays": [1, 2, 3, 4, 5, 6, 7]},
}

DIFFICULTY_COEFFICIENT = {1: 0.70, 2: 0.85, 3: 1.00, 4: 1.25, 5: 1.55}
WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

DEFAULT_CONFIG = {
    "是否已完成首次向导": False,
    "开始日期": date.today().isoformat(),
    "计划天数": 90,
    "阅读强度": "标准",
    "排期模式": "按优先级顺序",
    "是否每周复盘": True,
    "每周复盘星期": 7,
    "是否自动重排": True,
    "重排缓冲天数": 5,
    "每日提醒时间": "08:00",
    "打卡提醒时间": "21:30",
    "邮件提醒": {
        "是否启用": False,
        "收件邮箱": "",
        "发件邮箱": "",
        "SMTP服务器": "smtp.qq.com",
        "SMTP端口": 465,
        "SMTP密码环境变量": "READING_SMTP_PASSWORD"
    }
}

SAMPLE_BOOKS = [
    {"书名": "《万物简史》", "作者": "Bill Bryson", "总页数": "544", "已读页数": "0", "类别": "科学通识", "难度": "1", "优先级": "1", "是否必读": "是", "状态": "未开始", "备注": "从自然科学整体图景开始。"},
    {"书名": "《人类简史》", "作者": "Yuval Noah Harari", "总页数": "440", "已读页数": "0", "类别": "历史与社会思想", "难度": "1", "优先级": "2", "是否必读": "是", "状态": "未开始", "备注": "训练宏大叙事的理解与怀疑。"},
    {"书名": "《思考，快与慢》", "作者": "Daniel Kahneman", "总页数": "512", "已读页数": "0", "类别": "认知心理与决策", "难度": "3", "优先级": "3", "是否必读": "是", "状态": "未开始", "备注": "理解判断偏差和启发式。"},
]


# =========================
# 二、通用工具
# =========================

def ensure_dirs():
    for p in [DATA_DIR, REPORT_DIR, FIG_DIR, BACKUP_DIR]:
        p.mkdir(parents=True, exist_ok=True)


def today_str():
    return date.today().isoformat()


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def record_id():
    return datetime.now().strftime("%Y%m%d%H%M%S%f")


def safe_int(value, default=0):
    try:
        if value is None or str(value).strip() == "":
            return default
        return int(float(str(value).strip()))
    except Exception:
        return default


def safe_float(value, default=0.0):
    try:
        if value is None or str(value).strip() == "":
            return default
        return float(str(value).strip())
    except Exception:
        return default


def parse_date_safe(text, default=None):
    try:
        return datetime.strptime(str(text).strip(), "%Y-%m-%d").date()
    except Exception:
        return default if default is not None else date.today()


def weekday_num(d):
    return d.weekday() + 1


def bool_cn(value):
    return "是" if bool(value) else "否"


def cn_bool(value):
    return str(value).strip().lower() in ["是", "true", "1", "yes", "y"]


def read_csv_dict(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv_dict(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def append_csv_dict(path, row, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def load_config():
    ensure_dirs()
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return json.loads(json.dumps(DEFAULT_CONFIG, ensure_ascii=False))

    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return json.loads(json.dumps(DEFAULT_CONFIG, ensure_ascii=False))

    cfg = json.loads(json.dumps(DEFAULT_CONFIG, ensure_ascii=False))
    cfg.update(data)
    mail = DEFAULT_CONFIG["邮件提醒"].copy()
    mail.update(cfg.get("邮件提醒", {}))
    cfg["邮件提醒"] = mail
    return cfg


def save_config(cfg):
    ensure_dirs()
    with CONFIG_FILE.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def open_path(path):
    path = Path(path)
    if not path.exists():
        messagebox.showwarning("路径不存在", f"没有找到：\n{path}")
        return
    if sys.platform.startswith("win"):
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)])
    else:
        subprocess.run(["xdg-open", str(path)])


def init_files(force=False):
    ensure_dirs()
    if force or not BOOKS_FILE.exists():
        write_csv_dict(BOOKS_FILE, SAMPLE_BOOKS, BOOK_FIELDS)
    if force or not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
    if force or not PLAN_FILE.exists():
        write_csv_dict(PLAN_FILE, [], PLAN_FIELDS)
    if force or not LOG_FILE.exists():
        write_csv_dict(LOG_FILE, [], LOG_FIELDS)
    if force or not NOTES_FILE.exists():
        write_csv_dict(NOTES_FILE, [], NOTE_FIELDS)
    if force or not SUMMARY_FILE.exists():
        write_csv_dict(SUMMARY_FILE, [], SUMMARY_FIELDS)


def normalize_book_row(row, default_priority=999):
    title = str(row.get("书名", "")).strip()
    total_pages = safe_int(row.get("总页数"), 0)
    difficulty = max(1, min(5, safe_int(row.get("难度"), 3)))
    priority = safe_int(row.get("优先级"), default_priority)
    state = str(row.get("状态", "")).strip() or "未开始"

    return {
        "书名": title,
        "作者": str(row.get("作者", "")).strip(),
        "总页数": str(total_pages),
        "已读页数": str(max(0, safe_int(row.get("已读页数"), 0))),
        "类别": str(row.get("类别", "")).strip() or "未分类",
        "难度": str(difficulty),
        "优先级": str(priority),
        "是否必读": str(row.get("是否必读", "")).strip() or "是",
        "状态": state,
        "备注": str(row.get("备注", "")).strip(),
    }


# =========================
# 三、计划逻辑
# =========================

def active_books():
    rows = read_csv_dict(BOOKS_FILE)
    result = []
    for i, row in enumerate(rows, start=1):
        b = normalize_book_row(row, i)
        if not b["书名"] or safe_int(b["总页数"]) <= 0:
            continue
        if b.get("状态") in ["暂停", "已完成", "跳过"]:
            continue
        result.append(b)
    return sorted(result, key=lambda x: (safe_int(x["优先级"], 999), x["书名"]))


def all_books():
    rows = read_csv_dict(BOOKS_FILE)
    result = []
    for i, row in enumerate(rows, start=1):
        b = normalize_book_row(row, i)
        if b["书名"] and safe_int(b["总页数"]) > 0:
            result.append(b)
    return result


def sort_books_by_mode(books, mode):
    if mode == "按类别轮换":
        grouped = defaultdict(list)
        for b in sorted(books, key=lambda x: safe_int(x["优先级"], 999)):
            grouped[b["类别"]].append(b)
        cats = sorted(grouped.keys())
        out = []
        while any(grouped.values()):
            for c in cats:
                if grouped[c]:
                    out.append(grouped[c].pop(0))
        return out
    return sorted(books, key=lambda x: (safe_int(x["优先级"], 999), x["书名"]))


def current_pages_from_logs():
    current = {}
    for b in all_books():
        current[b["书名"]] = safe_int(b.get("已读页数"), 0)

    for log in read_csv_dict(LOG_FILE):
        title = log.get("书名", "")
        end = safe_int(log.get("实际结束页"), 0)
        if title:
            current[title] = max(current.get(title, 0), end)

    totals = {b["书名"]: safe_int(b["总页数"], 0) for b in all_books()}
    for title, total in totals.items():
        current[title] = min(current.get(title, 0), total)
    return current


def get_intensity(cfg):
    name = cfg.get("阅读强度", "标准")
    return INTENSITY_PRESETS.get(name, INTENSITY_PRESETS["标准"])


def planned_pages(book, base_pages):
    diff = safe_int(book.get("难度"), 3)
    coeff = DIFFICULTY_COEFFICIENT.get(diff, 1.0)
    return max(5, int(round(base_pages / coeff)))


def generate_plan(start_date=None, days=None, keep_before=None):
    cfg = load_config()
    intensity = get_intensity(cfg)
    start = parse_date_safe(start_date or cfg.get("开始日期", today_str()))
    days = days or safe_int(cfg.get("计划天数"), 90)
    books = sort_books_by_mode(active_books(), cfg.get("排期模式", "按优先级顺序"))
    current = current_pages_from_logs()

    old_before = []
    if keep_before and PLAN_FILE.exists():
        for r in read_csv_dict(PLAN_FILE):
            d = parse_date_safe(r.get("日期"), date(1900, 1, 1))
            if d < keep_before:
                old_before.append(r)

    states = []
    for b in books:
        cur = current.get(b["书名"], safe_int(b["已读页数"], 0))
        total = safe_int(b["总页数"], 0)
        if cur < total:
            states.append({"book": b, "current": cur})

    rows = []
    pid_start = len(old_before) + 1
    plan_id = pid_start
    book_index = 0

    for i in range(days):
        d = start + timedelta(days=i)
        if keep_before and d < keep_before:
            continue

        weekday = WEEKDAY_CN[d.weekday()]
        review_day = cfg.get("是否每周复盘", True) and weekday_num(d) == safe_int(cfg.get("每周复盘星期", 7), 7)

        if review_day:
            rows.append({
                "计划ID": f"P{plan_id:05d}", "日期": d.isoformat(), "星期": weekday,
                "任务类型": "每周复盘", "书名": "本周复盘", "作者": "", "类别": "复盘", "难度": "",
                "计划起始页": "", "计划结束页": "", "计划页数": "", "计划分钟": "30",
                "完成状态": "未开始", "是否复盘": "是", "备注": "整理本周核心概念、问题和下周调整。"
            })
            plan_id += 1

        if weekday_num(d) not in intensity["reading_weekdays"]:
            rows.append({
                "计划ID": f"P{plan_id:05d}", "日期": d.isoformat(), "星期": weekday,
                "任务类型": "休息/补读", "书名": "", "作者": "", "类别": "缓冲", "难度": "",
                "计划起始页": "", "计划结束页": "", "计划页数": "", "计划分钟": "0",
                "完成状态": "未开始", "是否复盘": "否", "备注": "可用于补读、整理笔记或休息。"
            })
            plan_id += 1
            continue

        if book_index >= len(states):
            rows.append({
                "计划ID": f"P{plan_id:05d}", "日期": d.isoformat(), "星期": weekday,
                "任务类型": "自由阅读", "书名": "", "作者": "", "类别": "自由", "难度": "",
                "计划起始页": "", "计划结束页": "", "计划页数": "", "计划分钟": str(intensity["daily_minutes"]),
                "完成状态": "未开始", "是否复盘": "否", "备注": "当前书单已排完，可添加新书。"
            })
            plan_id += 1
            continue

        state = states[book_index]
        book = state["book"]
        cur = state["current"]
        total = safe_int(book["总页数"], 0)
        pages_today = planned_pages(book, intensity["base_pages"])
        start_page = cur + 1
        end_page = min(total, cur + pages_today)
        actual_pages = max(end_page - start_page + 1, 0)

        rows.append({
            "计划ID": f"P{plan_id:05d}", "日期": d.isoformat(), "星期": weekday,
            "任务类型": "阅读", "书名": book["书名"], "作者": book["作者"], "类别": book["类别"], "难度": book["难度"],
            "计划起始页": str(start_page), "计划结束页": str(end_page), "计划页数": str(actual_pages),
            "计划分钟": str(intensity["daily_minutes"]), "完成状态": "未开始", "是否复盘": "否",
            "备注": book.get("备注", "")
        })
        plan_id += 1
        state["current"] = end_page
        if end_page >= total:
            book_index += 1

    write_csv_dict(PLAN_FILE, old_before + rows, PLAN_FIELDS)


def reschedule_from(d):
    cfg = load_config()
    old = read_csv_dict(PLAN_FILE)
    if old:
        dates = [parse_date_safe(r.get("日期"), d) for r in old if r.get("日期")]
        last = max(dates) if dates else d + timedelta(days=safe_int(cfg.get("计划天数"), 90))
        days = max((last - d).days + 1, 1)
    else:
        days = safe_int(cfg.get("计划天数"), 90)
    generate_plan(start_date=d.isoformat(), days=days, keep_before=d)


def update_plan_status(plan_id, status):
    rows = read_csv_dict(PLAN_FILE)
    for r in rows:
        if r.get("计划ID") == plan_id:
            r["完成状态"] = status
            break
    write_csv_dict(PLAN_FILE, rows, PLAN_FIELDS)


def move_task_days(plan_id, delta_days=1):
    rows = read_csv_dict(PLAN_FILE)
    for r in rows:
        if r.get("计划ID") == plan_id:
            d = parse_date_safe(r.get("日期"))
            r["日期"] = (d + timedelta(days=delta_days)).isoformat()
            r["星期"] = WEEKDAY_CN[(d + timedelta(days=delta_days)).weekday()]
            r["完成状态"] = "已推迟"
            break
    write_csv_dict(PLAN_FILE, rows, PLAN_FIELDS)


def pause_or_skip_book(title, state):
    rows = read_csv_dict(BOOKS_FILE)
    found = False
    for r in rows:
        if r.get("书名") == title:
            r["状态"] = state
            found = True
            break
    write_csv_dict(BOOKS_FILE, rows, BOOK_FIELDS)
    return found


# =========================
# 四、统计、建议、备份
# =========================

def stats_data():
    books = all_books()
    logs = read_csv_dict(LOG_FILE)
    plan = read_csv_dict(PLAN_FILE)

    total_pages = sum(safe_int(r.get("实际页数"), 0) for r in logs)
    total_minutes = sum(safe_int(r.get("阅读分钟"), 0) for r in logs)
    reading_dates = sorted({r["日期"] for r in logs if safe_int(r.get("实际页数"), 0) > 0 and r.get("日期")})

    current = current_pages_from_logs()
    totals = {b["书名"]: safe_int(b["总页数"], 0) for b in books}
    cats = {b["书名"]: b["类别"] for b in books}
    diffs = {b["书名"]: safe_int(b["难度"], 3) for b in books}

    by_cat_pages = defaultdict(int)
    by_diff_pages = defaultdict(int)
    by_book_minutes = defaultdict(int)
    by_book_pages = defaultdict(int)

    for log in logs:
        title = log.get("书名", "")
        pages = safe_int(log.get("实际页数"), 0)
        minutes = safe_int(log.get("阅读分钟"), 0)
        by_cat_pages[cats.get(title, "未分类")] += pages
        by_diff_pages[str(diffs.get(title, 3))] += pages
        by_book_pages[title] += pages
        by_book_minutes[title] += minutes

    completed_plan = sum(1 for r in plan if r.get("完成状态") in ["已完成", "已复盘"])
    partial_plan = sum(1 for r in plan if r.get("完成状态") == "部分完成")
    unfinished_plan = sum(1 for r in plan if r.get("完成状态") == "未完成")
    all_due = [r for r in plan if parse_date_safe(r.get("日期"), date.today()) <= date.today()]
    due_count = len(all_due)
    done_due = sum(1 for r in all_due if r.get("完成状态") in ["已完成", "已复盘"])
    completion_rate = round(done_due / due_count * 100, 2) if due_count else 0

    avg_pages = round(total_pages / len(reading_dates), 2) if reading_dates else 0
    avg_minutes = round(total_minutes / len(reading_dates), 2) if reading_dates else 0
    pages_per_hour = round(total_pages / (total_minutes / 60), 2) if total_minutes else 0

    remaining = 0
    book_progress = []
    for b in books:
        t = b["书名"]
        total = totals.get(t, 0)
        cur = min(current.get(t, safe_int(b["已读页数"], 0)), total)
        remain = max(total - cur, 0)
        remaining += remain
        pct = round(cur / total * 100, 2) if total else 0
        book_progress.append({
            "书名": t, "类别": b["类别"], "状态": b.get("状态", "未开始"),
            "当前页": cur, "总页数": total, "剩余页数": remain, "完成率": pct
        })

    if avg_pages > 0:
        days_left = int(round(remaining / avg_pages))
        finish_date = (date.today() + timedelta(days=days_left)).isoformat()
    else:
        days_left = None
        finish_date = "暂无足够数据"

    return {
        "logs": logs,
        "plan": plan,
        "books": books,
        "累计页数": total_pages,
        "累计分钟": total_minutes,
        "阅读天数": len(reading_dates),
        "日均页数": avg_pages,
        "日均分钟": avg_minutes,
        "每小时页数": pages_per_hour,
        "剩余页数": remaining,
        "预计剩余天数": days_left,
        "预计完成日期": finish_date,
        "类别页数": dict(by_cat_pages),
        "难度页数": dict(by_diff_pages),
        "书籍进度": book_progress,
        "到期完成率": completion_rate,
        "已完成计划": completed_plan,
        "部分完成计划": partial_plan,
        "未完成计划": unfinished_plan,
        "书籍页数": dict(by_book_pages),
        "书籍分钟": dict(by_book_minutes),
    }


def system_suggestions():
    s = stats_data()
    suggestions = []

    rate = s["到期完成率"]
    cfg = load_config()
    intensity = cfg.get("阅读强度", "标准")

    if not s["logs"]:
        suggestions.append("目前还没有打卡记录。建议先完成一次简洁打卡，再观察真实阅读速度。")
        return suggestions

    if rate < 50:
        suggestions.append(f"到期任务完成率为 {rate}%。当前计划明显偏紧，建议把阅读强度从“{intensity}”降低一级，或每周增加1—2天缓冲日。")
    elif rate < 75:
        suggestions.append(f"到期任务完成率为 {rate}%。计划略偏紧，建议暂时保持强度，但减少难度4—5书籍的每日页数。")
    elif rate >= 90:
        suggestions.append(f"到期任务完成率为 {rate}%。执行情况较稳定，可以保持当前强度。若连续两周超过90%，可考虑提高强度或增加一本副书。")

    if s["每小时页数"] > 0:
        suggestions.append(f"你的平均阅读速度约为 {s['每小时页数']} 页/小时。后续计划可用这个数值校准，不要只按理想速度安排。")

    by_book_speed = []
    for title, pages in s["书籍页数"].items():
        minutes = s["书籍分钟"].get(title, 0)
        if pages > 0 and minutes > 0:
            by_book_speed.append((title, pages / (minutes / 60)))
    if by_book_speed:
        slowest = sorted(by_book_speed, key=lambda x: x[1])[0]
        suggestions.append(f"目前读得最慢的书是《{slowest[0]}》，约 {round(slowest[1], 2)} 页/小时。若它是高难度书，建议改用深度打卡，减少每日页数。")

    unfinished_recent = []
    for r in s["plan"]:
        d = parse_date_safe(r.get("日期"), date.today())
        if date.today() - timedelta(days=7) <= d <= date.today():
            if r.get("完成状态") in ["未完成", "部分完成"]:
                unfinished_recent.append(r)
    if len(unfinished_recent) >= 3:
        suggestions.append("最近7天内有3条以上未完成或部分完成任务。建议使用“推迟一天”或“补读”按钮，不要继续累积心理负担。")

    cat_pages = s["类别页数"]
    if len(cat_pages) >= 2:
        max_cat = max(cat_pages.items(), key=lambda x: x[1])
        min_cat = min(cat_pages.items(), key=lambda x: x[1])
        suggestions.append(f"当前阅读类别最多的是“{max_cat[0]}”，最少的是“{min_cat[0]}”。如果目标是拓宽知识面，建议下轮计划增加“{min_cat[0]}”或相邻领域的书。")

    return suggestions


def create_backup():
    ensure_dirs()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = BACKUP_DIR / f"reading_backup_{stamp}.zip"

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for folder in [DATA_DIR, REPORT_DIR, FIG_DIR]:
            if folder.exists():
                for p in folder.rglob("*"):
                    if p.is_file():
                        z.write(p, p.relative_to(APP_DIR))
    return out


def restore_backup(zip_path):
    zip_path = Path(zip_path)
    if not zip_path.exists():
        raise FileNotFoundError("备份文件不存在。")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(APP_DIR)


# =========================
# 五、弹窗组件
# =========================

class WizardDialog(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("首次使用向导")
        self.geometry("560x420")
        self.resizable(False, False)
        self.master = master
        self.cfg = load_config()

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="欢迎使用读书打卡系统", font=("Microsoft YaHei", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text="请先完成几个基本设置。后续都可以在主界面修改。", foreground="#555555").pack(anchor="w", pady=(4, 16))

        form = ttk.Frame(frame)
        form.pack(fill="x")

        self.start_var = tk.StringVar(value=self.cfg.get("开始日期", today_str()))
        self.days_var = tk.StringVar(value=str(self.cfg.get("计划天数", 90)))
        self.intensity_var = tk.StringVar(value=self.cfg.get("阅读强度", "标准"))
        self.mode_var = tk.StringVar(value=self.cfg.get("排期模式", "按优先级顺序"))

        rows = [
            ("开始日期", self.start_var, "entry"),
            ("计划天数", self.days_var, "entry"),
            ("阅读强度", self.intensity_var, "intensity"),
            ("排期模式", self.mode_var, "mode"),
        ]

        for i, (label, var, kind) in enumerate(rows):
            ttk.Label(form, text=label, width=12).grid(row=i, column=0, sticky="w", pady=8)
            if kind == "intensity":
                w = ttk.Combobox(form, textvariable=var, values=list(INTENSITY_PRESETS.keys()), state="readonly", width=30)
            elif kind == "mode":
                w = ttk.Combobox(form, textvariable=var, values=["按优先级顺序", "按类别轮换"], state="readonly", width=30)
            else:
                w = ttk.Entry(form, textvariable=var, width=33)
            w.grid(row=i, column=1, sticky="w", pady=8)

        btns = ttk.Frame(frame)
        btns.pack(fill="x", pady=(20, 0))

        ttk.Button(btns, text="导入书单CSV", command=self.import_books).pack(side="left", padx=4)
        ttk.Button(btns, text="使用示例书单", command=self.use_sample).pack(side="left", padx=4)
        ttk.Button(btns, text="完成并生成计划", command=self.finish).pack(side="right", padx=4)

        self.status = ttk.Label(frame, text="", foreground="#006600")
        self.status.pack(anchor="w", pady=(16, 0))

        self.grab_set()
        self.transient(master)

    def import_books(self):
        path = filedialog.askopenfilename(title="选择书单CSV", filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            rows = import_books_from_csv(path, replace=True)
            self.status.config(text=f"已导入 {len(rows)} 本书。")
        except Exception as e:
            messagebox.showerror("导入失败", friendly_error(e))

    def use_sample(self):
        write_csv_dict(BOOKS_FILE, SAMPLE_BOOKS, BOOK_FIELDS)
        self.status.config(text="已写入示例书单。")

    def finish(self):
        cfg = load_config()
        cfg["开始日期"] = self.start_var.get().strip() or today_str()
        cfg["计划天数"] = safe_int(self.days_var.get(), 90)
        cfg["阅读强度"] = self.intensity_var.get()
        cfg["排期模式"] = self.mode_var.get()
        cfg["是否已完成首次向导"] = True
        save_config(cfg)

        if not BOOKS_FILE.exists() or not read_csv_dict(BOOKS_FILE):
            write_csv_dict(BOOKS_FILE, SAMPLE_BOOKS, BOOK_FIELDS)

        try:
            generate_plan()
            self.master.refresh_all()
            self.destroy()
        except Exception as e:
            messagebox.showerror("生成计划失败", friendly_error(e))


class BookEditDialog(tk.Toplevel):
    def __init__(self, master, initial=None):
        super().__init__(master)
        self.title("编辑书籍")
        self.geometry("520x460")
        self.resizable(False, False)
        self.result = None
        initial = initial or {}

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)

        self.vars = {}
        for i, field in enumerate(BOOK_FIELDS):
            ttk.Label(frame, text=field, width=10).grid(row=i, column=0, sticky="w", pady=5)
            var = tk.StringVar(value=str(initial.get(field, "")))
            self.vars[field] = var
            if field == "难度":
                w = ttk.Combobox(frame, textvariable=var, values=["1", "2", "3", "4", "5"], state="readonly", width=36)
                if not var.get():
                    var.set("3")
            elif field == "是否必读":
                w = ttk.Combobox(frame, textvariable=var, values=["是", "否"], state="readonly", width=36)
                if not var.get():
                    var.set("是")
            elif field == "状态":
                w = ttk.Combobox(frame, textvariable=var, values=["未开始", "阅读中", "暂停", "已完成", "跳过"], state="readonly", width=36)
                if not var.get():
                    var.set("未开始")
            else:
                w = ttk.Entry(frame, textvariable=var, width=39)
            w.grid(row=i, column=1, sticky="w", pady=5)

        btns = ttk.Frame(frame)
        btns.grid(row=len(BOOK_FIELDS), column=0, columnspan=2, sticky="e", pady=12)
        ttk.Button(btns, text="取消", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="保存", command=self.save).pack(side="right", padx=4)

        self.grab_set()
        self.transient(master)

    def save(self):
        row = {f: self.vars[f].get().strip() for f in BOOK_FIELDS}
        row = normalize_book_row(row)
        if not row["书名"]:
            messagebox.showerror("错误", "书名不能为空。")
            return
        if safe_int(row["总页数"], 0) <= 0:
            messagebox.showerror("错误", "总页数必须大于0。")
            return
        self.result = row
        self.destroy()


class HistoryEditDialog(tk.Toplevel):
    def __init__(self, master, log_row, note_row=None):
        super().__init__(master)
        self.title("修改历史打卡")
        self.geometry("760x640")
        self.result_log = None
        self.result_note = None
        self.log_row = log_row.copy()
        self.note_row = note_row.copy() if note_row else {}

        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)

        base = ttk.LabelFrame(outer, text="基础记录", padding=10)
        base.pack(fill="x")

        self.vars = {}
        fields = ["日期", "书名", "实际起始页", "实际结束页", "阅读分钟", "完成状态", "理解程度", "论证拆解", "反驳质量", "现实迁移", "一句话总结"]
        for i, f in enumerate(fields):
            ttk.Label(base, text=f).grid(row=i//2, column=(i%2)*2, sticky="w", padx=4, pady=4)
            var = tk.StringVar(value=str(self.log_row.get(f, "")))
            self.vars[f] = var
            ttk.Entry(base, textvariable=var, width=28).grid(row=i//2, column=(i%2)*2+1, sticky="w", padx=4, pady=4)

        note = ttk.LabelFrame(outer, text="深度笔记", padding=10)
        note.pack(fill="both", expand=True, pady=10)

        self.note_widgets = {}
        for i, f in enumerate(["核心概念", "作者观点", "论证链", "关键证据", "隐含前提", "可反驳之处", "可迁移观点", "心理学或法学连接", "今日问题"]):
            ttk.Label(note, text=f, width=14).grid(row=i, column=0, sticky="nw", pady=3)
            txt = tk.Text(note, height=2, wrap="word")
            txt.grid(row=i, column=1, sticky="ew", pady=3)
            txt.insert("1.0", self.note_row.get(f, ""))
            self.note_widgets[f] = txt
        note.columnconfigure(1, weight=1)

        btns = ttk.Frame(outer)
        btns.pack(fill="x")
        ttk.Button(btns, text="取消", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="保存修改", command=self.save).pack(side="right", padx=4)

        self.grab_set()
        self.transient(master)

    def save(self):
        log = self.log_row.copy()
        for f, var in self.vars.items():
            log[f] = var.get().strip()

        start = safe_int(log.get("实际起始页"), 0)
        end = safe_int(log.get("实际结束页"), 0)
        log["实际页数"] = str(max(end - start + 1, 0) if end >= start and end > 0 else 0)

        scores = [safe_int(log.get("理解程度"), 3), safe_int(log.get("论证拆解"), 3), safe_int(log.get("反驳质量"), 3), safe_int(log.get("现实迁移"), 3)]
        log["今日评分"] = str(round(sum(scores) / 4, 2))
        self.result_log = log

        note = self.note_row.copy()
        if not note:
            note["记录ID"] = log.get("记录ID", record_id())
            note["记录时间"] = now_str()
        note["日期"] = log.get("日期", today_str())
        note["书名"] = log.get("书名", "")
        note["阅读范围"] = f"{log.get('实际起始页', '')}-{log.get('实际结束页', '')}"
        for f, w in self.note_widgets.items():
            note[f] = w.get("1.0", "end").strip()
        self.result_note = note
        self.destroy()


# =========================
# 六、导入和错误提示
# =========================

def import_books_from_csv(path, replace=False):
    imported = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV文件没有表头。")

        for i, row in enumerate(reader, start=1):
            b = normalize_book_row(row, i)
            if b["书名"] and safe_int(b["总页数"], 0) > 0:
                imported.append(b)

    if not imported:
        raise ValueError("没有读取到有效书籍。请确认CSV至少包含“书名”和“总页数”，且总页数大于0。")

    if replace:
        rows = imported
    else:
        rows = read_csv_dict(BOOKS_FILE) + imported if BOOKS_FILE.exists() else imported
    write_csv_dict(BOOKS_FILE, rows, BOOK_FIELDS)
    return imported


def friendly_error(e):
    text = str(e)
    if "No such file" in text or "FileNotFoundError" in text:
        return "没有找到所需文件。请先进入“设置与备份”，点击“初始化项目文件”，或重新导入书单。"
    if "SMTP" in text or "Authentication" in text:
        return "邮件发送失败。请检查SMTP服务器、端口、授权码环境变量，以及是否开启邮箱SMTP服务。"
    if "Permission" in text:
        return "文件被占用或没有写入权限。请关闭正在打开的CSV/Excel文件后重试。"
    if "总页数" in text:
        return text
    return text or "发生未知错误。"


# =========================
# 七、主程序 GUI
# =========================

class ReadingApp(tk.Tk):
    def __init__(self):
        super().__init__()
        ensure_dirs()

        self.title("读书打卡系统 V3")
        self.geometry("1260x820")
        self.minsize(1120, 720)

        self.selected_home_task = None
        self.selected_check_task = None
        self.current_calendar_date = date.today().replace(day=1)

        init_files(force=False)
        self.create_widgets()

        cfg = load_config()
        if not cfg.get("是否已完成首次向导", False):
            self.after(300, lambda: WizardDialog(self))

        self.refresh_all()

    # -------------------------
    # 框架
    # -------------------------

    def create_widgets(self):
        self.create_topbar()

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=8)

        self.tab_home = ttk.Frame(self.nb)
        self.tab_books = ttk.Frame(self.nb)
        self.tab_calendar = ttk.Frame(self.nb)
        self.tab_check = ttk.Frame(self.nb)
        self.tab_history = ttk.Frame(self.nb)
        self.tab_stats = ttk.Frame(self.nb)
        self.tab_settings = ttk.Frame(self.nb)
        self.tab_log = ttk.Frame(self.nb)

        self.nb.add(self.tab_home, text="首页")
        self.nb.add(self.tab_books, text="书单")
        self.nb.add(self.tab_calendar, text="日历")
        self.nb.add(self.tab_check, text="打卡")
        self.nb.add(self.tab_history, text="历史记录")
        self.nb.add(self.tab_stats, text="统计与建议")
        self.nb.add(self.tab_settings, text="设置与备份")
        self.nb.add(self.tab_log, text="运行日志")

        self.create_home_tab()
        self.create_books_tab()
        self.create_calendar_tab()
        self.create_check_tab()
        self.create_history_tab()
        self.create_stats_tab()
        self.create_settings_tab()
        self.create_log_tab()

    def create_topbar(self):
        box = ttk.Frame(self, padding=(10, 10, 10, 4))
        box.pack(fill="x")
        self.status_label = ttk.Label(box, text=f"项目目录：{APP_DIR}")
        self.status_label.pack(side="left")
        ttk.Button(box, text="刷新", command=self.refresh_all).pack(side="right", padx=4)
        ttk.Button(box, text="打开data", command=lambda: open_path(DATA_DIR)).pack(side="right", padx=4)
        ttk.Button(box, text="打开项目文件夹", command=lambda: open_path(APP_DIR)).pack(side="right", padx=4)

    def log(self, msg):
        try:
            self.log_text.insert("end", f"[{now_str()}] {msg}\n")
            self.log_text.see("end")
        except Exception:
            pass

    # -------------------------
    # 首页
    # -------------------------

    def create_home_tab(self):
        outer = ttk.Frame(self.tab_home, padding=12)
        outer.pack(fill="both", expand=True)

        top = ttk.Frame(outer)
        top.pack(fill="x")
        ttk.Label(top, text="日期：").pack(side="left")
        self.home_date_var = tk.StringVar(value=today_str())
        ttk.Entry(top, textvariable=self.home_date_var, width=14).pack(side="left", padx=4)
        ttk.Button(top, text="今天", command=lambda: [self.home_date_var.set(today_str()), self.refresh_home()]).pack(side="left", padx=4)
        ttk.Button(top, text="查看任务", command=self.refresh_home).pack(side="left", padx=4)
        ttk.Button(top, text="生成/更新计划", command=self.generate_plan_gui).pack(side="left", padx=4)
        ttk.Button(top, text="首次向导", command=lambda: WizardDialog(self)).pack(side="left", padx=4)

        main = ttk.Frame(outer)
        main.pack(fill="both", expand=True, pady=10)

        left = ttk.LabelFrame(main, text="今日任务卡片", padding=10)
        left.pack(side="left", fill="both", expand=True)

        cols = ["计划ID", "任务类型", "书名", "页码", "分钟", "状态", "备注"]
        self.home_tree = ttk.Treeview(left, columns=cols, show="headings", height=14)
        for c in cols:
            self.home_tree.heading(c, text=c)
            self.home_tree.column(c, width=120 if c not in ["书名", "备注"] else 240, anchor="w")
        self.home_tree.pack(fill="both", expand=True)
        self.home_tree.bind("<<TreeviewSelect>>", self.on_home_select)
        self.home_tree.bind("<Double-1>", lambda e: self.go_checkin())

        btns = ttk.Frame(left)
        btns.pack(fill="x", pady=8)
        ttk.Button(btns, text="去打卡", command=self.go_checkin).pack(side="left", padx=3)
        ttk.Button(btns, text="推迟一天", command=self.delay_selected_task).pack(side="left", padx=3)
        ttk.Button(btns, text="标记未完成", command=lambda: self.mark_selected_task("未完成")).pack(side="left", padx=3)
        ttk.Button(btns, text="跳过本书", command=self.skip_selected_book).pack(side="left", padx=3)
        ttk.Button(btns, text="暂停本书", command=self.pause_selected_book).pack(side="left", padx=3)
        ttk.Button(btns, text="临时加书", command=self.add_book_dialog).pack(side="left", padx=3)

        right = ttk.LabelFrame(main, text="概览与系统建议", padding=10)
        right.pack(side="left", fill="both", padx=(12, 0))
        self.home_overview = scrolledtext.ScrolledText(right, width=42, wrap="word")
        self.home_overview.pack(fill="both", expand=True)

    def tasks_for_date(self, dstr):
        return [r for r in read_csv_dict(PLAN_FILE) if r.get("日期") == dstr]

    def refresh_home(self):
        target = self.home_date_var.get().strip() or today_str()
        tasks = self.tasks_for_date(target)
        self.home_tasks = tasks
        for item in self.home_tree.get_children():
            self.home_tree.delete(item)

        for r in tasks:
            page = ""
            if r.get("计划起始页") and r.get("计划结束页"):
                page = f"{r.get('计划起始页')}-{r.get('计划结束页')}"
            self.home_tree.insert("", "end", values=[
                r.get("计划ID", ""), r.get("任务类型", ""), r.get("书名", ""),
                page, r.get("计划分钟", ""), r.get("完成状态", ""), r.get("备注", "")
            ])

        self.home_overview.delete("1.0", "end")
        s = stats_data()
        lines = [
            f"今天：{target}",
            f"任务数量：{len(tasks)}",
            "",
            f"累计阅读：{s['累计页数']} 页 / {s['累计分钟']} 分钟",
            f"阅读天数：{s['阅读天数']} 天",
            f"到期任务完成率：{s['到期完成率']}%",
            f"预计完成日期：{s['预计完成日期']}",
            "",
            "系统建议："
        ]
        lines.extend([f"- {x}" for x in system_suggestions()[:5]])
        self.home_overview.insert("1.0", "\n".join(lines))

    def on_home_select(self, event=None):
        sel = self.home_tree.selection()
        self.selected_home_task = None
        if sel:
            idx = self.home_tree.index(sel[0])
            if 0 <= idx < len(getattr(self, "home_tasks", [])):
                self.selected_home_task = self.home_tasks[idx]

    def go_checkin(self):
        self.nb.select(self.tab_check)
        self.check_date_var.set(self.home_date_var.get().strip() or today_str())
        self.load_check_tasks()
        if self.selected_home_task:
            pid = self.selected_home_task.get("计划ID")
            for i, r in enumerate(self.check_tasks):
                if r.get("计划ID") == pid:
                    self.check_task_list.selection_clear(0, "end")
                    self.check_task_list.selection_set(i)
                    self.check_task_list.activate(i)
                    self.on_check_task_select()
                    break

    def delay_selected_task(self):
        if not self.selected_home_task:
            messagebox.showwarning("提示", "请先选择一条任务。")
            return
        move_task_days(self.selected_home_task.get("计划ID"), 1)
        self.refresh_all()
        self.log("已将选中任务推迟一天。")

    def mark_selected_task(self, status):
        if not self.selected_home_task:
            messagebox.showwarning("提示", "请先选择一条任务。")
            return
        update_plan_status(self.selected_home_task.get("计划ID"), status)
        self.refresh_all()

    def skip_selected_book(self):
        self._pause_skip_selected("跳过")

    def pause_selected_book(self):
        self._pause_skip_selected("暂停")

    def _pause_skip_selected(self, state):
        if not self.selected_home_task:
            messagebox.showwarning("提示", "请先选择一条阅读任务。")
            return
        title = self.selected_home_task.get("书名", "")
        if not title or title in ["本周复盘"]:
            messagebox.showwarning("提示", "该任务没有对应书籍。")
            return
        if messagebox.askyesno("确认", f"确定将《{title}》标记为“{state}”并重排计划吗？"):
            pause_or_skip_book(title, state)
            reschedule_from(date.today())
            self.refresh_all()

    # -------------------------
    # 书单页
    # -------------------------

    def create_books_tab(self):
        outer = ttk.Frame(self.tab_books, padding=10)
        outer.pack(fill="both", expand=True)

        btns = ttk.Frame(outer)
        btns.pack(fill="x")
        ttk.Button(btns, text="导入CSV", command=self.import_books_gui).pack(side="left", padx=3)
        ttk.Button(btns, text="添加书籍", command=self.add_book_dialog).pack(side="left", padx=3)
        ttk.Button(btns, text="编辑选中", command=self.edit_selected_book).pack(side="left", padx=3)
        ttk.Button(btns, text="删除选中", command=self.delete_selected_book).pack(side="left", padx=3)
        ttk.Button(btns, text="暂停/恢复", command=self.toggle_pause_book).pack(side="left", padx=3)
        ttk.Button(btns, text="标记已读", command=self.mark_book_done).pack(side="left", padx=3)
        ttk.Button(btns, text="保存书单", command=self.save_books_from_table).pack(side="left", padx=3)
        ttk.Button(btns, text="刷新", command=self.refresh_books).pack(side="left", padx=3)

        cols = BOOK_FIELDS
        self.books_tree = ttk.Treeview(outer, columns=cols, show="headings", height=22)
        for c in cols:
            self.books_tree.heading(c, text=c)
            width = 90
            if c == "书名":
                width = 240
            elif c == "备注":
                width = 260
            self.books_tree.column(c, width=width, anchor="w")
        self.books_tree.pack(fill="both", expand=True, pady=8)
        self.books_tree.bind("<Double-1>", lambda e: self.edit_selected_book())

    def refresh_books(self):
        for item in self.books_tree.get_children():
            self.books_tree.delete(item)
        self.book_rows_cache = all_books()
        for b in self.book_rows_cache:
            self.books_tree.insert("", "end", values=[b.get(f, "") for f in BOOK_FIELDS])

    def selected_book_index(self):
        sel = self.books_tree.selection()
        if not sel:
            return None
        return self.books_tree.index(sel[0])

    def add_book_dialog(self):
        dlg = BookEditDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            rows = all_books()
            rows.append(dlg.result)
            write_csv_dict(BOOKS_FILE, rows, BOOK_FIELDS)
            self.refresh_all()

    def edit_selected_book(self):
        idx = self.selected_book_index()
        if idx is None:
            messagebox.showwarning("提示", "请先选择一本书。")
            return
        rows = all_books()
        dlg = BookEditDialog(self, rows[idx])
        self.wait_window(dlg)
        if dlg.result:
            rows[idx] = dlg.result
            write_csv_dict(BOOKS_FILE, rows, BOOK_FIELDS)
            self.refresh_all()

    def delete_selected_book(self):
        idx = self.selected_book_index()
        if idx is None:
            messagebox.showwarning("提示", "请先选择一本书。")
            return
        rows = all_books()
        title = rows[idx]["书名"]
        if messagebox.askyesno("确认删除", f"确定删除《{title}》吗？不会删除已有打卡记录。"):
            rows.pop(idx)
            write_csv_dict(BOOKS_FILE, rows, BOOK_FIELDS)
            self.refresh_all()

    def toggle_pause_book(self):
        idx = self.selected_book_index()
        if idx is None:
            messagebox.showwarning("提示", "请先选择一本书。")
            return
        rows = all_books()
        old = rows[idx].get("状态", "未开始")
        rows[idx]["状态"] = "未开始" if old == "暂停" else "暂停"
        write_csv_dict(BOOKS_FILE, rows, BOOK_FIELDS)
        reschedule_from(date.today())
        self.refresh_all()

    def mark_book_done(self):
        idx = self.selected_book_index()
        if idx is None:
            messagebox.showwarning("提示", "请先选择一本书。")
            return
        rows = all_books()
        rows[idx]["状态"] = "已完成"
        rows[idx]["已读页数"] = rows[idx]["总页数"]
        write_csv_dict(BOOKS_FILE, rows, BOOK_FIELDS)
        reschedule_from(date.today())
        self.refresh_all()

    def save_books_from_table(self):
        rows = []
        for item in self.books_tree.get_children():
            vals = self.books_tree.item(item, "values")
            rows.append(normalize_book_row({f: vals[i] if i < len(vals) else "" for i, f in enumerate(BOOK_FIELDS)}))
        write_csv_dict(BOOKS_FILE, rows, BOOK_FIELDS)
        self.refresh_all()
        messagebox.showinfo("完成", "书单已保存。")

    def import_books_gui(self):
        path = filedialog.askopenfilename(title="选择书单CSV", filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")])
        if not path:
            return
        replace = messagebox.askyesno("导入方式", "是否替换当前书单？\n选择“否”则追加到当前书单。")
        try:
            imported = import_books_from_csv(path, replace=replace)
            self.refresh_all()
            messagebox.showinfo("导入成功", f"已导入 {len(imported)} 本书。")
        except Exception as e:
            messagebox.showerror("导入失败", friendly_error(e))

    # -------------------------
    # 日历
    # -------------------------

    def create_calendar_tab(self):
        outer = ttk.Frame(self.tab_calendar, padding=10)
        outer.pack(fill="both", expand=True)

        top = ttk.Frame(outer)
        top.pack(fill="x")
        ttk.Button(top, text="上一月", command=lambda: self.change_month(-1)).pack(side="left", padx=3)
        self.cal_title = ttk.Label(top, text="", font=("Microsoft YaHei", 12, "bold"))
        self.cal_title.pack(side="left", padx=12)
        ttk.Button(top, text="下一月", command=lambda: self.change_month(1)).pack(side="left", padx=3)
        ttk.Button(top, text="回到本月", command=self.back_this_month).pack(side="left", padx=3)

        main = ttk.Frame(outer)
        main.pack(fill="both", expand=True, pady=10)

        self.calendar_frame = ttk.Frame(main)
        self.calendar_frame.pack(side="left", fill="both", expand=True)

        detail = ttk.LabelFrame(main, text="日期详情", padding=10)
        detail.pack(side="left", fill="both", padx=(10, 0))
        self.calendar_detail = scrolledtext.ScrolledText(detail, width=42, wrap="word")
        self.calendar_detail.pack(fill="both", expand=True)

    def change_month(self, delta):
        y = self.current_calendar_date.year
        m = self.current_calendar_date.month + delta
        while m < 1:
            y -= 1
            m += 12
        while m > 12:
            y += 1
            m -= 12
        self.current_calendar_date = date(y, m, 1)
        self.render_calendar()

    def back_this_month(self):
        self.current_calendar_date = date.today().replace(day=1)
        self.render_calendar()

    def render_calendar(self):
        for child in self.calendar_frame.winfo_children():
            child.destroy()

        y, m = self.current_calendar_date.year, self.current_calendar_date.month
        self.cal_title.config(text=f"{y}年{m}月")

        for i, w in enumerate(["一", "二", "三", "四", "五", "六", "日"]):
            ttk.Label(self.calendar_frame, text=w, anchor="center", font=("Microsoft YaHei", 10, "bold")).grid(row=0, column=i, sticky="nsew", padx=2, pady=2)

        first = date(y, m, 1)
        start_col = first.weekday()
        if m == 12:
            next_month = date(y + 1, 1, 1)
        else:
            next_month = date(y, m + 1, 1)
        days = (next_month - first).days

        plan = read_csv_dict(PLAN_FILE)
        by_date = defaultdict(list)
        for r in plan:
            by_date[r.get("日期")].append(r)

        row = 1
        col = start_col
        for day in range(1, days + 1):
            d = date(y, m, day)
            tasks = by_date.get(d.isoformat(), [])
            done = any(t.get("完成状态") in ["已完成", "已复盘"] for t in tasks)
            partial = any(t.get("完成状态") == "部分完成" for t in tasks)
            review = any(t.get("任务类型") == "每周复盘" for t in tasks)

            label = f"{day}\n"
            if tasks:
                label += f"{len(tasks)}项"
            else:
                label += "无"

            btn = tk.Button(
                self.calendar_frame,
                text=label,
                width=14,
                height=4,
                command=lambda ds=d.isoformat(): self.show_calendar_date(ds)
            )
            if done:
                btn.configure(bg="#d9ead3")
            elif partial:
                btn.configure(bg="#fff2cc")
            elif tasks:
                btn.configure(bg="#f4cccc")
            if review:
                btn.configure(fg="#0000aa")
            if d == date.today():
                btn.configure(relief="solid", bd=3)

            btn.grid(row=row, column=col, sticky="nsew", padx=2, pady=2)
            col += 1
            if col >= 7:
                col = 0
                row += 1

        for i in range(7):
            self.calendar_frame.columnconfigure(i, weight=1)

    def show_calendar_date(self, dstr):
        tasks = self.tasks_for_date(dstr)
        self.calendar_detail.delete("1.0", "end")
        lines = [f"{dstr} 任务详情", ""]
        if not tasks:
            lines.append("当天没有安排任务。")
        else:
            for i, t in enumerate(tasks, 1):
                lines.append(f"{i}. {t.get('任务类型')}｜{t.get('书名')}")
                if t.get("计划起始页"):
                    lines.append(f"   页码：{t.get('计划起始页')}-{t.get('计划结束页')}")
                lines.append(f"   时间：{t.get('计划分钟')}分钟")
                lines.append(f"   状态：{t.get('完成状态')}")
                if t.get("备注"):
                    lines.append(f"   备注：{t.get('备注')}")
                lines.append("")
        self.calendar_detail.insert("1.0", "\n".join(lines))

    # -------------------------
    # 打卡
    # -------------------------

    def create_check_tab(self):
        outer = ttk.Frame(self.tab_check, padding=10)
        outer.pack(fill="both", expand=True)

        left = ttk.LabelFrame(outer, text="任务选择", padding=10)
        left.pack(side="left", fill="y")

        ttk.Label(left, text="打卡日期").pack(anchor="w")
        self.check_date_var = tk.StringVar(value=today_str())
        ttk.Entry(left, textvariable=self.check_date_var, width=16).pack(anchor="w", pady=4)
        ttk.Button(left, text="加载任务", command=self.load_check_tasks).pack(fill="x", pady=4)

        self.check_task_list = tk.Listbox(left, width=42, height=20)
        self.check_task_list.pack(fill="y", expand=True)
        self.check_task_list.bind("<<ListboxSelect>>", self.on_check_task_select)

        mode_frame = ttk.LabelFrame(left, text="打卡模式", padding=8)
        mode_frame.pack(fill="x", pady=8)
        self.check_mode_var = tk.StringVar(value="简洁")
        ttk.Radiobutton(mode_frame, text="简洁打卡", variable=self.check_mode_var, value="简洁", command=self.switch_check_mode).pack(anchor="w")
        ttk.Radiobutton(mode_frame, text="深度打卡", variable=self.check_mode_var, value="深度", command=self.switch_check_mode).pack(anchor="w")

        ttk.Button(left, text="保存打卡", command=lambda: self.save_checkin(False)).pack(fill="x", pady=4)
        ttk.Button(left, text="保存并重排", command=lambda: self.save_checkin(True)).pack(fill="x", pady=4)

        mid = ttk.LabelFrame(outer, text="基础信息", padding=10)
        mid.pack(side="left", fill="y", padx=10)

        self.check_vars = {}
        for i, f in enumerate(["计划ID", "书名", "计划起始页", "计划结束页", "实际起始页", "实际结束页", "阅读分钟", "完成状态", "理解程度", "论证拆解", "反驳质量", "现实迁移", "一句话总结"]):
            ttk.Label(mid, text=f).grid(row=i, column=0, sticky="w", pady=4)
            var = tk.StringVar()
            self.check_vars[f] = var
            if f == "完成状态":
                w = ttk.Combobox(mid, textvariable=var, values=["已完成", "部分完成", "未完成", "已复盘"], state="readonly", width=25)
            elif f in ["理解程度", "论证拆解", "反驳质量", "现实迁移"]:
                w = ttk.Combobox(mid, textvariable=var, values=["1", "2", "3", "4", "5"], state="readonly", width=25)
            else:
                w = ttk.Entry(mid, textvariable=var, width=28)
                if f in ["计划ID", "书名", "计划起始页", "计划结束页"]:
                    w.configure(state="readonly")
            w.grid(row=i, column=1, sticky="w", pady=4)

        self.deep_frame = ttk.LabelFrame(outer, text="深度笔记", padding=10)
        self.deep_frame.pack(side="left", fill="both", expand=True)
        self.note_widgets = {}
        for i, f in enumerate(["核心概念", "作者观点", "论证链", "关键证据", "隐含前提", "可反驳之处", "可迁移观点", "心理学或法学连接", "今日问题"]):
            ttk.Label(self.deep_frame, text=f, width=14).grid(row=i, column=0, sticky="nw", pady=3)
            txt = tk.Text(self.deep_frame, height=2, wrap="word")
            txt.grid(row=i, column=1, sticky="ew", pady=3)
            self.note_widgets[f] = txt
        self.deep_frame.columnconfigure(1, weight=1)
        self.switch_check_mode()

    def switch_check_mode(self):
        if self.check_mode_var.get() == "简洁":
            self.deep_frame.pack_forget()
        else:
            self.deep_frame.pack(side="left", fill="both", expand=True)

    def load_check_tasks(self):
        dstr = self.check_date_var.get().strip() or today_str()
        self.check_tasks = self.tasks_for_date(dstr)
        self.check_task_list.delete(0, "end")
        for r in self.check_tasks:
            self.check_task_list.insert("end", f"{r.get('计划ID')}｜{r.get('任务类型')}｜{r.get('书名')}｜{r.get('完成状态')}")
        if self.check_tasks:
            self.check_task_list.selection_set(0)
            self.on_check_task_select()

    def on_check_task_select(self, event=None):
        sel = self.check_task_list.curselection()
        if not sel:
            self.selected_check_task = None
            return
        r = self.check_tasks[sel[0]]
        self.selected_check_task = r
        for f in ["计划ID", "书名", "计划起始页", "计划结束页"]:
            self.check_vars[f].set(r.get(f, ""))
        self.check_vars["实际起始页"].set(r.get("计划起始页", ""))
        self.check_vars["实际结束页"].set(r.get("计划结束页", ""))
        self.check_vars["阅读分钟"].set(r.get("计划分钟", ""))
        self.check_vars["完成状态"].set("已完成" if r.get("任务类型") != "每周复盘" else "已复盘")
        for f in ["理解程度", "论证拆解", "反驳质量", "现实迁移"]:
            self.check_vars[f].set("3")
        self.check_vars["一句话总结"].set("")
        for w in self.note_widgets.values():
            w.delete("1.0", "end")

    def save_checkin(self, do_reschedule):
        r = self.selected_check_task
        if not r:
            messagebox.showwarning("提示", "请先选择任务。")
            return
        try:
            if r.get("任务类型") == "每周复盘":
                self.save_review_task(r)
            elif r.get("任务类型") == "阅读":
                self.save_reading_task(r)
            else:
                update_plan_status(r.get("计划ID"), self.check_vars["完成状态"].get() or "已完成")

            if do_reschedule:
                reschedule_from(date.today() + timedelta(days=1))
            self.refresh_all()
            messagebox.showinfo("完成", "打卡已保存。")
        except Exception as e:
            messagebox.showerror("保存失败", friendly_error(e))

    def save_reading_task(self, r):
        rid = record_id()
        start = safe_int(self.check_vars["实际起始页"].get(), safe_int(r.get("计划起始页"), 0))
        end = safe_int(self.check_vars["实际结束页"].get(), safe_int(r.get("计划结束页"), 0))
        pages = max(end - start + 1, 0) if end >= start and end > 0 else 0
        minutes = safe_int(self.check_vars["阅读分钟"].get(), safe_int(r.get("计划分钟"), 0))
        status = self.check_vars["完成状态"].get() or "已完成"
        scores = [safe_int(self.check_vars[x].get(), 3) for x in ["理解程度", "论证拆解", "反驳质量", "现实迁移"]]
        score = round(sum(scores) / 4, 2)

        log = {
            "记录ID": rid, "打卡时间": now_str(), "日期": r.get("日期", today_str()), "计划ID": r.get("计划ID"),
            "书名": r.get("书名"), "计划起始页": r.get("计划起始页"), "计划结束页": r.get("计划结束页"),
            "实际起始页": str(start), "实际结束页": str(end), "实际页数": str(pages), "阅读分钟": str(minutes),
            "完成状态": status, "理解程度": str(scores[0]), "论证拆解": str(scores[1]), "反驳质量": str(scores[2]),
            "现实迁移": str(scores[3]), "今日评分": str(score), "打卡模式": self.check_mode_var.get(),
            "一句话总结": self.check_vars["一句话总结"].get().strip()
        }
        append_csv_dict(LOG_FILE, log, LOG_FIELDS)

        note = {
            "记录ID": rid, "记录时间": now_str(), "日期": r.get("日期", today_str()), "书名": r.get("书名"),
            "阅读范围": f"{start}-{end}"
        }
        if self.check_mode_var.get() == "深度":
            for f, w in self.note_widgets.items():
                note[f] = w.get("1.0", "end").strip()
        else:
            note["核心概念"] = ""
            note["作者观点"] = self.check_vars["一句话总结"].get().strip()
            note["今日问题"] = ""
            for f in NOTE_FIELDS:
                note.setdefault(f, "")
        append_csv_dict(NOTES_FILE, note, NOTE_FIELDS)
        update_plan_status(r.get("计划ID"), status)

    def save_review_task(self, r):
        rid = record_id()
        summary = {
            "记录ID": rid, "记录时间": now_str(), "日期": r.get("日期", today_str()), "类型": "每周复盘",
            "本周完成": self.check_vars["一句话总结"].get().strip(),
            "三个概念": self.note_widgets["核心概念"].get("1.0", "end").strip(),
            "最有说服力观点": self.note_widgets["关键证据"].get("1.0", "end").strip(),
            "最可疑观点": self.note_widgets["可反驳之处"].get("1.0", "end").strip(),
            "改变的看法": self.note_widgets["可迁移观点"].get("1.0", "end").strip(),
            "下周调整": self.note_widgets["今日问题"].get("1.0", "end").strip(),
        }
        append_csv_dict(SUMMARY_FILE, summary, SUMMARY_FIELDS)
        update_plan_status(r.get("计划ID"), "已复盘")

    # -------------------------
    # 历史记录
    # -------------------------

    def create_history_tab(self):
        outer = ttk.Frame(self.tab_history, padding=10)
        outer.pack(fill="both", expand=True)

        top = ttk.Frame(outer)
        top.pack(fill="x")
        ttk.Button(top, text="刷新历史", command=self.refresh_history).pack(side="left", padx=3)
        ttk.Button(top, text="修改选中记录", command=self.edit_history).pack(side="left", padx=3)
        ttk.Button(top, text="删除选中记录", command=self.delete_history).pack(side="left", padx=3)
        ttk.Button(top, text="重新计算并重排", command=lambda: [reschedule_from(date.today()), self.refresh_all()]).pack(side="left", padx=3)

        cols = ["记录ID", "日期", "书名", "实际页数", "阅读分钟", "完成状态", "今日评分", "一句话总结"]
        self.history_tree = ttk.Treeview(outer, columns=cols, show="headings", height=24)
        for c in cols:
            self.history_tree.heading(c, text=c)
            self.history_tree.column(c, width=120 if c != "一句话总结" else 360, anchor="w")
        self.history_tree.pack(fill="both", expand=True, pady=8)
        self.history_tree.bind("<Double-1>", lambda e: self.edit_history())

    def refresh_history(self):
        for i in self.history_tree.get_children():
            self.history_tree.delete(i)
        self.history_logs = read_csv_dict(LOG_FILE)
        for r in self.history_logs:
            self.history_tree.insert("", "end", values=[r.get(c, "") for c in ["记录ID", "日期", "书名", "实际页数", "阅读分钟", "完成状态", "今日评分", "一句话总结"]])

    def selected_history_index(self):
        sel = self.history_tree.selection()
        if not sel:
            return None
        return self.history_tree.index(sel[0])

    def edit_history(self):
        idx = self.selected_history_index()
        if idx is None:
            messagebox.showwarning("提示", "请先选择一条历史记录。")
            return
        logs = read_csv_dict(LOG_FILE)
        notes = read_csv_dict(NOTES_FILE)
        log_row = logs[idx]
        rid = log_row.get("记录ID")
        note_row = next((n for n in notes if n.get("记录ID") == rid), {})
        dlg = HistoryEditDialog(self, log_row, note_row)
        self.wait_window(dlg)
        if dlg.result_log:
            logs[idx] = dlg.result_log
            write_csv_dict(LOG_FILE, logs, LOG_FIELDS)
            updated = False
            for i, n in enumerate(notes):
                if n.get("记录ID") == rid:
                    notes[i] = dlg.result_note
                    updated = True
                    break
            if not updated:
                notes.append(dlg.result_note)
            write_csv_dict(NOTES_FILE, notes, NOTE_FIELDS)
            self.refresh_all()

    def delete_history(self):
        idx = self.selected_history_index()
        if idx is None:
            messagebox.showwarning("提示", "请先选择一条历史记录。")
            return
        logs = read_csv_dict(LOG_FILE)
        rid = logs[idx].get("记录ID")
        if messagebox.askyesno("确认删除", "确定删除选中的打卡记录吗？"):
            logs.pop(idx)
            notes = [n for n in read_csv_dict(NOTES_FILE) if n.get("记录ID") != rid]
            write_csv_dict(LOG_FILE, logs, LOG_FIELDS)
            write_csv_dict(NOTES_FILE, notes, NOTE_FIELDS)
            self.refresh_all()

    # -------------------------
    # 统计与建议
    # -------------------------

    def create_stats_tab(self):
        outer = ttk.Frame(self.tab_stats, padding=10)
        outer.pack(fill="both", expand=True)

        btns = ttk.Frame(outer)
        btns.pack(fill="x")
        ttk.Button(btns, text="刷新统计", command=self.refresh_stats).pack(side="left", padx=3)
        ttk.Button(btns, text="生成图表", command=self.generate_plots).pack(side="left", padx=3)
        ttk.Button(btns, text="导出报告", command=self.export_report).pack(side="left", padx=3)
        ttk.Button(btns, text="打开报告文件夹", command=lambda: open_path(REPORT_DIR)).pack(side="left", padx=3)
        ttk.Button(btns, text="打开图表文件夹", command=lambda: open_path(FIG_DIR)).pack(side="left", padx=3)

        ttk.Label(btns, text="搜索笔记：").pack(side="left", padx=(20, 3))
        self.search_var = tk.StringVar()
        ttk.Entry(btns, textvariable=self.search_var, width=20).pack(side="left")
        ttk.Button(btns, text="搜索", command=self.search_notes).pack(side="left", padx=3)

        self.stats_text = scrolledtext.ScrolledText(outer, wrap="word")
        self.stats_text.pack(fill="both", expand=True, pady=8)

    def refresh_stats(self):
        s = stats_data()
        lines = [
            "一、总体统计",
            f"累计阅读页数：{s['累计页数']} 页",
            f"累计阅读分钟：{s['累计分钟']} 分钟",
            f"阅读天数：{s['阅读天数']} 天",
            f"日均页数：{s['日均页数']} 页",
            f"日均分钟：{s['日均分钟']} 分钟",
            f"每小时页数：{s['每小时页数']} 页",
            f"到期任务完成率：{s['到期完成率']}%",
            f"剩余页数：{s['剩余页数']} 页",
            f"预计完成日期：{s['预计完成日期']}",
            "",
            "二、系统建议",
        ]
        lines.extend([f"- {x}" for x in system_suggestions()])
        lines.append("")
        lines.append("三、类别阅读页数")
        for k, v in s["类别页数"].items():
            lines.append(f"{k}：{v} 页")
        lines.append("")
        lines.append("四、书籍进度")
        for b in s["书籍进度"]:
            lines.append(f"{b['书名']}｜{b['当前页']}/{b['总页数']}页｜完成率{b['完成率']}%｜状态：{b['状态']}")

        self.stats_text.delete("1.0", "end")
        self.stats_text.insert("1.0", "\n".join(lines))

    def generate_plots(self):
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            messagebox.showerror("缺少依赖", "未安装 matplotlib。\n请运行：pip install matplotlib\n如果使用exe版，请重新打包时包含matplotlib。")
            return

        logs = read_csv_dict(LOG_FILE)
        if not logs:
            messagebox.showinfo("提示", "暂无打卡记录，无法生成图表。")
            return

        FIG_DIR.mkdir(exist_ok=True)
        by_date_pages = defaultdict(int)
        by_date_minutes = defaultdict(int)
        for r in logs:
            d = r.get("日期", "")
            by_date_pages[d] += safe_int(r.get("实际页数"), 0)
            by_date_minutes[d] += safe_int(r.get("阅读分钟"), 0)

        dates = sorted(by_date_pages.keys())
        cum = []
        total = 0
        for d in dates:
            total += by_date_pages[d]
            cum.append(total)

        plt.figure(figsize=(10, 5))
        plt.plot(dates, cum, marker="o")
        plt.xticks(rotation=45, ha="right")
        plt.xlabel("日期")
        plt.ylabel("累计页数")
        plt.title("累计阅读页数趋势")
        plt.tight_layout()
        plt.savefig(FIG_DIR / "累计阅读页数趋势.png", dpi=200)
        plt.close()

        plt.figure(figsize=(10, 5))
        plt.bar(dates, [by_date_minutes[d] for d in dates])
        plt.xticks(rotation=45, ha="right")
        plt.xlabel("日期")
        plt.ylabel("分钟")
        plt.title("每日阅读时间")
        plt.tight_layout()
        plt.savefig(FIG_DIR / "每日阅读时间.png", dpi=200)
        plt.close()

        messagebox.showinfo("完成", f"图表已生成到：\n{FIG_DIR}")

    def export_report(self):
        s = stats_data()
        out = REPORT_DIR / f"阅读报告_{today_str()}.md"
        with out.open("w", encoding="utf-8") as f:
            f.write(f"# 阅读报告｜{today_str()}\n\n")
            f.write("## 一、总体统计\n\n")
            for k in ["累计页数", "累计分钟", "阅读天数", "日均页数", "每小时页数", "到期完成率", "剩余页数", "预计完成日期"]:
                f.write(f"- {k}：{s[k]}\n")
            f.write("\n## 二、系统建议\n\n")
            for item in system_suggestions():
                f.write(f"- {item}\n")
            f.write("\n## 三、书籍进度\n\n")
            for b in s["书籍进度"]:
                f.write(f"- {b['书名']}：{b['当前页']}/{b['总页数']}页，完成率{b['完成率']}%，状态：{b['状态']}\n")
            f.write("\n## 四、近期问题库\n\n")
            for n in read_csv_dict(NOTES_FILE)[-30:]:
                if n.get("今日问题"):
                    f.write(f"- {n.get('日期')}｜{n.get('书名')}：{n.get('今日问题')}\n")
        messagebox.showinfo("完成", f"报告已导出：\n{out}")

    def search_notes(self):
        kw = self.search_var.get().strip()
        if not kw:
            messagebox.showwarning("提示", "请输入关键词。")
            return
        results = []
        for n in read_csv_dict(NOTES_FILE):
            if kw.lower() in " ".join(str(v) for v in n.values()).lower():
                results.append(n)
        lines = [f"搜索关键词：{kw}", f"结果数量：{len(results)}", ""]
        for i, n in enumerate(results, 1):
            lines.append(f"{i}. {n.get('日期')}｜{n.get('书名')}｜{n.get('阅读范围')}")
            lines.append(f"核心概念：{n.get('核心概念')}")
            lines.append(f"作者观点：{n.get('作者观点')}")
            lines.append(f"可反驳之处：{n.get('可反驳之处')}")
            lines.append(f"今日问题：{n.get('今日问题')}")
            lines.append("")
        self.stats_text.delete("1.0", "end")
        self.stats_text.insert("1.0", "\n".join(lines))

    # -------------------------
    # 设置与备份
    # -------------------------

    def create_settings_tab(self):
        outer = ttk.Frame(self.tab_settings, padding=10)
        outer.pack(fill="both", expand=True)

        cfg_box = ttk.LabelFrame(outer, text="基础设置", padding=10)
        cfg_box.pack(fill="x")

        self.cfg_vars = {}
        fields = [
            ("开始日期", "entry"), ("计划天数", "entry"), ("阅读强度", "combo"),
            ("排期模式", "mode"), ("是否每周复盘", "bool"), ("每周复盘星期", "entry"),
            ("是否自动重排", "bool")
        ]
        cfg = load_config()
        for i, (name, kind) in enumerate(fields):
            ttk.Label(cfg_box, text=name, width=14).grid(row=i//2, column=(i%2)*2, sticky="w", padx=4, pady=5)
            var = tk.StringVar(value=str(cfg.get(name, "")))
            if name in ["是否每周复盘", "是否自动重排"]:
                var.set(bool_cn(cfg.get(name, True)))
            self.cfg_vars[name] = var
            if kind == "combo":
                w = ttk.Combobox(cfg_box, textvariable=var, values=list(INTENSITY_PRESETS.keys()), state="readonly", width=22)
            elif kind == "mode":
                w = ttk.Combobox(cfg_box, textvariable=var, values=["按优先级顺序", "按类别轮换"], state="readonly", width=22)
            elif kind == "bool":
                w = ttk.Combobox(cfg_box, textvariable=var, values=["是", "否"], state="readonly", width=22)
            else:
                w = ttk.Entry(cfg_box, textvariable=var, width=25)
            w.grid(row=i//2, column=(i%2)*2+1, sticky="w", padx=4, pady=5)

        ttk.Button(cfg_box, text="保存设置", command=self.save_settings).grid(row=4, column=1, sticky="w", pady=8)
        ttk.Button(cfg_box, text="保存并重排计划", command=lambda: [self.save_settings(), reschedule_from(date.today()), self.refresh_all()]).grid(row=4, column=3, sticky="w", pady=8)

        mail_box = ttk.LabelFrame(outer, text="邮件提醒", padding=10)
        mail_box.pack(fill="x", pady=10)

        self.mail_vars = {}
        mail = cfg.get("邮件提醒", {})
        mail_fields = ["是否启用", "收件邮箱", "发件邮箱", "SMTP服务器", "SMTP端口", "SMTP密码环境变量"]
        for i, name in enumerate(mail_fields):
            ttk.Label(mail_box, text=name, width=16).grid(row=i//2, column=(i%2)*2, sticky="w", padx=4, pady=5)
            value = mail.get(name, "")
            if name == "是否启用":
                value = bool_cn(value)
            var = tk.StringVar(value=str(value))
            self.mail_vars[name] = var
            if name == "是否启用":
                w = ttk.Combobox(mail_box, textvariable=var, values=["是", "否"], state="readonly", width=26)
            else:
                w = ttk.Entry(mail_box, textvariable=var, width=29)
            w.grid(row=i//2, column=(i%2)*2+1, sticky="w", padx=4, pady=5)

        mail_btns = ttk.Frame(mail_box)
        mail_btns.grid(row=4, column=0, columnspan=4, sticky="w", pady=8)
        ttk.Button(mail_btns, text="保存邮件设置", command=self.save_settings).pack(side="left", padx=3)
        ttk.Button(mail_btns, text="预览邮件", command=self.preview_email).pack(side="left", padx=3)
        ttk.Button(mail_btns, text="发送测试邮件", command=self.send_email).pack(side="left", padx=3)
        ttk.Button(mail_btns, text="创建8点提醒任务", command=self.create_schedule_task).pack(side="left", padx=3)

        file_box = ttk.LabelFrame(outer, text="文件、备份与恢复", padding=10)
        file_box.pack(fill="both", expand=True)

        buttons = [
            ("初始化项目文件", self.init_files_gui),
            ("打开data文件夹", lambda: open_path(DATA_DIR)),
            ("导入书单CSV", self.import_books_gui),
            ("生成/更新计划", self.generate_plan_gui),
            ("一键备份", self.backup_gui),
            ("恢复备份", self.restore_gui),
            ("打开备份文件夹", lambda: open_path(BACKUP_DIR)),
            ("打开报告文件夹", lambda: open_path(REPORT_DIR)),
        ]
        for i, (label, cmd) in enumerate(buttons):
            ttk.Button(file_box, text=label, command=cmd).grid(row=i//4, column=i%4, padx=5, pady=6, sticky="ew")

    def save_settings(self):
        cfg = load_config()
        cfg["开始日期"] = self.cfg_vars["开始日期"].get().strip() or today_str()
        cfg["计划天数"] = safe_int(self.cfg_vars["计划天数"].get(), 90)
        cfg["阅读强度"] = self.cfg_vars["阅读强度"].get() or "标准"
        cfg["排期模式"] = self.cfg_vars["排期模式"].get() or "按优先级顺序"
        cfg["是否每周复盘"] = cn_bool(self.cfg_vars["是否每周复盘"].get())
        cfg["每周复盘星期"] = safe_int(self.cfg_vars["每周复盘星期"].get(), 7)
        cfg["是否自动重排"] = cn_bool(self.cfg_vars["是否自动重排"].get())

        cfg["邮件提醒"] = {
            "是否启用": cn_bool(self.mail_vars["是否启用"].get()),
            "收件邮箱": self.mail_vars["收件邮箱"].get().strip(),
            "发件邮箱": self.mail_vars["发件邮箱"].get().strip(),
            "SMTP服务器": self.mail_vars["SMTP服务器"].get().strip() or "smtp.qq.com",
            "SMTP端口": safe_int(self.mail_vars["SMTP端口"].get(), 465),
            "SMTP密码环境变量": self.mail_vars["SMTP密码环境变量"].get().strip() or "READING_SMTP_PASSWORD",
        }
        save_config(cfg)
        self.log("设置已保存。")
        messagebox.showinfo("完成", "设置已保存。")

    def init_files_gui(self):
        if messagebox.askyesno("确认", "是否初始化项目文件？不会覆盖已有文件。"):
            init_files(force=False)
            self.refresh_all()

    def generate_plan_gui(self):
        try:
            generate_plan()
            self.refresh_all()
            messagebox.showinfo("完成", "阅读计划已生成/更新。")
        except Exception as e:
            messagebox.showerror("生成失败", friendly_error(e))

    def backup_gui(self):
        try:
            out = create_backup()
            messagebox.showinfo("完成", f"备份已生成：\n{out}")
        except Exception as e:
            messagebox.showerror("备份失败", friendly_error(e))

    def restore_gui(self):
        path = filedialog.askopenfilename(title="选择备份zip", filetypes=[("ZIP备份", "*.zip")])
        if not path:
            return
        if not messagebox.askyesno("确认恢复", "恢复备份会覆盖当前 data/reports/figures 中的同名文件。是否继续？"):
            return
        try:
            restore_backup(path)
            self.refresh_all()
            messagebox.showinfo("完成", "备份已恢复。")
        except Exception as e:
            messagebox.showerror("恢复失败", friendly_error(e))

    # -------------------------
    # 邮件
    # -------------------------

    def today_email_body(self):
        tasks = self.tasks_for_date(today_str())
        s = stats_data()
        lines = [f"今日阅读提醒｜{today_str()}", ""]
        if not tasks:
            lines.append("今天暂无任务。")
        else:
            for i, t in enumerate(tasks, 1):
                lines.append(f"{i}. {t.get('任务类型')}｜{t.get('书名')}")
                if t.get("计划起始页"):
                    lines.append(f"   页码：{t.get('计划起始页')}-{t.get('计划结束页')}")
                lines.append(f"   计划时间：{t.get('计划分钟')}分钟")
                lines.append(f"   状态：{t.get('完成状态')}")
        lines.extend(["", "当前统计：", f"- 累计页数：{s['累计页数']}", f"- 到期完成率：{s['到期完成率']}%", f"- 预计完成日期：{s['预计完成日期']}"])
        return "\n".join(lines)

    def preview_email(self):
        messagebox.showinfo("邮件预览", self.today_email_body())

    def send_email(self):
        cfg = load_config().get("邮件提醒", {})
        if not cfg.get("是否启用", False):
            messagebox.showwarning("提示", "邮件提醒未启用。请先在设置中启用。")
            return
        sender = cfg.get("发件邮箱", "")
        recipient = cfg.get("收件邮箱", "")
        server = cfg.get("SMTP服务器", "")
        port = safe_int(cfg.get("SMTP端口"), 465)
        env_name = cfg.get("SMTP密码环境变量", "READING_SMTP_PASSWORD")
        password = os.getenv(env_name, "")
        if not all([sender, recipient, server, password]):
            messagebox.showerror("配置不完整", f"请检查发件邮箱、收件邮箱、SMTP服务器和环境变量 {env_name}。")
            return

        try:
            msg = MIMEMultipart()
            msg["From"] = sender
            msg["To"] = recipient
            msg["Subject"] = f"今日阅读提醒｜{today_str()}"
            msg.attach(MIMEText(self.today_email_body(), "plain", "utf-8"))

            if port == 465:
                with smtplib.SMTP_SSL(server, port, context=ssl.create_default_context()) as s:
                    s.login(sender, password)
                    s.sendmail(sender, recipient, msg.as_string())
            else:
                with smtplib.SMTP(server, port) as s:
                    s.starttls(context=ssl.create_default_context())
                    s.login(sender, password)
                    s.sendmail(sender, recipient, msg.as_string())
            messagebox.showinfo("完成", "邮件已发送。")
        except Exception as e:
            messagebox.showerror("邮件发送失败", friendly_error(e))

    def create_schedule_task(self):
        if not sys.platform.startswith("win"):
            messagebox.showwarning("提示", "一键创建任务目前仅支持Windows。")
            return
        if not messagebox.askyesno("确认", "创建每天早上8点的阅读提醒任务？电脑需要在8点开机。"):
            return
        cmd = [
            "schtasks", "/Create", "/SC", "DAILY", "/TN", "ReadingReminderV3",
            "/TR", f'"{APP_EXECUTABLE}" --send-reminder',
            "/ST", "08:00", "/F"
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, encoding="gbk", errors="replace")
            if result.returncode == 0:
                messagebox.showinfo("完成", "已创建每天8点提醒任务。")
            else:
                messagebox.showerror("失败", result.stderr or result.stdout)
        except Exception as e:
            messagebox.showerror("失败", friendly_error(e))

    # -------------------------
    # 日志页
    # -------------------------

    def create_log_tab(self):
        outer = ttk.Frame(self.tab_log, padding=10)
        outer.pack(fill="both", expand=True)
        self.log_text = scrolledtext.ScrolledText(outer, wrap="word")
        self.log_text.pack(fill="both", expand=True)
        ttk.Button(outer, text="清空日志", command=lambda: self.log_text.delete("1.0", "end")).pack(anchor="w", pady=6)

    # -------------------------
    # 全局刷新
    # -------------------------

    def refresh_all(self):
        try:
            self.refresh_home()
            self.refresh_books()
            self.render_calendar()
            self.load_check_tasks()
            self.refresh_history()
            self.refresh_stats()
            self.log("界面已刷新。")
        except Exception as e:
            self.log("刷新时出现问题：" + friendly_error(e))


# =========================
# 八、命令行提醒入口
# =========================

def send_reminder_cli():
    init_files(force=False)
    cfg = load_config().get("邮件提醒", {})
    if not cfg.get("是否启用", False):
        return
    sender = cfg.get("发件邮箱", "")
    recipient = cfg.get("收件邮箱", "")
    server = cfg.get("SMTP服务器", "")
    port = safe_int(cfg.get("SMTP端口"), 465)
    env_name = cfg.get("SMTP密码环境变量", "READING_SMTP_PASSWORD")
    password = os.getenv(env_name, "")
    if not all([sender, recipient, server, password]):
        return

    # 构造简短邮件
    tasks = [r for r in read_csv_dict(PLAN_FILE) if r.get("日期") == today_str()]
    lines = [f"今日阅读提醒｜{today_str()}", ""]
    for i, t in enumerate(tasks, 1):
        lines.append(f"{i}. {t.get('任务类型')}｜{t.get('书名')}")
        if t.get("计划起始页"):
            lines.append(f"   页码：{t.get('计划起始页')}-{t.get('计划结束页')}")
        lines.append(f"   时间：{t.get('计划分钟')}分钟")
    body = "\n".join(lines)

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = f"今日阅读提醒｜{today_str()}"
    msg.attach(MIMEText(body, "plain", "utf-8"))

    if port == 465:
        with smtplib.SMTP_SSL(server, port, context=ssl.create_default_context()) as s:
            s.login(sender, password)
            s.sendmail(sender, recipient, msg.as_string())
    else:
        with smtplib.SMTP(server, port) as s:
            s.starttls(context=ssl.create_default_context())
            s.login(sender, password)
            s.sendmail(sender, recipient, msg.as_string())


def main():
    if "--send-reminder" in sys.argv:
        send_reminder_cli()
        return
    app = ReadingApp()
    app.mainloop()


if __name__ == "__main__":
    main()
