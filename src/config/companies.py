"""
Company target configurations for ATS boards (Greenhouse, Lever, Ashby, Workable)
Focusing on Top Global Capability Centers (GCCs), Tech Giants, and Unicorns with India / Hyderabad offices.
"""

# Companies using Greenhouse ATS:
# API endpoint: https://boards-api.greenhouse.io/v1/boards/{token}/jobs
GREENHOUSE_COMPANIES = [
    # Top GCCs / MNCs / Tech leaders
    {"name": "Stripe", "token": "stripe"},
    {"name": "Coinbase", "token": "coinbase"},
    {"name": "Airbnb", "token": "airbnb"},
    {"name": "Pinterest", "token": "pinterest"},
    {"name": "GitLab", "token": "gitlab"},
    {"name": "Twilio", "token": "twilio"},
    {"name": "Cloudflare", "token": "cloudflare"},
    {"name": "Databricks", "token": "databricks"},
    {"name": "Figma", "token": "figma"},
    {"name": "Brex", "token": "brex"},
    {"name": "Instacart", "token": "instacart"},
    {"name": "Rubrik", "token": "rubrik"},
    {"name": "Okta", "token": "okta"},
    {"name": "MongoDB", "token": "mongodb"},
    {"name": "Samsara", "token": "samsara"},
    {"name": "Branch", "token": "branch"},
    {"name": "Qualtrics", "token": "qualtrics"},
    {"name": "Snowflake", "token": "snowflake"},
    {"name": "Confluent", "token": "confluent"},
    {"name": "Elastic", "token": "elastic"},
    {"name": "Toast", "token": "toast"},
    {"name": "ServiceTitan", "token": "servicetitan"},
]

# Companies using Lever ATS:
# API endpoint: https://api.lever.co/v0/postings/{token}?mode=json
LEVER_COMPANIES = [
    {"name": "Palantir", "token": "palantir"},
    {"name": "FullStory", "token": "fullstory"},
    {"name": "Affirm", "token": "affirm"},
    {"name": "Coursera", "token": "coursera"},
]

# Companies using Ashby ATS:
# API endpoint: https://api.ashbyhq.com/posting-api/job-board/{token}
ASHBY_COMPANIES = [
    {"name": "Ramp", "token": "ramp"},
    {"name": "Notion", "token": "notion"},
    {"name": "OpenAI", "token": "openai"},
    {"name": "Vercel", "token": "vercel"},
    {"name": "Perplexity", "token": "perplexity"},
    {"name": "Linear", "token": "linear"},
    {"name": "Deel", "token": "deel"},
    {"name": "Synthesia", "token": "synthesia"},
    {"name": "Luma", "token": "luma"},
    {"name": "Cursor", "token": "anysphere"},
]

# Workable ATS boards
# API endpoint: https://apply.workable.com/api/v3/accounts/{token}/jobs
WORKABLE_COMPANIES = [
    {"name": "InVideo", "token": "invideo"},
    {"name": "BrowserStack (Workable)", "token": "browserstack"},
]

# Keywords for location filtering
HYDERABAD_KEYWORDS = [
    "hyderabad", "telangana", "hitec city", "gachibowli", "madhapur", "kondapur", "cyberabad"
]

INDIA_KEYWORDS = [
    "india", "bengaluru", "bangalore", "hyderabad", "pune", "mumbai", "gurgaon", 
    "gurugram", "noida", "chennai", "delhi", "remote - india", "india - remote"
]

