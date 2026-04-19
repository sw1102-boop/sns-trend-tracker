#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SNS 키워드 트래커 v2 — 키워드 자동 발굴
네이버 쇼핑인사이트 API로 카테고리 인기 키워드 자동 수집
+ 네이버 데이터랩 트렌드 + 블로그/뉴스 검색
"""

import requests, json, re, os, sys
from datetime import datetime, timedelta

CLIENT_ID     = os.environ.get("NAVER_CLIENT_ID",     "YOUR_CLIENT_ID")
CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "YOUR_CLIENT_SECRET")

# ============================================================
#  네이버 쇼핑 카테고리 코드
#  자동 발굴에 사용 — 이 카테고리에서 인기 키워드를 뽑아옴
# ============================================================
SHOPPING_CATEGORIES = {
    "디저트/식품": "50000006",   # 식품
    "패션의류":    "50000000",   # 패션의류
}

# 자동 발굴 실패 시 사용할 기본 키워드 (fallback)
FALLBACK_DESSERT  = ["두바이초콜릿", "크루아상타르트", "바스크치즈케이크", "마카롱", "생크림빵"]
FALLBACK_FASHION  = ["테니스코어", "미니멀룩", "Y2K패션", "고프코어", "세미포멀"]

BLOG_EXTRA    = ["현대백화점팝업", "신세계백화점팝업"]
NEWS_KEYWORDS = ["백화점 팝업", "디저트 트렌드", "패션 트렌드"]

HEADERS = {
    "X-Naver-Client-Id":     CLIENT_ID,
    "X-Naver-Client-Secret": CLIENT_SECRET,
}
CHART_COLORS = ["#e74c3c", "#e67e22", "#2980b9", "#8e44ad", "#27ae60"]

# ============================================================
#  API — 쇼핑인사이트 인기 키워드 자동 발굴
# ============================================================

def get_shopping_keywords(category_id: str, label: str, top_n: int = 5) -> list:
    """네이버 쇼핑인사이트 카테고리 인기 키워드 TOP N 자동 수집"""
    url  = "https://openapi.naver.com/v1/datalab/shopping/category/keywords"
    end  = datetime.now()
    start = end - timedelta(days=7)   # 최근 1주 인기 키워드
    body = {
        "startDate": start.strftime("%Y-%m-%d"),
        "endDate":   end.strftime("%Y-%m-%d"),
        "timeUnit":  "date",
        "category":  category_id,
        "keyword":   [],
        "device":    "mo",
        "ages":      [],
        "gender":    "",
    }
    try:
        res = requests.post(
            url,
            headers={**HEADERS, "Content-Type": "application/json"},
            json=body, timeout=12,
        )
        res.raise_for_status()
        data = res.json()
        # 결과: results[0].data 안에 keyword별 ratio 합산 → 상위 N개
        keywords = {}
        for item in data.get("results", []):
            kw = item.get("title", "")
            total = sum(d.get("ratio", 0) for d in item.get("data", []))
            if kw:
                keywords[kw] = total
        ranked = sorted(keywords, key=lambda k: keywords[k], reverse=True)[:top_n]
        print(f"  [{label}] 자동 발굴 키워드: {ranked}")
        return ranked if ranked else None
    except Exception as e:
        print(f"  [{label}] 쇼핑인사이트 오류: {e}", file=sys.stderr)
        return None


# ============================================================
#  API — 기존 함수들
# ============================================================

def get_trend(keywords: list, label: str) -> dict | None:
    url   = "https://openapi.naver.com/v1/datalab/search"
    end   = datetime.now()
    start = end - timedelta(days=28)
    body  = {
        "startDate":    start.strftime("%Y-%m-%d"),
        "endDate":      end.strftime("%Y-%m-%d"),
        "timeUnit":     "week",
        "keywordGroups": [{"groupName": kw, "keywords": [kw]} for kw in keywords[:5]],
        "device": "mo", "ages": [], "gender": "",
    }
    try:
        res = requests.post(
            url,
            headers={**HEADERS, "Content-Type": "application/json"},
            json=body, timeout=12,
        )
        res.raise_for_status()
        print(f"  [{label}] 트렌드 OK")
        return res.json()
    except Exception as e:
        print(f"  [{label}] 트렌드 오류: {e}", file=sys.stderr)
        return None


def search_blog(keyword: str, display: int = 5) -> dict | None:
    try:
        res = requests.get(
            "https://openapi.naver.com/v1/search/blog",
            headers=HEADERS,
            params={"query": keyword, "display": display, "sort": "date"},
            timeout=10,
        )
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"  [블로그:{keyword}] 오류: {e}", file=sys.stderr)
        return None


def search_news(keyword: str, display: int = 4) -> dict | None:
    try:
        res = requests.get(
            "https://openapi.naver.com/v1/search/news",
            headers=HEADERS,
            params={"query": keyword, "display": display, "sort": "date"},
            timeout=10,
        )
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"  [뉴스:{keyword}] 오류: {e}", file=sys.stderr)
        return None


# ============================================================
#  헬퍼
# ============================================================

def strip_tags(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()

def parse_trend(data):
    if not data or "results" not in data:
        return {}, []
    results = data["results"]
    periods = [d["period"] for d in results[0]["data"]] if results else []
    kw_data = {r["title"]: [d["ratio"] for d in r["data"]] for r in results}
    return kw_data, periods

def latest(vals):    return vals[-1] if vals else 0
def change(vals):    return vals[-1] - vals[-2] if len(vals) >= 2 else 0
def chg_str(vals):   v = change(vals); return f"+{v:.1f}" if v >= 0 else f"{v:.1f}"
def chg_color(vals): return "#c0392b" if change(vals) >= 0 else "#7f8c8d"


# ============================================================
#  HTML 빌더
# ============================================================

def kw_cards_html(sorted_kws):
    html = ""
    for i, (kw, vals) in enumerate(sorted_kws[:5]):
        bar   = min(100, int(latest(vals)))
        color = CHART_COLORS[i % len(CHART_COLORS)]
        html += f"""
      <div class="kw-card" onclick="goToBlog('{kw}')">
        <div class="kw-rank">{i+1}위</div>
        <div class="kw-name">{kw}</div>
        <div class="kw-bar-bg"><div class="kw-bar" style="width:{bar}%;background:{color}"></div></div>
        <div class="kw-meta">
          <span class="kw-val">지수 {latest(vals):.1f}</span>
          <span style="font-size:12px;color:{chg_color(vals)};">{chg_str(vals)}</span>
        </div>
      </div>"""
    return html or "<div class='empty'>데이터 없음</div>"


def blog_cards_html(items):
    html = ""
    for item in (items or [])[:5]:
        title    = strip_tags(item.get("title", ""))
        desc     = strip_tags(item.get("description", ""))[:90] + "…"
        link     = item.get("link", "#")
        date_raw = item.get("postdate", "")
        fmt_date = f"{date_raw[:4]}.{date_raw[4:6]}.{date_raw[6:]}" if len(date_raw) == 8 else date_raw
        html += f"""
      <div class="blog-card" onclick="window.open('{link}','_blank')">
        <div class="blog-ttl">{title}</div>
        <div class="blog-desc">{desc}</div>
        <div class="blog-date">{fmt_date}</div>
      </div>"""
    return html or "<div class='blog-date' style='padding:12px'>포스팅 없음</div>"


def build_html(dessert_keywords, fashion_keywords,
               dessert_trend, fashion_trend,
               blog_data, news_data) -> str:

    dessert_kw, d_periods = parse_trend(dessert_trend)
    fashion_kw, f_periods = parse_trend(fashion_trend)
    periods = d_periods or f_periods

    sorted_d = sorted(dessert_kw.items(), key=lambda x: latest(x[1]), reverse=True)
    sorted_f = sorted(fashion_kw.items(), key=lambda x: latest(x[1]), reverse=True)

    d_cards = kw_cards_html(sorted_d)
    f_cards = kw_cards_html(sorted_f)

    blog_tabs = blog_secs = ""
    for i, (kw, result) in enumerate(blog_data.items()):
        items  = (result or {}).get("items", [])
        active = "active" if i == 0 else ""
        show   = "" if i == 0 else 'style="display:none"'
        safe_kw = kw.replace("'", "\\'")
        blog_tabs += f'<div class="cat-tab {active}" onclick="switchBlog(\'{safe_kw}\',this)">{kw}</div>'
        blog_secs += f'<div class="blog-sec" id="blog-{kw}" {show}>{blog_cards_html(items)}</div>'

    news_html = ""
    for kw, result in news_data.items():
        for item in (result or {}).get("items", []):
            title  = strip_tags(item.get("title", ""))
            link   = item.get("link", "#")
            pub    = item.get("pubDate", "")[:16]
            source = item.get("originallink", link)
            try:    domain = source.split("/")[2]
            except: domain = "뉴스"
            news_html += f"""
      <div class="blog-card" onclick="window.open('{link}','_blank')">
        <div class="blog-ttl">{title}</div>
        <div class="blog-date">{domain} · {pub}</div>
      </div>"""

    today = datetime.now().strftime("%Y년 %m월 %d일 %H:%M")
    d_tag_list = " · ".join(dessert_keywords[:5])
    f_tag_list = " · ".join(fashion_keywords[:5])

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SNS 트렌드 트래커 · {today}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Noto Sans KR',sans-serif;background:#f4f4f0;color:#1a1a1a;font-size:14px}}
.header{{background:#fff;border-bottom:1px solid #e0e0dc;padding:14px 24px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:10;flex-wrap:wrap;gap:8px}}
.logo{{font-size:15px;font-weight:600}}
.badges{{display:flex;align-items:center;gap:6px;flex-wrap:wrap}}
.badge{{font-size:11px;padding:2px 8px;border-radius:10px}}
.badge-auto{{background:#e6f4ea;color:#1e7e34}}
.badge-naver{{background:#e8f4fd;color:#1a6fa8}}
.date{{font-size:12px;color:#999}}
.tab-bar{{background:#fff;border-bottom:1px solid #e0e0dc;padding:0 20px;display:flex;overflow-x:auto}}
.tab{{padding:11px 14px;font-size:13px;color:#999;cursor:pointer;border-bottom:2px solid transparent;transition:all .15s;white-space:nowrap}}
.tab.active{{color:#1a1a1a;border-bottom-color:#1a1a1a;font-weight:500}}
.wrap{{max-width:900px;margin:0 auto;padding:18px 14px}}
.tc{{display:none}}.tc.active{{display:block}}
.sec-label{{font-size:11px;font-weight:600;color:#aaa;letter-spacing:.05em;text-transform:uppercase;margin-bottom:10px}}
.auto-banner{{background:#e6f4ea;border:1px solid #a8d5b0;border-radius:8px;padding:10px 14px;margin-bottom:14px;font-size:12px;color:#1e5631;line-height:1.6}}
.cat-tabs{{display:flex;gap:6px;margin-bottom:14px;flex-wrap:wrap}}
.cat-tab{{font-size:12px;padding:4px 12px;border-radius:20px;border:1px solid #ddd;color:#666;cursor:pointer;transition:all .15s}}
.cat-tab.active{{background:#1a1a1a;color:#fff;border-color:#1a1a1a}}
.kw-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:18px}}
.kw-card{{background:#fff;border:1px solid #e5e5e0;border-radius:12px;padding:14px;cursor:pointer;transition:border-color .15s}}
.kw-card:hover{{border-color:#aaa}}
.kw-rank{{font-size:11px;color:#bbb;margin-bottom:4px}}
.kw-name{{font-size:15px;font-weight:600;margin-bottom:8px}}
.kw-bar-bg{{background:#f0f0ee;border-radius:3px;height:4px;margin-bottom:6px}}
.kw-bar{{height:4px;border-radius:3px}}
.kw-meta{{display:flex;justify-content:space-between}}
.kw-val{{font-size:12px;color:#999}}
.chart-box{{background:#fff;border:1px solid #e5e5e0;border-radius:12px;padding:18px;margin-bottom:14px}}
.chart-box h3{{font-size:13px;font-weight:500;margin-bottom:4px;color:#444}}
.chart-sub{{font-size:11px;color:#999;margin-bottom:14px}}
.blog-card{{background:#f8f8f5;border-radius:8px;padding:12px;margin-bottom:8px;cursor:pointer;transition:background .15s}}
.blog-card:hover{{background:#eeeee8}}
.blog-ttl{{font-size:13px;font-weight:500;margin-bottom:3px;line-height:1.4}}
.blog-desc{{font-size:12px;color:#777;line-height:1.5;margin-bottom:3px}}
.blog-date{{font-size:11px;color:#bbb}}
.empty{{font-size:13px;color:#bbb;padding:20px;text-align:center}}
@media(max-width:600px){{.kw-grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div class="header">
  <div class="logo">📊 SNS 트렌드 트래커</div>
  <div class="badges">
    <span class="badge badge-auto">🤖 키워드 자동 발굴</span>
    <span class="badge badge-naver">네이버 쇼핑인사이트</span>
    <span class="date">업데이트 {today}</span>
  </div>
</div>
<div class="tab-bar">
  <div class="tab active" onclick="showTab('trend',this)">오늘의 트렌드</div>
  <div class="tab" onclick="showTab('chart',this)">트렌드 그래프</div>
  <div class="tab" onclick="showTab('blog',this)">블로그 모니터링</div>
  <div class="tab" onclick="showTab('news',this)">뉴스 동향</div>
</div>

<div class="wrap">
  <div id="tab-trend" class="tc active">
    <div class="auto-banner">
      🤖 <strong>키워드 자동 발굴</strong> — 네이버 쇼핑인사이트 기준 최근 7일 인기 검색어를 자동 수집했습니다<br>
      디저트: {d_tag_list}<br>
      패션: {f_tag_list}
    </div>
    <div class="cat-tabs">
      <div class="cat-tab active" onclick="switchCat('d',this)">디저트/식품</div>
      <div class="cat-tab" onclick="switchCat('f',this)">패션의류</div>
    </div>
    <div id="cat-d">
      <div class="sec-label">디저트/식품 인기 키워드 (자동 발굴)</div>
      <div class="kw-grid">{d_cards}</div>
    </div>
    <div id="cat-f" style="display:none">
      <div class="sec-label">패션의류 인기 키워드 (자동 발굴)</div>
      <div class="kw-grid">{f_cards}</div>
    </div>
  </div>

  <div id="tab-chart" class="tc">
    <div class="chart-box">
      <h3>디저트/식품 트렌드 (최근 4주)</h3>
      <div class="chart-sub">자동 발굴 키워드: {d_tag_list}</div>
      <canvas id="dc" height="180"></canvas>
    </div>
    <div class="chart-box">
      <h3>패션의류 트렌드 (최근 4주)</h3>
      <div class="chart-sub">자동 발굴 키워드: {f_tag_list}</div>
      <canvas id="fc" height="180"></canvas>
    </div>
  </div>

  <div id="tab-blog" class="tc">
    <div class="sec-label">키워드별 최신 블로그 포스팅</div>
    <div class="cat-tabs">{blog_tabs}</div>
    {blog_secs}
  </div>

  <div id="tab-news" class="tc">
    <div class="sec-label">최신 뉴스</div>
    {news_html or "<div class='empty'>뉴스 없음</div>"}
  </div>
</div>

<script>
const dessertData={json.dumps(dessert_kw)};
const fashionData={json.dumps(fashion_kw)};
const labels={json.dumps([p[5:] for p in periods])};
const C=["#e74c3c","#e67e22","#2980b9","#8e44ad","#27ae60"];
function showTab(id,el){{
  document.querySelectorAll('.tc').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('tab-'+id).classList.add('active');
  el.classList.add('active');
  if(id==='chart')initCharts();
}}
function switchCat(id,el){{
  document.querySelectorAll('.cat-tab').forEach(e=>e.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('cat-d').style.display=id==='d'?'':'none';
  document.getElementById('cat-f').style.display=id==='f'?'':'none';
}}
function goToBlog(kw){{
  showTab('blog',document.querySelectorAll('.tab')[2]);
  const el=[...document.querySelectorAll('#tab-blog .cat-tab')].find(e=>e.textContent===kw);
  switchBlog(kw,el);
}}
function switchBlog(kw,el){{
  document.querySelectorAll('.blog-sec').forEach(s=>s.style.display='none');
  const t=document.getElementById('blog-'+kw);
  if(t)t.style.display='';
  document.querySelectorAll('#tab-blog .cat-tab').forEach(e=>e.classList.remove('active'));
  if(el)el.classList.add('active');
}}
let initiated=false;
function initCharts(){{
  if(initiated)return;initiated=true;
  const opts={{responsive:true,plugins:{{legend:{{position:'bottom',labels:{{font:{{size:12}}}}}},tooltip:{{mode:'index'}}}},scales:{{y:{{min:0,title:{{display:true,text:'검색지수',font:{{size:11}}}}}}}}}};
  function ds(data){{return Object.entries(data).map(([n,v],i)=>({{label:n,data:v,borderColor:C[i%C.length],backgroundColor:C[i%C.length]+'22',tension:0.4,fill:false,pointRadius:3}}));}}
  new Chart(document.getElementById('dc'),{{type:'line',data:{{labels,datasets:ds(dessertData)}},options:opts}});
  new Chart(document.getElementById('fc'),{{type:'line',data:{{labels,datasets:ds(fashionData)}},options:opts}});
}}
</script>
</body>
</html>"""


# ============================================================
#  메인
# ============================================================

def main():
    print("\n" + "="*52)
    print("  SNS 키워드 트래커 v2  |  키워드 자동 발굴")
    print("="*52)

    if CLIENT_ID == "YOUR_CLIENT_ID":
        print("\n⚠️  API 키 미설정.\n")
        sys.exit(1)

    # ① 쇼핑인사이트로 키워드 자동 발굴
    print("\n[1/5] 디저트/식품 인기 키워드 자동 발굴 중...")
    dessert_keywords = get_shopping_keywords("50000006", "디저트/식품", top_n=5)
    if not dessert_keywords:
        print("  → 자동 발굴 실패, 기본 키워드 사용")
        dessert_keywords = FALLBACK_DESSERT

    print("[2/5] 패션의류 인기 키워드 자동 발굴 중...")
    fashion_keywords = get_shopping_keywords("50000000", "패션의류", top_n=5)
    if not fashion_keywords:
        print("  → 자동 발굴 실패, 기본 키워드 사용")
        fashion_keywords = FALLBACK_FASHION

    # ② 발굴된 키워드로 트렌드 조회
    print("[3/5] 트렌드 지수 조회 중...")
    dessert_trend = get_trend(dessert_keywords, "디저트")
    fashion_trend = get_trend(fashion_keywords, "패션")

    # ③ 블로그 수집 (자동 발굴 키워드 상위 3개 + 경쟁사)
    print("[4/5] 블로그 수집 중...")
    blog_keywords = dessert_keywords[:3] + fashion_keywords[:2] + BLOG_EXTRA
    blog_data = {}
    for kw in blog_keywords:
        print(f"  → {kw}")
        blog_data[kw] = search_blog(kw, display=5)

    # ④ 뉴스 수집
    print("[5/5] 뉴스 수집 중...")
    news_data = {kw: search_news(kw) for kw in NEWS_KEYWORDS}

    # ⑤ HTML 생성
    print("\nHTML 생성 중...")
    html = build_html(
        dessert_keywords, fashion_keywords,
        dessert_trend, fashion_trend,
        blog_data, news_data,
    )

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅ 완료 → {out}")
    if not os.environ.get("CI"):
        import webbrowser
        webbrowser.open(f"file://{out}")


if __name__ == "__main__":
    main()
