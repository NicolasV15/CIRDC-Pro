# IEEE Publication Information Crawler

A tool to crawl publication information from IEEE Xplore digital library, including conferences and journals.

## Requirements

- Python 3.6+
- Required packages:
  - requests
  - urllib3
  - argparse

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/ieee-publication-crawler.git
cd ieee-publication-crawler

# Install dependencies
pip install -r requirements.txt
```

## Usage

The crawler can be used to fetch both conference and journal information from IEEE Xplore. You can specify different starting years for each data type.

### Command-line Arguments

```
usage: 1_ieee_publication_info_crawler.py [-h] [-c CONFERENCE] [-j JOURNAL] [year]

IEEE publication information crawler

positional arguments:
  year                  Set the starting year for both conference and journal data collection

optional arguments:
  -h, --help            show this help message and exit
  -c CONFERENCE, --conference CONFERENCE
                        Set the starting year for conference data collection
  -j JOURNAL, --journal JOURNAL
                        Set the starting year for journal data collection
```

### Usage Examples

1. Fetch both conference and journal data using default starting years (1936 for conferences, 1884 for journals):
   ```bash
   python 1_ieee_publication_info_crawler.py
   ```

2. Fetch both conference and journal data starting from a specific year:
   ```bash
   python 1_ieee_publication_info_crawler.py 2000
   ```

3. Fetch only conference data starting from a specific year:
   ```bash
   python 1_ieee_publication_info_crawler.py -c 2000
   ```

4. Fetch only journal data starting from a specific year:
   ```bash
   python 1_ieee_publication_info_crawler.py -j 2010
   ```

5. Fetch conference data starting from one year and journal data starting from another:
   ```bash
   python 1_ieee_publication_info_crawler.py -c 2000 -j 2010
   ```

## Data Storage

- Conference data is stored in `./publicationInfo/json_conference_year/{year}/` directories
- Journal data is stored in `./publicationInfo/json_journal_year/{year}/` directories
- Log files are stored in the `./log/` directory

## Notes

- The crawler requires a stable internet connection
- The process may take a long time, especially for earlier years
- If no records are found for two consecutive years, the crawler will stop
- The crawler respects existing data and will only update if the record count has changed
