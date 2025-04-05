import json
import os
import requests
import logging
import time
from datetime import datetime
import urllib3
import traceback

# 禁用不安全请求警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class IEEEDownloader:
    """IEEE论文下载器"""
    
    def __init__(self, conference_dir="./downloaded_conferences", journal_dir="./downloaded_journals"):
        """初始化下载器
        
        Args:
            conference_dir: 保存会议数据的目录
            journal_dir: 保存期刊数据的目录
        """
        self.api_url = 'https://ieeexplore.ieee.org/rest/search'
        self.conference_dir = conference_dir
        self.journal_dir = journal_dir
        self.last_request_time = 0  # 记录上次请求时间
        
        # 确保输出目录存在
        for directory in [self.conference_dir, self.journal_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)
            
        # 设置日志
        self.logger = self._setup_logger()
        
    def _setup_logger(self):
        """设置日志记录器"""
        # 创建日志目录
        log_dir = "logs/3_articleInfo"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        # 添加时间戳到日志文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"{timestamp}_ieee_download.log")
        
        # 配置日志
        logger = logging.getLogger('ieee_downloader')
        logger.setLevel(logging.DEBUG)
        
        # 清除已有的处理器，避免重复添加
        if logger.handlers:
            logger.handlers.clear()
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 创建文件处理器
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        
        # 设置格式
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)
        
        # 添加处理器
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        
        return logger
    
    def _get_request_headers(self):
        """返回请求头"""
        return {
            'Accept': 'application/json,text/plain,*/*',
            'Accept-Encoding': 'gzip,deflate,br',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
            'Referer': 'https://ieeexplore.ieee.org/search/searchresult.jsp?newsearch=true',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 '
                        'Safari/537.36 Edg/108.0.1462.46',
        }
    
    def _wait_between_requests(self, delay=1.0):
        """在请求之间等待指定的延迟时间
        
        Args:
            delay: 等待的秒数，默认为1秒
        """
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        if elapsed < delay:
            wait_time = delay - elapsed
            self.logger.debug(f"等待 {wait_time:.2f} 秒...")
            time.sleep(wait_time)
            
        self.last_request_time = time.time()
    
    def _make_request(self, data, retry=10):
        """发送HTTP请求并处理重试逻辑
        
        Args:
            data: 请求数据
            retry: 重试次数
            
        Returns:
            响应的JSON数据，失败时返回None
        """
        headers = self._get_request_headers()
        
        for attempt in range(retry):
            try:
                # 在发送请求前等待
                self._wait_between_requests()
                
                self.logger.info(f"正在发送请求 (尝试 {attempt+1}/{retry})...")
                res = requests.post(
                    url=self.api_url, 
                    data=json.dumps(data), 
                    headers=headers, 
                    verify=False
                )
                res.raise_for_status()
                return res.json()
            except requests.RequestException as e:
                self.logger.warning(f"请求错误: {e}")
                if attempt < retry - 1:
                    self.logger.info("准备重试...")
                else:
                    self.logger.error(f"达到最大重试次数，请求失败")
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON解析错误: {e}")
                if attempt < retry - 1:
                    self.logger.info("准备重试...")
                else:
                    self.logger.error(f"达到最大重试次数，请求失败")
        
        return None
    
    def _process_records(self, records):
        """处理记录数据，提取所需字段
        
        Args:
            records: API返回的原始记录列表
            
        Returns:
            处理后的记录列表
        """
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
    
    ###################
    # 会议下载相关方法 #
    ###################
    
    def get_conference_page_count(self, pub_number):
        """获取会议的总页数
        
        Args:
            pub_number: 会议出版号
            
        Returns:
            总页数，失败时返回0
        """
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
        
        response = self._make_request(data)
        
        if not response:
            self.logger.error(f"获取会议 {pub_number} 页数失败")
            return 0
            
        total_pages = response.get('totalPages', 0)
        self.logger.info(f"会议 {pub_number} 总页数: {total_pages}")
        return total_pages
    
    def download_conference_page(self, pub_number, page_number, parent_pub_number=None):
        """下载会议特定页面的数据
        
        Args:
            pub_number: 会议出版号
            page_number: 页码
            parent_pub_number: 父会议系列出版号
            
        Returns:
            成功返回True，失败返回False
        """
        self.logger.info(f"正在下载会议 {pub_number} 第 {page_number} 页...")
        
        data = {
            "newsearch": 'true',
            "highlight": 'true',
            'matchBoolean': 'true',
            'matchPubs': 'true',
            'action': 'search',
            "queryText": f"(\"Publication Number\":{pub_number})",
            "pageNumber": str(page_number),
            "rowsPerPage": 100,
        }
        
        response = self._make_request(data)
        
        if not response:
            self.logger.error(f"下载会议 {pub_number} 第 {page_number} 页失败")
            return False
        
        if 'records' not in response:
            self.logger.error(f"会议 {pub_number} 第 {page_number} 页中没有records字段")
            return False
            
        if len(response['records']) == 0:
            self.logger.warning(f"会议 {pub_number} 第 {page_number} 页中记录为空")
            return False
            
        # 使用父会议系列出版号作为目录名，如果没有提供，则使用会议自身的出版号
        save_pub_number = parent_pub_number or pub_number
            
        # 处理记录并保存到临时页面文件
        try:
            processed_records = self._process_records(response['records'])
            self._save_conference_page_json(processed_records, save_pub_number, page_number, pub_number)
            
            self.logger.info(f"会议 {pub_number} 第 {page_number} 页处理成功，保存了 {len(processed_records)} 条记录")
            return True
        except Exception as e:
            self.logger.error(f"处理会议 {pub_number} 第 {page_number} 页数据失败: {e}")
            return False
    
    def _save_conference_page_json(self, processed_records, parent_pub_number, page, pub_number):
        """保存单个会议页面的数据到临时文件
        
        Args:
            processed_records: 处理后的记录
            parent_pub_number: 父会议系列出版号
            page: 页码
            pub_number: 会议出版号
        """
        # 创建目标目录结构
        dst_dir = os.path.join(self.conference_dir, str(parent_pub_number))
        if not os.path.exists(dst_dir):
            try:
                os.makedirs(dst_dir)
            except Exception as e:
                self.logger.error(f"创建目录 {dst_dir} 失败: {e}")
                return
        
        # 保存至临时页面文件
        page_json = os.path.join(dst_dir, f"{pub_number}_page_{page}.tmp")
        
        try:
            with open(page_json, 'w', encoding='utf-8') as f:
                json.dump(processed_records, f, ensure_ascii=False, indent=4)
            self.logger.info(f"已保存页面 {page} 数据到 {page_json}，共 {len(processed_records)} 条记录")
        except Exception as e:
            self.logger.error(f"写入文件 {page_json} 失败: {e}")
    
    def _merge_conference_page_files(self, pub_number, parent_pub_number, total_pages):
        """合并所有会议页面临时文件到最终的JSON文件
        
        Args:
            pub_number: 会议出版号
            parent_pub_number: 父会议系列出版号
            total_pages: 总页数
            
        Returns:
            合并的记录数量
        """
        # 使用parent_pub_number作为目录名
        dst_dir = os.path.join(self.conference_dir, str(parent_pub_number))
        final_json = os.path.join(dst_dir, f"{pub_number}.json")
        tmp_final_json = os.path.join(dst_dir, f"{pub_number}.tmp")
        
        all_records = []
        processed_pages = 0
        
        # 读取所有临时页面文件并合并数据
        for page in range(1, total_pages + 1):
            page_json = os.path.join(dst_dir, f"{pub_number}_page_{page}.tmp")
            if not os.path.exists(page_json):
                self.logger.warning(f"页面 {page} 临时文件不存在: {page_json}")
                continue
                
            try:
                with open(page_json, 'r', encoding='utf-8') as f:
                    page_records = json.load(f)
                all_records.extend(page_records)
                processed_pages += 1
            except Exception as e:
                self.logger.error(f"读取页面 {page} 临时文件失败: {e}")
                continue
        
        # 如果没有成功处理任何页面，则退出
        if processed_pages == 0:
            self.logger.error(f"没有成功处理任何页面，不创建最终JSON文件")
            return 0
            
        # 使用临时文件进行原子写入最终JSON
        try:
            # 如果最终文件已存在，删除它
            if os.path.exists(final_json):
                os.remove(final_json)
                
            # 先写入临时文件
            with open(tmp_final_json, 'w', encoding='utf-8') as f:
                json.dump(all_records, f, ensure_ascii=False, indent=4)
            
            # 原子性地替换文件
            if os.name == 'nt':  # Windows系统
                os.rename(tmp_final_json, final_json)
            else:  # POSIX系统（Linux, macOS等）
                os.replace(tmp_final_json, final_json)
                
            self.logger.info(f"已合并 {processed_pages} 个页面的数据到 {final_json}，共 {len(all_records)} 条记录")
            
            # 清理临时页面文件
            for page in range(1, total_pages + 1):
                page_json = os.path.join(dst_dir, f"{pub_number}_page_{page}.tmp")
                if os.path.exists(page_json):
                    try:
                        os.remove(page_json)
                    except Exception as e:
                        self.logger.warning(f"删除临时页面文件 {page_json} 失败: {e}")
            
            return len(all_records)
        except Exception as e:
            self.logger.error(f"合并页面数据到最终文件失败: {e}")
            # 清理临时文件
            if os.path.exists(tmp_final_json):
                try:
                    os.remove(tmp_final_json)
                except Exception as te:
                    self.logger.error(f"删除临时文件 {tmp_final_json} 失败: {te}")
            return 0
    
    def download_conference(self, pub_number, parent_pub_number=None):
        """下载整个会议的所有页面
        
        Args:
            pub_number: 会议出版号
            parent_pub_number: 父会议系列出版号
            
        Returns:
            成功下载的记录数
        """
        self.logger.info(f"开始下载会议 {pub_number} 的所有页面")
        
        # 使用父会议系列出版号，如果没有提供，则使用会议自身的出版号
        save_pub_number = parent_pub_number or pub_number
        
        # 检查是否已下载
        final_json = os.path.join(self.conference_dir, str(save_pub_number), f"{pub_number}.json")
        if os.path.exists(final_json):
            self.logger.info(f"会议 {pub_number} 已下载，跳过")
            return 0
        
        # 获取总页数
        total_pages = self.get_conference_page_count(pub_number)
        if total_pages == 0:
            self.logger.error(f"无法获取会议 {pub_number} 的页数，下载失败")
            return 0
            
        # 下载每一页
        successful_pages = 0
        for page in range(1, total_pages + 1):
            if self.download_conference_page(pub_number, page, save_pub_number):
                successful_pages += 1
        
        # 如果至少有一页下载成功，合并所有页面到一个文件
        if successful_pages > 0:
            total_records = self._merge_conference_page_files(pub_number, save_pub_number, total_pages)
            self.logger.info(f"会议 {pub_number} 下载完成，合并了 {total_records} 条记录")
            return total_records
        else:
            self.logger.error(f"会议 {pub_number} 所有页面下载失败")
            return 0
    
    def download_all_conferences(self, conferences_file):
        """下载JSON文件中指定的所有会议
        
        Args:
            conferences_file: 包含会议信息的JSON文件路径
        """
        self.logger.info(f"开始下载文件 {conferences_file} 中的所有会议")
        
        try:
            # 读取会议信息
            with open(conferences_file, 'r', encoding='utf-8') as f:
                conferences_data = json.load(f)
                
            total_conferences = len(conferences_data)
            self.logger.info(f"共找到 {total_conferences} 个会议系列")
            
            # 遍历每个会议系列
            for i, (parent_pub_number, conference_data) in enumerate(conferences_data.items(), 1):
                self.logger.info(f"正在处理会议系列 {parent_pub_number} ({i}/{total_conferences})")
                
                # 处理每个会议年份
                title_history = conference_data.get('titleHistory', [])
                for title_item in title_history:
                    pub_number = title_item.get('publicationNumber')
                    year = title_item.get('year')
                    display_title = title_item.get('displayTitle', '')
                    
                    if not pub_number:
                        self.logger.warning(f"跳过没有出版号的会议: {title_item}")
                        continue
                        
                    self.logger.info(f"下载会议 {pub_number} - {display_title} ({year}年)")
                    
                    # 下载会议
                    self.download_conference(pub_number, parent_pub_number)
                    
            self.logger.info("所有会议下载完成")
            
        except Exception as e:
            self.logger.error(f"下载会议时出错: {e}")
            self.logger.error(traceback.format_exc())
    
    ###################
    # 期刊下载相关方法 #
    ###################
    
    def check_journal_year_record_count(self, pub_number, year):
        """检查期刊特定年份的记录总数
        
        Args:
            pub_number: 期刊出版号
            year: 年份
            
        Returns:
            记录总数，失败时返回None
        """
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
            
            response = self._make_request(data)
            
            if not response or 'totalRecords' not in response:
                return None
                
            return response['totalRecords']
        except Exception as e:
            self.logger.error(f"检查期刊记录数失败，出版号 {pub_number} 年份 {year}: {e}")
            return None
    
    def _get_existing_records_count(self, pub_number, year):
        """获取已存在的JSON文件中的记录数量
        
        Args:
            pub_number: 期刊出版号
            year: 年份
            
        Returns:
            记录数量，文件不存在或读取失败时返回0
        """
        dst_json = os.path.join(self.journal_dir, str(pub_number), f"{year}.json")
        if not os.path.exists(dst_json):
            return 0
            
        try:
            with open(dst_json, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            return len(existing_data)
        except Exception as e:
            self.logger.error(f"读取文件 {dst_json} 失败: {e}")
            return 0
    
    def _save_journal_page_json(self, processed_records, pub_number, year, page):
        """保存单个期刊页面的数据到临时文件
        
        Args:
            processed_records: 处理后的记录
            pub_number: 期刊出版号
            year: 年份
            page: 页码
        """
        # 创建目标目录结构
        dst_dir = os.path.join(self.journal_dir, str(pub_number))
        if not os.path.exists(dst_dir):
            try:
                os.makedirs(dst_dir)
            except Exception as e:
                self.logger.error(f"创建目录 {dst_dir} 失败: {e}")
                return
        
        # 保存至临时页面文件
        page_json = os.path.join(dst_dir, f"{year}_page_{page}.tmp")
        
        try:
            with open(page_json, 'w', encoding='utf-8') as f:
                json.dump(processed_records, f, ensure_ascii=False, indent=4)
            self.logger.info(f"已保存期刊 {pub_number} 年份 {year} 页面 {page} 数据到 {page_json}，共 {len(processed_records)} 条记录")
        except Exception as e:
            self.logger.error(f"写入文件 {page_json} 失败: {e}")
    
    def _merge_journal_page_files(self, pub_number, year, total_pages):
        """合并所有期刊页面临时文件到最终的JSON文件
        
        Args:
            pub_number: 期刊出版号
            year: 年份
            total_pages: 总页数
            
        Returns:
            合并的记录数量
        """
        # 设置目录和文件路径
        dst_dir = os.path.join(self.journal_dir, str(pub_number))
        final_json = os.path.join(dst_dir, f"{year}.json")
        tmp_final_json = os.path.join(dst_dir, f"{year}.tmp")
        
        all_records = []
        processed_pages = 0
        
        # 读取所有临时页面文件并合并数据
        for page in range(1, total_pages + 1):
            page_json = os.path.join(dst_dir, f"{year}_page_{page}.tmp")
            if not os.path.exists(page_json):
                self.logger.warning(f"期刊 {pub_number} 年份 {year} 页面 {page} 临时文件不存在: {page_json}")
                continue
                
            try:
                with open(page_json, 'r', encoding='utf-8') as f:
                    page_records = json.load(f)
                all_records.extend(page_records)
                processed_pages += 1
            except Exception as e:
                self.logger.error(f"读取期刊 {pub_number} 年份 {year} 页面 {page} 临时文件失败: {e}")
                continue
        
        # 如果没有成功处理任何页面，则退出
        if processed_pages == 0:
            self.logger.error(f"期刊 {pub_number} 年份 {year} 没有成功处理任何页面，不创建最终JSON文件")
            return 0
            
        # 使用临时文件进行原子写入最终JSON
        try:
            # 如果最终文件已存在，删除它
            if os.path.exists(final_json):
                os.remove(final_json)
                
            # 先写入临时文件
            with open(tmp_final_json, 'w', encoding='utf-8') as f:
                json.dump(all_records, f, ensure_ascii=False, indent=4)
            
            # 原子性地替换文件
            if os.name == 'nt':  # Windows系统
                os.rename(tmp_final_json, final_json)
            else:  # POSIX系统（Linux, macOS等）
                os.replace(tmp_final_json, final_json)
                
            self.logger.info(f"已合并期刊 {pub_number} 年份 {year} 的 {processed_pages} 个页面数据到 {final_json}，共 {len(all_records)} 条记录")
            
            # 清理临时页面文件
            for page in range(1, total_pages + 1):
                page_json = os.path.join(dst_dir, f"{year}_page_{page}.tmp")
                if os.path.exists(page_json):
                    try:
                        os.remove(page_json)
                    except Exception as e:
                        self.logger.warning(f"删除临时页面文件 {page_json} 失败: {e}")
            
            return len(all_records)
        except Exception as e:
            self.logger.error(f"合并期刊 {pub_number} 年份 {year} 页面数据到最终文件失败: {e}")
            # 清理临时文件
            if os.path.exists(tmp_final_json):
                try:
                    os.remove(tmp_final_json)
                except Exception as te:
                    self.logger.error(f"删除临时文件 {tmp_final_json} 失败: {te}")
            return 0
    
    def download_journal_year_page(self, pub_number, year, page, get_page_number=False):
        """处理期刊年份页面
        
        Args:
            pub_number: 期刊出版号
            year: 年份
            page: 页码
            get_page_number: 是否只获取总页数
            
        Returns:
            get_page_number为True时返回总页数，否则返回处理结果（成功为True，失败为False）
        """
        self.logger.info(f"处理期刊 {pub_number} 年份 {year} 页面 {page} 获取页数 {get_page_number}")
        
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
        
        response = self._make_request(data)
        
        if not response:
            self.logger.error(f"获取期刊 {pub_number} 年份 {year} 页面 {page} 数据失败")
            return None if get_page_number else False
            
        if get_page_number:
            return response.get('totalPages', 0)
        
        if 'records' not in response:
            self.logger.error(f"期刊 {pub_number} 年份 {year} 页面 {page} 中没有records字段")
            return False
            
        if len(response['records']) == 0:
            self.logger.warning(f"期刊 {pub_number} 年份 {year} 页面 {page} 中记录为空")
            return False
            
        try:
            # 处理记录并保存到临时页面文件
            processed_records = self._process_records(response['records'])
            self._save_journal_page_json(processed_records, pub_number, year, page)
            
            self.logger.info(f"期刊 {pub_number} 年份 {year} 页面 {page} 处理成功，保存了 {len(processed_records)} 条记录")
            return True
        except Exception as e:
            self.logger.error(f"处理期刊 {pub_number} 年份 {year} 页面 {page} 数据失败: {e}")
            return False
    
    def download_journal_year(self, pub_number, year):
        """下载期刊单一年份的所有页面
        
        Args:
            pub_number: 期刊出版号
            year: 年份
            
        Returns:
            处理的记录总数
        """
        self.logger.info(f"开始下载期刊 {pub_number} 年份 {year}")
        
        # 检查是否已下载
        dst_json = os.path.join(self.journal_dir, str(pub_number), f"{year}.json")
        if os.path.exists(dst_json):
            self.logger.info(f"期刊 {pub_number} 年份 {year} 已下载，跳过")
            return 0
        
        # 获取网络记录数量
        web_record_count = self.check_journal_year_record_count(pub_number, year)
        
        # 检查记录数量是否一致
        if os.path.exists(dst_json) and web_record_count is not None:
            existing_count = self._get_existing_records_count(pub_number, year)
            if existing_count == web_record_count:
                self.logger.info(f"期刊 {pub_number} 年份 {year} 记录数一致 ({existing_count})，跳过处理")
                return 0
            elif existing_count != web_record_count:
                self.logger.info(f"期刊 {pub_number} 年份 {year} 记录数不一致 (本地: {existing_count}, 网页: {web_record_count})，需要处理")
        
        # 获取总页数
        total_pages = self.download_journal_year_page(pub_number, year, page=1, get_page_number=True)
        if not total_pages:
            self.logger.error(f"获取期刊 {pub_number} 年份 {year} 总页数失败")
            return 0
        
        # 下载每一页
        successful_pages = 0
        for page in range(1, total_pages + 1):
            if self.download_journal_year_page(pub_number, year, page=page):
                successful_pages += 1
        
        # 如果至少有一页下载成功，合并所有页面到一个文件
        if successful_pages > 0:
            total_records = self._merge_journal_page_files(pub_number, year, total_pages)
            self.logger.info(f"期刊 {pub_number} 年份 {year} 下载完成，合并了 {total_records} 条记录")
            return total_records
        else:
            self.logger.error(f"期刊 {pub_number} 年份 {year} 所有页面下载失败")
            return 0
    
    def download_all_journals(self, journals_file):
        """下载所有期刊论文信息
        
        Args:
            journals_file: 包含期刊信息的JSON文件路径
        """
        self.logger.info(f"开始下载文件 {journals_file} 中的所有期刊")
        
        try:
            # 读取期刊信息
            with open(journals_file, 'r', encoding='utf-8') as f:
                all_journals = json.load(f)
                
            total_journals = len(all_journals)
            self.logger.info(f"共找到 {total_journals} 个期刊")
            
            # 遍历每个期刊
            for i, (pub_number, entry) in enumerate(all_journals.items(), 1):
                self.logger.info(f"处理期刊 {pub_number} - {entry.get('title', '')} ({i}/{total_journals})")
                
                start_year = int(entry['start_year'])
                end_year = entry['end_year']
                
                if end_year == 'Present':
                    end_year = datetime.now().year  # 使用当前年份代替硬编码值
                else:
                    end_year = int(end_year)
                
                for each_year in range(start_year, end_year+1):
                    total_records = self.download_journal_year(pub_number, each_year)
                    if total_records > 0:
                        self.logger.info(f"期刊 {pub_number} 年份 {each_year} 处理完成，共 {total_records} 条记录")
            
            self.logger.info("所有期刊下载完成")
        except Exception as e:
            self.logger.error(f"处理期刊数据时出现异常: {e}")
            self.logger.error(traceback.format_exc())


def main():
    """主函数"""
    # 配置文件路径
    conference_file = "./publicationInfo/all_conferences.json"
    journal_file = "./publicationInfo/all_journals.json"
    
    # 输出目录
    conference_dir = "./articleInfo/Conferences"
    journal_dir = "./articleInfo/Journals"
    
    # 创建下载器
    downloader = IEEEDownloader(
        conference_dir=conference_dir,
        journal_dir=journal_dir
    )
    
    # 根据命令行参数或配置选择下载内容
    download_conferences = True
    download_journals = True
    
    if download_conferences:
        try:
            downloader.download_all_conferences(conference_file)
        except Exception as e:
            print(f"下载会议数据时出错: {e}")
    
    if download_journals:
        try:
            downloader.download_all_journals(journal_file)
        except Exception as e:
            print(f"下载期刊数据时出错: {e}")


if __name__ == "__main__":
    main() 