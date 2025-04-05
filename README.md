# Comprehensive IEEE Research Data Collections (CIRDC)

[中文版](README_CN.md)

This repository provides detailed information on all articles available through IEEE Xplore up to April 2025, organized for easy access and use by researchers. The repository also includes the necessary code for data collecting, facilitating further updates to the database. For an in-depth explanation of the dataset, please refer to the following publication: 

[Y. Zhang, Y. Li, S. Makonin and R. Kumar, "Descriptor: Comprehensive IEEE Research Data Collections (CIRDC)," IEEE Data Descriptions, vol. 1, pp. 80-86, 2024](https://ieeexplore.ieee.org/document/10716731)

## Database Structure

The database is organized into two main directories: `articleInfo` and `publicationInfo`.

- **articleInfo**: This directory is divided into two main subdirectories: `Conferences` and `Journals`. 
  - **Conferences**: This subdirectory contains folders named by `parentPublicationNumber`, each representing a specific conference. Within each folder, there are multiple JSON files named by `year.json`, containing metadata for all papers published in that conference for the specified year.
  - **Journals**: This subdirectory contains folders named by `publicationNumber`, each representing a specific journal. Similar to the Conferences structure, each folder contains JSON files named by `year.json`, with metadata for all papers published in that journal for the specified year.

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

- **publicationInfo**: This directory provides additional metadata about the publications themselves, such as the name, type, and other relevant details. Each file in this directory is named by `publication number.json`, containing information about the corresponding journal or conference.

This structure allows for efficient access and management of both article-specific data and publication-level metadata.

## Data File Structure

Each JSON file contains a list, and each entity in the list corresponds to the metadata of a paper. The paper metadata is structured as follows:

| Name                | Description                                                                 | Type   |
|---------------------|-----------------------------------------------------------------------------|--------|
| publicationNumber   | Identifier for the journal/conference                                        | String |
| doi                 | Digital Object Identifier of the paper                                       | String |
| publicationYear     | Year the paper was published                                                 | String |
| publicationDate     | Full date of publication                                                     | String |
| articleNumber       | A unique number assigned to the paper                                        | String |
| articleTitle        | Title of the paper                                                           | String |
| volume              | Volume number                                                               | String |
| issue               | Issue number                                                                | String |
| startPage           | Starting page number                                                        | String |
| endPage             | Ending page number                                                          | String |
| publisher           | Name of the publisher                                                       | String |
| articleContentType  | Type of the paper (journal, conference, magazine, or early access article)    | String |
| publicationTitle    | Name of journal/conference                                                   | String |
| authors             | A list of authors                                                           | Array  |
| abstract            | The abstract of the paper                                                   | String |
| keywords            | The keywords of the paper, organized by type (e.g., IEEE Keywords, Author Keywords) | Object |

Each author entry in the `authors` field contains the following data:

| Name            | Description                                 | Type   |
|-----------------|---------------------------------------------|--------|
| id              | ID number of the author in IEEE system      | Number |
| preferredName   | Full name of the author                     | String |
| firstName       | First name of the author                    | String |
| lastName        | Last name of the author                     | String |

The `keywords` field is an object with keyword types as keys and arrays of keywords as values. For example:

```json
"keywords": {
  "IEEE Keywords": ["keyword1", "keyword2", "keyword3"],
  "Author Keywords": ["keyword4", "keyword5", "keyword6"]
}
```

## Scripts for Data Collection

The scripts for collecting CIRDC are in the `script` folder. As the maximum number of entries returned in a single query is restricted to 10,000 in IEEE Xplore, the collection involves a multi-stage process. The data collection workflow is designed to efficiently gather, process, and organize IEEE publication and article information.

Follow the steps below to collect and update the data:

1. **Update Publication Information**: 
   Run `./Update_publicationInfo.sh` to automatically execute the publication information collection process:
   - Creates necessary directory structure
   - Runs `1_ieee_publication_info_crawler.py` to collect publication metadata
   - Executes `2_ieee_publication_info_integrater.py` to integrate and organize the data
   - Automatically commits and pushes changes to the repository

2. **Collect Article Information**:
   Run `python3 script/3_ieee_article_info_crawler.py` to crawl detailed article information based on the publication data collected in step 1.

3. **Download PDF Files** (Optional):
   Run `python3 script/batch_download_from_json.py` to download PDF files of articles based on the collected article information.

4. **Retrieve Abstracts and Keywords**:
   Run `python3 script/getAbstract\&Keyword.py` to collect abstracts and keywords for articles and update the JSON files.

5. **Citation Analysis** (Optional):
   - `ieee_citations_fetcher.py`: Fetches citation information for specific articles
   - `ieee_citations_tree.py`: Builds citation trees to visualize citation relationships
   - `ieee_reference_scraper.py`: Extracts reference information from IEEE articles

The data collection process is designed to be incremental, so you can run these scripts periodically to update the database with new publications and articles.

## Dependencies

The scripts require Python 3.6 or later and the following libraries:

- `requests`: HTTP requests for API interactions
- `beautifulsoup4`: HTML parsing for abstract and keyword extraction
- `lxml`: XML/HTML parser used with BeautifulSoup
- `PyPDF2`: PDF processing for downloaded papers
- `pandas`: Data manipulation and analysis
- `urllib3`: HTTP client for Python
- `pathlib`: Object-oriented filesystem paths

You can install all required dependencies using the requirements.txt file:

```bash
pip install -r requirements.txt
```

## License

This repository is licensed under the terms of the [Creative Commons Attribution 4.0 International License](LICENSE).
