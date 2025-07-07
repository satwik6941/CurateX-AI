import os
import dotenv as env
import requests
from google import genai
from google.genai import types
from newspaper import Article

env.load_dotenv()

client = None

# Global variable to store user query (set by main.py)
user_query = ""

def get_gemini_client():
    """Get or initialize the Gemini client"""
    global client
    if client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        client = genai.Client(api_key=api_key)
    return client

def set_user_query(query):
    """Set the user query for search"""
    global user_query
    user_query = query

def extract_article_summary(url):
    """
    Extract article summary using newspaper3k
    """
    try:
        article = Article(url)
        article.download()
        article.parse()
        article.nlp()
        return article.summary
    except Exception as e:
        print(f"Error extracting summary from {url}: {e}")
        return "Summary extraction failed"

def get_news_for_keyword(keyword, websites=None, max_articles=10, from_specific_sites=True):
    """Get news articles for a specific keyword"""
    results = []
    gnews_api_key = os.getenv("GNEWS_API_KEY")
    
    if not gnews_api_key:
        raise ValueError("GNEWS_API_KEY environment variable not set")
    
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
                        
                        # Extract summary for each article
                        print(f"Extracting summary for: {article.get('title', 'Unknown Title')}")
                        summary = extract_article_summary(article.get('url'))
                        
                        results.append({
                            'title': article.get('title'),
                            'description': article.get('description'),
                            'url': article.get('url'),
                            'publishedAt': article.get('publishedAt'),
                            'source': site,
                            'keyword': keyword,
                            'source_type': 'tech_website',
                            'extracted_summary': summary
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
                    
                    # Extract summary for each article
                    print(f"Extracting summary for: {article.get('title', 'Unknown Title')}")
                    summary = extract_article_summary(article.get('url'))
                    
                    results.append({
                        'title': article.get('title'),
                        'description': article.get('description'),
                        'url': article.get('url'),
                        'publishedAt': article.get('publishedAt'),
                        'source': article.get('source', {}).get('name', 'Unknown'),
                        'keyword': keyword,
                        'source_type': 'general_web',
                        'extracted_summary': summary
                    })
        except Exception as e:
            print(f"Error fetching news for keyword '{keyword}' from general web: {e}")
    
    return results

def run_search_process():
    """Run the complete search process"""
    global user_query
    
    print(f"🔍 Starting search for: {user_query}")
    
    # Generate keywords using Gemini
    client = get_gemini_client()
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        config=types.GenerateContentConfig(
            system_instruction="You are an expert in providing news articles. Based on the user query, create a list of top 20 keywords that are highly relevant to the query." \
            "The keywords can contain more than one word also to keep the users context. Return only the keywords, one per line, without numbering or additional text.",),
        contents=user_query,
    )

    keywords_text = response.text
    keywords_list = [keyword.strip() for keyword in keywords_text.split('\n') if keyword.strip()]

    # Collect 200 unique articles from general web
    all_articles = []
    seen_urls = set()

    print("Fetching articles from the web...")
    for keyword in keywords_list:
        if len(all_articles) >= 200:
            break
            
        print(f"Fetching news for keyword: {keyword}")
        articles = get_news_for_keyword(keyword, None, max_articles=10, from_specific_sites=False)
        
        # Add unique articles only
        for article in articles:
            if article['url'] not in seen_urls and len(all_articles) < 200:
                seen_urls.add(article['url'])
                all_articles.append(article)
                
        print(f"Found {len(articles)} articles for '{keyword}', Total unique articles: {len(all_articles)}")

    # Ensure data folder exists
    os.makedirs("data", exist_ok=True)

    # Save to file in data folder
    with open("data/news_results.txt", "w", encoding="utf-8") as f:
        f.write(f"Search Query: {user_query}\n")
        f.write(f"Total Articles Found: {len(all_articles)}\n")
        f.write("="*50 + "\n\n")
        
        for idx, article in enumerate(all_articles, 1):
            f.write(f"Article {idx}\n")
            f.write(f"Keyword: {article['keyword']}\n")
            f.write(f"Title: {article['title']}\n")
            f.write(f"Description: {article['description']}\n")
            f.write(f"URL: {article['url']}\n")
            f.write(f"Summary:\n{article['extracted_summary']}\n\n")
            f.write(f"Published At: {article['publishedAt']}\n")
            f.write(f"Source: {article['source']}\n")
            f.write("-"*40 + "\n")

    print(f"\n✅ Results saved to data/news_results.txt")
    print(f"Total unique articles: {len(all_articles)}")
    
    return True

def main():
    """Main function called by the bot"""
    global user_query
    if not user_query:
        raise ValueError("user_query must be set before calling main()")
    
    # Run the search process
    return run_search_process()

# If run directly (for testing)
if __name__ == "__main__":
    try:
        query = input("What do you want to search for?: ")
        set_user_query(query)
        main()
    except KeyboardInterrupt:
        print("\nSearch cancelled by user.")
    except Exception as e:
        print(f"Error: {e}")
