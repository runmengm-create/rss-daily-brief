import os
import re
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from html import unescape
from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo

import feedparser


RSS_SOURCES: Dict[str, str] = {
    "36氪": "https://36kr.com/feed",
    "虎嗅": "https://www.huxiu.com/rss/0.xml",
    "汽车之家快讯": "https://www.autohome.com.cn/rss/news.xml",
}

KEYWORDS = [
    "OMS",
    "驾驶员监测",
    "智能座舱",
    "车载Agent",
    "自驾游",
    "新能源",
    "理想",
    "问界",
    "小鹏",
]

WEIGHTED_TERMS: List[Tuple[str, int]] = [
    ("OMS", 5),
    ("DMS", 5),
    ("驾驶员监测", 5),
    ("驾驶员状态监测", 5),
    ("智能座舱", 5),
    ("车载Agent", 5),
    ("车载 Agent", 5),
    ("座舱Agent", 5),
    ("自驾游", 3),
    ("新能源", 3),
    ("新能源汽车", 4),
    ("理想汽车", 5),
    ("理想L", 5),
    ("问界", 5),
    ("小鹏汽车", 5),
    ("小鹏", 4),
]

AMBIGUOUS_TERMS = {"理想", "小鹏"}

AUTO_CONTEXT_TERMS = [
    "汽车",
    "车企",
    "车市",
    "车型",
    "新车",
    "座舱",
    "智舱",
    "智驾",
    "智能驾驶",
    "自动驾驶",
    "辅助驾驶",
    "驾驶",
    "新能源",
    "纯电",
    "电动",
    "增程",
    "混动",
    "电池",
    "充电",
    "比亚迪",
    "特斯拉",
    "蔚来",
    "理想",
    "问界",
    "小鹏",
    "华为",
    "赛力斯",
    "SUV",
    "MPV",
]

MIN_RELEVANCE_SCORE = int(os.getenv("MIN_RELEVANCE_SCORE") or "4")
MAX_ARTICLES = int(os.getenv("MAX_ARTICLES") or "20")
TIMEZONE = ZoneInfo("Asia/Shanghai")


def normalize_text(value: str) -> str:
    return (value or "").strip()


def clean_html(value: str) -> str:
    text = unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

