#!/usr/bin/env python3
"""技術記事の書き方を機械的に測る。Qiita(API/markdown) と Zenn(HTML) の両対応。
usage: python3 measure.py targets.tsv > metrics.tsv
targets.tsv: site<TAB>author<TAB>id_or_url<TAB>label
"""
import json, re, sys, os, time, urllib.request, html as htmllib

UA = {'Accept': 'application/json', 'User-Agent': 'writing-research/1.0'}
CACHE = 'bodies'

def fetch(url, binary=False):
    key = os.path.join(CACHE, re.sub(r'[^A-Za-z0-9]+', '_', url)[-120:] + '.cache')
    if os.path.exists(key):
        return open(key, encoding='utf-8').read()
    req = urllib.request.Request(url, headers={'User-Agent': UA['User-Agent'], 'Accept': '*/*'})
    t = urllib.request.urlopen(req).read().decode('utf-8', 'replace')
    open(key, 'w', encoding='utf-8').write(t)
    time.sleep(1)
    return t

# ---------- 本文の取り出し ----------
def qiita_body(item_id):
    d = json.loads(fetch(f'https://qiita.com/api/v2/items/{item_id}'))
    return d['body'], d['title'], d['likes_count'], d['created_at'][:10], d['url']

def zenn_body(url):
    h = fetch(url)
    i = h.find('class="znc')
    if i < 0: raise RuntimeError('znc not found: ' + url)
    start = h.rfind('<div', 0, i)
    # 対応する閉じdivまでを深さで追う
    depth, j = 0, start
    while j < len(h):
        m = re.compile(r'</?div\b').search(h, j)
        if not m: break
        depth += 1 if h[m.start():m.start()+5] != '</div' else -1
        j = m.end()
        if depth == 0: break
    body_html = h[start:j]
    title = re.search(r'<title>(.*?)</title>', h, re.S)
    # いいね数・公開日はページ埋め込みJSONの先頭の出現（＝この記事のもの）から取る
    m_like = re.search(r'"likedCount":(\d+)', h)
    m_date = re.search(r'"publishedAt":"(\d{4}-\d{2}-\d{2})', h)
    return (body_html, htmllib.unescape(title.group(1)) if title else '',
            int(m_like.group(1)) if m_like else None,
            m_date.group(1) if m_date else '', url)

# ---------- HTML/MDの正規化 ----------
def from_markdown(md):
    code = re.findall(r'```.*?```', md, re.S) + re.findall(r'^(?:    \S.*\n)+', md, re.M)
    md_nc = re.sub(r'```.*?```', '\x00CODE\x00', md, flags=re.S)
    imgs = re.findall(r'!\[[^\]]*\]\([^)]+\)', md_nc)
    h2 = re.findall(r'^##\s+(.+)$', md_nc, re.M) + re.findall(r'^#\s+(.+)$', md_nc, re.M)
    h3 = re.findall(r'^###\s+(.+)$', md_nc, re.M)
    tables = len(re.findall(r'^\|.+\|\s*$\n\|[\s:|-]+\|', md_nc, re.M))
    ul = len(re.findall(r'^\s*[-*+]\s+\S', md_nc, re.M))
    ol = len(re.findall(r'^\s*\d+[.)]\s+\S', md_nc, re.M))
    bold = len(re.findall(r'\*\*[^*\n]+\*\*', md_nc))
    links = len(re.findall(r'https?://', md_nc))
    prose = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', md_nc)
    prose = re.sub(r'\[([^\]]*)\]\([^)]+\)', r'\1', prose)
    prose = re.sub(r'^\s*(#{1,6}|>|[-*+]|\d+[.)])\s*', '', prose, flags=re.M)
    prose = re.sub(r'`[^`\n]*`', '', prose)
    prose = re.sub(r'\x00CODE\x00', '', prose)
    prose = re.sub(r'[*_|]', '', prose)
    return dict(code=len(code), code_lines=sum(c.count('\n') for c in code), imgs=len(imgs),
                h2=h2, h3=len(h3), tables=tables, ul=ul, ol=ol, bold=bold, links=links, prose=prose)

def from_html(bh):
    code = re.findall(r'<pre\b.*?</pre>', bh, re.S)
    nc = re.sub(r'<pre\b.*?</pre>', '', bh, flags=re.S)
    imgs = len(re.findall(r'<img\b', nc))
    def tag_texts(t):
        return [re.sub(r'<[^>]+>', '', x) for x in re.findall(rf'<{t}\b.*?</{t}>', nc, re.S)]
    h2 = tag_texts('h2') + tag_texts('h1')
    h3 = len(tag_texts('h3'))
    tables = len(re.findall(r'<table\b', nc))
    ul = len(re.findall(r'<li\b', nc))
    ol = sum(len(re.findall(r'<li\b', o)) for o in re.findall(r'<ol\b.*?</ol>', nc, re.S))
    bold = len(re.findall(r'<strong\b', nc))
    links = len(re.findall(r'<a\b[^>]*href="https?://', nc))
    prose = re.sub(r'<(script|style|aside)\b.*?</\1>', '', nc, flags=re.S)
    prose = re.sub(r'<h[1-6]\b.*?</h[1-6]>', '', prose, flags=re.S)
    prose = re.sub(r'<code\b.*?</code>', '', prose, flags=re.S)
    prose = re.sub(r'<br\s*/?>', '\n', prose)
    prose = re.sub(r'</(p|li|div|h[1-6]|tr)>', '\n', prose)
    prose = htmllib.unescape(re.sub(r'<[^>]+>', '', prose))
    return dict(code=len(code), code_lines=sum(c.count('\n') for c in code), imgs=imgs,
                h2=h2, h3=h3, tables=tables, ul=ul, ol=ol - 0, bold=bold, links=links, prose=prose)

# ---------- 指標 ----------
# 「向け」「の人」だけだと「◯◯向けコミュニティ」「周りの人」を拾ってしまうので、
# 読者を名指しする定型句に絞る
READER = r'(対象読者|想定読者|対象者|こんな(?:人|方)|向けの(?:記事|内容|話)|向けです|この記事は[^。]{0,25}(?:向け|方へ)|読者の方)'
GOAL   = r'(本記事では|この記事では|本稿では|今回は|紹介します|解説します|書きます|まとめます|説明します)'
ENVVER = r'(\d{4}年\d{1,2}月|時点|バージョン|version|v\d+\.\d+|環境[:：]|検証環境|動作環境|\d+\.\d+\.\d+)'
PITFALL= r'(ハマ|はま[らりるっ]|つまず|つまづ|躓|失敗|注意点|うまくいかな|エラー|落とし穴|できなかった|詰まった|罠|トラブル)'
FIRSTP = r'(私|僕|自分|我々|筆者)'
CALL   = r'(ましょう|してください|してみてください|みなさん|あなた|ぜひ)'
HEDGE  = r'(かもしれません|と思います|気がする|だろう|ような気)'

def sentences(prose):
    # 単独行の裸URLは文として数えない（リンクの多い記事で平均文長が上振れするため）
    prose = re.sub(r'^\s*https?://\S+\s*$', '', prose, flags=re.M)
    s = [x.strip() for x in re.split(r'(?<=[。！？])\s*|\n{2,}', prose) if x and x.strip()]
    return [x for x in s if len(x) > 3 and not re.fullmatch(r'https?://\S+', x)]

def measure(site, author, ident, label):
    if site == 'qiita':
        raw, title, likes, date, url = qiita_body(ident)
        f = from_markdown(raw)
    else:
        raw, title, likes, date, url = zenn_body(ident)
        f = from_html(raw)
    prose = re.sub(r'\n{3,}', '\n\n', f['prose'])
    chars = len(re.sub(r'\s', '', prose))
    sents = sentences(prose)
    lens = [len(re.sub(r'\s', '', s)) for s in sents] or [0]
    head = prose[:600]
    h2n = len(f['h2'])
    return dict(
        site=site, author=author, label=label, url=url, likes=likes or '', date=date,
        chars=chars, h2=h2n, h3=f['h3'],
        chars_per_h2=round(chars / h2n) if h2n else chars,
        sent=len(sents), avg_sent=round(sum(lens) / len(lens), 1),
        over80=round(100 * sum(1 for l in lens if l > 80) / len(lens)),
        code=f['code'], code_lines=f['code_lines'], imgs=f['imgs'], tables=f['tables'],
        li=f['ul'], ol=f['ol'], bold=f['bold'], links=f['links'],
        reader_head=int(bool(re.search(READER, head))),
        goal_head=int(bool(re.search(GOAL, head))),
        env=len(re.findall(ENVVER, prose)),
        pitfall=len(re.findall(PITFALL, prose)),
        firstp=len(re.findall(FIRSTP, prose)),
        call=len(re.findall(CALL, prose)),
        hedge=len(re.findall(HEDGE, prose)),
        title=title[:60],
    )

if __name__ == '__main__':
    cols = None
    for line in open(sys.argv[1], encoding='utf-8'):
        line = line.rstrip('\n')
        if not line or line.startswith('#'): continue
        site, author, ident, label = (line.split('\t') + ['', '', '', ''])[:4]
        try:
            r = measure(site, author, ident, label)
        except Exception as e:
            print('ERR', author, label, e, file=sys.stderr); continue
        if cols is None:
            cols = list(r.keys()); print('\t'.join(cols))
        print('\t'.join(str(r[c]) for c in cols))
