import json,time
from pathlib import Path
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"audit"/"bedesten_pagination_probe"
ENDPOINT="https://bedesten.adalet.gov.tr/emsal-karar/searchDocuments"
HEADERS={
 "Accept":"*/*","AdaletApplicationName":"UyapMevzuat",
 "Content-Type":"application/json; charset=utf-8",
 "Origin":"https://mevzuat.adalet.gov.tr","Referer":"https://mevzuat.adalet.gov.tr/",
 "User-Agent":"Mozilla/5.0 Chrome/137.0.0.0 Safari/537.36"
}

def fetch(page,size,direction="asc"):
    body=json.dumps({
      "data":{
        "pageSize":size,"pageNumber":page,
        "itemTypeList":["YARGITAYKARARI"],"phrase":"karar",
        "kararTarihiStart":"2026-01-01T00:00:00.000Z",
        "kararTarihiEnd":"2026-09-19T23:59:59.999Z",
        "sortFields":["KARAR_TARIHI"],"sortDirection":direction,
      },"applicationName":"UyapMevzuat","paging":True
    }).encode()
    req=Request(ENDPOINT,data=body,headers=HEADERS,method="POST")
    with urlopen(req,timeout=90) as r:p=json.load(r)
    d=p["data"]
    items=d.get("emsalKararList") or []
    return {
      "page":page,"page_size":size,"direction":direction,
      "total":d.get("total"),"start":d.get("start"),
      "count":len(items),
      "document_ids":[x.get("documentId") for x in items],
      "dates":[x.get("kararTarihi") for x in items],
      "first_safe":({k:items[0].get(k) for k in ["documentId","birimAdi","esasNo","kararNo","kararTarihi"]} if items else None),
      "last_safe":({k:items[-1].get(k) for k in ["documentId","birimAdi","esasNo","kararNo","kararTarihi"]} if items else None),
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    tests=[]
    for page in [1,2,3]:
        tests.append(fetch(page,5,"asc"));time.sleep(2)
    tests.append(fetch(1,5,"desc"));time.sleep(2)
    tests.append(fetch(100,5,"asc"))
    total=tests[0]["total"]
    result={
      "audit_version":"bedesten_pagination_probe_v1",
      "year_window":"2026-01-01..2026-09-19",
      "tests":tests,
      "page1_page2_disjoint":set(tests[0]["document_ids"]).isdisjoint(tests[1]["document_ids"]),
      "page2_page3_disjoint":set(tests[1]["document_ids"]).isdisjoint(tests[2]["document_ids"]),
      "reported_total":total,
    }
    (OUT/"probe.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
