"""Open a read-only view of the local database schemas and record counts."""
from contextlib import closing
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import os
import sqlite3

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')
DATA = ROOT / os.getenv('DEMO_DATA_DIR', 'artifacts')
DATABASES = dict.fromkeys((
    DATA / 'pages_chat_demo.sqlite3',
    DATA / 'pages_demo.sqlite3',
    ROOT / os.getenv('SQLITE_PATH', 'artifacts/demo.sqlite3'),
))


def database_html(path):
    if not path.is_file():
        return f'<section><h2>{escape(path.name)}</h2><p>文件尚未生成</p></section>'
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        tables = db.execute("""SELECT name, sql FROM sqlite_schema WHERE type = 'table'
            AND name NOT GLOB 'sqlite_*' ORDER BY name""").fetchall()
        content = []
        for name, sql in tables:
            quoted = '"' + name.replace('"', '""') + '"'
            count = db.execute(f'SELECT COUNT(*) FROM {quoted}').fetchone()[0]
            indexes = db.execute("""SELECT name, sql FROM sqlite_schema
                WHERE type = 'index' AND tbl_name = ? AND sql IS NOT NULL ORDER BY name""", (name,))
            schema = '\n\n'.join([sql or '', *(row[1] for row in indexes)])
            content.append(f'<details><summary><code>{escape(name)}</code><span>{count:,} 行</span></summary>'
                           f'<pre>{escape(schema)}</pre></details>')
    return f'<section><h2>{escape(path.name)}</h2><p>{escape(str(path))}</p>{"".join(content)}</section>'


class Inspector(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/':
            self.send_error(404)
            return
        sections = ''.join(database_html(path.resolve()) for path in DATABASES)
        body = f"""<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>心屿 · SQLite 数据库</title>
<style>
body{{font:16px system-ui,sans-serif;color:#24362d;background:#f4f6f1;margin:0}}
main{{max-width:880px;margin:32px auto;padding:0 16px}}header{{display:flex;align-items:center;justify-content:space-between;gap:12px}}
h1{{font-size:28px}}h2{{font-size:19px;margin:0 0 8px}}p{{color:#4f6256;overflow-wrap:anywhere}}
section{{margin:24px 0;background:white;border:1px solid #d8e2d8;border-radius:12px;padding:20px}}
details{{border-top:1px solid #e1e9e2}}summary{{padding:11px 0;cursor:pointer}}summary span{{float:right;color:#4f6256}}
pre{{overflow:auto;background:#f0f4ee;padding:14px;border-radius:6px;line-height:1.55}}
a{{color:#25573e}}
</style><main><header><h1>心屿 SQLite 数据库</h1><a href="/">刷新</a></header>
<p>点击表名查看字段、约束和索引。行数实时读取，只显示结构和数量。</p>{sections}</main></html>"""
        payload = body.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(payload)


if __name__ == '__main__':
    with HTTPServer(('127.0.0.1', 5175), Inspector) as server:
        print('SQLite 数据库查看器：http://127.0.0.1:5175/', flush=True)
        server.serve_forever()
