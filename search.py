import os
import dotenv as env
import requests
from google import genai
from google.genai import types

env.load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

user_query = input("What do you want to search for?: ")

response = client.models.generate_content(
    model="gemini-2.0-flash",
    config=types.GenerateContentConfig(
        system_instruction="You are an expert in providing news articles. Based on the user query, create a list of top 20 keywords that are highly relevant to the query. Return only the keywords, one per line, without numbering or additional text.",),
    contents=user_query,
)

keywords_text = response.text
keywords_list = [keyword.strip() for keyword in keywords_text.split('\n') if keyword.strip()]

# Define the specific websites to search
TECH_WEBSITES = [
    "tomsguide.com",
    "techwiser.com",
    "techradar.com",
    "tech.hindustantimes.com",
    "gsmarena.com",
    "techcrunch.com",
    "wired.com",
    "thenextweb.com",
    "in.mashable.com",
    "artificialintelligence-news.com"
]

# Configure the client
gnews_api_key = os.getenv("GNEWS_API_KEY")
if not gnews_api_key:
    raise ValueError("GNEWS_API_KEY environment variable not set")

def get_news_for_keyword(keyword, websites=None, max_articles=10, from_specific_sites=True):
    results = []
    
    if from_specific_sites and websites:
        # Search from specific tech websites
        for site in websites:
            if len(results) >= max_articles:
                break
                
            url = f"https://gnews.io/api/v4/search"
            params = {
                "q": keyword,
                "token": gnews_api_key,
                "lang": "en",
                "max": max_articles,
                "site": site
            }
            
            try:
                response = requests.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    for article in data.get("articles", []):
                        if len(results) >= max_articles:
                            break
                        results.append({
                            'title': article.get('title'),
                            'description': article.get('description'),
                            'url': article.get('url'),
                            'publishedAt': article.get('publishedAt'),
                            'source': site,
                            'keyword': keyword,
                            'source_type': 'tech_website'
                        })
            except Exception as e:
                print(f"Error fetching news for keyword '{keyword}' from {site}: {e}")
                continue
    else:
        # Search from the whole web (no site restriction)
        url = f"https://gnews.io/api/v4/search"
        params = {
            "q": keyword,
            "token": gnews_api_key,
            "lang": "en",
            "max": max_articles
        }
        
        try:
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                for article in data.get("articles", []):
                    if len(results) >= max_articles:
                        break
                    results.append({
                        'title': article.get('title'),
                        'description': article.get('description'),
                        'url': article.get('url'),
                        'publishedAt': article.get('publishedAt'),
                        'source': article.get('source', {}).get('name', 'Unknown'),
                        'keyword': keyword,
                        'source_type': 'general_web'
                    })
        except Exception as e:
            print(f"Error fetching news for keyword '{keyword}' from general web: {e}")
    
    return results

# Collect articles from tech websites first (first 100)
specific_articles = []
seen_urls = set()

print("Fetching articles from tech websites...")
for keyword in keywords_list:
    if len(specific_articles) >= 100:
        break
        
    print(f"Fetching tech news for keyword: {keyword}")
    articles = get_news_for_keyword(keyword, TECH_WEBSITES, max_articles=10, from_specific_sites=True)
    
    # Add unique articles only
    for article in articles:
        if article['url'] not in seen_urls and len(specific_articles) < 100:
            seen_urls.add(article['url'])
            specific_articles.append(article)
            
    print(f"Found {len(articles)} tech articles for '{keyword}', Total specific articles: {len(specific_articles)}")

# Collect articles from general web (next 100)
general_articles = []

print("\nFetching articles from general web...")
for keyword in keywords_list:
    if len(general_articles) >= 100:
        break
        
    print(f"Fetching general news for keyword: {keyword}")
    articles = get_news_for_keyword(keyword, None, max_articles=10, from_specific_sites=False)
    
    # Add unique articles only
    for article in articles:
        if article['url'] not in seen_urls and len(general_articles) < 100:
            seen_urls.add(article['url'])
            general_articles.append(article)
            
    print(f"Found {len(articles)} general articles for '{keyword}', Total general articles: {len(general_articles)}")

# Combine all articles
final_articles = specific_articles + general_articles

# Save to file
with open("news_results.txt", "w", encoding="utf-8") as f:
    f.write(f"Search Query: {user_query}\n")
    f.write(f"Total Articles Found: {len(final_articles)}\n")
    f.write(f"Tech Website Articles: {len(specific_articles)}\n")
    f.write(f"General Web Articles: {len(general_articles)}\n")
    f.write("="*50 + "\n\n")
    
    for idx, article in enumerate(final_articles, 1):
        f.write(f"Article {idx}\n")
        f.write(f"Source Type: {article['source_type']}\n")
        f.write(f"Keyword: {article['keyword']}\n")
        f.write(f"Title: {article['title']}\n")
        f.write(f"Description: {article['description']}\n")
        f.write(f"URL: {article['url']}\n")
        f.write(f"Published At: {article['publishedAt']}\n")
        f.write(f"Source: {article['source']}\n")
        f.write("-"*40 + "\n")

print(f"\nResults saved to news_results.txt")
print(f"Tech website articles: {len(specific_articles)}")
print(f"General web articles: {len(general_articles)}")
print(f"Total unique articles: {len(final_articles)}")