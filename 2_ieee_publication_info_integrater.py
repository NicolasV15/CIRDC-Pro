import json
import os


def parse_years(years):
    if ' - ' in years:
        start_year, end_year = years.split(' - ')
        return start_year.strip(), end_year.strip()
    return years.strip(), 'Present'


JOURNAL_FLAG = 1
CONFERENCE_FLAG = 1

if JOURNAL_FLAG:
    #### Process Journals ####
    all_journals = {}
    for year in range (1884, 2026):
        print (year)
        for root, dirs, names in os.walk(os.path.join('./publicationInfo/json_journal_year', '{}'.format(year))):
            for name in names:
                json_path = os.path.join(root, name)
                with open(json_path, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    for record in data.get('records', []):
                        title = record.get('title')
                        all_years = record.get('allYears', '')
                        publication_number = record.get('publicationNumber')
                        
                        if publication_number and publication_number not in all_journals:
                            start_year, end_year = parse_years(all_years)
                            
                            all_journals[publication_number] = {
                                'title': title,
                                'start_year': start_year,
                                'end_year': end_year, 
                                'publication_number': publication_number
                            }

                        # Process title history
                        for history in record.get('titleHistory', []):
                            history_title = history.get('displayTitle')
                            start_year = history.get('startYear')
                            end_year = history.get('endYear')
                            history_publication_number = history.get('publicationNumber')
                            if history_publication_number and history_publication_number not in all_journals:
                                all_journals[history_publication_number] = {
                                    'title': history_title,
                                    'start_year': start_year,
                                    'end_year': end_year,
                                    'publication_number': history_publication_number
                                }


    with open ("./publicationInfo/all_journals.json", 'w') as f:
        json.dump(all_journals, f, indent=4)



if CONFERENCE_FLAG == 1:

    all_conferences = {}
    #### Process Conference ####
    for year in range (1884, 2026):
        for root, dirs, names in os.walk(os.path.join('./publicationInfo/json_conference_year', '{}'.format(year))):
            for name in names:
                json_path = os.path.join(root, name)
                with open(json_path, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    for record in data.get('records', []):
                        # 获取父级出版号和标题
                        parent_pub_number = record.get("parentPublicationNumber")
                        parent_title = record.get("parentTitle")
                        
                        if not parent_pub_number:
                            continue
                            
                        # 处理parentTitle不存在的情况
                        if not parent_title:
                            # 从displayTitle获取标题
                            parent_title = record.get("displayTitle")
                            
                            if not parent_title:
                                continue
                                
                            # 初始化会议数据结构
                            if parent_pub_number not in all_conferences:
                                all_conferences[parent_pub_number] = {
                                    "parentPublicationNumber": parent_pub_number,
                                    "parentTitle": parent_title,
                                    "titleHistory": []
                                }
                                
                            # 直接从记录中获取displayTitle和publicationNumber，不获取startYear
                            display_title = record.get("displayTitle")
                            pub_number = record.get("publicationNumber")
                            
                            if not display_title or not pub_number:
                                continue
                                
                            # 创建新的历史记录，year字段留空
                            history_entry = {
                                "displayTitle": display_title,
                                "publicationNumber": pub_number,
                                "year": ""  # year内容留空
                            }
                            
                            # 检查是否存在相同publicationNumber的记录
                            existing_index = -1
                            for idx, existing in enumerate(all_conferences[parent_pub_number]["titleHistory"]):
                                if existing["publicationNumber"] == pub_number:
                                    existing_index = idx
                                    break
                            
                            # 如果存在则替换，不存在则添加
                            if existing_index >= 0:
                                all_conferences[parent_pub_number]["titleHistory"][existing_index] = history_entry
                            else:
                                all_conferences[parent_pub_number]["titleHistory"].append(history_entry)
                        else:
                            # 正常处理包含parentTitle的记录
                            # 初始化会议数据结构
                            if parent_pub_number not in all_conferences:
                                all_conferences[parent_pub_number] = {
                                    "parentPublicationNumber": parent_pub_number,
                                    "parentTitle": parent_title,
                                    "titleHistory": []
                                }
                            
                            # 处理titleHistory
                            if "titleHistory" in record:
                                for each_history in record["titleHistory"]:
                                    # 提取所需字段
                                    display_title = each_history.get("displayTitle")
                                    pub_number = each_history.get("publicationNumber")
                                    start_year = each_history.get("startYear")
                                    
                                    if not display_title or not pub_number:
                                        continue
                                        
                                    # 创建新的历史记录
                                    history_entry = {
                                        "displayTitle": display_title,
                                        "publicationNumber": pub_number,
                                        "year": start_year or ""  # 将startYear重命名为year，如果不存在则为空字符串
                                    }
                                    
                                    # 检查是否存在相同publicationNumber的记录
                                    existing_index = -1
                                    for idx, existing in enumerate(all_conferences[parent_pub_number]["titleHistory"]):
                                        if existing["publicationNumber"] == pub_number:
                                            existing_index = idx
                                            break
                                    
                                    # 如果存在则替换，不存在则添加
                                    if existing_index >= 0:
                                        all_conferences[parent_pub_number]["titleHistory"][existing_index] = history_entry
                                    else:
                                        all_conferences[parent_pub_number]["titleHistory"].append(history_entry)


    with open ("./publicationInfo/all_conferences.json", 'w') as f:
        json.dump(all_conferences, f, indent=4)