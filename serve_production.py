"""Run behind the HTTPS reverse proxy; never expose this port publicly."""
import os
from pathlib import Path

from dotenv import load_dotenv
from waitress import serve

load_dotenv(Path(__file__).with_name('.env'))
if os.getenv('APP_ENV') != 'production':
    raise RuntimeError('请先设置 APP_ENV=production 并填写生产访问控制配置')

from app import app

if __name__ == '__main__':
    serve(app, host='127.0.0.1', port=int(os.getenv('APP_PORT', '5000')),
          threads=8, max_request_body_size=32 * 1024, clear_untrusted_proxy_headers=True)
