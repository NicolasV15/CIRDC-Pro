import requests
import json
import time
import urllib3
import os
import logging
import argparse
import shutil
from datetime import datetime
from abc import ABC, abstractmethod

# 创建log目录
if not os.path.exists('./log'):
    os.makedirs('./log')

# 配置日志
log_dir = os.path.join('./log', '1_publicationInfo')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_filename = os.path.join(log_dir, f'publication_crawl_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('ieee_crawler')

class IEEEFetcher(ABC):
    """IEEE数据抓取基类"""
    
    def __init__(self, start_year, sleep_time=1, retry=15):
        self.start_year = start_year
        self.sleep_time = sleep_time
        self.retry = retry
        self.base_url = 'https://ieeexplore.ieee.org/rest/publication'
        self.headers = {
            'Accept': 'application/json,text/plain,*/*',
            'Accept-Encoding': 'gzip,deflate,br',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'Connection': 'keep-alive',
            'Content-Length': '147',
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36 Edg/108.0.1462.46',
        }
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    @abstractmethod
    def get_content_type(self):
        """获取内容类型，由子类实现"""
        pass
    
    @abstractmethod
    def get_referer(self):
        """获取Referer URL，由子类实现"""
        pass
    
    @abstractmethod
    def get_json_dir(self, year):
        """获取JSON保存目录，由子类实现"""
        pass
    
    def prepare_request_data(self, year, page):
        """准备请求数据"""
        return {
            "contentType": self.get_content_type(),
            "tabId": "title",
            "ranges": ["{}_{}_Year".format(year, year)],
            "pageNumber": page
        }
    
    def check_existing_data(self, year):
        """检查是否已存在当前年份的数据文件，并比较totalRecords"""
        json_dir = self.get_json_dir(year)
        first_page_file = os.path.join(json_dir, "1.json")
        
        if not os.path.exists(first_page_file):
            logger.info(f"年份 {year} 没有现有数据文件，需要抓取。")
            return None
        
        try:
            with open(first_page_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                existing_total_records = existing_data.get('totalRecords', 0)
                logger.info(f"年份 {year} 已有数据文件，记录数为 {existing_total_records}。")
                return existing_total_records
        except Exception as e:
            logger.error(f"读取年份 {year} 现有数据文件时出错: {e}")
            return None
    
    def fetch_data(self, year, page, get_total_page=False, check_only=False):
        """抓取数据"""
        if get_total_page is True:
            assert page == 1
        
        data = self.prepare_request_data(year, page)
        headers = self.headers.copy()
        headers['Referer'] = self.get_referer()
        
        for attempt in range(self.retry):
            try:
                res = requests.post(
                    url=self.base_url, 
                    data=json.dumps(data), 
                    headers=headers, 
                    verify=False
                )
                res.raise_for_status()
                
                try:
                    dic_obj = res.json()
                    total_records = dic_obj.get('totalRecords', 0)
                    
                    # 如果该年份没有记录，返回特殊值表示结束爬取
                    if total_records == 0 and page == 1:
                        logger.info(f"年份 {year} 没有记录，停止爬取。")
                        return -1
                    
                    # 如果只是检查，则返回totalRecords，不保存文件
                    if check_only:
                        return total_records
                    
                    if not get_total_page:
                        json_dir = self.get_json_dir(year)
                        if not os.path.exists(json_dir):
                            os.makedirs(json_dir)
                        
                        # 只保存records数组、totalRecords和totalPages字段
                        filtered_data = {
                            "records": dic_obj.get("records", []),
                            "totalRecords": dic_obj.get("totalRecords", 0),
                            "totalPages": dic_obj.get("totalPages", 0)
                        }
                        
                        target_file = os.path.join(json_dir, "{}.json".format(page))
                        temp_file = target_file + ".tmp"
                        
                        # 使用临时文件进行原子写入
                        try:
                            # 先写入临时文件
                            with open(temp_file, 'w', encoding='utf-8') as f:
                                json.dump(filtered_data, f, ensure_ascii=False, indent=4)
                            
                            # 原子性地替换文件
                            if os.name == 'nt':  # Windows系统
                                if os.path.exists(target_file):
                                    os.remove(target_file)  # Windows可能需要先删除目标文件
                                os.rename(temp_file, target_file)
                            else:  # POSIX系统（Linux, macOS等）
                                os.replace(temp_file, target_file)  # 使用os.replace进行原子替换
                                
                            logger.info(f"年份 {year} 页数 {page} 成功抓取并保存。")
                        except Exception as e:
                            logger.error(f"写入文件 {target_file} 失败: {e}")
                            # 清理临时文件
                            if os.path.exists(temp_file):
                                try:
                                    os.remove(temp_file)
                                except Exception as te:
                                    logger.error(f"删除临时文件 {temp_file} 失败: {te}")
                            raise
                        
                        return total_records
                    else:
                        num_of_page = dic_obj.get('totalPages', 0)
                        return num_of_page
                
                except json.JSONDecodeError:
                    logger.warning(f"JSON解码错误，年份 {year}，尝试 {attempt+1}/{self.retry}。重试中...")
            
            except requests.RequestException as e:
                logger.warning(f"请求错误，年份 {year} 页数 {page}，尝试 {attempt+1}/{self.retry}: {e}。重试中...")
        
        logger.error(f"抓取年份 {year} 页数 {page} 失败，已尝试 {self.retry} 次。")
        return None
    
    def run(self):
        """运行抓取过程"""
        results = []
        current_year = self.start_year
        zero_records_year = None
        
        logger.info(f"开始抓取，起始年份: {self.start_year}")
        
        while True:
            # 检查是否已存在当前年份的数据
            existing_total_records = self.check_existing_data(current_year)
            
            # 获取网页上的记录数，但不保存文件
            web_total_records = self.fetch_data(current_year, page=1, get_total_page=False, check_only=True)
            
            # 检查是否应该终止
            if web_total_records == -1:
                # 如果遇到没有记录的年份，记录下来并检查下一年
                if zero_records_year is None:
                    zero_records_year = current_year
                    current_year += 1
                    continue
                else:
                    # 如果连续两年都没有记录，终止爬取
                    if zero_records_year == current_year - 1:
                        logger.info(f"连续两年 ({zero_records_year}, {current_year}) 没有记录，停止爬取。")
                        break
                    zero_records_year = current_year
                    current_year += 1
                    continue
            
            # 重置没有记录的年份标记
            zero_records_year = None
            
            if web_total_records is None:
                current_year += 1
                continue
            
            # 比较现有数据和网页上的记录数
            if existing_total_records is not None and existing_total_records == web_total_records:
                logger.info(f"年份 {current_year} 的数据未变化，跳过抓取。")
                current_year += 1
                continue
            
            # 获取总页数
            num_of_page_this_year = self.fetch_data(current_year, page=1, get_total_page=True)
            if num_of_page_this_year is None or num_of_page_this_year <= 0:
                current_year += 1
                continue
            
            # 数据不一致或不存在，重新抓取
            if existing_total_records is not None:
                logger.info(f"年份 {current_year} 的数据已变化 (原: {existing_total_records}, 新: {web_total_records})，重新抓取。")
            
            for page in range(1, num_of_page_this_year + 1):
                record_count = self.fetch_data(current_year, page=page, get_total_page=False)
                if record_count is not None and record_count > 0:
                    results.append(record_count)
                time.sleep(self.sleep_time)
            
            logger.info(f"年份 {current_year} 抓取完成。")
            current_year += 1
        
        return results


class ConferenceFetcher(IEEEFetcher):
    """IEEE会议数据抓取类"""
    
    def get_content_type(self):
        return "conferences"
    
    def get_referer(self):
        return "https://ieeexplore.ieee.org/browse/conferences/title"
    
    def get_json_dir(self, year):
        return f'./publicationInfo/Conferences/{year}'


class JournalFetcher(IEEEFetcher):
    """IEEE期刊数据抓取类"""
    
    def get_content_type(self):
        return "periodicals"
    
    def get_referer(self):
        return "https://ieeexplore.ieee.org/browse/periodicals/title"
    
    def get_json_dir(self, year):
        return f'./publicationInfo/Journals/{year}'


if __name__ == "__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='IEEE出版物信息爬虫')
    parser.add_argument('year', type=int, nargs='?', help='设置期刊和会议数据的起始年份')
    parser.add_argument('-c', '--conference', type=int, help='设置会议数据的起始年份并爬取会议数据')
    parser.add_argument('-j', '--journal', type=int, help='设置期刊数据的起始年份并爬取期刊数据')
    args = parser.parse_args()
    
    # 默认年份
    conf_start_year = 1936
    jour_start_year = 1884
    
    # 根据参数设置起始年份
    if args.year is not None:
        # 如果直接指定了年份，期刊和会议都从该年份开始爬取
        conf_start_year = args.year
        jour_start_year = args.year
        crawl_conference = True
        crawl_journal = True
    else:
        # 根据-c和-j参数设置起始年份
        if args.conference:
            conf_start_year = args.conference
        if args.journal:
            jour_start_year = args.journal
        
        # 确定要爬取的数据类型
        crawl_conference = args.conference is not None or (args.conference is None and args.journal is None)
        crawl_journal = args.journal is not None or (args.conference is None and args.journal is None)
    
    # 爬取会议数据
    if crawl_conference:
        logger.info(f"开始抓取会议数据，起始年份: {conf_start_year}...")
        conference_fetcher = ConferenceFetcher(start_year=conf_start_year)
        conference_results = conference_fetcher.run()
        logger.info(f"会议数据抓取完成，共获取 {len(conference_results)} 条记录")
    
    # 爬取期刊数据
    if crawl_journal:
        logger.info(f"开始抓取期刊数据，起始年份: {jour_start_year}...")
        journal_fetcher = JournalFetcher(start_year=jour_start_year)
        journal_results = journal_fetcher.run()
        logger.info(f"期刊数据抓取完成，共获取 {len(journal_results)} 条记录") 