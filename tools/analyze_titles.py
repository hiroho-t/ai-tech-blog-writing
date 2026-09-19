import json, re, collections, statistics as st
q=json.load(open('qiita_pool.json')); z=json.load(open('zenn_pool.json'))
T=[(x['title'], x['likes_count'], 'qiita') for x in q]+[(x['title'], x['liked_count'], 'zenn') for x in z]
pats = {
 '【】で囲う前置き': r'^【.+?】',
 '数字＋選/個/つ/のこと': r'\d+\s*(選|個|つ|のこと|Tips|tips|パターン|手順|ステップ)',
 '「まとめ」「集」で終わる': r'(まとめ|集)$',
 '入門/超入門/はじめて': r'(入門|はじめて|初めて|初心者|ゼロから|0から)',
 '〜してみた/やってみた': r'(してみた|やってみた|作ってみた|試してみた|使ってみた)',
 '〜する方法/やり方': r'(方法|やり方|手順|ガイド)',
 '疑問形（？で終わる）': r'[?？]\s*$',
 'なぜ〜のか': r'^なぜ|のか[？?]?$',
 '〜完全版/決定版/永久保存版': r'(完全版|決定版|永久保存版|総まとめ|徹底)',
 '命令形（〜しろ/やめろ/集合）': r'(しろ|やめろ|するな|集合|見ろ|読め)',
 '体験の数値（〜年/〜ヶ月/〜円/〜倍）': r'(\d+年|\d+ヶ月|\d+か月|\d+円|\d+万|\d+倍|\d+%)',
 '比較（違い/vs/どっち）': r'(の違い|との違い|[Vv][Ss]|どっち|比較)',
 '丁寧に/やさしく/わかりやすく': r'(丁寧|やさしく|優しく|わかりやすく|分かりやすく|figure|図解)',
}
print(f"母集団：Qiita {len(q)}本（stocks>300）＋ Zenn {len(z)}本（liked降順40ページ）= {len(T)}本\n")
print(f"{'タイトルの型':<28} {'本数':>5} {'占有率':>6} {'LGTM中央':>8}")
allmed=st.median([l for _,l,_ in T])
for name,p in sorted(pats.items(), key=lambda kv:-sum(1 for t,_,_ in T if re.search(kv[1],t))):
    hit=[l for t,l,_ in T if re.search(p,t)]
    if not hit: continue
    print(f"{name:<28} {len(hit):>5} {100*len(hit)/len(T):>5.1f}% {st.median(hit):>8.0f}")
print(f"{'（全体）':<28} {len(T):>5} {100.0:>5.1f}% {allmed:>8.0f}")
print('\n--- タイトル長 ---')
ln=[len(t) for t,_,_ in T]
print(f"中央 {st.median(ln):.0f}字 / 平均 {st.mean(ln):.1f}字 / 25〜75%帯 {sorted(ln)[len(ln)//4]}〜{sorted(ln)[3*len(ln)//4]}字")
print('\n--- Zenn：本文字数とlikedの関係（本文字数で5分割）---')
zz=sorted([(x['body_letters_count'], x['liked_count']) for x in z if x['body_letters_count']])
n=len(zz)//5
for i in range(5):
    seg=zz[i*n:(i+1)*n] if i<4 else zz[4*n:]
    print(f"  {seg[0][0]:>6}〜{seg[-1][0]:>6}字  n={len(seg):>4}  liked中央 {st.median([l for _,l in seg]):>5.0f}  liked上位10%の閾値 {sorted([l for _,l in seg])[int(len(seg)*0.9)]:>5}")
