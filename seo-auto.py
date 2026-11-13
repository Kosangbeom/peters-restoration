# -*- coding: utf-8 -*-
"""
피터의복원 · 네이버/구글 검색 자동 최적화 스크립트
------------------------------------------------------------
깃허브에 파일을 올릴 때마다 자동으로 실행됩니다. (손댈 필요 없음)

하는 일
  1. 사례 상세페이지(case-*.html)마다
     - 본문 제목(h1)으로   <title>글 제목 | 피터의복원</title>
     - 현장 정보 + 본문 첫 단락으로   설명(description)
     - 카카오톡·네이버 공유용 og 태그, 대표 주소(canonical)
     를 자동으로 만들어 넣습니다.
  2. 메인·복원사례·서비스·교육·사례목록 페이지 안에
     검색 로봇이 읽을 수 있는 '글자 버전'(사례 목록 링크 포함)을 넣습니다.
     (화면이 뜨면 원래 디자인으로 바뀌므로 방문자에게는 그대로 보입니다)
  3. sitemap.xml, robots.txt 를 최신 상태로 다시 만듭니다.
"""
import glob
import html
import os
import re
import subprocess
from datetime import date

SITE = "https://peters-restoration.com"
BRAND = "피터의복원"
TEL = "010-3665-7273"
DESC_MAX = 150
EXCLUDE = {"cases.html"}  # 예전 페이지 (검색 대상 제외)

# 메인·안내 페이지의 고정 설명 (한 번 써 두면 계속 사용)
HUBS = {
    "index.html": {
        "title": "피터의복원 | 가구·가죽·대리석·악기 아티스틱 복원 전문",
        "h1": "피터의복원 · 아티스틱 하이엔드 복원 전문",
        "desc": "교체 대신 복원으로. 가구·가죽 소파·대리석·마루·싱크볼부터 하프·미술품·호텔 시설물까지, "
                "미술 전공 복원전문가가 이질감 없이 되살립니다. 서울·경기·인천·전국 출장, 사진 문자 견적.",
    },
    "case.html": {
        "title": "복원 사례 | 피터의복원",
        "h1": "피터의복원 복원 사례",
        "desc": "실내외 원상복구, 가구 복원, 특수 복원까지. 피터의복원이 교체 없이 손상 부위만 되살린 "
                "실제 현장 기록을 항목별로 모았습니다.",
    },
    "case-list.html": {
        "title": "복원 사례 목록 | 피터의복원",
        "h1": "복원 사례 목록",
        "desc": "피터의복원 복원 사례 목록. 가죽 소파·대리석·하프·조형물 등 복원 항목별 현장 기록을 모아 볼 수 있습니다.",
    },
    "service.html": {
        "title": "복원 서비스 | 피터의복원",
        "h1": "피터의복원 복원 서비스",
        "desc": "마루·문틀·타일·대리석·싱크대 상판 원상복구, 원목·가죽·세라믹 가구 복원, 하프·미술품·조형물·명품 특수 복원. "
                "최고급 재료와 정밀 조색으로 이질감 없이 복원합니다.",
    },
    "education.html": {
        "title": "복원 교육 | 피터의복원",
        "h1": "피터의복원 특수 복원 교육",
        "desc": "속성 집수리 교육이 아닌 특수 복원 기술. 하이엔드 가구·명품 가죽·악기·미술품·호텔 인테리어 복원을 "
                "현업 복원전문가에게 배우는 피터의복원 교육과정입니다.",
    },
}
NAV = [("index.html", "홈"), ("case.html", "복원 사례"), ("service.html", "복원 서비스"), ("education.html", "복원 교육")]

IMG_RE = re.compile(r"data:image/[a-zA-Z+]+;base64,[A-Za-z0-9+/=]+")


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def write(p, s):
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)


def text(fragment):
    t = re.sub(r"<br\s*/?>", " ", fragment)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t)
    return re.sub(r"\s+", " ", t).strip()


def cut(t, n=DESC_MAX):
    if len(t) <= n:
        return t
    t = t[:n]
    for mark in (". ", "다. ", "요. "):
        i = t.rfind(mark)
        if i > n * 0.6:
            return t[: i + 1].strip()
    return t.rstrip(" ,·") + "…"


def git_date(path, first=False):
    try:
        args = ["git", "log", "--format=%cs"]
        if first:
            args += ["--diff-filter=A", "--follow"]
        out = subprocess.run(args + ["--", path], capture_output=True, text=True).stdout.split()
        if out:
            return out[-1] if first else out[0]
    except Exception:
        pass
    return date.today().isoformat()


def url_of(name):
    return SITE + "/" if name == "index.html" else f"{SITE}/{name}"


# ---------- <head> 정리 ----------
OLD_TAGS = [
    r"<title>[^<]*</title>",
    r'<meta\s+name="description"[^>]*>',
    r'<meta\s+property="og:(?:title|description|url)"[^>]*>',
    r'<link\s+rel="canonical"[^>]*>',
]


def strip_outside_comments(head):
    """주석(<!-- -->) 안의 안내문은 건드리지 않고, 기존 제목·설명 태그만 지웁니다."""
    parts = re.split(r"(<!--.*?-->)", head, flags=re.S)
    for i, part in enumerate(parts):
        if part.startswith("<!--"):
            continue
        for pat in OLD_TAGS:
            part = re.sub(pat + r"(?:[ \t]*<!--\s*\[교체\]\s*-->)?[ \t]*\n?", "", part)
        parts[i] = part
    return "".join(parts)


def set_head(src, name, title, desc):
    block = (
        "<!--SEO-AUTO-START (자동 생성 · 직접 고치지 마세요)-->\n"
        f"<title>{html.escape(title, quote=False)}</title>\n"
        f'<meta name="description" content="{html.escape(desc)}">\n'
        f'<link rel="canonical" href="{url_of(name)}">\n'
        f'<meta property="og:title" content="{html.escape(title)}">\n'
        f'<meta property="og:description" content="{html.escape(desc)}">\n'
        f'<meta property="og:url" content="{url_of(name)}">\n'
        "<!--SEO-AUTO-END-->\n"
    )
    end = src.find("</head>")
    head, rest = src[:end], src[end:]
    head = re.sub(r"<!--SEO-AUTO-START.*?<!--SEO-AUTO-END-->\n?", "", head, flags=re.S)
    head = strip_outside_comments(head)
    head = re.sub(r"^[ \t]*<!--\s*\[교체\]\s*-->[ \t]*\n", "", head, flags=re.M)
    if 'property="og:site_name"' not in head:
        block = block.replace("<!--SEO-AUTO-END-->",
                              f'<meta property="og:site_name" content="{BRAND}">\n'
                              '<meta property="og:locale" content="ko_KR">\n<!--SEO-AUTO-END-->')
    m = re.search(r'<meta\s+name="viewport"[^>]*>\n?', head)
    pos = m.end() if m else head.find(">", head.find("<head")) + 1
    if m and not head[m.end() - 1] == "\n":
        block = "\n" + block
    head = head[:pos] + block + head[pos:]
    return head + rest


# ---------- 사례 상세페이지 정보 읽기 ----------
def read_case(name):
    s = IMG_RE.sub("", read(name))
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", s, re.S)
    if not h1:
        return None
    title_txt = text(h1.group(1)).replace(",", ", ").replace(",  ", ", ")
    facts = {}
    fm = re.search(r'<ul class="facts">(.*?)</ul>', s, re.S)
    if fm:
        for k, v in re.findall(r"<li>([^<]*)<b>(.*?)</b></li>", fm.group(1)):
            facts[text(k)] = text(v)
    cat = re.search(r'<span class="cat">(.*?)</span>', s, re.S)
    cat = text(cat.group(1)).replace("복원사례 / ", "") if cat else ""
    lead = re.search(r'<p class="lead">(.*?)</p>', s, re.S) or re.search(r"<article.*?<p[^>]*>(.*?)</p>", s, re.S)
    lead = text(lead.group(1)) if lead else ""

    tidy = lambda v: v.replace(" · ", "·").replace(" (", "(")
    place = facts.get("현장", "").replace(" · ", " ")
    target = tidy(facts.get("대상", ""))
    brand = facts.get("브랜드", "")
    if brand and brand not in target:
        target = f"{brand} {target}"
    damage = tidy(facts.get("손상", ""))
    scope = tidy(facts.get("범위", ""))
    time = facts.get("작업") or facts.get("작업시간") or facts.get("시공시간", "")
    head = ", ".join(x for x in [place, target] if x)
    summary = f"{head} {damage} 복원 사례".replace("  ", " ") if head else ""
    extra = [x for x in [("" if damage else scope), (f"작업 {tidy(time)}" if re.search(r"\d", time) else "")] if x]
    if summary and extra:
        summary += f"({', '.join(extra)})"
    desc = cut(f"{summary}. {lead}" if summary else lead)
    return {"name": name, "h1": title_txt, "title": f"{title_txt} | {BRAND}", "desc": desc, "cat": cat}


# ---------- 메인·목록 페이지에 '글자 버전' 넣기 ----------
def static_block(page, cases):
    info = HUBS[page]
    nav = " · ".join(f'<a href="{h}" style="color:#d8c08a">{t}</a>' for h, t in NAV)
    items = "\n".join(
        f'<li style="margin:0 0 10px"><a href="{c["name"]}" style="color:#e9e4da">{html.escape(c["h1"])}</a>'
        f'<br><span style="font-size:13px;color:#8d8a84">{html.escape(c["cat"])} · {html.escape(c["desc"][:70])}…</span></li>'
        for c in cases
    )
    return (
        "<!--SEO-STATIC-START (자동 생성 · 화면이 뜨면 원래 디자인으로 바뀝니다)-->\n"
        '<div style="min-height:100vh;background:#16171a;color:#cfcac0;padding:40px 24px;'
        'font-family:sans-serif;line-height:1.7">\n'
        f'<h1 style="font-size:22px;color:#e9e4da;margin:0 0 8px">{html.escape(info["h1"])}</h1>\n'
        f'<p style="max-width:720px;margin:0 0 16px">{html.escape(info["desc"])}</p>\n'
        f"<nav>{nav}</nav>\n"
        '<h2 style="font-size:17px;color:#e9e4da;margin:28px 0 12px">복원 사례</h2>\n'
        f'<ul style="list-style:none;padding:0;max-width:720px">\n{items}\n</ul>\n'
        f'<p>복원 상담 · 견적 문의 <a href="tel:{TEL.replace("-", "")}" style="color:#d8c08a">{TEL}</a> '
        "(손상 부위 사진과 지역을 문자로 보내 주세요)</p>\n"
        "</div>\n<!--SEO-STATIC-END-->"
    )


def set_static(src, block):
    src = re.sub(r"<!--SEO-STATIC-START.*?<!--SEO-STATIC-END-->", "", src, flags=re.S)
    return re.sub(r'(<div id="root">)\s*(</div>)', lambda m: m.group(1) + "\n" + block + "\n" + m.group(2), src, count=1)


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    names = sorted(n for n in glob.glob("case-*.html") if n != "case-list.html" and n not in EXCLUDE)
    cases = []
    for n in names:
        c = read_case(n)
        if not c:
            print("  건너뜀(제목 없음):", n)
            continue
        c["added"] = git_date(n, first=True)
        cases.append(c)
        src = read(n)
        new = set_head(src, n, c["title"], c["desc"])
        if new != src:
            write(n, new)
            print("  갱신:", n, "→", c["title"])
    cases.sort(key=lambda c: c["added"], reverse=True)

    for page, info in HUBS.items():
        if not os.path.exists(page):
            continue
        src = read(page)
        new = set_head(src, page, info["title"], info["desc"])
        if '<div id="root">' in new:
            new = set_static(new, static_block(page, cases))
        if new != src:
            write(page, new)
            print("  갱신:", page)

    pages = [p for p in HUBS if os.path.exists(p)] + [c["name"] for c in cases]
    rows = "\n".join(
        f"  <url><loc>{url_of(p)}</loc><lastmod>{git_date(p)}</lastmod></url>" for p in pages
    )
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + rows + "\n</urlset>\n")
    write("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n")
    print(f"완료: 사례 {len(cases)}개, 사이트맵 {len(pages)}개 주소")


if __name__ == "__main__":
    main()
