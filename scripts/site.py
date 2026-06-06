from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import hashlib
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import markdown
import yaml


ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = ROOT / "content"
ARTICLE_DIR = CONTENT_DIR / "articles"
LOCAL_DIR = ROOT / "local"
SITE_FILE = CONTENT_DIR / "site.yml"
DEFAULT_KEYWORDS = LOCAL_DIR / "keywords.txt"
LOCAL_DEEPSEEK_KEY = LOCAL_DIR / "deepseek.key"
LOCAL_INDEXNOW_KEY = LOCAL_DIR / "indexnow.key"


def read_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def write_yaml(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(data, file, allow_unicode=True, sort_keys=False)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def site_url(config: dict, override: str | None = None) -> str:
    return (override or os.getenv("SITE_URL") or config.get("site_url") or "https://hongchayun.github.io").rstrip("/")


def base_path_from_url(url: str) -> str:
    path = urllib.parse.urlparse(url).path.rstrip("/")
    return "" if path in ("", "/") else path


def site_path(config: dict, path: str) -> str:
    value = str(path or "")
    if not value or value.startswith(("#", "http://", "https://", "mailto:", "tel:")):
        return value
    if not value.startswith("/"):
        value = f"/{value}"
    prefix = config.get("_base_path", "")
    if value == "/":
        return f"{prefix}/" if prefix else "/"
    return f"{prefix}{value}"


def deepseek_key() -> str | None:
    if os.getenv("DEEPSEEK_API_KEY"):
        return os.getenv("DEEPSEEK_API_KEY", "").strip()
    if LOCAL_DEEPSEEK_KEY.exists():
        return LOCAL_DEEPSEEK_KEY.read_text(encoding="utf-8").strip()
    return None


def indexnow_key() -> str | None:
    if os.getenv("INDEXNOW_KEY"):
        return os.getenv("INDEXNOW_KEY", "").strip()
    if LOCAL_INDEXNOW_KEY.exists():
        return LOCAL_INDEXNOW_KEY.read_text(encoding="utf-8").strip()
    return None


def slugify(text: str) -> str:
    ascii_text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    if ascii_text:
        return ascii_text[:80]
    return "post-" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def markdown_html(text: str) -> str:
    return markdown.markdown(text or "", extensions=["extra", "tables", "sane_lists"])


def article_url(article: dict) -> str:
    return f"/articles/{article['slug']}.html"


def article_path(article: dict) -> Path:
    return ROOT / "articles" / f"{article['slug']}.html"


def load_articles() -> list[dict]:
    articles = []
    for path in ARTICLE_DIR.glob("*.json"):
        item = read_json(path)
        item["_source"] = path.name
        articles.append(item)
    articles.sort(key=lambda item: (item.get("date", ""), item.get("title", "")), reverse=True)
    return articles


def render_popup_ad(config: dict) -> str:
    ad = config.get("popup_ad") or {}
    if not ad.get("enabled"):
        return ""
    return f"""
  <div id="popupOverlay" class="popup-overlay" aria-label="推荐广告">
    <div class="popup-content">
      <div class="popup-stack">
        <a href="{esc(ad.get("link"))}" target="_blank" rel="sponsored noopener" class="popup-link">
          <p class="popup-title">{esc(ad.get("title"))}</p>
          <img src="{esc(ad.get("image"))}" alt="{esc(ad.get("image_alt"))}" class="popup-image">
        </a>
        <div class="popup-shop-wrap">
          <a href="{esc(ad.get("shop_link"))}" target="_blank" rel="sponsored noopener" class="popup-shop-btn">
            {esc(ad.get("shop_text"))}
          </a>
        </div>
      </div>
      <button class="popup-close-btn" id="popupCloseBtn" type="button" aria-label="关闭">&times;</button>
    </div>
  </div>
"""


def layout(config: dict, title: str, description: str, body: str, canonical: str, keywords: str = "") -> str:
    nav = "".join(
        f'<a href="{esc(site_path(config, item["url"]))}">{esc(item["name"])}</a>'
        for item in config.get("nav", [])
    )
    full_title = title if title == config["title"] else f"{title} | {config['title']}"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(full_title)}</title>
  <meta name="description" content="{esc(description)}">
  <meta name="keywords" content="{esc(keywords or config.get("keywords", ""))}">
  <link rel="canonical" href="{esc(canonical)}">
  <link rel="stylesheet" href="{esc(site_path(config, "/assets/css/style.css"))}">
  <link rel="alternate" type="application/rss+xml" title="{esc(config['title'])}" href="{esc(site_path(config, "/feed.xml"))}">
</head>
<body>
  <header class="site-header">
    <div class="container nav-wrap">
      <a class="brand" href="{esc(site_path(config, "/"))}"><span>茶</span>{esc(config['title'])}</a>
      <nav>{nav}</nav>
    </div>
  </header>
  <main>{body}</main>
  <footer class="site-footer">
    <div class="container footer-grid">
      <div><strong>{esc(config['title'])}</strong><p>{esc(config['description'])}</p></div>
      <div><a href="{esc(site_path(config, "/articles/"))}">文章列表</a><a href="{esc(site_path(config, "/sitemap.xml"))}">站点地图</a><a href="{esc(site_path(config, "/feed.xml"))}">RSS</a></div>
    </div>
  </footer>
  {render_popup_ad(config)}
  <script src="{esc(site_path(config, "/assets/js/main.js"))}"></script>
</body>
</html>
"""


def render_home(config: dict, articles: list[dict], base_url: str) -> None:
    latest = articles[:6]
    article_cards = "".join(
        f"""<article class="post-card">
          <div class="post-meta">{esc(item.get("date"))} · {esc(item.get("category"))}</div>
          <h3><a href="{esc(site_path(config, article_url(item)))}">{esc(item.get("title"))}</a></h3>
          <p>{esc(item.get("description"))}</p>
        </article>"""
        for item in latest
    )
    friends = "".join(
        f"""<a class="friend-card" href="{esc(item.get("url"))}" rel="nofollow noopener" target="_blank">
          <strong>{esc(item.get("name"))}</strong>
          <span>{esc(item.get("desc"))}</span>
          <small>核验：{esc(item.get("last_checked"))}</small>
        </a>"""
        for item in config.get("friends", [])
    )
    body = f"""
<section class="hero">
  <div class="container hero-grid">
    <div>
      <p class="eyebrow">纯 HTML · Python 构建 · 每日更新</p>
      <h1>{esc(config['title'])}</h1>
      <p>{esc(config['description'])}</p>
      <div class="hero-actions">
        <a class="btn btn-primary" href="{esc(site_path(config, "/articles/"))}">查看最新文章</a>
        <a class="btn btn-secondary" href="#friends">友情链接</a>
      </div>
      <div class="update-pill">最近更新：{esc(config.get("last_updated"))} · {esc(config.get("notice"))}</div>
    </div>
    <div class="hero-card"><img src="{esc(site_path(config, config.get("hero_image")))}" alt="{esc(config['title'])}"></div>
  </div>
</section>
<section class="stats">
  <div class="container stats-grid">
    <div class="stat"><strong>{len(articles)}</strong><span>已发布文章</span></div>
    <div class="stat"><strong>{esc(config.get("last_updated"))}</strong><span>最新更新日期</span></div>
    <div class="stat"><strong>{len(config.get("friends", []))}</strong><span>友情链接</span></div>
    <div class="stat"><strong>HTML</strong><span>纯静态页面</span></div>
  </div>
</section>
<section class="section">
  <div class="container">
    <div class="section-heading"><h2>最新文章</h2><p>由 Python 根据关键词生成 HTML，推送到 GitHub Pages 后直接发布。</p></div>
    <div class="post-list compact">{article_cards}</div>
  </div>
</section>
<section class="section section-muted" id="friends">
  <div class="container">
    <div class="section-heading"><h2>友情链接</h2><p>友情链接由 Python 构建首页时写入，核验日期会自动更新。</p></div>
    <div class="friend-grid">{friends}</div>
  </div>
</section>
"""
    (ROOT / "index.html").write_text(
        layout(config, config["title"], config["description"], body, f"{base_url}/", config.get("keywords", "")),
        encoding="utf-8",
    )


def render_article(config: dict, article: dict, articles: list[dict], base_url: str) -> None:
    related = "".join(
        f'<a class="side-link" href="{esc(site_path(config, article_url(item)))}"><span>{esc(item["title"][:28])}</span><small>{esc(item.get("date"))}</small></a>'
        for item in articles[:6]
    )
    tag_html = "".join(f"<span>{esc(tag)}</span>" for tag in article.get("tags", []))
    body_html = markdown_html(article.get("body_markdown", ""))
    image = article.get("image") or config.get("default_image", "/assets/img/hero.png")
    body = f"""
<section class="post-header">
  <div class="container">
    <div class="breadcrumb-line"><a href="{esc(site_path(config, "/"))}">首页</a><span>/</span><a href="{esc(site_path(config, "/articles/"))}">文章</a><span>/</span><span>{esc(article.get("category"))}</span></div>
    <h1>{esc(article["title"])}</h1>
    <div class="post-meta light"><span>{esc(article.get("date"))}</span><span>{esc(config.get("author"))}</span></div>
  </div>
</section>
<section class="post-shell">
  <div class="container post-grid">
    <article class="post-content">
      <img class="article-image" src="{esc(site_path(config, image))}" alt="{esc(article.get("image_alt", article["title"]))}">
      <p class="caption">{esc(article.get("image_caption", ""))}</p>
      {body_html}
      <div class="article-note">最后生成日期：{esc(article.get("date"))}。公开信息可能变化，请以官网实时显示为准。</div>
    </article>
    <aside class="sidebar">
      <div class="side-block"><h2>最新文章</h2>{related}</div>
      <div class="side-block"><h2>标签</h2><div class="tag-row">{tag_html}</div></div>
    </aside>
  </div>
</section>
"""
    path = article_path(article)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        layout(
            config,
            article["title"],
            article.get("description", article["title"]),
            body,
            f"{base_url}{article_url(article)}",
            article.get("keywords", ""),
        ),
        encoding="utf-8",
    )


def render_articles_index(config: dict, articles: list[dict], base_url: str) -> None:
    cards = "".join(
        f"""<article class="post-card">
          <div class="post-meta">{esc(item.get("date"))} · {esc(item.get("category"))}</div>
          <h2><a href="{esc(site_path(config, article_url(item)))}">{esc(item.get("title"))}</a></h2>
          <p>{esc(item.get("description"))}</p>
        </article>"""
        for item in articles
    )
    body = f"""<section class="page-header"><div class="container"><a class="breadcrumb" href="{esc(site_path(config, "/"))}">首页</a><h1>文章列表</h1><p>红茶云加速器最新发布的测评、官网入口和优惠信息。</p></div></section>
<section class="section"><div class="container"><div class="post-list">{cards}</div></div></section>"""
    path = ROOT / "articles" / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(layout(config, "文章列表", config["description"], body, f"{base_url}/articles/"), encoding="utf-8")


def update_site_dates(config: dict) -> dict:
    today = dt.date.today().strftime("%Y-%m-%d")
    config["last_updated"] = today
    for friend in config.get("friends", []):
        friend["last_checked"] = today
    write_yaml(SITE_FILE, config)
    return config


def build(args: argparse.Namespace) -> None:
    config = update_site_dates(read_yaml(SITE_FILE))
    base_url = site_url(config, args.site_url)
    config["_base_path"] = base_path_from_url(base_url)
    articles = load_articles()
    for article in articles:
        render_article(config, article, articles, base_url)
    render_articles_index(config, articles, base_url)
    render_home(config, articles, base_url)
    render_sitemap(config, articles, base_url)
    render_feed(config, articles, base_url)
    render_robots(config, base_url)
    write_indexnow_key()
    print(f"Built {len(articles)} articles.")


def render_sitemap(config: dict, articles: list[dict], base_url: str) -> None:
    today = dt.date.today().strftime("%Y-%m-%d")
    urls = [("/", today), ("/articles/", today)]
    urls.extend((article_url(item), item.get("date", today)) for item in articles)
    body = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod in urls:
        body.append(f"<url><loc>{esc(base_url + loc)}</loc><lastmod>{esc(lastmod)}</lastmod></url>")
    body.append("</urlset>")
    (ROOT / "sitemap.xml").write_text("\n".join(body), encoding="utf-8")


def render_feed(config: dict, articles: list[dict], base_url: str) -> None:
    items = []
    for article in articles[:20]:
        pub = email.utils.format_datetime(dt.datetime.fromisoformat(article.get("date") + "T08:00:00+08:00"))
        items.append(
            f"""<item><title>{esc(article['title'])}</title><link>{esc(base_url + article_url(article))}</link><guid>{esc(base_url + article_url(article))}</guid><pubDate>{esc(pub)}</pubDate><description>{esc(article.get('description', ''))}</description></item>"""
        )
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>{esc(config['title'])}</title><link>{esc(base_url)}/</link><description>{esc(config['description'])}</description>{''.join(items)}</channel></rss>"""
    (ROOT / "feed.xml").write_text(feed, encoding="utf-8")


def render_robots(config: dict, base_url: str) -> None:
    (ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {base_url}/sitemap.xml\n", encoding="utf-8")


def clean_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def fallback_article(keyword: str, config: dict) -> dict:
    today = dt.date.today().strftime("%Y-%m-%d")
    return {
        "title": f"{keyword}：官网入口、测评信息与注意事项整理",
        "slug": slugify(keyword),
        "date": today,
        "category": "机场测评",
        "tags": ["机场测评", "机场官网", "加速器"],
        "keywords": f"{keyword},{keyword}官网,{keyword}优惠码",
        "description": f"{keyword}，整理官网入口、公开信息、优惠情况、核验日期和使用注意事项。",
        "image": config.get("default_image", "/assets/img/hero.png"),
        "image_alt": f"{keyword}信息整理",
        "image_caption": f"{keyword}公开信息整理，最后更新：{today}",
        "body_markdown": f"""## 一、信息概览

本文围绕 **{keyword}** 整理公开信息，包括官网入口、套餐说明、优惠情况、适合人群和注意事项。

| 项目 | 内容 |
| --- | --- |
| 关键词 | {keyword} |
| 信息类型 | 官网入口 / 测评 / 优惠信息 |
| 最后更新 | {today} |

## 二、官网入口说明

建议优先从服务商公开官网进入，不要轻信来源不明的跳转链接。优惠码、套餐和活动规则都可能变化，下单前应再次核验。

## 三、注意事项

- 不发布来源不明的共享账号。
- 不把测试订阅写成永久可用资源。
- 服务可用性和合规性以当地法律、平台规则和服务条款为准。
""",
    }


def generate_deepseek_article(keyword: str, config: dict) -> dict:
    key = deepseek_key()
    if not key:
        print("No DeepSeek key found, using fallback article.")
        return fallback_article(keyword, config)
    today = dt.date.today().strftime("%Y-%m-%d")
    prompt = f"""
围绕关键词「{keyword}」生成一篇中文 SEO 文章，主题是机场测评、机场官网入口、优惠码或使用注意事项。
要求：
- 不编造真实可用账号、测试订阅、token、永久免费资源。
- 不承诺一定可用，强调公开信息整理和以官网为准。
- 固定图片为站内图，只生成 image_alt 和 image_caption。
- 正文 Markdown，包含表格、分节标题、注意事项。
- 日期使用 {today}。
只输出 JSON，字段：
title, category, tags, keywords, description, image_alt, image_caption, body_markdown
"""
    payload = {
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        "messages": [
            {"role": "system", "content": "你只输出可解析 JSON。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions"),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepSeek API error {error.code}: {detail}") from error
    article = clean_json(result["choices"][0]["message"]["content"])
    article["date"] = today
    article["slug"] = slugify(keyword) + "-" + hashlib.sha1(article["title"].encode("utf-8")).hexdigest()[:8]
    article["image"] = config.get("default_image", "/assets/img/hero.png")
    return article


def save_article(article: dict) -> Path:
    ARTICLE_DIR.mkdir(parents=True, exist_ok=True)
    source = ARTICLE_DIR / f"{article['date']}-{article['slug']}.json"
    counter = 2
    while source.exists():
        source = ARTICLE_DIR / f"{article['date']}-{article['slug']}-{counter}.json"
        counter += 1
    write_json(source, article)
    print(f"Created {source}")
    return source


def new_article(args: argparse.Namespace) -> None:
    config = read_yaml(SITE_FILE)
    article = fallback_article(args.keyword, config) if args.no_ai else generate_deepseek_article(args.keyword, config)
    if "slug" not in article:
        article["slug"] = slugify(args.keyword) + "-" + hashlib.sha1(article["title"].encode("utf-8")).hexdigest()[:8]
    if "date" not in article:
        article["date"] = dt.date.today().strftime("%Y-%m-%d")
    if "image" not in article:
        article["image"] = config.get("default_image", "/assets/img/hero.png")
    save_article(article)
    build(argparse.Namespace(site_url=args.site_url))


def keyword_lines(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"keyword file not found: {path}")
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.strip().startswith("#")]


def select_keywords(keywords: list[str], limit: int, rotate: bool = False) -> list[str]:
    if limit <= 0 or not keywords:
        return []
    count = min(limit, len(keywords))
    if not rotate:
        return keywords[:count]
    run_number = os.getenv("GITHUB_RUN_NUMBER", "")
    if run_number.isdigit():
        start = (int(run_number) - 1) % len(keywords)
    else:
        start = dt.date.today().toordinal() % len(keywords)
    return [keywords[(start + index) % len(keywords)] for index in range(count)]


def batch(args: argparse.Namespace) -> None:
    config = read_yaml(SITE_FILE)
    source = Path(args.file or DEFAULT_KEYWORDS)
    env_keywords = os.getenv("KEYWORDS")
    keywords = [line.strip() for line in env_keywords.splitlines() if line.strip()] if env_keywords else keyword_lines(source)
    selected = select_keywords(keywords, args.limit, rotate=bool(env_keywords))
    for keyword in selected:
        article = fallback_article(keyword, config) if args.no_ai else generate_deepseek_article(keyword, config)
        if "slug" not in article:
            article["slug"] = slugify(keyword) + "-" + hashlib.sha1(article["title"].encode("utf-8")).hexdigest()[:8]
        if "date" not in article:
            article["date"] = dt.date.today().strftime("%Y-%m-%d")
        if "image" not in article:
            article["image"] = config.get("default_image", "/assets/img/hero.png")
        save_article(article)
    build(argparse.Namespace(site_url=args.site_url))


def write_indexnow_key() -> None:
    key = indexnow_key()
    if key:
        (ROOT / f"{key}.txt").write_text(key, encoding="utf-8")


def indexnow(args: argparse.Namespace) -> None:
    config = read_yaml(SITE_FILE)
    base_url = site_url(config, args.site_url)
    key = indexnow_key()
    if not key:
        print("No INDEXNOW_KEY/local indexnow.key found, skip.")
        return
    urls = [f"{base_url}/", f"{base_url}/articles/"]
    urls += [base_url + article_url(article) for article in load_articles()]
    payload = {
        "host": urllib.parse.urlparse(base_url).netloc,
        "key": key,
        "keyLocation": f"{base_url}/{key}.txt",
        "urlList": sorted(set(urls)),
    }
    request = urllib.request.Request(
        "https://api.indexnow.org/indexnow",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        print(f"IndexNow {response.status}: {response.read().decode('utf-8', errors='replace')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Pure HTML builder for hongchayun.github.io")
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build")
    p_build.add_argument("--site-url", default=None)
    p_build.set_defaults(func=build)

    p_new = sub.add_parser("new")
    p_new.add_argument("keyword")
    p_new.add_argument("--no-ai", action="store_true")
    p_new.add_argument("--site-url", default=None)
    p_new.set_defaults(func=new_article)

    p_batch = sub.add_parser("batch")
    p_batch.add_argument("--file", default=None)
    p_batch.add_argument("--limit", type=int, default=1)
    p_batch.add_argument("--no-ai", action="store_true")
    p_batch.add_argument("--site-url", default=None)
    p_batch.set_defaults(func=batch)

    p_indexnow = sub.add_parser("indexnow")
    p_indexnow.add_argument("--site-url", default=None)
    p_indexnow.set_defaults(func=indexnow)

    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
