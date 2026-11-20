"""Write an interactive reviewer password hash without exposing the password."""
import argparse
from getpass import getpass
from pathlib import Path

from werkzeug.security import generate_password_hash


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path, help='New secret file path (existing files are preserved)')
    args = parser.parse_args()
    password = getpass('审核员新密码（至少 12 位）: ')
    if len(password) < 12 or len(password) > 128 or password != getpass('再次输入: '):
        parser.error('密码长度须为 12 至 128 位，且两次输入一致')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as output:
        output.write(generate_password_hash(password) + '\n')
    print('审核员密码哈希已写入指定文件；配置 DEMO_REVIEWER_PASSWORD_HASH_FILE 后重启服务。')


if __name__ == '__main__':
    main()
