import os
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from typing import Dict, Iterable, List
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

TIMEZONE = ZoneInfo("Asia/Shanghai")


def normalize_text(value: str) -> str:
    return (value or "").strip()


def contains_keyword(title: str, summary: str, keywords: Iterable[str]) -> bool:
    text = f"{title} {summary}".lower()
    return any(keyword.lower() in text for keyword in keywords)


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
            summary = normalize_text(entry.get("summary", ""))

            if not title or not link or link in seen_links:
                continue

            if contains_keyword(title, summary, KEYWORDS):
                seen_links.add(link)
                matches.append(
                    {
                        "source": source_name,
                        "title": title,
                        "link": link,
                    }
                )

    return matches


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

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(sender_email, sender_password)
        server.send_message(message)


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
