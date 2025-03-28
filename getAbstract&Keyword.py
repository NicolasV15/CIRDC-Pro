import requests
from bs4 import BeautifulSoup
import re
import json
from time import sleep
import os
from pathlib import Path
import logging
import datetime

# 配置日志
log_dir = Path("./log/4_getAbstract_Keyword")
if not os.path.exists(log_dir):
    os.makedirs(log_dir, exist_ok=True)

current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = log_dir / f"getAbstract_Keyword_{current_time}.log"

# 配置logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()  # 同时输出到控制台
    ]
)
logger = logging.getLogger(__name__)

# 请求头
gheaders = {
    'Referer': 'https://ieeexplore.ieee.org/search/searchresult.jsp',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive'
}


def get_ieee_abstract(articleNumber):
    """获取单篇论文的摘要和关键词"""
    url = f'https://ieeexplore.ieee.org/document/{articleNumber}'

    try:
        response = requests.get(url=url, headers=gheaders, timeout=10)
        response.raise_for_status()  # 检查HTTP错误

        soup = BeautifulSoup(response.text, 'lxml')
        pattern = re.compile(r'xplGlobal\.document\.metadata=({.*?});', re.DOTALL)

        script = soup.find("script", string=pattern)

        if not script:
            logger.warning(f"未找到元数据：{articleNumber}")
            return None

        json_str = pattern.search(script.string).group(1)
        json_data = json.loads(json_str)
        abstract = json_data.get('abstract', '')  # 提取abstract
        raw_keywords = json_data.get('keywords', [])  # 提取keywords
        
        # 将keywords数组重新格式化为以type为键名的结构
        formatted_keywords = {}
        for keyword_item in raw_keywords:
            kw_type = keyword_item.get('type', 'Unknown')
            kw_list = keyword_item.get('kwd', [])
            formatted_keywords[kw_type] = kw_list
        
        return {
            'articleNumber': articleNumber,
            'abstract': abstract,
            'keywords': formatted_keywords  # 以type为键名的keywords结构
        }

    except json.JSONDecodeError as json_err:
        logger.error(f"JSON解析错误：{str(json_err)}")
    except Exception as e:
        logger.error(f"获取 {articleNumber} 失败：{str(e)}")
        return None


def read_json_file(json_file_path):
    """从单个JSON文件中读取文章信息和articleNumber"""
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        articles = []
        for i, article in enumerate(data):
            if 'articleNumber' in article:
                # 检查是否已有abstract和keywords
                has_abstract = 'abstract' in article and article['abstract']
                has_keywords = 'keywords' in article and article['keywords']
                
                articles.append({
                    'articleNumber': article['articleNumber'],
                    'json_file_path': json_file_path,
                    'index_in_file': i,
                    'has_abstract': has_abstract,
                    'has_keywords': has_keywords
                })
        
        return articles
    except Exception as e:
        logger.error(f"读取JSON文件 {json_file_path} 失败: {str(e)}")
        return []


def find_all_json_files(root_dir):
    """递归查找目录下所有JSON文件"""
    json_files = []
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith('.json'):
                json_files.append(os.path.join(root, file))
    return json_files


def update_json_with_abstract_keywords(json_file_path, index, abstract_data):
    """更新JSON文件中指定索引位置的文章信息，添加摘要和关键词"""
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 更新特定文章的信息
        if 0 <= index < len(data):
            # 添加abstract到对应的文章
            data[index]['abstract'] = abstract_data.get('abstract', '')
            
            # 添加格式化后的keywords
            if 'keywords' in abstract_data:
                data[index]['keywords'] = abstract_data['keywords']
            
            # 写回文件
            with open(json_file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            
            logger.info(f"已更新 {json_file_path} 中索引为 {index} 的文章信息")
            return True
        else:
            logger.warning(f"索引 {index} 超出范围，文件 {json_file_path} 包含 {len(data)} 篇文章")
            return False
    
    except Exception as e:
        logger.error(f"更新JSON文件 {json_file_path} 失败: {str(e)}")
        return False


def main():
    logger.info("开始运行摘要和关键词获取程序")
    
    # 指定articleInfo目录路径
    article_info_dir = './articleInfo'
    
    # 查找所有JSON文件
    json_files = find_all_json_files(article_info_dir)
    logger.info(f"找到 {len(json_files)} 个JSON文件")
    
    # 从所有JSON文件中提取articleNumber
    all_articles = []
    for json_file in json_files:
        articles = read_json_file(json_file)
        all_articles.extend(articles)
        logger.info(f"从 {json_file} 中读取到 {len(articles)} 个articleNumber")
    
    logger.info(f"总共找到 {len(all_articles)} 篇文章")
    
    # 处理每篇文章
    success_count = 0
    skipped_count = 0
    for i, article in enumerate(all_articles):
        articleNumber = article['articleNumber']
        json_file_path = article['json_file_path']
        index_in_file = article['index_in_file']
        
        # 检查是否已有abstract和keywords
        if article['has_abstract'] or article['has_keywords']:
            logger.info(f"[{i+1}/{len(all_articles)}] 跳过文章: {articleNumber} (已有摘要或关键词)")
            skipped_count += 1
            continue
        
        logger.info(f"[{i+1}/{len(all_articles)}] 正在处理文章: {articleNumber}")
        
        # 获取摘要和关键词
        abstract_data = get_ieee_abstract(articleNumber)
        if abstract_data:
            # 更新原始JSON文件
            update_success = update_json_with_abstract_keywords(
                json_file_path, index_in_file, abstract_data
            )
            
            if update_success:
                success_count += 1
        
        # 添加间隔防止被封
        sleep(1)
    
    logger.info(f"成功处理 {success_count} 篇文章，跳过 {skipped_count} 篇已有内容的文章")
    logger.info("摘要和关键词获取程序运行完成")


if __name__ == '__main__':
    main()