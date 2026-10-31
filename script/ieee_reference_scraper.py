"""Explicit CSV-driven relationship analysis; never invoked by metadata updates."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from cirdc.analysis import analyze
from cirdc.config import Config

if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--input','-i',required=True)
    args=p.parse_args()
    source=Path(args.input)
    rows=list(csv.DictReader(source.open(encoding='utf-8-sig')))
    results=[analyze(Config.load(),r['articleNumber'],'references') for r in rows if r.get('articleNumber')]
    source.with_suffix('.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    counts=Counter()
    for result in results:
        for child in result['tree']['children']:
            counts[(child.get('articleNumber') or '',child.get('title') or '')]+=1
    with source.with_name(source.stem+'_refstat.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f);w.writerow(['articleNumber','articleTitle','frequency'])
        w.writerows((n,t,count) for (n,t),count in counts.most_common())
