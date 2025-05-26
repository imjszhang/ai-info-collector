# AI Info Collector

A Python-based tool for collecting, processing, and organizing AI news and information from various sources. This project automatically scrapes AI-related content from websites, converts it to markdown format, and can publish the data to collaborative platforms like Feishu Bitable.

## Features

- 🔍 **Web Scraping**: Automatically collects AI news from aibase.com
- 📝 **Markdown Conversion**: Converts web content to clean, readable markdown format
- 📊 **Data Organization**: Organizes collected data by date for easy browsing
- 🚀 **Feishu Integration**: Publishes collected data to Feishu Bitable for team collaboration
- ⚡ **Async Processing**: Uses asynchronous processing for efficient data collection
- 📁 **Structured Storage**: Maintains organized file structure with date-based directories

## Project Structure

```
ai-info-collector/
├── data/
│   └── aibase_com/           # Collected data organized by date
│       ├── 2024-11-30/       # Daily collections
│       │   ├── 13603.md      # Individual news articles
│       │   └── ...
│       └── processed_records.json  # Processing log
├── scripts/
│   └── aibase_com/           # Source-specific scripts
│       ├── web_to_md.py      # Web scraping and markdown conversion
│       └── publish_to_feishu_bitable.py  # Feishu publishing
├── requirements.txt          # Python dependencies
├── LICENSE                   # Apache 2.0 License
└── README.md                # This file
```

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/imjszhang/ai-info-collector.git
   cd ai-info-collector
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables** (for Feishu integration):
   ```bash
   # Create a .env file with your Feishu app credentials
   echo "FEISHU_APP_ID=your_app_id" > .env
   echo "FEISHU_APP_SECRET=your_app_secret" >> .env
   ```

## Usage

### Web Scraping and Markdown Conversion

To collect AI news from aibase.com and convert to markdown:

```python
# Run the web scraping script
python scripts/aibase_com/web_to_md.py
```

This will:
- Scrape the latest AI news from aibase.com
- Convert articles to markdown format
- Save files in the [`data/aibase_com/`](./data/aibase_com/) directory organized by date
- Generate files like `data/aibase_com/2024-11-30/13603.md`

### Publishing to Feishu Bitable

To publish collected data to Feishu Bitable:

```python
# Run the Feishu publishing script
python scripts/aibase_com/publish_to_feishu_bitable.py
```

This will:
- Read markdown files from the data directory
- Upload content to your configured Feishu Bitable
- Track processed records to avoid duplicates

## Dependencies

The project uses the following Python packages (see [`requirements.txt`](./requirements.txt)):

- `requests` - HTTP library for web requests
- `beautifulsoup4` - HTML parsing and web scraping
- `pytz` - Timezone handling
- `aiohttp` - Asynchronous HTTP client/server

## Data Format

Collected articles are stored as markdown files with the following structure:

```markdown
# Article Title

**发布日期**: 2024年11月30号 10:23

![新闻图片](image_url)

**新闻链接**: [点击查看原文](original_url)

## 内容

Article content goes here...
```

## Configuration

### Feishu Integration

To use the Feishu publishing feature:

1. Create a Feishu app in the [Feishu Developer Console](https://open.feishu.cn/)
2. Get your App ID and App Secret
3. Set up environment variables as shown in the [Installation](#installation) section
4. Configure your Bitable permissions

### Customizing Sources

To add new data sources:

1. Create a new directory under [`scripts/`](./scripts/) for your source
2. Implement scraping logic following the pattern in [`scripts/aibase_com/`](./scripts/aibase_com/)
3. Update the data organization structure as needed

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](./LICENSE) file for details.

## Acknowledgments

- Thanks to aibase.com for providing AI news content
- Built with Python and modern async libraries for efficient data processing