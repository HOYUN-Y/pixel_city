#!/usr/bin/env python3
"""Collect a bounded Seoul tourism sample; requires Python 3 and system curl."""
import argparse
from datetime import datetime
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import time
import urllib.parse
from zoneinfo import ZoneInfo

BASE = "https://apis.data.go.kr/B551011/KorService2/"
BBOX = (126.971, 37.568, 126.984, 37.581)
CENTER = (126.9775, 37.5745)
TYPES = {"12": "관광지", "14": "문화시설", "39": "음식점"}
LANDMARKS = ["광화문", "근정전", "경회루", "세종대왕동상", "이순신장군동상",
             "세종문화회관", "보신각", "종로타워"]
ALIASES = {"이순신장군동상": ["충무공 이순신 동상", "이순신 동상"],
           "세종대왕동상": ["세종대왕 동상"]}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def coordinates(item):
    try:
        x, y = float(item["mapx"]), float(item["mapy"])
        if math.isfinite(x) and math.isfinite(y) and 124 <= x <= 132 and 33 <= y <= 39:
            return x, y
    except (KeyError, ValueError, TypeError):
        pass
    return None


def inside(item):
    xy = coordinates(item)
    return bool(xy and BBOX[0] <= xy[0] <= BBOX[2] and BBOX[1] <= xy[1] <= BBOX[3])


def distance(item):
    xy = coordinates(item)
    if not xy:
        return float("inf")
    return math.hypot((xy[0] - CENTER[0]) * 88237.38, (xy[1] - CENTER[1]) * 110540)


def unpack(data):
    response = data.get("response", {})
    header = response.get("header") or data.get("OpenAPI_ServiceResponse", {}).get("cmmMsgHeader") or data
    code = str(header.get("resultCode", header.get("returnReasonCode", "unknown")))
    body = response.get("body") or {}
    container = body.get("items") or {}
    items = container.get("item") or [] if isinstance(container, dict) else []
    if isinstance(items, dict):
        items = [items]
    return code, body, items


class StopCollection(Exception):
    pass


class Client:
    def __init__(self, key, output):
        self.key = urllib.parse.unquote(key.strip())
        self.secrets = {key.strip(), self.key, urllib.parse.quote(key.strip(), safe=""),
                        urllib.parse.quote(self.key, safe=""), urllib.parse.quote_plus(self.key)}
        self.output = output
        self.records = []
        self.errors = []

    def redact(self, text):
        for value in sorted(self.secrets, key=len, reverse=True):
            if value:
                text = text.replace(value, "[REDACTED]")
        return text

    def get(self, endpoint, **params):
        public = {"MobileOS": "ETC", "MobileApp": "PixelCityResearch", "_type": "json",
                  "numOfRows": 100, "pageNo": 1, **params}
        url = BASE + endpoint + "?" + urllib.parse.urlencode({**public, "serviceKey": self.key})
        for attempt in range(3):
            if len(self.records) >= 200:
                raise StopCollection("200회 호출 제한 도달")
            time.sleep(0.25 if attempt == 0 else (1 if attempt == 1 else 3))
            started = time.monotonic()
            status, code, payload, items, body = "", "transport_error", None, [], {}
            try:
                result = subprocess.run(
                    ["curl", "--silent", "--max-time", "20", "--proto", "=https",
                     "--write-out", "\n%{http_code}", "--config", "-"],
                    input='url = "' + url + '"\n', capture_output=True, text=True, timeout=22)
                raw, _, status = result.stdout.rpartition("\n")
                raw = self.redact(raw)
                try:
                    payload = json.loads(raw)
                    if isinstance(payload, dict):
                        code, body, items = unpack(payload)
                    else:
                        code = "invalid_json_shape"
                except ValueError:
                    payload, code = raw, "non_json_response"
                if result.returncode:
                    code = "transport_error"
            except subprocess.TimeoutExpired:
                code = "timeout"
            elapsed = round(time.monotonic() - started, 4)
            ok = status == "200" and code in ("0", "00", "0000")
            record = {"endpoint": endpoint, "params": public, "attempt": attempt + 1,
                      "http_status": status, "result_code": code, "seconds": elapsed, "success": ok}
            self.records.append(record)
            number = len(self.records)
            write_json(self.output / "raw" / f"{number:03d}_{endpoint}.json", payload)
            with (self.output / "requests.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(f"[{number:03d}] {endpoint} HTTP={status} code={code} {elapsed:.2f}s", flush=True)
            if ok:
                return body, items
            if status in ("401", "403") or code in ("20", "22", "30", "31"):
                raise StopCollection(f"인증/할당량 오류: HTTP {status}, code {code}")
            if code == "10":
                raise StopCollection(f"요청 매개변수 오류: {endpoint}")
            transient = status == "429" or status.startswith("5") or code in ("23", "05", "timeout", "transport_error")
            if not transient or attempt == 2:
                self.errors.append(record)
                return None, []

    def pages(self, endpoint, **params):
        gathered = []
        page = 1
        while True:
            body, items = self.get(endpoint, pageNo=page, **params)
            if body is None:
                return gathered
            gathered.extend(items)
            total = int(body.get("totalCount") or 0)
            if page * 100 >= total:
                return gathered
            if not items:
                self.errors.append({"endpoint": endpoint, "error": "empty_page_before_total", "page": page})
                return gathered
            page += 1


def normalized(text):
    return "".join(c for c in text if c.isalnum())


def candidate_ids(name, catalog):
    needles = [normalized(x) for x in [name, *ALIASES.get(name, [])]]
    return [cid for cid, item in catalog.items()
            if str(item.get("contenttypeid")) in ("12", "14")
            and any(needle in normalized(item.get("title", "")) for needle in needles) and inside(item)]


def select_ids(catalog):
    priority, landmarks = [], []
    for name in LANDMARKS:
        ids = candidate_ids(name, catalog)
        exact = [cid for cid in ids if normalized(catalog[cid].get("title", "")) == normalized(name)]
        chosen = exact[:1] or ids[:1]
        priority.extend(chosen)
        landmarks.append({"name": name, "status": "후보 검토 필요" if ids else "검색에서 개별 후보 확인 못 함",
                          "candidate_ids": ids, "detail_sample_ids": chosen})
    palace = [cid for cid in candidate_ids("경복궁", catalog)
              if normalized(catalog[cid].get("title", "")) in ("경복궁", "서울경복궁", "경복궁서울")]
    priority.extend(palace[:1])
    ids = list(dict.fromkeys(priority))
    for content_type in TYPES:
        eligible = [(cid, x) for cid, x in catalog.items() if inside(x)
                    and str(x.get("contenttypeid")) == content_type and cid not in ids]
        eligible.sort(key=lambda pair: (distance(pair[1]), pair[0]))
        ids.extend(cid for cid, _ in eligible[:10])
    return ids, landmarks


def report(output, client, catalog, selected, landmarks, status):
    rows = []
    for endpoint in sorted({r["endpoint"] for r in client.records}):
        calls = [r for r in client.records if r["endpoint"] == endpoint]
        durations = [r["seconds"] for r in calls]
        rows.append(f"| {endpoint} | {len(calls)} | {sum(r['success'] for r in calls)} | {statistics.median(durations):.3f} | {max(durations):.3f} |")
    lines = ["# TourAPI 수집 검토", "", f"상태: {status}",
             f"목록 고유 항목 {len(catalog)}건 · 경계 안 {sum(inside(x) for x in catalog.values())}건 · 상세 표본 {len(selected)}건", "",
             "호출 시간은 개별 HTTP 요청 측정값이며 챗봇 응답시간이 아니다. 좌표는 API 원문값이며 출입구·실제 건물 위치로 검증되지 않았다.", "",
             "## API 응답시간", "", "| API | 호출 수 | 성공 수 | 중앙값(초) | 최대(초) |", "|---|---:|---:|---:|---:|", *rows,
             "", "## 랜드마크 대응", "", "| 랜드마크 | 자동 검색 상태 | 후보 ID |", "|---|---|---|"]
    lines += [f"| {x['name']} | {x['status']} | {', '.join(x['candidate_ids']) or '—'} |" for x in landmarks]
    lines += ["", "## 상세정보 점검", "", "| 장소 | 유형 | 소개문 | 소개정보 필드 수 | 반복정보 건수 |", "|---|---|---|---:|---:|"]
    for place in selected:
        title = place["listing"].get("title", "").replace("|", "\\|").replace("\n", " ")
        common, intro, repeated = place.get("common", []), place.get("intro", []), place.get("repeated", [])
        overview = any(x.get("overview", "").strip() for x in common)
        intro_count = sum(bool(v) for x in intro for k, v in x.items() if k not in ("contentid", "contenttypeid"))
        lines.append(f"| {title} | {TYPES.get(str(place['listing'].get('contenttypeid')), '기타')} | {'있음' if overview else '없음/미수집'} | {intro_count} | {len(repeated)} |")
    lines += ["", "## 해석 기준", "", "- 소개문이 있으면 출처를 붙인 장소 설명의 근거 후보로 사용할 수 있다.",
              "- 운영시간·휴무·요금은 유형별 상세 필드와 반복정보를 읽고 확인한다. 빈 값은 미제공으로 취급한다.",
              "- 실내 여부·추천 체류시간·오늘 개방 여부·보행 경로는 이 수집만으로 확정하지 않는다.",
              "- 표본은 위치·유형 기준으로 선정했으며 인기·품질 순위가 아니다.",
              f"- 미해결 오류: {len(client.errors)}건. 과거 실패와 보완 요청은 requests.jsonl 참조."]
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def collect(root, key):
    stamp = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y%m%dT%H%M%S%f%z")
    output = root.expanduser().resolve() / "tourapi" / stamp
    (output / "raw").mkdir(parents=True, exist_ok=False)
    client = Client(key, output)
    catalog, selected, landmarks = {}, [], []
    status = "partial"
    def add(items):
        for item in items:
            if item.get("contentid"):
                catalog[str(item["contentid"])] = item
        write_json(output / "catalog.json", list(catalog.values()))
    try:
        add(client.pages("locationBasedList2", mapX=CENTER[0], mapY=CENTER[1], radius=1200, arrange="A"))
        for name in [*LANDMARKS, "경복궁", *(alias for values in ALIASES.values() for alias in values)]:
            add(client.pages("searchKeyword2", keyword=name, arrange="A"))
        ids, landmarks = select_ids(catalog)
        for cid in ids:
            item = catalog[cid]
            place = {"contentid": cid, "listing": item}
            selected.append(place)
            for field, endpoint in (("common", "detailCommon2"), ("intro", "detailIntro2"), ("repeated", "detailInfo2")):
                params = {"contentId": cid}
                if field != "common":
                    params["contentTypeId"] = item["contenttypeid"]
                _, entries = client.get(endpoint, **params)
                place[field] = entries
                write_json(output / "places.json", selected)
        status = "complete"
    except (StopCollection, KeyboardInterrupt) as error:
        status = "partial"
        client.errors.append({"collection_stopped": str(error) or "interrupted"})
    finally:
        if client.errors:
            status = "partial"
        if not landmarks:
            landmarks = [{"name": name, "status": "수집 중단으로 미검토", "candidate_ids": [],
                          "detail_sample_ids": []} for name in LANDMARKS]
        write_json(output / "catalog.json", list(catalog.values()))
        write_json(output / "places.json", selected)
        write_json(output / "landmarks.json", landmarks)
        write_json(output / "manifest.json", {"collected_at":stamp, "status":status, "bbox":BBOX,
                   "center":CENTER, "radius_m":1200, "sample_per_type":10,
                   "source":"https://www.data.go.kr/data/15101578/openapi.do",
                   "request_count":len(client.records), "errors":client.errors})
        report(output, client, catalog, selected, landmarks, status)
        print(f"Output: {output}\nStatus: {status}", flush=True)
    return 0 if status == "complete" else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="Base directory; creates tourapi/<timestamp> inside")
    args = parser.parse_args()
    key = os.environ.get("TOUR_API_SERVICE_KEY", "").strip()
    if not key:
        parser.error("TOUR_API_SERVICE_KEY 환경변수가 필요합니다")
    return collect(args.output_dir, key)


if __name__ == "__main__":
    raise SystemExit(main())
