import requests
import os
import time
from datetime import datetime
import logging
from PyPDF2 import PdfReader
import shutil

def setup_logger():
    """配置日志记录器
    仅记录错误信息到文件中
    """
    # 获取当前脚本所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(current_dir, 'ieee_download_errors.log')
    
    # 配置日志记录器
    logger = logging.getLogger('ieee_downloader')
    logger.setLevel(logging.ERROR)
    
    # 创建文件处理器
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.ERROR)
    
    # 设置日志格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    
    # 添加处理器到日志记录器
    logger.addHandler(file_handler)
    
    return logger

def flush_logger(logger):
    """强制刷新日志记录器的所有处理器
    Args:
        logger: 日志记录器对象
    """
    for handler in logger.handlers:
        handler.flush()

def verify_pdf(file_path, paper_id):
    """验证PDF文件是否完整且可读
    Args:
        file_path (str): PDF文件路径
        paper_id (str): 论文ID，用于日志记录
    Returns:
        bool: 文件是否有效
    """
    try:
        # 尝试打开并读取PDF文件
        with open(file_path, 'rb') as file:
            # 尝试解析PDF
            pdf = PdfReader(file)
            # 尝试获取页数，如果能获取说明文件基本完整
            num_pages = len(pdf.pages)
            # 尝试读取第一页内容，确保文件可读
            pdf.pages[0].extract_text()
            return True
    except Exception as e:
        logger = logging.getLogger('ieee_downloader')
        logger.error(f"[论文ID: {paper_id}] PDF验证失败: {str(e)}")
        flush_logger(logger)  # 使用新的flush_logger函数
        return False

def check_existing_pdf(file_path, paper_id):
    """检查PDF文件是否已存在且有效
    Args:
        file_path (str): PDF文件路径
        paper_id (str): 论文ID，用于日志记录
    Returns:
        bool: 文件是否存在且有效
    """
    if not os.path.exists(file_path):
        return False
        
    # 检查文件大小
    if os.path.getsize(file_path) == 0:
        print(f"[警告] 已存在的文件 {file_path} 大小为0，将重新下载")
        return False
        
    # 验证PDF完整性
    if verify_pdf(file_path, paper_id):
        print(f"[信息] 文件 {file_path} 已存在且验证通过，跳过下载")
        return True
    else:
        print(f"[警告] 已存在的文件 {file_path} 验证失败，将重新下载")
        return False

def download_ieee_pdf(paper_id, output_dir=None, max_retries=5):
    """下载IEEE论文PDF文件
    Args:
        paper_id (str): 论文ID
        output_dir (str, optional): 输出目录路径，默认为当前目录
        max_retries (int): 最大重试次数，默认为5次
    Returns:
        bool: 下载是否成功
    """
    logger = logging.getLogger('ieee_downloader')
    
    # 确定输出文件路径
    if output_dir:
        # 确保输出目录存在
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"[论文ID: {paper_id}] 创建目录失败 {output_dir}: {str(e)}")
            flush_logger(logger)  # 使用新的flush_logger函数
            return False
        
        output_filename = os.path.join(output_dir, f"{paper_id}.pdf")
    else:
        output_filename = f"{paper_id}.pdf"
    
    # 检查文件是否已存在且有效
    if check_existing_pdf(output_filename, paper_id):
        return True
    
    # 定义每次重试的等待时间
    retry_wait_times = {1: 3, 2: 5, 3: 8, 4: 10}  # 重试次数对应的等待时间
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                wait_time = retry_wait_times.get(attempt, 10)  # 如果找不到对应的等待时间，默认使用10秒
                print(f"[信息] 第 {attempt + 1} 次尝试下载...")
                print(f"[信息] 等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
            
            # 构建URL
            url = f"https://ieeexplore.ieee.org/stampPDF/getPDF.jsp?tp=&arnumber={paper_id}&ref="
            
            # 设置请求头
            headers = {
                'Connection': 'keep-alive',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': f'https://ieeexplore.ieee.org/document/{paper_id}'
            }
            
            # 发送请求
            try:
                response = requests.get(url, headers=headers)
            except requests.exceptions.RequestException as e:
                error_msg = f"[论文ID: {paper_id}] 网络请求失败: {str(e)}"
                logger.error(error_msg)
                flush_logger(logger)  # 使用新的flush_logger函数
                if attempt < max_retries - 1:
                    continue
                return False
            
            # 检查响应状态
            if response.status_code == 200 and response.headers.get('content-type', '').startswith('application/pdf'):
                # 先下载到临时文件
                temp_filename = output_filename + '.tmp'
                
                # 保存PDF文件
                try:
                    with open(temp_filename, 'wb') as f:
                        f.write(response.content)
                except Exception as e:
                    error_msg = f"[论文ID: {paper_id}] 写入文件失败 {temp_filename}: {str(e)}"
                    logger.error(error_msg)
                    flush_logger(logger)  # 使用新的flush_logger函数
                    if os.path.exists(temp_filename):
                        os.remove(temp_filename)
                    if attempt < max_retries - 1:
                        continue
                    return False
                
                # 验证文件大小和完整性
                if os.path.getsize(temp_filename) > 0 and verify_pdf(temp_filename, paper_id):
                    # 验证成功，将临时文件移动到目标位置
                    try:
                        shutil.move(temp_filename, output_filename)
                        print(f"[信息] PDF文件验证成功")
                        return True
                    except Exception as e:
                        error_msg = f"[论文ID: {paper_id}] 移动文件失败 {temp_filename} -> {output_filename}: {str(e)}"
                        logger.error(error_msg)
                        flush_logger(logger)  # 使用新的flush_logger函数
                        if os.path.exists(temp_filename):
                            os.remove(temp_filename)
                        if attempt < max_retries - 1:
                            continue
                        return False
                else:
                    # 验证失败，删除临时文件
                    if os.path.exists(temp_filename):
                        os.remove(temp_filename)
                    if attempt < max_retries - 1:
                        print(f"[警告] PDF文件验证失败，准备重试...")
                        continue
                    else:
                        error_msg = f"[论文ID: {paper_id}] PDF文件验证失败: {output_filename}"
                        logger.error(error_msg)
                        flush_logger(logger)  # 使用新的flush_logger函数
                        return False
            else:
                if attempt < max_retries - 1:
                    print(f"[警告] 下载失败，状态码: {response.status_code}，准备重试...")
                    continue
                else:
                    error_msg = f"[论文ID: {paper_id}] 下载失败: 状态码={response.status_code}, 内容类型={response.headers.get('content-type')}, URL={url}"
                    logger.error(error_msg)
                    flush_logger(logger)  # 使用新的flush_logger函数
                    return False
                
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"[警告] 下载出错: {str(e)}，准备重试...")
                continue
            else:
                error_msg = f"[论文ID: {paper_id}] 下载过程中发生未知错误: {str(e)}"
                logger.error(error_msg)
                flush_logger(logger)  # 使用新的flush_logger函数
                return False
        
    return False

if __name__ == "__main__":
    # 初始化日志记录器
    setup_logger()
    
    # 使用一个不存在的IEEE论文ID来测试
    paper_id = "4430340"
    
    # 下载PDF
    result = download_ieee_pdf(paper_id)
    
    if not result:
        print("\n下载失败。错误信息已记录到 ieee_download_errors.log 文件中。")

