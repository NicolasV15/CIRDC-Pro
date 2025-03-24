import os
import json
import time
import logging
from datetime import datetime
from Download_PDF import download_ieee_pdf, setup_logger

def setup_custom_logger():
    """
    配置自定义日志记录器，将日志保存在log文件夹下
    """
    # 创建log目录
    log_dir = "log"
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, 'ieee_download_errors.log')
    
    # 配置日志记录器
    logger = logging.getLogger('ieee_downloader')
    logger.setLevel(logging.ERROR)
    
    # 清除现有处理器
    if logger.handlers:
        logger.handlers.clear()
    
    # 创建文件处理器
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.ERROR)
    
    # 设置日志格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    
    # 添加处理器到日志记录器
    logger.addHandler(file_handler)
    
    return logger

def batch_download_from_json(json_root_dir="articleInfo", pdf_root_dir="PDF", max_retries=5):
    """
    批量从articleInfo子文件夹下的每一个JSON文件中读取articleNumber的键值下载，
    保存在PDF文件夹下，目录结构保持一致，PDF文件名与articleNumber一致
    
    Args:
        json_root_dir (str): JSON文件所在的根目录，默认为'articleInfo'
        pdf_root_dir (str): PDF文件保存的根目录，默认为'PDF'
        max_retries (int): 最大重试次数，默认为5次
    """
    # 初始化自定义日志记录器，保存在log文件夹下
    setup_custom_logger()
    
    # 统计变量
    total_files = 0
    processed_files = 0
    success_count = 0
    failed_count = 0
    failed_papers = []
    
    # 先计算总文件数
    for root, dirs, files in os.walk(json_root_dir):
        for file in files:
            if file.endswith('.json'):
                total_files += 1
    
    print(f"[信息] 共发现 {total_files} 个JSON文件")
    
    # 遍历JSON文件目录
    for root, dirs, files in os.walk(json_root_dir):
        for file in files:
            if file.endswith('.json'):
                # 获取相对路径
                rel_path = os.path.relpath(root, json_root_dir)
                if rel_path == '.':
                    rel_path = ''
                
                # 构建对应的PDF保存目录
                pdf_dir = os.path.join(pdf_root_dir, rel_path)
                
                # 获取JSON文件名(不带扩展名)作为额外的子目录
                json_file_name = os.path.splitext(file)[0]
                
                # 将JSON文件名添加到PDF保存路径中
                pdf_dir = os.path.join(pdf_dir, json_file_name)
                
                os.makedirs(pdf_dir, exist_ok=True)
                
                # 构建JSON文件的完整路径
                json_file_path = os.path.join(root, file)
                
                processed_files += 1
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 处理第 {processed_files}/{total_files} 个文件")
                print(f"[信息] 正在处理: {json_file_path}")
                print(f"[信息] PDF将保存到: {pdf_dir}")
                
                try:
                    # 读取JSON文件
                    with open(json_file_path, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)
                    
                    # 处理单个JSON对象或JSON数组
                    if isinstance(json_data, list):
                        articles = json_data
                    else:
                        articles = [json_data]
                    
                    # 遍历每个文章
                    for article in articles:
                        # 提取articleNumber
                        if 'articleNumber' not in article:
                            print(f"[警告] 文件 {json_file_path} 中缺少articleNumber字段，跳过")
                            continue
                        
                        article_number = article['articleNumber']
                        
                        print(f"[信息] 正在下载论文 articleNumber: {article_number}")
                        
                        # 检查PDF文件是否已存在
                        pdf_file_path = os.path.join(pdf_dir, f"{article_number}.pdf")
                        if os.path.exists(pdf_file_path) and os.path.getsize(pdf_file_path) > 0:
                            print(f"[信息] 文件 {pdf_file_path} 已存在，跳过下载")
                            success_count += 1
                            continue
                        
                        # 下载PDF
                        result = download_ieee_pdf(article_number, pdf_dir, max_retries)
                        
                        if result:
                            success_count += 1
                            print(f"[成功] 论文 {article_number} 下载成功")
                        else:
                            failed_count += 1
                            failed_papers.append((json_file_path, article_number))
                            print(f"[失败] 论文 {article_number} 下载失败")
                        
                        # 添加延时，避免请求过于频繁
                        time.sleep(3)
                
                except Exception as e:
                    print(f"[错误] 处理文件 {json_file_path} 时发生错误: {str(e)}")
    
    # 打印下载统计
    print("\n" + "="*50)
    print("下载统计:")
    print(f"总JSON文件数: {total_files}")
    print(f"成功下载: {success_count}")
    print(f"下载失败: {failed_count}")
    
    if failed_papers:
        print("\n下载失败的论文:")
        for json_file, article_number in failed_papers:
            print(f"- JSON文件: {json_file}, 论文ID: {article_number}")
        print("\n详细错误信息请查看 log/ieee_download_errors.log 文件")

if __name__ == "__main__":
    # 开始批量下载
    batch_download_from_json() 