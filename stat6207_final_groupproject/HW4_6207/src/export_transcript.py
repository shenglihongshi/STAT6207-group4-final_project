"""Export the complete conversation from the local OpenCode session database.

Outputs (submission/):
  complete_session_transcript.md    -- full dialogue + tool calls
  complete_session_transcript.html  -- styled full transcript
  complete_session_dialogue.pdf     -- readable dialogue-only PDF
"""
from __future__ import annotations

import html
import json
import re
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

import mistune

md_render = mistune.create_markdown(escape=True, plugins=["table", "strikethrough", "task_lists"])


def render_md(text: str) -> str:
    return md_render(text)

ROOT = Path(__file__).resolve().parents[1]
SUBMISSION = ROOT / "submission"
SUBMISSION.mkdir(parents=True, exist_ok=True)
DB = Path(r"C:\Users\admin\.local\share\opencode\opencode.db")
SID = "ses_e5ada32afffd7ucLkj9QlbZEe0"

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def clean(s: str) -> str:
    return ANSI.sub("", s).replace("\r\n", "\n").replace("\r", "\n")


def q(con, sql, args=()):
    cur = con.cursor()
    cur.execute(sql, args)
    return cur.fetchall()


def main() -> None:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    ses = q(con, "SELECT * FROM session_v2 WHERE id=?", (SID,))[0]
    rows = q(
        con,
        "SELECT seq, type, time_created, data FROM session_message WHERE session_id=? ORDER BY seq ASC",
        (SID,),
    )

    events = []  # (kind, text, tools)
    for r in rows:
        typ = r["type"]
        data = json.loads(r["data"])
        if typ == "user":
            text = clean(data.get("text", "")).strip()
            if text:
                events.append({"kind": "user", "text": text, "tools": []})
        elif typ == "assistant":
            texts = []
            tools = []
            for p in data.get("content", []):
                ptype = p.get("type")
                if ptype == "text":
                    t = clean(p.get("text", "")).strip()
                    if t:
                        texts.append(t)
                elif ptype == "tool":
                    tools.append(p)
            if texts or tools:
                events.append({"kind": "assistant", "text": "\n\n".join(texts), "tools": tools})
        elif typ == "synthetic":
            # Keep the interruption note; skip shell-completion duplicates.
            meta = data.get("metadata", {}) or {}
            if meta.get("source") == "shell":
                continue
            text = clean(data.get("text", "")).strip()
            if text:
                events.append({"kind": "note", "text": text, "tools": []})
        elif typ == "system":
            text = clean(data.get("text", "")).strip()
            if text:
                events.append({"kind": "note", "text": text, "tools": []})

    user_n = sum(1 for e in events if e["kind"] == "user")
    assistant_n = sum(1 for e in events if e["kind"] == "assistant")
    assistant_text_n = sum(1 for e in events if e["kind"] == "assistant" and e["text"])
    tool_n = sum(len(e["tools"]) for e in events)

    md = []
    md.append("# 完整会话记录 / Complete Session Transcript\n")
    md.append(f"- Session ID: `{SID}`")
    md.append(f"- Title: {ses['title']}")
    md.append(f"- Directory: `{ses['directory']}`")
    md.append(f"- Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    md.append(f"- User messages: {user_n}; assistant text replies: {assistant_text_n}; tool calls: {tool_n}")
    md.append(
        "- 说明：以下为完整对话原文，不是摘要。工具调用以折叠块保留；"
        "内部 reasoning 与二进制/base64 文件内容未包含在正文中。\n"
        "  Note: this is the verbatim conversation, not a summary. Tool calls are kept "
        "in collapsible blocks; internal reasoning and binary/base64 attachments are omitted.\n"
    )
    md.append("---\n")

    for i, ev in enumerate(events, 1):
        if ev["kind"] == "user":
            md.append(f"## {i}. 用户 / User\n")
            md.append(ev["text"] + "\n")
        elif ev["kind"] == "assistant":
            md.append(f"## {i}. 助手 / Assistant\n")
            if ev["text"]:
                md.append(ev["text"] + "\n")
            for j, tool in enumerate(ev["tools"], 1):
                name = tool.get("name", "tool")
                state = tool.get("state", {}) or {}
                inp = state.get("input", {}) or {}
                content = state.get("content", []) or []
                texts = []
                nfiles = 0
                for c in content:
                    if c.get("type") == "text":
                        texts.append(clean(c.get("text", "")))
                    elif c.get("type") == "file":
                        nfiles += 1
                out = "\n".join(texts).strip()
                meta = state.get("metadata", {}) or {}
                status = meta.get("status", state.get("status", ""))
                exit_code = meta.get("exit", "")
                md.append(f"<details><summary>工具调用 / Tool {j}: {name} (seq {i})</summary>\n")
                md.append("**Input**\n")
                md.append("<pre>" + html.escape(json.dumps(inp, ensure_ascii=False, indent=2)) + "</pre>\n")
                md.append(f"**Status:** {status}  **Exit:** {exit_code}\n")
                if out:
                    md.append("**Output**\n")
                    md.append("<pre>" + html.escape(out) + "</pre>\n")
                if nfiles:
                    md.append(f"*(omitted {nfiles} binary/file attachment(s))*\n")
                md.append("</details>\n")
        else:
            md.append(f"## {i}. 系统提示 / System note\n")
            md.append(ev["text"] + "\n")

    md_path = SUBMISSION / "complete_session_transcript.md"
    md_path.write_text("\n".join(md), encoding="utf-8")

    # Full HTML (tool blocks collapsible)
    body = []
    for i, ev in enumerate(events, 1):
        if ev["kind"] == "user":
            body.append(f"<section class='msg user'><div class='role'>用户 / User · {i}</div>{render_md(ev['text'])}</section>")
        elif ev["kind"] == "assistant":
            inner = ""
            if ev["text"]:
                inner += render_md(ev["text"])
            for j, tool in enumerate(ev["tools"], 1):
                state = tool.get("state", {}) or {}
                inp = state.get("input", {}) or {}
                content = state.get("content", []) or []
                texts = [clean(c.get("text", "")) for c in content if c.get("type") == "text"]
                nfiles = sum(1 for c in content if c.get("type") == "file")
                meta = state.get("metadata", {}) or {}
                inner += f"<details><summary>Tool {j}: {html.escape(tool.get('name','tool'))}</summary>"
                inner += "<pre>" + html.escape(json.dumps(inp, ensure_ascii=False, indent=2)) + "</pre>"
                if texts:
                    inner += "<pre>" + html.escape("\n".join(texts)) + "</pre>"
                if nfiles:
                    inner += f"<p><i>omitted {nfiles} binary/file attachment(s)</i></p>"
                inner += "</details>"
            body.append(f"<section class='msg assistant'><div class='role'>助手 / Assistant · {i}</div>{inner}</section>")
        else:
            body.append(f"<section class='msg note'><div class='role'>系统 / System · {i}</div>{render_md(ev['text'])}</section>")

    css = """
    body{font-family:"Microsoft YaHei","Segoe UI",Arial,sans-serif;color:#1b2a3a;line-height:1.55;font-size:10pt;margin:0;background:#f3f6f9}
    .wrap{max-width:1000px;margin:0 auto;padding:24px}
    h1{font-size:24pt;color:#0C2340}
    .meta{background:#fff;border-left:4px solid #0E7C86;padding:12px 16px;margin:14px 0;font-size:9pt;color:#3f5064}
    .msg{background:#fff;border-radius:6px;padding:10px 14px;margin:10px 0;box-shadow:0 1px 4px rgba(0,0,0,.06)}
    .user{border-left:4px solid #0E7C86}.assistant{border-left:4px solid #9DB4C0}.note{border-left:4px solid #C96A2B}
    .role{font-size:8pt;font-weight:700;color:#5B6B7F;letter-spacing:.5px;margin-bottom:6px}
    pre{white-space:pre-wrap;word-break:break-word;background:#f4f7fa;padding:8px;border-radius:4px;font-size:8pt;max-height:420px;overflow:auto}
    .msg table{border-collapse:collapse;width:100%;margin:6px 0;font-size:8.5pt}
    .msg th{background:#e9eff4;text-align:left;padding:3px 5px;border:1px solid #dce4ec}
    .msg td{padding:3px 5px;border:1px solid #dce4ec;vertical-align:top}
    .msg h1,.msg h2,.msg h3{font-size:12pt;margin:8px 0 4px;border:0;padding:0}
    .msg code{background:#f1f5f8;padding:0 2px;border-radius:2px}
    details{margin:6px 0}
    summary{cursor:pointer;color:#0E7C86;font-weight:600}
    """
    header = f"""<h1>完整会话记录 / Complete Session Transcript</h1>
    <div class='meta'><b>Session:</b> {SID}<br><b>Title:</b> {html.escape(str(ses['title']))}<br>
    <b>Directory:</b> {html.escape(str(ses['directory']))}<br>
    <b>Exported:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
    <b>User messages:</b> {user_n} · <b>Assistant text replies:</b> {assistant_text_n} · <b>Tool calls:</b> {tool_n}<br>
    完整对话原文，不是摘要；工具调用折叠保留；内部 reasoning 和二进制附件未包含。<br>
    Verbatim conversation, not a summary; tool calls are collapsible; internal reasoning and binary attachments omitted.</div>"""
    html_path = SUBMISSION / "complete_session_transcript.html"
    html_path.write_text(
        f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>Complete Session Transcript</title><style>{css}</style></head>"
        f"<body><div class='wrap'>{header}{''.join(body)}</div></body></html>",
        encoding="utf-8",
    )

    # Dialogue-only PDF (readable; no tool blocks)
    dialogue = []
    for i, ev in enumerate(events, 1):
        if ev["kind"] == "user":
            dialogue.append(f"<section class='msg user'><div class='role'>用户 / User · {i}</div>{render_md(ev['text'])}</section>")
        elif ev["kind"] == "assistant" and ev["text"]:
            dialogue.append(f"<section class='msg assistant'><div class='role'>助手 / Assistant · {i}</div>{render_md(ev['text'])}</section>")
        elif ev["kind"] == "note":
            dialogue.append(f"<section class='msg note'><div class='role'>系统 / System · {i}</div>{render_md(ev['text'])}</section>")
    dialogue_css = css + """
    @page{size:A4;margin:16mm}
    .wrap{max-width:none;padding:0}
    .msg{page-break-inside:auto;box-shadow:none;border:1px solid #DCE4EC}
    """
    dialogue_html = SUBMISSION / "complete_session_dialogue.html"
    dialogue_html.write_text(
        f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>Complete Session Dialogue</title><style>{dialogue_css}</style></head>"
        f"<body><div class='wrap'><h1>完整会话记录 / Complete Session Dialogue</h1>"
        f"<div class='meta'>Session: {SID} · {html.escape(str(ses['title']))}<br>"
        f"完整对话原文，不是摘要。工具调用日志见完整版 Markdown/HTML。<br>"
        f"Verbatim dialogue, not a summary. Tool logs are in the full Markdown/HTML version.</div>"
        f"{''.join(dialogue)}</div></body></html>",
        encoding="utf-8",
    )

    edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    pdf_path = SUBMISSION / "complete_session_dialogue.pdf"
    subprocess.run(
        [edge, "--headless", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={pdf_path}", dialogue_html.resolve().as_uri()],
        check=False,
    )

    # Full technical PDF: expand all tool blocks and let pre blocks flow.
    full_print = html_path.read_text(encoding="utf-8").replace("<details>", "<details open>")
    full_print = full_print.replace(
        "</style>",
        ".msg pre{max-height:none;overflow:visible}.wrap{max-width:none}"
        "@page{size:A4;margin:14mm}.msg{page-break-inside:auto;box-shadow:none}"
        "</style>",
    )
    full_print_html = SUBMISSION / "complete_session_transcript_print.html"
    full_print_html.write_text(full_print, encoding="utf-8")
    full_pdf = SUBMISSION / "complete_session_transcript.pdf"
    subprocess.run(
        [edge, "--headless", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={full_pdf}", full_print_html.resolve().as_uri()],
        check=False,
    )

    print(f"events={len(events)} user={user_n} assistant={assistant_n} tools={tool_n}")
    print(f"md:  {md_path}")
    print(f"html:{html_path}")
    print(f"pdf: {pdf_path}")
    print(f"full pdf: {full_pdf}")


if __name__ == "__main__":
    main()
