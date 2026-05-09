#!/usr/bin/env python3
"""
compress_kaikki.py — convert kaikki JSONL dumps to compact parquet.

Keeps only fields the pipeline actually uses (word, pos, lang_code,
senses' glosses+links, translations). Drops forms, etymology, sounds,
categories, head_templates, etc. Expected size reduction: 30-50x.

Usage: .venv/bin/python compress_kaikki.py FILE [FILE ...]
       Each FILE should be ../sanakirja/kaikki_<lang>.jsonl
       Writes ../sanakirja/kaikki_<lang>.parquet next to it.
"""

import json
import os
import sys
import time

import pyarrow as pa
import pyarrow.parquet as pq


SCHEMA = pa.schema([
    pa.field("word", pa.string()),
    pa.field("pos", pa.string()),
    pa.field("lang_code", pa.string()),
    pa.field("senses_glosses", pa.list_(pa.list_(pa.string()))),
    pa.field("senses_links", pa.list_(pa.list_(pa.list_(pa.string())))),
    pa.field("translations", pa.list_(pa.struct([
        pa.field("lang", pa.string()),
        pa.field("code", pa.string()),
        pa.field("word", pa.string()),
    ]))),
])


def extract_record(d: dict) -> dict:
    senses = d.get("senses") or []
    senses_glosses = []
    senses_links = []
    for s in senses:
        senses_glosses.append([str(g) for g in (s.get("glosses") or [])])
        # links is list of [text, url] pairs
        links = s.get("links") or []
        senses_links.append([[str(x) for x in pair] for pair in links if isinstance(pair, list)])
    trans = d.get("translations") or []
    translations = []
    for t in trans:
        translations.append({
            "lang": t.get("lang") or "",
            "code": t.get("code") or "",
            "word": t.get("word") or "",
        })
    return {
        "word": d.get("word") or "",
        "pos": d.get("pos") or "",
        "lang_code": d.get("lang_code") or "",
        "senses_glosses": senses_glosses,
        "senses_links": senses_links,
        "translations": translations,
    }


def convert(jsonl_path: str, parquet_path: str, batch_size: int = 50_000):
    if not os.path.exists(jsonl_path):
        print(f"ERROR: {jsonl_path} not found", file=sys.stderr)
        return False
    src_size = os.path.getsize(jsonl_path)
    print(f"\n→ {jsonl_path} ({src_size/1e6:.1f} MB)")

    writer = None
    n = 0
    batch: list[dict] = []
    t0 = time.time()
    try:
        with open(jsonl_path, "rb") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                batch.append(extract_record(d))
                n += 1
                if len(batch) >= batch_size:
                    table = pa.Table.from_pylist(batch, schema=SCHEMA)
                    if writer is None:
                        writer = pq.ParquetWriter(parquet_path, SCHEMA, compression="zstd",
                                                  compression_level=9)
                    writer.write_table(table)
                    batch.clear()
                    if n % 200_000 == 0:
                        print(f"  {n:,} entries, {time.time() - t0:.0f}s elapsed")
        if batch:
            table = pa.Table.from_pylist(batch, schema=SCHEMA)
            if writer is None:
                writer = pq.ParquetWriter(parquet_path, SCHEMA, compression="zstd",
                                          compression_level=9)
            writer.write_table(table)
    finally:
        if writer is not None:
            writer.close()

    out_size = os.path.getsize(parquet_path)
    ratio = src_size / out_size if out_size else float("inf")
    print(f"  ✓ {n:,} rows, parquet {out_size/1e6:.1f} MB ({ratio:.1f}× smaller, {time.time()-t0:.0f}s)")
    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: compress_kaikki.py FILE [FILE ...]")
        sys.exit(1)
    for src in sys.argv[1:]:
        if not src.endswith(".jsonl"):
            print(f"Skipping non-JSONL: {src}")
            continue
        dst = src[:-len(".jsonl")] + ".parquet"
        convert(src, dst)


if __name__ == "__main__":
    main()
