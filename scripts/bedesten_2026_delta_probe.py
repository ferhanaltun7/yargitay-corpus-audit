import json
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"audit"/"incremental_2026_probe"
ENDPOINT="https://bedesten.adalet.gov.tr/emsal-karar/searchDocuments"
HEADERS={
  "Accept":"*/*",
  "Accept-Language":"tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
  "AdaletApplicationName":"UyapMevzuat",
  "Content-Type":"application/json; charset=utf-8",
  "Origin":"https://mevzuat.adalet.gov.tr",
  "Referer":"https://mevzuat.adalet.gov.tr/",
  "User-Agent":"Mozilla/5.0 Chrome/137.0.0.0 Safari/537.36",
}

def typename(v):
    if v is None:return "null"
    if isinstance(v,bool):return "bool"
    if isinstance(v,int):return "int"
    if isinstance(v,float):return "float"
    if isinstance(v,str):return "str"
    if isinstance(v,list):return "list"
    if isinstance(v,dict):return "dict"
    return type(v).__name__

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    body=json.dumps({
      "data":{
        "pageSize":10,
        "pageNumber":1,
        "itemTypeList":["YARGITAYKARARI"],
        "phrase":"karar",
        "kararTarihiStart":"2026-05-07T00:00:00.000Z",
        "kararTarihiEnd":"2026-09-19T23:59:59.999Z",
        "sortFields":["KARAR_TARIHI"],
        "sortDirection":"asc",
      },
      "applicationName":"UyapMevzuat",
      "paging":True,
    }).encode("utf-8")
    req=Request(ENDPOINT,data=body,headers=HEADERS,method="POST")
    with urlopen(req,timeout=90) as r:
        payload=json.load(r)

    data=payload.get("data")
    if data is None:
        raise SystemExit("No data returned")

    schema={"payload_keys":sorted(payload.keys()),"data_type":typename(data)}
    total=None
    items=[]
    if isinstance(data,dict):
        schema["data_keys"]=sorted(data.keys())
        total=data.get("total")
        for k,v in data.items():
            if isinstance(v,list) and v and isinstance(v[0],dict):
                schema["list_field"]=k
                schema["item_keys"]=sorted(v[0].keys())
                schema["item_types"]={kk:typename(v[0].get(kk)) for kk in sorted(v[0].keys())}
                items=v
                break

    # Commit no raw text/party names. Keep only structural and clearly non-sensitive
    # decision identifiers when those fields exist.
    safe_candidates=[
      "documentId","document_id","id","itemType","kararTarihi","karar_tarihi",
      "esasNo","esas_no","kararNo","karar_no","birimAdi","daire","court"
    ]
    safe_rows=[]
    for item in items[:10]:
        safe_rows.append({k:item.get(k) for k in safe_candidates if k in item})

    result={
      "audit_version":"incremental_2026_delta_probe_v1",
      "window_start":"2026-05-07",
      "window_end":"2026-09-19",
      "phrase":"karar",
      "reported_total":total,
      "schema":schema,
      "safe_first_page_metadata":safe_rows,
      "raw_response_persisted":False,
    }
    (OUT/"probe.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"README.md").write_text(
      "# 2026 Incremental Delta Probe\n\n"
      f"- Window: **2026-05-07 → 2026-09-19**\n"
      f"- Bedesten reported total: **{total}**\n"
      "- Raw response/text is not committed.\n"
      "- Purpose: freeze response schema before implementing paginated delta ingestion.\n",
      encoding="utf-8"
    )
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
