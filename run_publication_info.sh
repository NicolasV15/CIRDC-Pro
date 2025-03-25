#!/bin/bash

# 设置颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 设置日期格式
DATE=$(date +"%Y-%m-%d")
TIME=$(date +"%H:%M:%S")
DATETIME="$DATE $TIME"

echo -e "${GREEN}[开始] $DATETIME 开始IEEE Publication信息更新流程${NC}"

# 创建必要的目录
echo -e "${BLUE}[提示] 检查并创建必要目录${NC}"
mkdir -p ./publicationInfo
mkdir -p ./publicationInfo/Journals
mkdir -p ./publicationInfo/Conferences
mkdir -p ./log/1_publicationInfo

# 确定起始年份(可以根据需要修改)
# 如果想指定特定年份，可以删除下面两行，直接设置JOURNAL_START_YEAR和CONFERENCE_START_YEAR为固定值
JOURNAL_START_YEAR=1884 # 期刊起始年份
CONFERENCE_START_YEAR=1936 # 会议起始年份

# 运行爬虫脚本
echo -e "${BLUE}[步骤1] 开始运行Publication爬虫...${NC}"
echo -e "${YELLOW}[信息] 期刊起始年份: $JOURNAL_START_YEAR${NC}"
echo -e "${YELLOW}[信息] 会议起始年份: $CONFERENCE_START_YEAR${NC}"

python3 1_ieee_publication_info_crawler.py -j $JOURNAL_START_YEAR -c $CONFERENCE_START_YEAR

if [ $? -ne 0 ]; then
    echo -e "${RED}[错误] Publication爬虫运行失败!${NC}"
    exit 1
else
    echo -e "${GREEN}[完成] Publication爬虫运行成功!${NC}"
fi

# 运行整合脚本
echo -e "${BLUE}[步骤2] 开始运行Publication整合脚本...${NC}"
python3 2_ieee_publication_info_integrater.py

if [ $? -ne 0 ]; then
    echo -e "${RED}[错误] Publication整合脚本运行失败!${NC}"
    exit 1
else
    echo -e "${GREEN}[完成] Publication整合脚本运行成功!${NC}"
fi

# Git操作
echo -e "${BLUE}[步骤3] 开始进行Git操作...${NC}"

# 检查articleInfo和publicationInfo目录下是否有修改
ARTICLE_STATUS=$(git status --porcelain -- ./articleInfo)
PUBLICATION_STATUS=$(git status --porcelain -- ./publicationInfo)

if [ -z "$ARTICLE_STATUS" ] && [ -z "$PUBLICATION_STATUS" ]; then
    echo -e "${YELLOW}[信息] 没有发现需要提交的更改${NC}"
else
    # 构建简化的commit信息，只包含更新时间
    COMMIT_MSG="更新publication数据 ($DATE)"
    
    # 添加并提交更改
    echo -e "${YELLOW}[Git] 提交更改: $COMMIT_MSG${NC}"
    
    # 分别添加两个目录下的更改
    if [ ! -z "$ARTICLE_STATUS" ]; then
        git add ./articleInfo/
        echo -e "${YELLOW}[Git] 添加articleInfo目录下的更改${NC}"
    fi
    
    if [ ! -z "$PUBLICATION_STATUS" ]; then
        git add ./publicationInfo/
        echo -e "${YELLOW}[Git] 添加publicationInfo目录下的更改${NC}"
    fi
    
    git commit -m "$COMMIT_MSG"
    
    # 推送到远程仓库
    echo -e "${YELLOW}[Git] 推送到origin main分支${NC}"
    git push origin main
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}[错误] Git推送失败!${NC}"
        exit 1
    else
        echo -e "${GREEN}[完成] Git推送成功!${NC}"
    fi
fi

# 完成时间
END_TIME=$(date +"%Y-%m-%d %H:%M:%S")
echo -e "${GREEN}[结束] $END_TIME IEEE Publication信息更新流程完成${NC}"

exit 0 