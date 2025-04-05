#!/bin/bash

# Set color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Set date format
DATE=$(date +"%Y-%m-%d")
TIME=$(date +"%H:%M:%S")
DATETIME="$DATE $TIME"

echo -e "${GREEN}[START] $DATETIME Starting IEEE Publication information update process${NC}"

# Create necessary directories
echo -e "${BLUE}[INFO] Checking and creating necessary directories${NC}"
mkdir -p ./publicationInfo
mkdir -p ./publicationInfo/Journals
mkdir -p ./publicationInfo/Conferences
mkdir -p ./log/1_publicationInfo

# Determine start year (can be modified as needed)
# If you want to specify a specific year, you can delete the two lines below and set JOURNAL_START_YEAR and CONFERENCE_START_YEAR to fixed values
JOURNAL_START_YEAR=2000 # Journal start year
CONFERENCE_START_YEAR=2000 # Conference start year

# Run crawler script
echo -e "${BLUE}[STEP 1] Starting Publication crawler...${NC}"
echo -e "${YELLOW}[INFO] Journal start year: $JOURNAL_START_YEAR${NC}"
echo -e "${YELLOW}[INFO] Conference start year: $CONFERENCE_START_YEAR${NC}"

python3 script/1_ieee_publication_info_crawler.py -j $JOURNAL_START_YEAR -c $CONFERENCE_START_YEAR

if [ $? -ne 0 ]; then
    echo -e "${RED}[ERROR] Publication crawler failed!${NC}"
    exit 1
else
    echo -e "${GREEN}[DONE] Publication crawler completed successfully!${NC}"
fi

# Run integration script
echo -e "${BLUE}[STEP 2] Starting Publication integration script...${NC}"
python3 script/2_ieee_publication_info_integrater.py

if [ $? -ne 0 ]; then
    echo -e "${RED}[ERROR] Publication integration script failed!${NC}"
    exit 1
else
    echo -e "${GREEN}[DONE] Publication integration script completed successfully!${NC}"
fi

# Git operations
echo -e "${BLUE}[STEP 3] Starting Git operations...${NC}"

# Check if there are changes in the articleInfo and publicationInfo directories
ARTICLE_STATUS=$(git status --porcelain -- ./articleInfo)
PUBLICATION_STATUS=$(git status --porcelain -- ./publicationInfo)

if [ -z "$ARTICLE_STATUS" ] && [ -z "$PUBLICATION_STATUS" ]; then
    echo -e "${YELLOW}[INFO] No changes found to commit${NC}"
else
    # Build simplified commit message with just the update time
    COMMIT_MSG="Update publication data ($DATE)"

    # Add and commit changes
    echo -e "${YELLOW}[Git] Committing changes: $COMMIT_MSG${NC}"
    
    # Add changes from both directories separately
    if [ ! -z "$ARTICLE_STATUS" ]; then
        git add ./articleInfo/
        echo -e "${YELLOW}[Git] Added changes from articleInfo directory${NC}"
    fi
    
    if [ ! -z "$PUBLICATION_STATUS" ]; then
        git add ./publicationInfo/
        echo -e "${YELLOW}[Git] Added changes from publicationInfo directory${NC}"
    fi
    
    git commit -m "$COMMIT_MSG"
    
    # Push to remote repository
    echo -e "${YELLOW}[Git] Pushing to origin main branch${NC}"
    git push origin main
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}[ERROR] Git push failed!${NC}"
        exit 1
    else
        echo -e "${GREEN}[DONE] Git push successful!${NC}"
    fi
fi

# Completion time
END_TIME=$(date +"%Y-%m-%d %H:%M:%S")
echo -e "${GREEN}[END] $END_TIME IEEE Publication information update process completed${NC}"

exit 0 
