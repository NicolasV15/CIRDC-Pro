import requests
import json
import sys
import time
from typing import Dict, List
import os

class CitationTreeBuilder:
    def __init__(self, max_depth: int = 3, delay: float = 1.0):
        self.max_depth = max_depth  # 最大搜索深度
        self.delay = delay  # 请求间隔时间
        self.processed_articles = set()  # 用于存储已处理的文章ID，避免重复处理
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive'
        }

    def clean_title(self, title: str) -> str:
        """清理标题中的转义引号"""
        if title.startswith('\\"'):
            title = title[2:]
        if title.endswith('\\"'):
            title = title[:-2]
        return title

    def get_citations(self, paper_id: str) -> Dict:
        """获取单篇文章的引用信息"""
        self.headers['Referer'] = f'https://ieeexplore.ieee.org/document/{paper_id}/citations'
        
        # 获取引用数量
        initial_url = f'https://ieeexplore.ieee.org/rest/document/{paper_id}/citations'
        try:
            response = requests.get(initial_url, headers=self.headers)
            response.raise_for_status()
            citation_data = response.json()
            citation_count = citation_data.get('ieeeCitationCount', 0)

            if citation_count == 0:
                return {"articleNumber": paper_id, "citations": []}

            # 获取详细引用信息
            citations_url = f'https://ieeexplore.ieee.org/rest/document/{paper_id}/citations?count={citation_count}&start=1&type=ieee'
            response = requests.get(citations_url, headers=self.headers)
            response.raise_for_status()
            full_data = response.json()

            citations = []
            if "paperCitations" in full_data and "ieee" in full_data["paperCitations"]:
                for citation in full_data["paperCitations"]["ieee"]:
                    if "links" in citation and "title" in citation:
                        article_number = citation["links"].get("articleNumber")
                        if article_number:
                            # 使用clean_title方法处理标题
                            clean_title = self.clean_title(citation["title"])
                            citations.append({
                                "articleNumber": article_number,
                                "title": clean_title
                            })

            return {
                "articleNumber": paper_id,
                "citations": citations
            }

        except requests.exceptions.RequestException as e:
            print(f'获取文章 {paper_id} 的引用数据时发生错误: {str(e)}')
            return {"articleNumber": paper_id, "citations": []}
        except Exception as e:
            print(f'处理文章 {paper_id} 时发生未知错误: {str(e)}')
            return {"articleNumber": paper_id, "citations": []}

    def build_citation_tree(self, paper_id: str, current_depth: int = 0) -> Dict:
        """递归构建引用树"""
        # 检查是否已处理过该文章
        if paper_id in self.processed_articles:
            return {"articleNumber": paper_id, "citations": [], "note": "already_processed"}
        
        # 检查是否超过最大深度
        if current_depth >= self.max_depth:
            return {"articleNumber": paper_id, "citations": [], "note": "max_depth_reached"}

        # 将当前文章标记为已处理
        self.processed_articles.add(paper_id)
        
        # 获取当前文章的引用信息
        print(f'正在处理深度 {current_depth} 的文章: {paper_id}')
        citation_data = self.get_citations(paper_id)
        
        # 为每个引用递归获取其引用信息
        citations_with_tree = []
        for citation in citation_data["citations"]:
            time.sleep(self.delay)  # 添加延时，避免请求过于频繁
            child_tree = self.build_citation_tree(citation["articleNumber"], current_depth + 1)
            citations_with_tree.append({
                "articleNumber": citation["articleNumber"],
                "title": citation["title"],
                "citations": child_tree["citations"]
            })

        return {
            "articleNumber": paper_id,
            "citations": citations_with_tree
        }

def main():
    if len(sys.argv) != 2:
        print('使用方法: python ieee_citations_tree.py <paper_id>')
        sys.exit(1)

    paper_id = sys.argv[1]
    
    # 创建输出目录
    output_dir = "citation_trees"
    os.makedirs(output_dir, exist_ok=True)
    
    # 构建引用树
    tree_builder = CitationTreeBuilder(max_depth=3, delay=1.0)  # 设置最大深度为3，请求间隔为1秒
    citation_tree = tree_builder.build_citation_tree(paper_id)
    
    # 保存结果
    output_file = os.path.join(output_dir, f'citation_tree_{paper_id}.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(citation_tree, f, ensure_ascii=False, indent=2)
    
    print(f'引用树已保存到: {output_file}')
    print(f'处理的文章总数: {len(tree_builder.processed_articles)}')

if __name__ == '__main__':
    main() 