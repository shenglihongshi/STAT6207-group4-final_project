# -*- coding: utf-8 -*-
"""程序侧直接解析 `Location:` 行，修正 country / city。

背景：JD 原文常有两处 Location（元信息块 + 正文），互相矛盾；模型会选正文那个。
既然 `Location:` 格式固定，就由程序决定，不依赖模型判断。
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 项目根，由本文件位置反推
EXT = os.path.join(ROOT, "main", "match_work", "extracted")
SRC = os.path.join(ROOT, "dataset_from_blackboard", "JD_examples")

# 顺序重要：长的、含歧义的要排前面（Hong Kong 必须在 China 之前）
COUNTRIES = [
    "Hong Kong", "United Arab Emirates", "United States", "United Kingdom",
    "South Korea", "Saudi Arabia", "Vietnam", "Indonesia", "Malaysia",
    "Singapore", "Philippines", "Thailand", "Taiwan", "China", "Japan",
    "India", "Qatar", "Bahrain", "Kuwait", "Spain", "Portugal",
    "Germany", "France", "Netherlands", "Ireland", "Poland", "Romania",
    "Australia", "Canada", "Brazil", "Mexico", "Myanmar", "Cambodia",
]

NON_COUNTRY = re.compile(r"^\s*(remote|any\s|global|worldwide|multiple)", re.I)


def parse_location(raw):
    """取第一处 Location 行的 (country, city)；无法判定返回 (None, None)"""
    m = re.search(r"^\s*Location:\s*(.+?)\s*$", raw, re.M)
    if not m:
        return None, None
    loc = m.group(1).strip()
    if NON_COUNTRY.match(loc):
        return None, None
    country = None
    for c in COUNTRIES:
        if re.search(r"\b" + re.escape(c) + r"\b", loc, re.I):
            country = c
            break
    city = None
    if "," in loc:
        first = loc.split(",")[0].strip()
        if first and not re.search(r"\b" + re.escape(country or "###") + r"\b", first, re.I):
            city = first
    elif country and loc.lower() != country.lower():
        city = loc
    return country, city


def main():
    changed = []
    for f in sorted(os.listdir(os.path.join(EXT, "JD"))):
        if not f.endswith(".json"):
            continue
        jid = f[:-5]
        p = os.path.join(EXT, "JD", f)
        jd = json.load(open(p, encoding="utf-8"))
        raw_p = os.path.join(SRC, jid + ".txt")
        if not os.path.exists(raw_p):
            continue
        raw = open(raw_p, encoding="utf-8").read()
        c, city = parse_location(raw)
        old_c, old_city = jd.get("country"), jd.get("city")
        if c == old_c and (city == old_city or city is None):
            continue
        if c:
            jd["country"] = c
            if city:
                jd["city"] = city
            jd.setdefault("_meta", {})["country_fixed_by"] = "location_line"
            json.dump(jd, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            changed.append((jid, old_c, c, old_city, jd.get("city")))

    print(f"修正 {len(changed)} 份：")
    for jid, oc, nc, ocity, ncity in changed:
        print(f"  {jid}: {oc} → {nc} | city {ocity} → {ncity}")


if __name__ == "__main__":
    main()
