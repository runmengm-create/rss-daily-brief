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


def truncate_text(value: str, limit: int = 180) -> str:
    text = clean_html(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def get_entry_summary(entry: dict) -> str:
    if entry.get("summary"):
        return clean_html(entry["summary"])

    content_items = entry.get("content") or []
    if content_items and content_items[0].get("value"):
        return clean_html(content_items[0]["value"])

    return ""


def score_article(title: str, summary: str) -> Tuple[int, List[str]]:
    title_text = title.lower()
    full_text = f"{title} {summary}".lower()
    has_auto_context = any(term.lower() in full_text for term in AUTO_CONTEXT_TERMS)
    matched_terms: List[str] = []
    score = 0

    for term, weight in WEIGHTED_TERMS:
        term_lower = term.lower()
        if term_lower not in full_text:
            continue

        matched_terms.append(term)
        score += weight

        if term_lower in title_text:
            score += 2

    for term in AMBIGUOUS_TERMS:
        term_lower = term.lower()
        if term_lower in full_text and term not in matched_terms:
            matched_terms.append(term)
            score += 1
            if term_lower in title_text:
                score += 1

    if not has_auto_context:
        score -= 4

    return max(score, 0), matched_terms


def fetch_matching_articles() -> List[dict]:
    matches: List[dict] = []
    seen_links = set()

    for source_name, feed_url in RSS_SOURCES.items():
        feed = feedparser.parse(feed_url)

        if feed.bozo:
            print(f"[WARN] RSS解析可能异常：{source_name} - {feed.bozo_exception}")

        for entry in feed.entries:
            title = normalize_text(entry.get("title", ""))
            link = normalize_text(entry.get("link", ""))
            summary = get_entry_summary(entry)

            if not title or not link or link in seen_links:
                continue

            score, matched_terms = score_article(title, summary)
            if score >= MIN_RELEVANCE_SCORE:
                seen_links.add(link)
                matches.append(
                    {
                        "source": source_name,
                        "title": title,
                        "link": link,
                        "summary": truncate_text(summary) or "RSS未提供摘要。",
                        "score": score,
                        "matched_terms": matched_terms,
                    }
                )

    matches.sort(key=lambda item: (-item["score"], item["source"], item["title"]))
    return matches[:MAX_ARTICLES]


def build_brief(articles: List[dict]) -> str:
    today = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    lines = [
        f"每日RSS简报 - {today}",
        "",
        "关键词：" + "、".join(KEYWORDS),
        "",
    ]

    if not articles:
        lines.append("今日暂无匹配文章。")
        return "\n".join(lines)

    current_source = None
    for article in articles:
        if article["source"] != current_source:
            current_source = article["source"]
            lines.extend(["", f"【{current_source}】"])

        lines.append(f"- {article['title']}")
        lines.append(f"  摘要：{article['summary']}")
        lines.append(f"  匹配：{'、'.join(article['matched_terms'])}；相关性：{article['score']}")
        lines.append(f"  {article['link']}")

    return "\n".join(lines).strip() + "\n"


def send_email(subject: str, body: str) -> None:
    smtp_host = os.getenv("SMTP_HOST") or "smtp.gmail.com"
    smtp_port = int(os.getenv("SMTP_PORT") or "587")
    sender_email = os.getenv("SENDER_EMAIL") or os.environ["OUTLOOK_EMAIL"]
    sender_password = os.getenv("SENDER_PASSWORD") or os.environ["OUTLOOK_PASSWORD"]
    recipient_email = os.getenv("RECIPIENT_EMAIL") or sender_email

    message = EmailMessage()
    message["From"] = sender_email
    message["To"] = recipient_email
    message["Subject"] = subject
    message.set_content(body)

    print(
        "[INFO] 准备发送邮件："
        f"from={mask_email(sender_email)}, "
        f"to={mask_email(recipient_email)}, "
        f"smtp={smtp_host}:{smtp_port}"
    )

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(sender_email, sender_password)
        refused_recipients = server.send_message(message)

    if refused_recipients:
        raise RuntimeError(f"部分收件人被SMTP服务器拒收：{refused_recipients}")

    print("[OK] SMTP服务器已接受邮件投递。")


def mask_email(email: str) -> str:
    if "@" not in email:
        return "***"

    name, domain = email.split("@", 1)
    if len(name) <= 2:
        masked_name = name[:1] + "***"
    else:
        masked_name = name[:2] + "***" + name[-1:]

    return f"{masked_name}@{domain}"


def main() -> None:
    articles = fetch_matching_articles()
    body = build_brief(articles)
    today = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    subject = f"每日RSS简报 - {today} - {len(articles)}篇"

    print(body)
    send_email(subject, body)
    print(f"[OK] 已发送邮件，共 {len(articles)} 篇匹配文章。")


if __name__ == "__main__":
    main()
