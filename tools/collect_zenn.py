import json, urllib.request, time, collections, sys
def get(url):
    req=urllib.request.Request(url, headers={'Accept':'application/json','User-Agent':'research/1.0'})
    return json.load(urllib.request.urlopen(req))
arts=[]; page=1
while page<=40:
    d=get(f"https://zenn.dev/api/articles?order=liked_count&page={page}")
    a=d.get('articles',[])
    if not a: break
    arts+=a
    print('page',page,len(a),'max',max(x['liked_count'] for x in a), file=sys.stderr)
    nxt=d.get('next_page')
    if not nxt: break
    page=nxt; time.sleep(0.6)
json.dump(arts, open('zenn_pool.json','w'), ensure_ascii=False)
print(f"\n総記事数 {len(arts)}  liked最大 {max(a['liked_count'] for a in arts)}")
top=sorted(arts,key=lambda a:-a['liked_count'])[:25]
print("\n--- liked上位 ---")
for a in top:
    print(f"{a['liked_count']:>4} {a['body_letters_count']:>6}字 {a['user']['username']:<18} {a['title'][:50]}")
by=collections.defaultdict(list)
for a in arts: by[a['user']['username']].append(a)
rows=[]
for u,xs in by.items():
    if len(xs)>=2:
        lg=sorted(x['liked_count'] for x in xs); med=lg[len(lg)//2]
        rows.append((len(xs),med,sum(lg),u))
rows.sort(key=lambda r:(-r[2]))
print(f"\n--- 複数本の著者（合計liked順）著者数{len(by)} ---")
for n,med,tot,u in rows[:30]:
    print(f"{n:>3}本 中央{med:>4} 合計{tot:>5}  {u}")
