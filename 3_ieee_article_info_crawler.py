import json
import os
import urllib3
import requests
import logging
from abc import ABC, abstractmethod
import traceback
from datetime import datetime  # 导入datetime


class IEEEDownloader(ABC):
    """IEEE论文下载器基类"""
    
    def __init__(self, log_file="download.log", processed_data_path=None, refresh_from_year=None):
        """初始化下载器，设置日志"""
        # 创建日志目录
        log_dir = os.path.join("log", "3_articleinfo")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        # 添加时间戳到日志文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"{timestamp}_{log_file}")
        
        self.logger = self._setup_logger(log_file)
        self.processed_data_path = processed_data_path
        self.refresh_from_year = refresh_from_year
        
        # 确保处理后的数据目录存在
        if self.processed_data_path and not os.path.exists(self.processed_data_path):
            os.makedirs(self.processed_data_path)
            
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
    def _setup_logger(self, log_file):
        """设置日志记录器"""
        logger = logging.getLogger('ieee_downloader')
        logger.setLevel(logging.DEBUG)
        
        # 清除已有的处理器，避免重复添加
        if logger.handlers:
            logger.handlers.clear()
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        
        # 创建文件处理器
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        
        # 创建错误日志文件处理器（只记录ERROR及以上级别的日志）
        error_log_file = log_file.replace('.log', '_error.log')
        error_file_handler = logging.FileHandler(error_log_file)
        error_file_handler.setLevel(logging.ERROR)
        
        # 设置格式
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)
        error_file_handler.setFormatter(formatter)
        
        # 添加处理器
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        logger.addHandler(error_file_handler)
        
        return logger
    
    def _make_request(self, url, data, headers, retry=15):
        """发送HTTP请求并处理重试逻辑"""
        for attempt in range(retry):
            try:
                res = requests.post(url=url, data=json.dumps(data), headers=headers, verify=False)
                res.raise_for_status()
                return res.json()
            except requests.RequestException as e:
                if attempt < retry - 1:
                    self.logger.warning(f"请求错误，尝试 {attempt+1}/{retry}：{e}。重试中...")
                else:
                    self.logger.error(f"请求错误，已达到最大重试次数：{e}")
            except json.JSONDecodeError as e:
                if attempt < retry - 1:
                    self.logger.warning(f"JSON解析错误，尝试 {attempt+1}/{retry}。重试中...")
                else:
                    self.logger.error(f"JSON解析错误，已达到最大重试次数：{e}")
        
        self.logger.error(f"在 {retry} 次尝试后请求失败。")
        return None
    
    def _get_request_headers(self):
        """返回请求头"""
        return {
            'Accept': 'application/json,text/plain,*/*',
            'Accept-Encoding': 'gzip,deflate,br',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'Connection': 'keep-alive',
            'Content-Length': '147',
            'Content-Type': 'application/json',
            'Referer': 'https://ieeexplore.ieee.org/search/searchresult.jsp?newsearch=true',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 '
                        'Safari/537.36 Edg/108.0.1462.46',
        }
    
    def _process_records(self, records):
        """处理记录数据，提取所需字段"""
        processed_records = []
        
        for record in records:
            processed_record = {
                'publicationNumber': record.get('publicationNumber'),
                'doi': record.get('doi'),
                'publicationYear': record.get('publicationYear'),
                'publicationDate': record.get('publicationDate'),
                'articleNumber': record.get('articleNumber'),
                'articleTitle': record.get('articleTitle'),
                'volume': record.get('volume'),
                'issue': record.get('issue'),
                'startPage': record.get('startPage'),
                'endPage': record.get('endPage'),
                'publisher': record.get('publisher'),
                'articleContentType': record.get('articleContentType'),
                'publicationTitle': record.get('publicationTitle'),
                'authors': []
            }
            
            # 处理作者信息
            if 'authors' in record:
                for author in record['authors']:
                    author_info = {
                        'id': author.get('id'),
                        'preferredName': author.get('preferredName'),
                        'firstName': author.get('firstName'),
                        'lastName': author.get('lastName')
                    }
                    processed_record['authors'].append(author_info)
            
            processed_records.append(processed_record)
        
        return processed_records
    
    def _save_processed_json(self, processed_records, pub_number, year):
        """保存处理后的JSON数据"""
        if not self.processed_data_path:
            return
            
        # 创建目标目录结构
        dst_dir = os.path.join(self.processed_data_path, str(pub_number))
        if not os.path.exists(dst_dir):
            try:
                os.makedirs(dst_dir)
            except Exception as e:
                self.logger.error(f"创建目录 {dst_dir} 失败: {e}")
                return
            
        # 保存至目标JSON文件
        dst_json = os.path.join(dst_dir, f"{year}.json")
        # 创建临时文件用于原子写入
        tmp_json = dst_json + ".tmp"
        
        # 如果文件已存在，读取并合并数据
        if os.path.exists(dst_json):
            try:
                with open(dst_json, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                # 合并数据（通过doi去重）
                existing_dois = {record.get('doi', '') for record in existing_data if record.get('doi')}
                for record in processed_records:
                    if record.get('doi') and record.get('doi') not in existing_dois:
                        existing_data.append(record)
                        existing_dois.add(record.get('doi', ''))
                processed_records = existing_data
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON解析错误，文件 {dst_json} 可能已损坏: {e}")
                # 创建备份文件
                try:
                    import shutil
                    backup_file = dst_json + ".bak"
                    shutil.copy2(dst_json, backup_file)
                    self.logger.info(f"已创建损坏文件的备份: {backup_file}")
                except Exception as be:
                    self.logger.error(f"创建备份文件失败: {be}")
            except Exception as e:
                self.logger.error(f"合并既有数据时出错: {e}")
        
        # 使用临时文件进行原子写入
        try:
            # 先写入临时文件
            with open(tmp_json, 'w', encoding='utf-8') as f:
                json.dump(processed_records, f, ensure_ascii=False, indent=4)
            
            # 原子性地替换文件
            if os.name == 'nt':  # Windows系统
                if os.path.exists(dst_json):
                    os.remove(dst_json)  # Windows可能需要先删除目标文件
                os.rename(tmp_json, dst_json)
            else:  # POSIX系统（Linux, macOS等）
                os.replace(tmp_json, dst_json)  # 使用os.replace进行原子替换
                
            self.logger.info(f"已保存处理后的数据到 {dst_json}，共 {len(processed_records)} 条记录")
        except Exception as e:
            self.logger.error(f"写入文件 {dst_json} 失败: {e}")
            # 清理临时文件
            if os.path.exists(tmp_json):
                try:
                    os.remove(tmp_json)
                except Exception as te:
                    self.logger.error(f"删除临时文件 {tmp_json} 失败: {te}")
            
    def _get_existing_records_count(self, pub_number, year):
        """获取已存在的JSON文件中的记录数量"""
        if not self.processed_data_path:
            return 0
            
        dst_json = os.path.join(self.processed_data_path, str(pub_number), f"{year}.json")
        if not os.path.exists(dst_json):
            return 0
            
        try:
            with open(dst_json, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            return len(existing_data)
        except Exception as e:
            self.logger.error(f"读取文件 {dst_json} 失败: {e}")
            return 0
            
    def _should_process_year(self, pub_number, year, web_record_count=None):
        """判断是否应该处理该年份的数据"""
        # 如果未指定刷新年份，则始终处理
        if self.refresh_from_year is None:
            return True
            
        # 获取已有文件路径
        dst_json = os.path.join(self.processed_data_path, str(pub_number), f"{year}.json")
        
        # 文件不存在，需要处理
        if not os.path.exists(dst_json):
            self.logger.info(f"出版号 {pub_number} 年份 {year} 文件不存在，需要处理")
            return True
            
        # 年份早于刷新年份且文件存在，跳过处理
        if year < self.refresh_from_year:
            self.logger.info(f"出版号 {pub_number} 年份 {year} 早于刷新年份 {self.refresh_from_year}，跳过处理")
            return False
            
        # 年份大于等于刷新年份，且文件存在，检查记录数
        if web_record_count is not None:
            existing_count = self._get_existing_records_count(pub_number, year)
            if existing_count == web_record_count:
                self.logger.info(f"出版号 {pub_number} 年份 {year} 记录数一致 ({existing_count})，跳过处理")
                return False
            else:
                self.logger.info(f"出版号 {pub_number} 年份 {year} 记录数不一致 (本地: {existing_count}, 网页: {web_record_count})，需要处理")
                return True
                
        # 默认需要处理
        return True


class ConferenceDownloader(IEEEDownloader):
    """会议论文下载器"""
    
    def __init__(self, processed_data_path=None, refresh_from_year=None):
        """初始化会议下载器"""
        self.api_url = 'https://ieeexplore.ieee.org/rest/search'
        super().__init__(
            log_file="download_conference.log", 
            processed_data_path=processed_data_path,
            refresh_from_year=refresh_from_year
        )
    
    def process_conference_page(self, pub_number, page, year=None, parent_pub_number=None, get_page_number=False, retry=15):
        """处理会议页面"""
        self.logger.info(f"处理出版号 {pub_number} 页面 {page} 获取页数 {get_page_number}")
        
        if get_page_number:
            assert page == 1
        
        data = {
            "newsearch": 'true',
            "highlight": 'true',
            'matchBoolean': 'true',
            'matchPubs': 'true',
            'action': 'search',
            "queryText": f"(\"Publication Number\":{pub_number})",
            "pageNumber": str(page),
            "rowsPerPage": 100,
        }
        
        headers = self._get_request_headers()
        response_data = self._make_request(self.api_url, data, headers, retry)
        
        if not response_data:
            self.logger.error(f"获取出版号 {pub_number} 页面 {page} 数据失败")
            return None
            
        if get_page_number:
            return response_data.get('totalPages', 0)
        
        if 'records' not in response_data:
            self.logger.error(f"出版号 {pub_number} 页面 {page} 中没有records字段")
            return 0
            
        if len(response_data['records']) == 0:
            self.logger.warning(f"出版号 {pub_number} 页面 {page} 中记录为空")
            return 0
            
        # 如果提供了年份和父出版号，使用它们；否则从记录中提取年份信息
        save_year = year
        save_pub_number = parent_pub_number or pub_number
        
        if not save_year:
            try:
                save_year = response_data['records'][0].get('publicationYear', 'unknown')
            except Exception as e:
                self.logger.error(f"获取出版号 {pub_number} 页面 {page} 年份信息失败: {e}")
                save_year = 'unknown'
        
        # 处理记录并保存
        try:
            processed_records = self._process_records(response_data['records'])
            self._save_processed_json(processed_records, save_pub_number, save_year)
            
            self.logger.info(f"出版号 {pub_number} 年份 {save_year} 页面 {page} 处理成功，保存到目录 {save_pub_number}")
            
            # 返回记录数
            return len(processed_records)
        except Exception as e:
            self.logger.error(f"处理记录失败，出版号 {pub_number} 年份 {save_year} 页面 {page}: {e}")
            return 0
            
    def check_conference_record_count(self, pub_number):
        """检查会议记录总数"""
        try:
            data = {
                "newsearch": 'true',
                "highlight": 'true',
                'matchBoolean': 'true',
                'matchPubs': 'true',
                'action': 'search',
                "queryText": f"(\"Publication Number\":{pub_number})",
                "pageNumber": "1",
                "rowsPerPage": 100,
            }
            
            headers = self._get_request_headers()
            response_data = self._make_request(self.api_url, data, headers)
            
            if not response_data or 'totalRecords' not in response_data:
                return None
                
            return response_data['totalRecords']
        except Exception as e:
            self.logger.error(f"检查会议记录数失败，出版号 {pub_number}: {e}")
            return None
    
    def download_all(self, conferences_file):
        """下载所有会议论文信息"""
        self.logger.info(f"开始下载和处理会议论文信息，使用文件：{conferences_file}")
        
        try:
            with open(conferences_file, 'r', encoding='utf-8') as fr:
                all_conferences = json.load(fr)
                total_conferences = len(all_conferences)
                
                for i, (parent_pub_number, conference_data) in enumerate(all_conferences.items(), 1):
                    self.logger.info(f"处理会议系列 {parent_pub_number} - {conference_data.get('parentTitle', '')} ({i}/{total_conferences})")
                    
                    # 处理titleHistory中的每个会议年份
                    title_history = conference_data.get('titleHistory', [])
                    
                    for title_item in title_history:
                        pub_number = title_item.get('publicationNumber')
                        year = title_item.get('year')
                        display_title = title_item.get('displayTitle', '')
                        
                        if not pub_number or not year:
                            self.logger.warning(f"跳过不完整的会议记录: {title_item}")
                            continue
                            
                        self.logger.info(f"处理会议 {pub_number} - {display_title} ({year}年)")
                        
                        # 检查是否需要处理该会议年份
                        if not self._should_process_year(parent_pub_number, int(year)):
                            self.logger.info(f"会议 {pub_number} ({year}年) 已处理且不需更新，跳过")
                            continue
                        
                        # 需要处理会议数据
                        num_of_page = self.process_conference_page(
                            pub_number, 
                            page=1,
                            year=year,
                            parent_pub_number=parent_pub_number,
                            get_page_number=True
                        )
                        
                        if num_of_page:
                            for page in range(1, num_of_page+1):
                                self.process_conference_page(
                                    pub_number, 
                                    page=page,
                                    year=year,
                                    parent_pub_number=parent_pub_number,
                                    get_page_number=False
                                )
            
            self.logger.info("会议论文信息下载和处理完成")
        except Exception as e:
            self.logger.error(f"处理会议数据时出现异常: {e}")
            self.logger.error(traceback.format_exc())


class JournalDownloader(IEEEDownloader):
    """期刊论文下载器"""
    
    def __init__(self, processed_data_path=None, refresh_from_year=None):
        """初始化期刊下载器"""
        self.api_url = 'https://ieeexplore.ieee.org/rest/search'
        super().__init__(
            log_file="download_journal.log", 
            processed_data_path=processed_data_path,
            refresh_from_year=refresh_from_year
        )
    
    def check_journal_year_record_count(self, pub_number, year):
        """检查期刊特定年份的记录总数"""
        try:
            data = {
                "newsearch": 'true',
                "highlight": 'true',
                'matchBoolean': 'true',
                'matchPubs': 'true',
                'action': 'search',
                "queryText": f"(\"Publication Number\":{pub_number})",
                "pageNumber": "1",
                "rowsPerPage": 100,
                "ranges": [f"{year}_{year}_Year"]
            }
            
            headers = self._get_request_headers()
            response_data = self._make_request(self.api_url, data, headers)
            
            if not response_data or 'totalRecords' not in response_data:
                return None
                
            return response_data['totalRecords']
        except Exception as e:
            self.logger.error(f"检查期刊记录数失败，出版号 {pub_number} 年份 {year}: {e}")
            return None
    
    def process_journal_year_page(self, pub_number, year, page, get_page_number=False, retry=15):
        """处理期刊年份页面"""
        self.logger.info(f"处理出版号 {pub_number} 年份 {year} 页面 {page} 获取页数 {get_page_number}")
        
        if get_page_number:
            assert page == 1
        
        data = {
            "newsearch": 'true',
            "highlight": 'true',
            'matchBoolean': 'true',
            'matchPubs': 'true',
            'action': 'search',
            "queryText": f"(\"Publication Number\":{pub_number})",
            "pageNumber": str(page),
            "rowsPerPage": 100,
            "ranges": [f"{year}_{year}_Year"]
        }
        
        headers = self._get_request_headers()
        response_data = self._make_request(self.api_url, data, headers, retry)
        
        if not response_data:
            self.logger.error(f"获取出版号 {pub_number} 年份 {year} 页面 {page} 数据失败")
            return None
            
        if get_page_number:
            return response_data.get('totalPages', 0)
        
        if 'records' not in response_data:
            self.logger.error(f"出版号 {pub_number} 年份 {year} 页面 {page} 中没有records字段")
            return 0
            
        if len(response_data['records']) == 0:
            self.logger.warning(f"出版号 {pub_number} 年份 {year} 页面 {page} 中记录为空")
            return 0
            
        try:
            # 处理记录并保存
            processed_records = self._process_records(response_data['records'])
            self._save_processed_json(processed_records, pub_number, year)
            
            self.logger.info(f"出版号 {pub_number} 年份 {year} 页面 {page} 处理成功，找到 {len(processed_records)} 条记录")
            return len(processed_records)
        except Exception as e:
            self.logger.error(f"处理记录失败，出版号 {pub_number} 年份 {year} 页面 {page}: {e}")
            return 0
    
    def process_journal_year(self, pub_number, year):
        """处理期刊单一年份的所有页面"""
        # 首先检查是否需要处理该年份
        web_record_count = self.check_journal_year_record_count(pub_number, year)
        if not self._should_process_year(pub_number, year, web_record_count):
            self.logger.info(f"跳过处理出版号 {pub_number} 年份 {year}")
            return 0
            
        self.logger.info(f"开始处理出版号 {pub_number} 年份 {year}")
        total_page = self.process_journal_year_page(pub_number, year, page=1, get_page_number=True)
        total_records = 0
        
        if total_page:
            for each_page in range(1, total_page+1):
                records = self.process_journal_year_page(pub_number, year, page=each_page)
                if records:
                    total_records += records
        
        return total_records
    
    def download_all(self, journals_file):
        """下载所有期刊论文信息"""
        self.logger.info(f"开始下载和处理期刊论文信息，使用文件：{journals_file}")
        
        try:
            with open(journals_file, 'r', encoding='utf-8') as fr:
                all_journals = json.load(fr)
                total_journals = len(all_journals)
                
                for i, (pub_number, entry) in enumerate(all_journals.items(), 1):
                    self.logger.info(f"处理期刊 {pub_number} - {entry.get('title', '')} ({i}/{total_journals})")
                    
                    start_year = int(entry['start_year'])
                    end_year = entry['end_year']
                    
                    if end_year == 'Present':
                        end_year = datetime.now().year  # 使用当前年份代替硬编码值
                    else:
                        end_year = int(end_year)
                    
                    for each_year in range(start_year, end_year+1):
                        total_records = self.process_journal_year(pub_number, each_year)
                        self.logger.info(f"出版号 {pub_number} 年份 {each_year} 处理完成，共 {total_records} 条记录")
            
            self.logger.info("期刊论文信息下载和处理完成")
        except Exception as e:
            self.logger.error(f"处理期刊数据时出现异常: {e}")
            self.logger.error(traceback.format_exc())


def main(conference_file="./publicationInfo/all_conferences.json", 
         journal_file="./publicationInfo/all_journal.json",
         refresh_from_year=None):
    """
    主函数，接受文件路径参数
    
    参数:
        conference_file: 会议文件路径
        journal_file: 期刊文件路径
        refresh_from_year: 从哪一年开始刷新数据，为None则全部刷新
    """
    
    # 创建日志目录
    log_dir = os.path.join("log", "3_articleinfo")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 添加时间戳到日志文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    main_log_file = os.path.join(log_dir, f"{timestamp}_ieee_main.log")
    main_error_log_file = os.path.join(log_dir, f"{timestamp}_ieee_main_error.log")
    
    # 设置主日志记录器
    main_logger = logging.getLogger('ieee_main')
    main_logger.setLevel(logging.DEBUG)
    
    # 清除已有的处理器
    if main_logger.handlers:
        main_logger.handlers.clear()
    
    # 创建控制台和文件处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    file_handler = logging.FileHandler(main_log_file)
    file_handler.setLevel(logging.DEBUG)
    
    error_file_handler = logging.FileHandler(main_error_log_file)
    error_file_handler.setLevel(logging.ERROR)
    
    # 设置格式
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    error_file_handler.setFormatter(formatter)
    
    # 添加处理器
    main_logger.addHandler(console_handler)
    main_logger.addHandler(file_handler)
    main_logger.addHandler(error_file_handler)
    
    # 设置路径
    base_dir = "./articleInfo"
    
    # 设置处理后数据的路径
    processed_conference_path = os.path.join(base_dir, "Conferences")
    processed_journal_path = os.path.join(base_dir, "Journals")
    
    main_logger.info("开始IEEE数据下载和处理任务")
    if refresh_from_year:
        main_logger.info(f"增量更新模式：从 {refresh_from_year} 年开始刷新数据")
    else:
        main_logger.info("全量更新模式：刷新所有数据")
    
    # 下载并处理会议论文信息
    try:
        main_logger.info("开始处理会议数据")
        
        conference_downloader = ConferenceDownloader(
            processed_data_path=processed_conference_path,
            refresh_from_year=refresh_from_year
        )
        conference_downloader.download_all(conferences_file=conference_file)
        
        main_logger.info("会议数据处理完成")
    except Exception as e:
        main_logger.error(f"处理会议数据时出错: {e}")
        main_logger.error(traceback.format_exc())
    
    # 下载并处理期刊论文信息
    try:
        main_logger.info("开始处理期刊数据")
        
        journal_downloader = JournalDownloader(
            processed_data_path=processed_journal_path,
            refresh_from_year=refresh_from_year
        )
        journal_downloader.download_all(journals_file=journal_file)
        
        main_logger.info("期刊数据处理完成")
    except Exception as e:
        main_logger.error(f"处理期刊数据时出错: {e}")
        main_logger.error(traceback.format_exc())
    
    main_logger.info("IEEE数据下载和处理任务完成")


if __name__ == "__main__":
    # 可以在这里修改参数
    main(
        conference_file="./publicationInfo/all_conferences.json", 
        journal_file="./publicationInfo/empty.json",
        #refresh_from_year=1980  # 从指定年份年开始刷新数据，之前的数据如果已存在则不再获取
    )