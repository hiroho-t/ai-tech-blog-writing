import json, urllib.request, time, collections, sys
def get(url):
    req=urllib.request.Request(url, headers={'Accept':'application/json','User-Agent':'research/1.0'})
    return json.load(urllib.request.urlopen(req))
items=[]
for page in range(1,11):
    url=f"https://qiita.com/api/v2/items?page={page}&per_page=100&query=stocks%3A%3E300"
    try:
        d=get(url)
    except Exception as e:
        print('ERR',page,e, file=sys.stderr); break
    if not d: break
    items+=d
    print('page',page,len(d),'total',len(items), file=sys.stderr)
    time.sleep(1)
json.dump(items, open('qiita_pool.json','w'), ensure_ascii=False)
by=collections.defaultdict(list)
for i in items:
    by[i['user']['id']].append(i)
rows=[]
for u,arts in by.items():
    if len(arts)>=2:
        lg=sorted(x['likes_count'] for x in arts)
        med=lg[len(lg)//2]
        rows.append((len(arts), med, sum(lg), u))
rows.sort(key=lambda r:(-r[0], -r[1]))
print(f"\n総記事数 {len(items)} / 著者数 {len(by)} / 複数本ヒット著者 {len(rows)}")
print(f"{'本数':>3} {'中央LGTM':>7} {'合計':>6}  著者")
for n,med,tot,u in rows[:40]:
    print(f"{n:>3} {med:>7} {tot:>6}  {u}")
