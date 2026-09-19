import json,time
from pathlib import Path
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"audit"/"bedesten_page_size_probe"
ENDPOINT="https://bedesten.adalet.gov.tr/emsal-karar/searchDocuments"
HEADERS={"Accept":"*/*","AdaletApplicationName":"UyapMevzuat","Content-Type":"application/json; charset=utf-8","Origin":"https://mevzuat.adalet.gov.tr","Referer":"https://mevzuat.adalet.gov.tr/","User-Agent":"Mozilla/5.0 Chrome/137.0.0.0 Safari/537.36"}
def get(size):
    body=json.dumps({"data":{"pageSize":size,"pageNumber":1,"itemTypeList":["YARGITAYKARARI"],"phrase":"karar","kararTarihiStart":"2026-01-01T00:00:00.000Z","kararTarihiEnd":"2026-09-19T23:59:59.999Z","sortFields":["KARAR_TARIHI"],"sortDirection":"desc"},"applicationName":"UyapMevzuat","paging":True}).encode()
    with urlopen(Request(ENDPOINT,data=body,headers=HEADERS,method="POST"),timeout=90) as r:p=json.load(r)
    d=p["data"];xs=d.get("emsalKararList") or []
    return {"requested_page_size":size,"returned_count":len(xs),"total":d.get("total"),"start":d.get("start")}
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    res=[]
    for s in [10,50,100,250,500,1000]:
        res.append(get(s));time.sleep(1.5)
    out={"audit_version":"bedesten_page_size_probe_v1","results":res}
    (OUT/"probe.json").write_text(json.dumps(out,indent=2),encoding="utf-8")
    print(json.dumps(out,indent=2))
if __name__=="__main__":main()
