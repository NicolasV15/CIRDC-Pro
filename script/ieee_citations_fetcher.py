import requests
import json
import sys
import time

def fetch_ieee_citations(paper_id):
    # 设置请求头
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
        'Referer': f'https://ieeexplore.ieee.org/document/{paper_id}/citations',
    }
    
    # 第一步：获取引用数量
    initial_url = f'https://ieeexplore.ieee.org/rest/document/{paper_id}/citations'
    try:
        response = requests.get(initial_url, headers=headers)
        response.raise_for_status()
        citation_data = response.json()
        citation_count = citation_data.get('ieeeCitationCount', 0)
        
        # 第二步：获取详细引用信息
        citations_url = f'https://ieeexplore.ieee.org/rest/document/{paper_id}/citations?count={citation_count}&start=1&type=ieee'
        response = requests.get(citations_url, headers=headers)
        response.raise_for_status()
        full_data = response.json()
        
        # 提取并重组所需的数据
        filtered_data = {
            "articleNumber": paper_id,
            "citations": []
        }
        
        # 检查是否存在 paperCitations 和 ieee 数组
        if "paperCitations" in full_data and "ieee" in full_data["paperCitations"]:
            for citation in full_data["paperCitations"]["ieee"]:
                if "links" in citation and "title" in citation:
                    article_number = citation["links"].get("articleNumber")
                    if article_number:
                        # 去除title中的转义引号
                        clean_title = citation["title"].replace('\"', '')
                        filtered_data["citations"].append({
                            "articleNumber": article_number,
                            "title": clean_title
                        })
        
        # 保存到JSON文件
        output_filename = f'ieee_citations_{paper_id}.json'
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(filtered_data, f, ensure_ascii=False, indent=2)
            
        print(f'成功获取引用数据！已保存到 {output_filename}')
        print(f'处理的引用数量: {len(filtered_data["citations"])}')
        
    except requests.exceptions.RequestException as e:
        print(f'获取数据时发生错误: {str(e)}')
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f'解析JSON数据时发生错误: {str(e)}')
        sys.exit(1)
    except Exception as e:
        print(f'发生未知错误: {str(e)}')
        sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('使用方法: python ieee_citations_fetcher.py <paper_id>')
        sys.exit(1)
    
    paper_id = sys.argv[1]
    fetch_ieee_citations(paper_id) 
