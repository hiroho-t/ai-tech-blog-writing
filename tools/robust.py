#!/usr/bin/env python3
"""数字を主張に変える前の検算。

analyze_titles.py と measure.py が出した数字を、次の3点で潰しにいく。
  1. プラットフォームを混ぜていないか（QiitaのLGTMとZennのいいねは単位が違う）
  2. 標本の作られ方（生存バイアス）が、見えている差を作っていないか
  3. 書き手ごとの相関を無視していないか（同じ人の記事は似る）
  4. 作った判別規則を、作るのに使っていない記事で試したか

usage: python3 tools/robust.py
必要なファイル: qiita_pool.json / zenn_pool.json（collect_*.py が作る）、metrics.tsv
"""
import json, re, csv, random, collections, statistics as st, datetime as dt, os, sys, time, urllib.request

random.seed(42)
HERE = os.path.dirname(os.path.abspath(__file__))

PATS = {
    '【】で囲う前置き': r'^【.+?】',
    '数字＋選/個/つ/のこと': r'\d+\s*(選|個|つ|のこと|Tips|tips|パターン|手順|ステップ)',
    '「まとめ」「集」で終わる': r'(まとめ|集)$',
    '入門/はじめて/初心者': r'(入門|はじめて|初めて|初心者|ゼロから|0から)',
    '〜してみた/やってみた': r'(してみた|やってみた|作ってみた|試してみた|使ってみた)',
    '〜する方法/やり方/ガイド': r'(方法|やり方|手順|ガイド)',
    '疑問形（？で終わる）': r'[?？]\s*$',
    'なぜ〜のか': r'^なぜ|のか[？?]?$',
    '完全版/決定版/永久保存版': r'(完全版|決定版|永久保存版|総まとめ|徹底)',
    '命令形（〜しろ/やめろ）': r'(しろ|やめろ|するな|集合|見ろ|読め)',
    '体験の数値': r'(\d+年|\d+ヶ月|\d+か月|\d+円|\d+万|\d+倍|\d+%)',
    '比較（違い/vs/どっち）': r'(の違い|との違い|[Vv][Ss]|どっち|比較)',
    '丁寧に/やさしく/図解': r'(丁寧|やさしく|優しく|わかりやすく|分かりやすく|figure|図解)',
}
MIN_N = 10          # これ未満の型は判定しない
BOOT = 4000


def boot_median_ci(vals, n=BOOT):
    meds = sorted(st.median(random.choices(vals, k=len(vals))) for _ in range(n))
    return meds[int(n * .025)], meds[int(n * .975)]


CACHE = os.path.join(HERE, '..', 'bodies')


def fetch(url):
    """measure.py と同じキャッシュを使う"""
    os.makedirs(CACHE, exist_ok=True)
    key = os.path.join(CACHE, re.sub(r'[^A-Za-z0-9]+', '_', url)[-120:] + '.cache')
    if os.path.exists(key):
        return open(key, encoding='utf-8').read()
    req = urllib.request.Request(url, headers={'User-Agent': 'writing-research/1.0', 'Accept': '*/*'})
    t = urllib.request.urlopen(req).read().decode('utf-8', 'replace')
    open(key, 'w', encoding='utf-8').write(t)
    time.sleep(1.1)
    return t


def load(name):
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        p = name
    if not os.path.exists(p):
        print(f'[skip] {name} がありません（collect_*.py を先に実行）', file=sys.stderr)
        return None
    return json.load(open(p, encoding='utf-8'))


# ---------- 1. プラットフォームを分けて、信頼区間つきで見る ----------
def check_titles(q, z):
    print('=' * 72)
    print('1. タイトルの型：プラットフォームを分けて、95%信頼区間をつける')
    print('=' * 72)
    print('  QiitaのLGTMとZennのいいねは単位も母数も違う。混ぜて中央値を出すと、')
    print('  「その型がQiita寄りかZenn寄りか」を測っているだけになる。\n')

    for label, data in (('Qiita（stocks>300の打ち切り標本）', q), ('Zenn（いいね順）', z)):
        if data is None:
            continue
        allv = [x[1] for x in data]
        base = st.median(allv)
        lo, hi = boot_median_ci(allv)
        print(f'--- {label}  n={len(data)}  全体中央={base:.0f}（95%CI {lo:.0f}〜{hi:.0f}）')
        print(f"    {'タイトルの型':<24}{'n':>5}{'中央':>7}  95%信頼区間        判定")
        rows = []
        for k, p in PATS.items():
            v = [l for t, l in data if re.search(p, t)]
            if len(v) < MIN_N:
                rows.append((-1, k, len(v), 0, 0, 'n<10で判定せず'))
                continue
            m = st.median(v)
            l2, h2 = boot_median_ci(v)
            j = '高い' if l2 > base else '低い' if h2 < base else '差があるとは言えない'
            rows.append((m, k, len(v), l2, h2, j))
        for m, k, n_, l2, h2, j in sorted(rows, reverse=True):
            if m < 0:
                print(f'    {k:<24}{n_:>5}{"—":>7}  （{j}）')
            else:
                print(f'    {k:<24}{n_:>5}{m:>7.0f}  {l2:>6.0f}〜{h2:<10.0f} {j}')
        print()

    # 混合プールの中央値が、Qiita比率でどれだけ説明できるか
    if q and z:
        print('--- 混ぜるとどうなるか（Qiita比率と、混合プールでの中央値）')
        both = [(t, l, 'q') for t, l in q] + [(t, l, 'z') for t, l in z]
        print(f"    {'タイトルの型':<24}{'Qiita本数':>9}{'Zenn本数':>9}{'Qiita比率':>10}{'混合の中央':>11}")
        out = []
        for k, p in PATS.items():
            hit = [(l, s) for t, l, s in both if re.search(p, t)]
            nq = sum(1 for _, s in hit if s == 'q')
            nz = len(hit) - nq
            if not hit:
                continue
            out.append((nq / len(hit), k, nq, nz, st.median([l for l, _ in hit])))
        for ratio, k, nq, nz, med in sorted(out, reverse=True):
            print(f'    {k:<24}{nq:>9}{nz:>9}{100*ratio:>9.0f}%{med:>11.0f}')
        print('    → Qiita比率の順番と、混合の中央値の順番がほぼ一致するなら、')
        print('       それは「型の効き目」ではなく「どちらのサイトに多い型か」を見ている。\n')


# ---------- 2. 標本の作られ方を暴く ----------
def check_pool(z):
    if z is None:
        return
    print('=' * 72)
    print('2. Zennプールの実体：どこまでが「全量」で、どこからが「当たりだけ」か')
    print('=' * 72)
    c = collections.Counter(a['published_at'][:10] for a in z)
    days = sorted(c)
    latest = dt.date.fromisoformat(days[-1])
    # 1日あたりの本数が急に落ちるところを境目とみなす
    dense = [d for d in days if c[d] >= 20]
    if not dense:
        print('  日別の密度が低く、判定できません\n')
        return
    cut = min(dense)
    full = [a for a in z if a['published_at'][:10] >= cut]
    old = [a for a in z if a['published_at'][:10] < cut]
    print(f'  取得日の最新記事: {latest}')
    print(f'  1日20本以上入っている期間: {cut} 〜 {days[-1]}（{len(full)}本 = 全体の{100*len(full)/len(z):.0f}%）')
    print(f'    いいね中央 {st.median([a["liked_count"] for a in full]):.0f}／'
          f'いいね0の割合 {100*sum(1 for a in full if a["liked_count"]==0)/len(full):.0f}%'
          f'／本文字数の中央 {st.median([a["body_letters_count"] for a in full if a["body_letters_count"]]):.0f}字')
    if old:
        print(f'  それ以前: {len(old)}本  いいね中央 {st.median([a["liked_count"] for a in old]):.0f}'
              f'／本文字数の中央 {st.median([a["body_letters_count"] for a in old if a["body_letters_count"]]):.0f}字')
    print()
    print('  → 前者は「ほぼ全量」、後者は「いいねが多くて残ったもの」。性質が違う2つが入っている。')
    print('     この境目をまたいで長さや型を比べると、比べているのは長さではなく')
    print('     「生き残ったかどうか」になる（生存バイアス）。')
    print('     長さと評価の関係を言いたいなら、全量の期間の中だけで、')
    print('     しかも評価が溜まる時間をそろえて比べる必要がある。\n')


# ---------- 3. 書き手ごとの相関を無視しない ----------
def check_metrics():
    p = os.path.join(HERE, 'metrics.tsv')
    if not os.path.exists(p):
        print('[skip] metrics.tsv がありません', file=sys.stderr)
        return
    rows = list(csv.DictReader(open(p, encoding='utf-8'), delimiter='\t'))
    by = collections.defaultdict(list)
    for r in rows:
        by[r['author']].append(r)
    authors = list(by)
    print('=' * 72)
    print('3. 指標の帯：書き手を選び直すブートストラップで信頼区間をつける')
    print('=' * 72)
    print(f'  記事{len(rows)}本／書き手{len(authors)}人。同じ人の記事は似るので、')
    print('  記事ではなく「人」を選び直す（クラスタブートストラップ）。\n')

    def ci(field, f, quant):
        out = []
        for _ in range(BOOT):
            picked = [r for a in random.choices(authors, k=len(authors)) for r in by[a]]
            v = sorted(f(r[field]) for r in picked)
            out.append(v[int(len(v) * quant)])
        out.sort()
        return out[int(BOOT * .025)], out[int(BOOT * .975)]

    for field, label, f in (('chars_per_h2', '1見出しあたり文字数', int),
                            ('avg_sent', '1文の平均文字数', float),
                            ('over80', '80字超えの文の割合(%)', int)):
        v = sorted(f(r[field]) for r in rows)
        print(f'  {label}')
        for q, nm in ((.25, '25%'), (.5, '中央'), (.75, '75%')):
            lo, hi = ci(field, f, q)
            print(f'    {nm:<4}{v[int(len(v)*q)]:>8.1f}   95%CI {lo:>6.0f}〜{hi:<6.0f}')
        print()
    print('  → 信頼区間の幅の中でしか、しきい値を語れない。')
    print('     「中央505字」ではなく「おおよそ400〜700字」と書く。\n')


# ---------- 4. 判別規則を、作るのに使っていない記事で試す ----------
CURATION_TITLE = r'(まとめ|集$|チートシート|ロードマップ|リンク集|資料|教材|選$|\d+選|一覧)'


def article_features(item_id, fetch_fn):
    """Qiita記事1本から、判別規則に使う値を出す"""
    d = json.loads(fetch_fn(f'https://qiita.com/api/v2/items/{item_id}'))
    md = d['body']
    nc = re.sub(r'```.*?```', '', md, flags=re.S)
    heads = re.findall(r'^#{1,6}\s+(.+)$', nc, re.M)
    link_heads = [h for h in heads if re.match(r'^\s*\**\[[^\]]*\]\(https?://', h.strip())]
    prose = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', nc)
    prose = re.sub(r'\[([^\]]*)\]\([^)]+\)', r'\1', prose)
    prose = re.sub(r'^\s*(#{1,6}|>|[-*+]|\d+[.)])\s*', '', prose, flags=re.M)
    prose = re.sub(r'`[^`\n]*`', '', prose)
    chars = len(re.sub(r'\s', '', prose))
    env = len(re.findall(r'(\d{4}年\d{1,2}月|時点|バージョン|version|v\d+\.\d+|環境[:：]|\d+\.\d+\.\d+)', prose))
    pit = len(re.findall(r'(ハマ|つまず|つまづ|失敗|注意点|うまくいかな|エラー|落とし穴|罠|トラブル)', prose))
    return dict(
        pct_link_heads=100 * len(link_heads) / len(heads) if heads else 0,
        per_head=chars / len(heads) if heads else chars,
        env_pit=env + pit,
        per_100=100 * d['likes_count'] / max(chars, 1),
    )


def check_rule(qp, fetch_fn, n_each=12, seed=3):
    """method/02 の4基準を、測っていない記事で採点する"""
    if qp is None:
        return
    print('=' * 72)
    print('4. 判別規則を、作るのに使っていない記事で試す')
    print('=' * 72)
    rng = random.Random(seed)
    pool = [a for a in qp if a['user']['id'] != 'KNR109']
    cur = [a for a in pool if re.search(CURATION_TITLE, a['title'])]
    non = [a for a in pool if not re.search(CURATION_TITLE, a['title'])]
    rng.shuffle(cur); rng.shuffle(non)
    sel = [(a, 'まとめ系') for a in cur[:n_each]] + [(a, 'それ以外') for a in non[:n_each]]
    print(f'  タイトルで「まとめ系」{len(cur)}本／「それ以外」{len(non)}本。'
          f'各{n_each}本を無作為に取って規則を当てる。\n')

    names = ['①見出しリンク>30%', '②env+pit=0', '③1見出し<350字', '④評価/100字>50']
    tab = {n: [0, 0] for n in names}
    tp = fp = 0
    for a, grp in sel:
        try:
            f = article_features(a['id'], fetch_fn)
        except Exception:
            continue
        c = [f['pct_link_heads'] > 30, f['env_pit'] == 0, f['per_head'] < 350, f['per_100'] > 50]
        for n, v in zip(names, c):
            if v:
                tab[n][0 if grp == 'まとめ系' else 1] += 1
        if sum(c) >= 2:
            if grp == 'まとめ系':
                tp += 1
            else:
                fp += 1
    print(f"  {'基準':<16}{'まとめ系で当たる':>12}{'それ以外で当たる':>14}")
    for n in names:
        print(f'  {n:<16}{tab[n][0]:>10}/{n_each}{tab[n][1]:>12}/{n_each}')
    print(f'\n  4基準のうち2つ以上で除外した場合：')
    print(f'    感度（まとめ系を正しく除外）{100*tp/n_each:>5.0f}%'
          f'   偽陽性（それ以外を誤って除外）{100*fp/n_each:>5.0f}%')
    print('    → 感度が低く偽陽性が残るなら、その規則は使えない。')
    print('       少数の例から作った規則は、作るのに使った記事では必ず当たる。')
    print('       測っていない記事で試してから書く。\n')


if __name__ == '__main__':
    qp, zp = load('qiita_pool.json'), load('zenn_pool.json')
    q = [(x['title'], x['likes_count']) for x in qp] if qp else None
    z = [(x['title'], x['liked_count']) for x in zp] if zp else None
    check_titles(q, z)
    check_pool(zp)
    check_metrics()
    check_rule(qp, fetch)
