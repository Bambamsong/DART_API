#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_pipeline_utf8.py
--------------------
- Reads corp_code, corp_name from stock_code.csv
- For each company and year, fetches business report (A001) rcept_no via DART list.json
- Downloads document.zip (document.xml endpoint), finds <rcept_no>.xml within nested folders
- Primary extraction from XML using TITLE range:
    start: "경영진단 및 분석의견"
    end  : "회계감사인의 감사의견 등"
  Fallback: HTML parsing from ZIP if XML range not found.
- ALWAYS SAVES OUTPUT FILES AS UTF-8 (even if source is EUC-KR/CP949).

Requirements:
    pip install requests python-dotenv beautifulsoup4 lxml pandas

Env:
    export DART_API="your_api_key"
"""
import os
import io
import re
import zipfile
import pathlib
from datetime import datetime
from typing import List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
import pandas as pd
from dotenv import load_dotenv

# -------------------- Config --------------------
load_dotenv()
API_KEY = os.getenv("DART_API")
if not API_KEY:
    raise RuntimeError("환경변수 DART_API 가 설정되어 있지 않습니다. .env 또는 환경변수로 설정해주세요.")

DART_LIST_URL = "https://opendart.fss.or.kr/api/list.json"
DART_DOC_URL = "https://opendart.fss.or.kr/api/document.xml"
ENCODING_CANDIDATES = ("utf-8", "cp949", "euc-kr", "utf-8-sig", "iso-8859-1")

# -------------------- Helpers --------------------
def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/?:*"<>|]+', '_', name)
    return name.strip()

def sniff_declared_encoding(raw: bytes) -> Optional[str]:
    """Try to detect encoding from XML declaration or HTML meta tags (best-effort)."""
    head = raw[:4096].decode("latin-1", errors="ignore")
    # XML: <?xml version="1.0" encoding="EUC-KR"?>
    m = re.search(r'encoding\s*=\s*["\']\s*([A-Za-z0-9_\-]+)\s*["\']', head, re.I)
    if m:
        return m.group(1).lower()

    # HTML <meta charset="euc-kr">
    m = re.search(r'<meta[^>]+charset\s*=\s*["\']?\s*([A-Za-z0-9_\-]+)', head, re.I)
    if m:
        return m.group(1).lower()

    # HTML <meta http-equiv="Content-Type" content="text/html; charset=EUC-KR">
    m = re.search(r'charset\s*=\s*([A-Za-z0-9_\-]+)', head, re.I)
    if m:
        return m.group(1).lower()
    return None

def decode_to_utf8_text(raw: bytes) -> str:
    """Decode raw bytes to *Unicode string*, preferring declared encoding; fallback through candidates.
       The returned Python string can then be saved as UTF-8."""
    hint = sniff_declared_encoding(raw)
    tried = []
    if hint:
        try:
            return raw.decode(hint)
        except Exception:
            tried.append(hint)

    for enc in ENCODING_CANDIDATES:
        if enc in tried: 
            continue
        try:
            return raw.decode(enc)
        except Exception:
            continue

    # Last resort: ignore errors but keep going
    return raw.decode("utf-8", errors="ignore")

def get_business_report_rcept_nos(corp_code: str, year: int) -> List[Tuple[str, str]]:
    params = {
        "crtfc_key": API_KEY,
        "corp_code": corp_code,
        "bgn_de": f"{year}0101",
        "end_de": f"{year}1231",
        # "pblntf_ty": "A",           # 정기공시
        "pblntf_detail_ty": "A001", # 사업보고서
        "page_count": 100
    }
    r = requests.get(DART_LIST_URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    items = data.get("list", []) or []
    items.sort(key=lambda x: x.get("rcept_dt", ""), reverse=True)  # 최신순
    return [(it["rcept_no"], it.get("rcept_dt", "")) for it in items]

def download_document_zip(rcept_no: str):
    """Return (ZipFile, main_xml_name, main_xml_text[unicode])"""
    params = {"crtfc_key": API_KEY, "rcept_no": rcept_no}
    r = requests.get(DART_DOC_URL, params=params, timeout=60)
    r.raise_for_status()
    zf = zipfile.ZipFile(io.BytesIO(r.content))

    main_xml_name = None
    for name in zf.namelist():
        if name.endswith(f"{rcept_no}.xml"):
            main_xml_name = name
            break

    main_xml_text = None
    if main_xml_name:
        with zf.open(main_xml_name) as f:
            raw = f.read()
            main_xml_text = decode_to_utf8_text(raw)  # <- decode to Unicode (we will SAVE as UTF-8)

    return zf, main_xml_name, main_xml_text

def extract_management_opinion_from_xml(xml_text: str) -> Optional[str]:
    if not xml_text:
        return None

    def norm(s: str) -> str:
        # 공백/특수공백 정리, 로마숫자 통일
        s = (s or "").replace("\xa0", " ").replace("\u200b", " ")
        s = s.replace("Ⅳ", "IV").replace("Ⅴ", "V")
        s = re.sub(r"\s+", " ", s)
        return s.strip()

    # 유연한 매칭 (점 유무, 공백, 표현 변형 허용)
    start_re = re.compile(r"^IV\.?\s*이사의\s*경영진단\s*및\s*분석의견", re.I)
    end_re   = re.compile(r"^V\.?\s*회계감사인의\s*감사(?:의\s*)?의견(?:\s*등)?", re.I)

    soup = BeautifulSoup(xml_text, "xml")

    content = []
    collecting = False

    # 문서 순회하며 TITLE로 on/off, 그 사이의 TITLE/P/SPAN 텍스트 수집
    for tag in soup.find_all(True):
        if tag.name == "TITLE":
            t = norm(tag.get_text())
            if not collecting and start_re.search(t):
                collecting = True
                # 시작 제목도 포함하려면 아래 라인 유지
                if t:
                    content.append(t)
                continue
            if collecting and end_re.search(t):
                break  # 종료 TITLE 만나면 수집 종료

        if collecting and tag.name in {"TITLE", "P", "SPAN"}:
            t = norm(tag.get_text())
            if t:
                content.append(t)

    if not content:
        return None

    # 연속 중복 제거
    deduped = []
    prev = None
    for line in content:
        if line != prev:
            deduped.append(line)
        prev = line

    return "\n".join(deduped).strip()


# def extract_management_from_xml(xml_text: str) -> str | None:
#     soup = BeautifulSoup(xml_text, "xml")

#     def norm(s): 
#         s = (s or "").replace("\xa0"," ").replace("\u200b"," ")
#         s = s.replace("Ⅳ","IV").replace("Ⅴ","V")
#         return re.sub(r"\s+"," ", s).strip()

#     # 1) 섹션-1 블록을 찾아서 타이틀로 필터
#     for sec in soup.find_all("SECTION-1"):
#         t = sec.find("TITLE")
#         if not t: 
#             continue
#         if ("경영진단" in norm(t.get_text()) 
#             and "분석의견" in norm(t.get_text())):
#             # 2) 이 블록 내부에서만 텍스트 수집
#             lines = []
#             for tag in sec.find_all(True):
#                 if tag.name and tag.name.upper() in {"TITLE","P","SPAN","DIV","TD","TH","LI"}:
#                     txt = norm(tag.get_text())
#                     if txt:
#                         lines.append(txt)
#             out = []
#             prev = None
#             for s in lines:
#                 if s != prev:
#                     out.append(s)
#                 prev = s
#             return "\n".join(out).strip() or None

#     return None

def extract_management_from_xml(xml_text: str) -> Optional[str]:
    """<TITLE> 텍스트만 기준:
       '이사의 경영진단 및 분석의견' 시작 ~ '감사인의 감사의견'(=회계감사인의 감사의견 포함) TITLE '직전'까지 수집."""
    if not xml_text:
        return None

    from bs4 import BeautifulSoup
    import re

    def norm(s: str | None) -> str:
        s = (s or "").replace("\xa0", " ").replace("\u200b", " ")
        s = s.replace("Ⅳ", "IV").replace("Ⅴ", "V")
        return re.sub(r"\s+", " ", s).strip()

    # 핵심: 느슨한 파싱으로 TITLE 전부 읽히도록 'lxml' 사용
    soup = BeautifulSoup(xml_text, "lxml")

    # lxml 파서에선 태그/속성명이 소문자로 내려오므로 소문자 기준 사용
    TITLE = "title"
    SECTION = "section-1"

    def is_start_title(tag) -> bool:
        if getattr(tag, "name", "") != TITLE:
            return False
        txt = norm(tag.get_text())
        return bool(re.search(r"이사의\s*경영진단\s*및\s*분석의견", txt))

    def is_stop_title(tag) -> bool:
        """정확히 '감사인의 감사의견' 직전에서 끊기 위해, 다음을 stop으로 인정:
           - AASSOCNOTE=D-0-5-0-0 (V 섹션 공식 표기)
           - 텍스트가 '감사인의 감사의견' 또는 '회계감사인의 감사의견' (변형 포함)
        """
        if getattr(tag, "name", "") != TITLE:
            return False
        # 속성 기반 먼저 (lxml에선 속성명도 소문자)
        if (tag.get("aassocnote") or "").strip() == "D-0-5-0-0":
            return True
        txt = norm(tag.get_text())
        # 'V.' 유무, '회계' 유무, 공백/전각점 변형 허용
        return bool(re.search(
            r"^(?:V)?\s*[.\．]?\s*(?:회계\s*)?감사인의?\s*감사\s*의견",
            txt, re.IGNORECASE
        ))

    # 시작/종료 TITLE 찾기
    titles = soup.find_all(TITLE)
    start_title = next((t for t in titles if is_start_title(t)), None)
    if not start_title:
        return None
    stop_title = next((t for t in start_title.find_all_next(TITLE) if is_stop_title(t)), None)

    # 가능하면 같은 SECTION-1 내부 텍스트만 수집 (가장 깔끔)
    sec = start_title.find_parent(SECTION)
    TEXTUAL = {"title", "p", "span", "div", "td", "th", "li"}

    def collect_between(start_tag, stop_tag) -> str:
        lines: list[str] = []
        # 시작 제목은 포함(원하면 아래 두 줄을 주석처리)
        start_line = norm(start_tag.get_text())
        if start_line:
            lines.append(start_line)

        for el in start_tag.next_elements:
            if stop_tag and el is stop_tag:
                break  # ← '감사인의 감사의견' TITLE '직전'에서 정확히 끊음
            name = getattr(el, "name", None)
            if name and name.lower() in TEXTUAL:
                txt = norm(getattr(el, "get_text", lambda: "")())
                if txt and (not lines or txt != lines[-1]):
                    lines.append(txt)
        return "\n".join(lines).strip()

    if sec:
        # SECTION-1 블록 내부에서 stop_title이 같은 블록에 있으면 그 직전까지 수집
        # (stop_title이 다른 블록에 있더라도 collect_between이 안전하게 끊어줌)
        return collect_between(start_title, stop_title) or None

    # SECTION-1이 없으면 문서 흐름 기준으로 수집
    return collect_between(start_title, stop_title) or None

def ensure_dir(path: pathlib.Path):
    path.mkdir(parents=True, exist_ok=True)

# -------------------- Main Pipeline --------------------
def run_pipeline(
    stock_csv_path: str = "stock_code.csv",
    years: Optional[List[int]] = None,
    out_root: str = "./outputs"
):
    if years is None:
        current_year = datetime.now().year
        years = list(range(current_year-9, current_year+1))

    # Force strings to preserve leading zeros
    df = pd.read_csv(stock_csv_path, dtype={"corp_code": str, "corp_name": str})
    required_cols = {"corp_code", "corp_name"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"CSV에 필요한 컬럼이 없습니다: {missing}")

    for _, row in df.iterrows():
        corp_code = (row["corp_code"] or "").strip()
        corp_name = (row["corp_name"] or "").strip()
        if not corp_code or not corp_name:
            continue

        corp_dir = pathlib.Path(out_root) / sanitize_filename(corp_name)
        company_saved_any = False  # ← 이번 실행에서 이 회사로 저장된 파일이 있는지 추적
        print(f"\n=== {corp_name} ({corp_code}) ===")

        for y in years:
            try:
                filings = get_business_report_rcept_nos(corp_code, y)
                if not filings:
                    print(f"  {y}: 사업보고서 없음")
                    continue

                rcept_no, rcept_dt = filings[0]
                print(f"  {y}: rcept_no={rcept_no} (접수일 {rcept_dt}) - 다운로드 중...")

                zf, main_xml_name, main_xml_text = download_document_zip(rcept_no)
                if main_xml_name:
                    print(f"    메인 XML 발견: {main_xml_name}")
                else:
                    print("    메인 XML을 찾지 못했습니다. (계속 진행)")

                # 1) XML 우선 추출
                text = extract_management_from_xml(main_xml_text)

                if not text:
                    print(f"    경영진단 섹션을 찾지 못했습니다.")
                    continue

                if not company_saved_any:
                    ensure_dir(corp_dir)      # ← 첫 저장 직전, 폴더 생성
                    company_saved_any = True

                out_path = corp_dir / f"{y}.txt"
                with open(out_path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(text)
                print(f"    저장 완료(UTF-8): {out_path}")

            except Exception as e:
                print(f"  {y}: 오류 발생 - {e}")

if __name__ == "__main__":
    # Example: only Samsung Electronics for 2023-2024
    # Create a small CSV like:
    # corp_code,corp_name
    # 00126380,삼성전자
    run_pipeline()
