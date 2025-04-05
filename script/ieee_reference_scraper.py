import requests
import pandas as pd
import os
from datetime import datetime
import logging
import json
import time
import argparse
import sys

def setup_logger():
    """配置日志记录器"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(current_dir, 'ieee_scraper_errors.log')
    
    logger = logging.getLogger('ieee_scraper')
    logger.setLevel(logging.ERROR)
    
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.ERROR)
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    return logger

def extract_article_id(url):
    """从URL中提取文章ID"""
    try:
        return url.split('/document/')[1].split('/')[0]
    except:
        return None

def get_references(paper_id, wait_time=2):
    """通过API获取论文引用信息
    Args:
        paper_id (str): 论文ID
        wait_time (int): 请求间隔时间（秒）
    Returns:
        list: 包含引用信息的列表
    """
    # API端点
    api_url = f"https://ieeexplore.ieee.org/rest/document/{paper_id}/references?start=1&count=300"
    
    # 设置请求头
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
        'Referer': f'https://ieeexplore.ieee.org/document/{paper_id}',
    }
    
    try:
        # 发送请求
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()  # 检查响应状态
        
        # 解析JSON响应
        data = response.json()
        
        if 'references' in data:
            return data['references']
        else:
            print(f"[警告] 未找到引用数据，响应内容: {data}")
            return []
            
    except requests.exceptions.RequestException as e:
        print(f"[错误] 请求失败: {str(e)}")
        return []

def load_existing_json(file_path):
    """加载现有的JSON文件，如果文件不存在则返回空列表"""
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"[警告] 加载现有JSON文件失败: {str(e)}")
        return []

def save_to_json(data, file_path):
    """保存数据到JSON文件"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[信息] 数据已保存到JSON文件: {file_path}")
    except Exception as e:
        print(f"[错误] 保存JSON文件失败: {str(e)}")

def scrape_ieee_references(article_number, output_file=None, wait_time=2):
    """爬取IEEE参考文献页面中的文章链接
    Args:
        article_number (str): IEEE文章编号
        output_file (str, optional): 输出文件路径（支持.json、.csv、.xlsx）
        wait_time (int): 请求间隔时间（秒）
    Returns:
        dict: 包含文章编号和引用列表的字典
    """
    logger = logging.getLogger('ieee_scraper')
    
    try:
        # 构建IEEE参考文献页面URL
        url = f"https://ieeexplore.ieee.org/document/{article_number}/references"
        
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始获取IEEE参考文献...")
        print(f"[信息] 目标URL: {url}")
        
        # 从URL中提取论文ID
        paper_id = article_number
        if not paper_id:
            print("[错误] 无效的文章编号")
            return None
            
        print(f"[信息] 论文ID: {paper_id}")
        
        # 获取引用数据
        references = get_references(paper_id, wait_time)
        
        if not references:
            print("[错误] 未能获取到引用数据")
            return None
            
        # 处理引用数据
        references_list = []
        print("\n[信息] 开始处理引用数据：")
        print("-" * 50)
        
        for i, ref in enumerate(references, 1):
            articleNumber = None
            if 'links' in ref and ref['links'].get('documentLink'):
                articleNumber = extract_article_id(ref['links']['documentLink'])
            
            reference_item = {
                'articleNumber': articleNumber,
                'articleTitle': ref.get('title', '')
            }
            references_list.append(reference_item)
            print(f"[引用 {i}]")
            if articleNumber:
                print(f"文章编号: {articleNumber}")
            else:
                print("文章编号: 无有效链接")
            print(f"标题: {reference_item['articleTitle']}")
            print("-" * 50)
        
        # 构建最终的输出结构
        result = {
            'articleNumber': article_number,
            'references': references_list
        }
        
        print(f"[统计信息]")
        print(f"总引用数: {len(references)}")
        print(f"有效链接数: {len([ref for ref in references_list if ref['articleNumber']])}")
        
        # 保存结果
        if output_file and result:
            file_ext = os.path.splitext(output_file)[1].lower()
            
            if file_ext == '.json':
                # 加载现有数据
                existing_data = load_existing_json(output_file)
                # 检查是否已存在相同的文章编号
                existing_data = [item for item in existing_data if item['articleNumber'] != article_number]
                # 添加新数据
                existing_data.append(result)
                # 保存更新后的数据
                save_to_json(existing_data, output_file)
            
            elif file_ext == '.csv':
                df = pd.DataFrame(references_list)
                df.to_csv(output_file, index=False, encoding='utf-8-sig')
                print(f"[信息] 数据已保存到CSV文件: {output_file}")
            
            elif file_ext == '.xlsx':
                df = pd.DataFrame(references_list)
                df.to_excel(output_file, index=False)
                print(f"[信息] 数据已保存到Excel文件: {output_file}")
            
            else:
                print(f"[警告] 不支持的文件格式: {file_ext}，数据未保存")
        
        return result
        
    except Exception as e:
        error_msg = f"获取过程中发生错误: {str(e)}"
        print(f"[错误] {error_msg}")
        logger.error(error_msg)
        return None

def load_article_numbers_from_csv(csv_file):
    """从CSV文件中读取文章编号
    
    Args:
        csv_file (str): CSV文件路径
        
    Returns:
        list: 文章编号列表
    """
    try:
        if not os.path.exists(csv_file):
            print(f"[错误] CSV文件不存在: {csv_file}")
            return []
            
        df = pd.read_csv(csv_file)
        
        if 'articleNumber' not in df.columns:
            print(f"[错误] CSV文件中没有articleNumber列: {csv_file}")
            return []
            
        # 移除NaN值并转换为字符串
        article_numbers = df['articleNumber'].dropna().astype(str).tolist()
        article_numbers = [an for an in article_numbers if an.strip()]
        
        print(f"[信息] 从CSV文件中读取了{len(article_numbers)}个文章编号")
        return article_numbers
        
    except Exception as e:
        print(f"[错误] 读取CSV文件失败: {str(e)}")
        return []

def analyze_references_frequency(json_file, output_csv):
    """分析引用文献出现的频率
    
    Args:
        json_file (str): 包含引用数据的JSON文件路径
        output_csv (str): 输出统计结果的CSV文件路径
    """
    try:
        # 加载JSON数据
        data = load_existing_json(json_file)
        
        if not data:
            print(f"[错误] JSON文件为空或不存在: {json_file}")
            return
            
        print(f"[信息] 开始分析引用频率...")
        
        # 引用计数器 - 使用两个字典，一个用于articleNumber，一个用于title
        num_counter = {}  # 通过articleNumber计数
        title_counter = {}  # 通过title计数
        
        # 遍历所有文章及其引用
        total_refs = 0
        for article in data:
            for ref in article.get('references', []):
                total_refs += 1
                
                # 如果有文章编号，按编号统计
                if ref.get('articleNumber'):
                    article_num = str(ref['articleNumber'])
                    num_counter[article_num] = num_counter.get(article_num, 0) + 1
                # 否则按标题统计
                elif ref.get('articleTitle'):
                    article_title = ref['articleTitle'].strip()
                    if article_title:  # 确保标题不为空
                        title_counter[article_title] = title_counter.get(article_title, 0) + 1
        
        # 合并统计结果
        # 首先处理有编号的文章
        results = []
        for article_num, count in num_counter.items():
            # 查找此编号的所有标题，通常应该只有一个
            titles = []
            for article in data:
                for ref in article.get('references', []):
                    if ref.get('articleNumber') == article_num:
                        title = ref.get('articleTitle', '')
                        if title and title not in titles:
                            titles.append(title)
            
            results.append({
                'articleNumber': article_num,
                'articleTitle': titles[0] if titles else '',
                'frequency': count,
                'match_by': 'articleNumber'
            })
        
        # 然后处理仅有标题的文章（确保不重复计算已经统计过的编号文章）
        for article_title, count in title_counter.items():
            # 检查这个标题是否已经在有编号的文章中出现过
            found = False
            for item in results:
                if item['articleTitle'] == article_title:
                    found = True
                    break
            
            if not found:
                results.append({
                    'articleNumber': '',
                    'articleTitle': article_title,
                    'frequency': count,
                    'match_by': 'articleTitle'
                })
        
        # 按频率降序排序
        results.sort(key=lambda x: x['frequency'], reverse=True)
        
        # 保存到CSV
        df = pd.DataFrame(results)
        df.to_csv(output_csv, index=False, encoding='utf-8-sig')
        
        print(f"[统计信息] 总分析引用数: {total_refs}")
        print(f"[统计信息] 不同文章数: {len(results)}")
        print(f"[信息] 引用频率分析已保存到: {output_csv}")
        
    except Exception as e:
        print(f"[错误] 分析引用频率时发生错误: {str(e)}")

if __name__ == "__main__":
    import argparse
    
    # 初始化日志记录器
    setup_logger()
    
    # 命令行参数解析
    parser = argparse.ArgumentParser(description='IEEE参考文献爬取工具')
    parser.add_argument('--input', '-i', type=str, required=True, help='输入CSV文件路径，包含articleNumber列')
    
    args = parser.parse_args()
    
    # 从输入文件名生成输出文件名
    input_base = os.path.splitext(args.input)[0]
    output_json = f"{input_base}.json"
    output_frequency = f"{input_base}_refstat.csv"
    
    print(f"[信息] 输入文件: {args.input}")
    print(f"[信息] 引用数据将保存到: {output_json}")
    print(f"[信息] 频率分析将保存到: {output_frequency}")
    
    # 从CSV文件加载文章编号
    target_article_numbers = load_article_numbers_from_csv(args.input)
    
    if not target_article_numbers:
        print("[错误] 没有找到有效的文章编号，程序终止")
        sys.exit(1)
    
    # 处理每个文章
    for i, target_article_number in enumerate(target_article_numbers, 1):
        print(f"\n[进度] 处理文章 {i}/{len(target_article_numbers)}: {target_article_number}")
        result = scrape_ieee_references(
            article_number=target_article_number,
            output_file=output_json,
            wait_time=1  # 固定等待1秒
        )
        
        if result:
            print(f"\n[成功] 文章 {target_article_number} 的引用数据已保存")
        else:
            print(f"\n[失败] 无法处理文章 {target_article_number}")
    
    print(f"\n[完成] 所有文章处理完毕，数据已保存到 {output_json}")
    
    # 自动进行引用频率分析
    print("\n[信息] 开始进行引用频率分析...")
    analyze_references_frequency(output_json, output_frequency)