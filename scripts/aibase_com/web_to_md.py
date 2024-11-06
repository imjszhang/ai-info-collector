import json
import os
import re  # 用于正则表达式
import asyncio
from datetime import datetime
from crawl4ai import AsyncWebCrawler
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

# 创建保存路径的函数
def create_save_path(publication_date, news_id):
    # 使用正则表达式提取日期部分（例如 '2024年11月6号'）
    date_match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})号', publication_date)
    
    if date_match:
        # 将提取到的日期部分转换为标准的 YYYY-MM-DD 格式
        year, month, day = date_match.groups()
        date_str = f"{year}-{int(month):02d}-{int(day):02d}"
    else:
        # 如果无法匹配日期，使用默认日期
        date_str = "未知日期"

    # 创建保存目录：data/aibase_com/[日期]/
    save_dir = os.path.join("data", "aibase_com", date_str)
    os.makedirs(save_dir, exist_ok=True)
    
    # 创建文件路径：data/aibase_com/[日期]/[新闻编号].md
    file_path = os.path.join(save_dir, f"{news_id}.md")
    return file_path

# 将新闻数据转换为 Markdown 格式
def convert_to_markdown(news_data):
    title = news_data.get("title", "无标题")
    publication_date = news_data.get("publication_date", "无发布日期")
    content = news_data.get("content", "无内容")
    image = news_data.get("image", "")
    link = news_data.get("link", "")

    # 生成 Markdown 内容
    markdown_content = f"# {title}\n\n"
    markdown_content += f"**发布日期**: {publication_date}\n\n"
    if image:
        markdown_content += f"![新闻图片]({image})\n\n"
    markdown_content += f"**新闻链接**: [点击查看原文]({link})\n\n"
    markdown_content += f"## 内容\n\n{content}\n"

    return markdown_content

# 提取新闻链接中的编号
def extract_news_id(news_url):
    # 使用正则表达式提取新闻链接中的编号
    match = re.search(r'/news/(\d+)', news_url)
    if match:
        return match.group(1)
    return "未知编号"

async def extract_news_list():
    print("\n--- 提取新闻列表 ---")

    # 定义新闻列表页面的提取 schema
    list_schema = {
        "name": "AIbase News List",
        "baseSelector": "a.flex.group",  # 新闻链接的 CSS 选择器
        "fields": [
            {
                "name": "url",
                "type": "attribute",  # 提取 href 属性
                "attribute": "href"
            },
            {
                "name": "image",
                "selector": "img",  # 选择图片
                "type": "attribute",  # 抓取图片的 src 属性
                "attribute": "src"
            }
        ]
    }

    # 创建提取策略
    list_extraction_strategy = JsonCssExtractionStrategy(list_schema, verbose=True)

    # 使用 AsyncWebCrawler 进行爬取新闻列表页面
    async with AsyncWebCrawler(verbose=True) as crawler:
        result = await crawler.arun(
            url="https://www.aibase.com/zh/news",  # 新闻列表页面的 URL
            extraction_strategy=list_extraction_strategy,
            bypass_cache=True,  # 忽略缓存，确保获取最新内容
        )

        if not result.success:
            print("新闻列表页面爬取失败")
            return []

        # 解析提取的内容
        extracted_data = json.loads(result.extracted_content)
        print(f"成功提取 {len(extracted_data)} 条新闻链接")
        return extracted_data

async def extract_news_article(news_url, image_url=None):
    print(f"\n--- 提取新闻文章: {news_url} ---")

    # 定义新闻文章页面的提取 schema
    article_schema = {
        "name": "AIbase News Article",
        "baseSelector": "div.pb-32",  # 主容器的 CSS 选择器
        "fields": [
            {
                "name": "title",
                "selector": "h1",
                "type": "text",
            },
            {
                "name": "publication_date",
                "selector": "div.flex.flex-col > div.flex.flex-wrap > span:nth-child(6)",
                "type": "text",
            },
            {
                "name": "content",
                "selector": "div.post-content",
                "type": "text",  
            },
        ],
    }

    # 创建提取策略
    article_extraction_strategy = JsonCssExtractionStrategy(article_schema, verbose=True)

    # 使用 AsyncWebCrawler 进行爬取新闻文章页面
    async with AsyncWebCrawler(verbose=True) as crawler:
        result = await crawler.arun(
            url=news_url,
            extraction_strategy=article_extraction_strategy,
            bypass_cache=True,  # 忽略缓存，确保获取最新内容
        )

        if not result.success:
            print(f"新闻页面 {news_url} 爬取失败")
            return None

        # 解析提取的内容
        extracted_data = json.loads(result.extracted_content)
        print(f"成功提取新闻文章: {news_url}")

        # 如果有图片 URL，添加到提取的数据中
        if image_url:
            if isinstance(extracted_data, list):
                # 如果 extracted_data 是列表，遍历每个元素并添加 image 字段
                for item in extracted_data:
                    item["image"] = image_url
            elif isinstance(extracted_data, dict):
                # 如果是字典，直接添加 image 字段
                extracted_data["image"] = image_url

        return extracted_data

async def main():
    # 提取新闻列表
    news_list = await extract_news_list()

    # 构建完整的新闻 URL 列表
    base_url = "https://www.aibase.com"
    news_urls = [(base_url + news["url"], news.get("image")) for news in news_list]

    # 存储所有新闻文章数据
    all_news_data = []

    # 循环抓取每个新闻页面的内容
    for news_url, image_url in news_urls:
        news_data = await extract_news_article(news_url, image_url)
        
        # 如果 news_data 是列表，取第一个元素作为字典
        if isinstance(news_data, list) and len(news_data) > 0:
            news_data = news_data[0]

        # 确保 news_data 是字典
        if isinstance(news_data, dict):
            # 添加 link 字段
            news_data["link"] = news_url
            all_news_data.append(news_data)

            # 提取新闻编号
            news_id = extract_news_id(news_url)

            # 保存每条新闻为 Markdown 文件
            publication_date = news_data.get("publication_date", "未知日期")
            file_path = create_save_path(publication_date, news_id)  # 使用新闻编号作为文件名
            markdown_content = convert_to_markdown(news_data)
            
            # 将 Markdown 内容写入文件
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            print(f"新闻已保存为 Markdown 文件: {file_path}")

    print(f"\n--- 所有新闻数据已保存 ---")

# 运行异步函数
if __name__ == "__main__":
    asyncio.run(main())