import os
import aiohttp
import asyncio
import json
import re
from datetime import datetime, timezone
import pytz  # 用于处理时区
from dotenv import load_dotenv
from urllib.parse import unquote  # 用于解码 URL
import ssl

# 定义一个全局的信号量，限制并发请求数量
semaphore = asyncio.Semaphore(5)  # 限制并发请求数量为 5

PROCESSED_RECORDS_LOG = 'data/aibase_com/processed_records.json'

def load_processed_records():
    """
    从日志文件中加载已处理的记录。
    """
    if os.path.exists(PROCESSED_RECORDS_LOG):
        with open(PROCESSED_RECORDS_LOG, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_processed_record(file_name, record_name):
    """
    将已处理的记录保存到日志文件中。
    """
    processed_records = load_processed_records()
    if file_name not in processed_records:
        processed_records[file_name] = []
    processed_records[file_name].append(record_name)

    with open(PROCESSED_RECORDS_LOG, 'w', encoding='utf-8') as f:
        json.dump(processed_records, f, ensure_ascii=False, indent=4)

async def get_tenant_access_token(app_id, app_secret):
    url = f"https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "app_id": app_id,
        "app_secret": app_secret,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            response_data = await response.json()
            return response_data.get("tenant_access_token")

async def upload_image_to_feishu(api_key, image_url, file_name, app_token, retries=3):
    async with semaphore:  # 使用信号量限制并发
        print(f"Uploading image from URL: {image_url}")
        url = "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all"
        headers = {
            "Authorization": f"Bearer {api_key}"
        }
        
        # 解码 URL，防止特殊字符问题
        image_url = unquote(image_url)
        
        # 创建一个不验证 SSL 的上下文
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # 下载图片
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(image_url, ssl=ssl_context) as image_response:
                    image_data = await image_response.read()
            except aiohttp.client_exceptions.InvalidURL as e:
                print(f"Invalid URL: {image_url}")
                return None
        
        # 构建上传请求
        data = aiohttp.FormData()
        data.add_field('file_name', file_name)
        data.add_field('parent_type', 'bitable_image')
        data.add_field('parent_node', app_token)
        data.add_field('file', image_data, filename=file_name)
        data.add_field("size", str(len(image_data)))  # 如果需要 size，可以将其转换为字符串

        # 上传图片，带有重试机制
        for attempt in range(retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers=headers, data=data, ssl=ssl_context) as response:
                        # 打印响应的内容类型和状态码
                        print(f"Response status: {response.status}")
                        print(f"Response content-type: {response.headers.get('Content-Type')}")

                        # 尝试解析为 JSON
                        try:
                            response_data = await response.json()
                        except aiohttp.ContentTypeError:
                            # 如果不是 JSON 响应，打印原始的响应内容
                            response_text = await response.text()
                            print(f"Non-JSON response: {response_text}")
                            return None

                        if response_data.get('code') == 0:
                            return response_data['data']['file_token']
                        else:
                            print(f"Failed to upload image: {response_data}")
                            return None
            except aiohttp.ClientResponseError as e:
                if e.status == 429:  # 429 表示频率限制
                    retry_after = int(e.headers.get("Retry-After", 1))  # 获取重试等待时间
                    print(f"Rate limit hit, retrying after {retry_after} seconds...")
                    await asyncio.sleep(retry_after)
                else:
                    raise  # 其他错误直接抛出
        print(f"Failed to upload image after {retries} attempts")
        return None

async def create_record_with_image(api_key, app_token, table_id, fields, file_token, retries=3):
    async with semaphore:  # 使用信号量限制并发
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json; charset=utf-8"
        }
        
        # 将 file_token 添加到 fields 中的附件字段
        fields['封面图'] = [{"file_token": file_token}]
        
        payload = {
            "fields": fields,
        }

        # 创建记录，带有重试机制
        for attempt in range(retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers=headers, json=payload) as response:
                        return await response.json()
            except aiohttp.ClientResponseError as e:
                if e.status == 429:  # 429 表示频率限制
                    retry_after = int(e.headers.get("Retry-After", 1))  # 获取重试等待时间
                    print(f"Rate limit hit, retrying after {retry_after} seconds...")
                    await asyncio.sleep(retry_after)
                else:
                    raise  # 其他错误直接抛出
        print(f"Failed to create record after {retries} attempts")
        return None

def parse_markdown_to_records(content):
    """
    解析Markdown内容，将其转换为飞书多维表格的记录格式。
    """
    records = []
    articles = content.split('\n\n# ')  # 每篇新闻用 '# ' 分隔
    for article in articles:
        lines = article.strip().splitlines()
        if not lines:
            continue

        record = {}
        for i, line in enumerate(lines):
            if line.startswith('# '):  # 新闻标题
                record['标题'] = line[2:].strip()
            elif line.startswith('**发布日期**'):
                record['发布日期'] = line.split(':', 1)[1].strip()
            elif line.startswith('![新闻图片]'):
                record['封面图链接'] = line.split('(')[1].strip(')')
            elif line.startswith('**新闻链接**'):
                record['原文链接'] = line.split('](', 1)[1].strip(')')
            elif line.startswith('## 内容'):
                # 将内容部分的所有行合并为一个字符串
                content_lines = lines[i+1:]
                record['原文'] = '\n'.join(content_lines).strip()

        if record:
            records.append(record)

    return records

async def process_record(feishu_api_key, app_token, table_id, record, file_name=""):
    # 上传图片并获取 file_token
    image_url = record.get('封面图链接')
    if image_url:
        file_token = await upload_image_to_feishu(feishu_api_key, image_url, "news_image.jpeg", app_token)
        if file_token:
            # 创建记录时，将 file_token 添加到 fields 中
            fields = {
                '标题': record.get('标题'),
                '发布日期': record.get('发布日期'),
                '原文链接': record.get('原文链接'),
                '原文': record.get('原文'),
                '封面图链接': record.get('封面图链接'),
                '封面图': [{"file_token": file_token}]
            }
            response = await create_record_with_image(feishu_api_key, app_token, table_id, fields, file_token)
            if response.get('code') == 0:
                print(f"Record created successfully: {record['原文链接']}")
                # 记录已处理的记录
                save_processed_record(file_name, record['原文链接'])
            else:
                print(f"Failed to create record: {response}")
        else:
            print(f"Failed to upload image for news: {record['原文链接']}")
    else:
        print(f"No image found for news: {record['原文链接']}")

async def publish_to_feishu_bitable():
    """
    处理今天的 Markdown 文件并将其内容发布到飞书多维表格。
    """
    # 从环境变量中获取飞书 API 相关信息
    load_dotenv(override=True)
    FEISHU_APP_ID = os.getenv('FEISHU_APP_ID')
    FEISHU_APP_SECRET = os.getenv('FEISHU_APP_SECRET')    
    feishu_api_key = await get_tenant_access_token(FEISHU_APP_ID, FEISHU_APP_SECRET)
    app_token = os.getenv('FEISHU_BITABLE_APP_TOKEN')
    table_id = os.getenv('FEISHU_BITABLE_TABLE_ID')

    # 获取今天的日期并格式化
    today = datetime.now(timezone.utc)
    date_today = today.strftime('%Y-%m-%d')

    # 假设今天的 Markdown 文件存储在 data/aibase_com/[日期] 目录下
    data_folder = f'data/aibase_com/{date_today}'
    
    # 获取该目录下的所有 Markdown 文件
    markdown_files = [f for f in os.listdir(data_folder) if f.endswith('.md')]

    if not markdown_files:
        print(f"No markdown files found in {data_folder}")
        return

    # 加载已处理的记录
    processed_records = load_processed_records()

    # 创建异步任务列表
    tasks = []
    for file_name in markdown_files:
        file_path = os.path.join(data_folder, file_name)

        # 读取 Markdown 文件内容
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
        except FileNotFoundError:
            print(f"Error: File not found: {file_path}")
            continue

        # 解析 Markdown 内容为飞书多维表格的记录
        records = parse_markdown_to_records(content)

        # 检查该文件是否已经处理过
        if file_name in processed_records:
            print(f"Skipping already processed file: {file_name}")
            continue  # 跳过已处理的文件

        # 为每条记录创建异步任务
        for record in records:
            tasks.append(process_record(feishu_api_key, app_token, table_id, record, file_name))

    # 并发执行所有任务
    await asyncio.gather(*tasks)

async def publish_to_feishu_bitable_by_path(file_path):
    """
    处理单个 Markdown 文件并将其内容发布到飞书多维表格。
    :param file_path: Markdown 文件的路径
    """
    # 从环境变量中获取飞书 API 相关信息
    load_dotenv(override=True)
    FEISHU_APP_ID = os.getenv('FEISHU_APP_ID')
    FEISHU_APP_SECRET = os.getenv('FEISHU_APP_SECRET')    
    feishu_api_key = await get_tenant_access_token(FEISHU_APP_ID, FEISHU_APP_SECRET)
    app_token = os.getenv('FEISHU_BITABLE_APP_TOKEN')
    table_id = os.getenv('FEISHU_BITABLE_TABLE_ID')

    # 读取指定的Markdown文件内容
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
    except FileNotFoundError:
        print(f"Error: File not found: {file_path}")
        return

    # 解析Markdown内容为飞书多维表格的记录
    records = parse_markdown_to_records(content)

    # 加载已处理的记录
    processed_records = load_processed_records().get(os.path.basename(file_path), [])

    # 创建异步任务列表
    tasks = []
    for record in records:
        # 检查该记录是否已经处理过
        if record['标题'] in processed_records:
            print(f"Skipping already processed record: {record['标题']}")
            continue  # 跳过已处理的记录

        # 如果没有处理过，则添加到任务列表中
        tasks.append(process_record(feishu_api_key, app_token, table_id, record, os.path.basename(file_path)))

    # 并发执行所有任务
    await asyncio.gather(*tasks)

async def process_all_markdown_files():
    """
    批量处理 data 文件夹中的所有 Markdown 文件，按顺序一个文件处理完成后再处理下一个。
    如果中断，下次运行时会跳过已处理的文件和记录。
    """
    # 获取 data 文件夹中的所有 Markdown 文件
    data_folder = 'data'
    markdown_files = [f for f in os.listdir(data_folder) if f.endswith('.md')]

    if not markdown_files:
        print(f"No markdown files found in {data_folder}")
        return

    # 顺序处理每个文件
    for file_name in markdown_files:
        file_path = os.path.join(data_folder, file_name)
        print(f"Processing file: {file_path}")
        await publish_to_feishu_bitable_by_path(file_path)  # 顺序执行，等待一个文件处理完成后再处理下一个

if __name__ == "__main__":
    # 单独处理今天的 Markdown 文件
    asyncio.run(publish_to_feishu_bitable())

    # 如果需要批量处理所有 Markdown 文件，可以取消注释以下行
    # asyncio.run(process_all_markdown_files())