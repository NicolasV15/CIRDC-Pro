# 综合IEEE研究数据收集（CIRDC）

[English Version](README.md)

本仓库提供了截至2024年7月通过IEEE Xplore提供的所有文章的详细信息，为研究人员提供便捷的访问和使用方式。该仓库还包含用于数据收集的必要代码，便于进一步更新数据库。有关数据集的深入解释，请参阅以下出版物：

[Y. Zhang, Y. Li, S. Makonin and R. Kumar, "Descriptor: Comprehensive IEEE Research Data Collections (CIRDC)," IEEE Data Descriptions, vol. 1, pp. 80-86, 2024](https://ieeexplore.ieee.org/document/10716731)

## 数据库结构

数据库分为两个主要目录：`articleInfo`和`publicationInfo`。

- **articleInfo**：此目录分为两个主要子目录：`Conferences`和`Journals`。
  - **Conferences**：此子目录包含以`parentPublicationNumber`命名的文件夹，每个文件夹代表一个特定的会议。每个文件夹内有多个以`year.json`命名的JSON文件，其中包含该会议在指定年份出版的所有论文的元数据。
  - **Journals**：此子目录包含以`publicationNumber`命名的文件夹，每个文件夹代表一个特定的期刊。与Conferences结构类似，每个文件夹包含以`year.json`命名的JSON文件，其中包含该期刊在指定年份出版的所有论文的元数据。

  ```
  articleInfo/
  ├── Conferences/
  │   ├── 200/
  │   │   ├── 1964.json
  │   │   ├── 1965.json
  │   │   ├── ...
  │   ├── 201/
  │   │   ├── 1970.json
  │   │   ├── 1971.json
  │   │   ├── ...
  │   └── ...
  ├── Journals/
  │   ├── 100/
  │   │   ├── 1980.json
  │   │   ├── 1981.json
  │   │   ├── ...
  │   ├── 101/
  │   │   ├── 1990.json
  │   │   ├── 1991.json
  │   │   ├── ...
  │   └── ...
  ```

- **publicationInfo**：此目录提供关于出版物本身的额外元数据，如名称、类型和其他相关详细信息。该目录中的每个文件都以`publication number.json`命名，包含对应期刊或会议的信息。

这种结构允许高效访问和管理文章特定数据和出版物级别的元数据。

## 数据文件结构

每个JSON文件包含一个列表，列表中的每个实体对应一篇论文的元数据。论文元数据的结构如下：

| 名称               | 描述                                                                    | 类型   |
|-------------------|------------------------------------------------------------------------|--------|
| publicationNumber  | 期刊/会议的标识符                                                        | 字符串 |
| doi               | 论文的数字对象标识符                                                      | 字符串 |
| publicationYear   | 论文发表年份                                                             | 字符串 |
| publicationDate   | 完整的发表日期                                                           | 字符串 |
| articleNumber     | 分配给论文的唯一编号                                                      | 字符串 |
| articleTitle      | 论文标题                                                                | 字符串 |
| volume            | 卷号                                                                   | 字符串 |
| issue             | 期号                                                                   | 字符串 |
| startPage         | 起始页码                                                                | 字符串 |
| endPage           | 结束页码                                                                | 字符串 |
| publisher         | 出版商名称                                                              | 字符串 |
| articleContentType | 论文类型（期刊、会议、杂志或提前获取文章）                                  | 字符串 |
| publicationTitle  | 期刊/会议名称                                                            | 字符串 |
| authors           | 作者列表                                                                | 数组   |
| abstract          | 论文摘要                                                                | 字符串 |
| keywords          | 论文关键词，按类型组织（例如IEEE关键词、作者关键词）                          | 对象   |

`authors`字段中的每个作者条目包含以下数据：

| 名称            | 描述                                  | 类型   |
|----------------|--------------------------------------|--------|
| id             | 作者在IEEE系统中的ID号                  | 数字   |
| preferredName  | 作者全名                              | 字符串 |
| firstName      | 作者名                                | 字符串 |
| lastName       | 作者姓                                | 字符串 |

`keywords`字段是一个对象，以关键词类型为键，关键词数组为值。例如：

```json
"keywords": {
  "IEEE Keywords": ["keyword1", "keyword2", "keyword3"],
  "Author Keywords": ["keyword4", "keyword5", "keyword6"]
}
```

## 数据收集脚本

CIRDC的收集脚本位于`script`文件夹中。由于IEEE Xplore在单次查询中返回的最大条目数限制为10,000条，收集过程涉及多个阶段。数据收集工作流程旨在高效地收集、处理和组织IEEE出版物和文章信息。

按照以下步骤收集和更新数据：

1. **更新出版物信息**：
   运行`./Update_publicationInfo.sh`自动执行出版物信息收集过程：
   - 创建必要的目录结构
   - 运行`1_ieee_publication_info_crawler.py`收集出版物元数据
   - 执行`2_ieee_publication_info_integrater.py`整合和组织数据
   - 自动提交并推送更改到仓库

2. **收集文章信息**：
   运行`python3 script/3_ieee_article_info_crawler.py`爬取基于步骤1中收集的出版物数据的详细文章信息。

3. **下载PDF文件**（可选）：
   运行`python3 script/batch_download_from_json.py`下载基于收集的文章信息的PDF文件。

4. **检索摘要和关键词**：
   运行`python3 script/getAbstract\&Keyword.py`收集文章的摘要和关键词并更新JSON文件。

5. **引用分析**（可选）：
   - `ieee_citations_fetcher.py`：获取特定文章的引用信息
   - `ieee_citations_tree.py`：构建引用树以可视化引用关系
   - `ieee_reference_scraper.py`：从IEEE文章中提取参考信息

数据收集过程设计为增量式，因此您可以定期运行这些脚本来用新的出版物和文章更新数据库。

## 依赖项

脚本需要Python 3.6或更高版本以及以下库：

- `requests`：用于API交互的HTTP请求
- `beautifulsoup4`：用于摘要和关键词提取的HTML解析
- `lxml`：与BeautifulSoup一起使用的XML/HTML解析器
- `PyPDF2`：用于下载论文的PDF处理
- `pandas`：数据操作和分析
- `urllib3`：Python的HTTP客户端
- `pathlib`：面向对象的文件系统路径

您可以使用requirements.txt文件安装所有必需的依赖项：

```bash
pip install -r requirements.txt
```

## 许可

本仓库根据[知识共享署名4.0国际许可协议](LICENSE)的条款授权。 