import os
import dotenv as env
from google import genai
from google.genai import types
import pathlib
from search import user_query
from newspaper import Article
import time
import random

env.load_dotenv()
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

news_number = int(input("How many news articles do you want to fetch? (default is 10): ") or 10)

filepath = pathlib.Path('news_results.txt')

def extract_detailed_summary(url):
    """Extract detailed summary from article URL using newspaper3k"""
    try:
        article = Article(url)
        article.download()
        article.parse()
        article.nlp()
        
        return {
            'summary': article.summary,
        }
    except Exception as e:
        print(f"Error extracting detailed content from {url}: {e}")
        return {
            'summary': "Could not extract detailed summary from this article.",
        }

prompt = f'''You are an expert news curator and analyst with deep expertise in content filtering and ranking. Your task is to analyze the provided news articles and create a curated selection of the highest quality, most relevant content.

**CONTEXT:**
- Original User Query: "{user_query}"
- Requested Number of Articles: {news_number}
- Document Source: Complete news collection from multiple sources
- Enhanced Capability: Google Search access for additional research + Detailed Article Analysis

**YOUR MISSION:**
Carefully analyze ALL provided news articles and intelligently filter them to select exactly {news_number} of the BEST articles that perfectly match the user's query: "{user_query}"

**ENHANCED RESEARCH CAPABILITY:**
If necessary, use Google Search to find additional high-quality news articles that are NOT already present in the provided text file. This will help you:
- Fill gaps in coverage for the user's specific query
- Find more recent or breaking news developments
- Discover alternative perspectives or sources
- Ensure you have the best possible selection of {news_number} articles

**SELECTION CRITERIA (in order of priority):**
1. **Relevance Score (40%)**: How closely does the article match the user's specific query?
2. **Content Quality (25%)**: Well-written, comprehensive, factual content with proper sources
3. **Recency (20%)**: Newer articles get priority (check publication dates)
4. **Source Credibility (10%)**: Prefer established, reputable news sources
5. **Uniqueness (5%)**: Avoid duplicate stories, select diverse perspectives

**QUALITY FILTERS:**
- Exclude articles with incomplete or missing content
- Remove promotional content or advertisements disguised as news
- Filter out articles with poor grammar or obvious misinformation
- Prioritize articles with substantial content over brief snippets
- Favor articles with proper attribution and sources

**RESEARCH STRATEGY:**
1. First, analyze all articles in the provided document
2. If the provided articles don't give you enough high-quality options for {news_number} selections, use Google Search to find additional relevant news
3. Combine both sources to create the best possible curated selection
4. Clearly indicate which articles came from the original document vs. Google Search
5. For each selected article, I will extract detailed summaries using the article URLs

**OUTPUT FORMAT:**
Provide ONLY the selected article URLs and titles in this exact format:

SELECTED_ARTICLES:
Article X
Title: Title of the article
Description / Summary: Description or summary of the article (if not available, fetch it using google search)
URL: URL of the article
Published At: Date and time of the publication in IST(Indian Standard Time) 
Source:  Name of the source or website
...and so on for {news_number} articles

**IMPORTANT GUIDELINES:**
- Be extremely selective - quality over quantity
- Maintain objectivity and avoid bias
- If fewer than {news_number} articles meet quality standards, explain why
- Prioritize articles that provide actionable insights or unique perspectives
- Consider the user's intent behind their query when making selections
- Use Google Search strategically to enhance, not replace, your analysis of the provided document
- Return ONLY the selected articles list - detailed analysis will be added separately

**TONE:** Professional, analytical, and insightful - like a premium news curation service with access to real-time research capabilities.

Analyze the provided news collection and, if necessary, use Google Search to find additional relevant news articles to deliver your expert curation of exactly {news_number} top-quality articles. Return only the selected articles list.'''

# Define the grounding tool
grounding_tool = types.Tool(
    google_search=types.GoogleSearch()
)

# Configure generation settings
config = types.GenerateContentConfig(
    tools=[grounding_tool]
)

def generate_with_retry(max_retries=3):
    for attempt in range(max_retries):
        try:
            print(f"🔄 Generating curated selection... (Attempt {attempt + 1})")
            
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    types.Part.from_bytes(
                        data=filepath.read_bytes(),
                        mime_type='text/plain',
                    ),
                    prompt
                ],
                config=config
            )
            return response
            
        except Exception as e:
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ["overloaded", "quota", "rate", "limit"]):
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                print(f"⚠️  Model overloaded/rate limited. Waiting {wait_time:.2f} seconds...")
                time.sleep(wait_time)
            else:
                print(f"❌ Unexpected error: {e}")
                raise e
    
    raise Exception("❌ Max retries exceeded. Please try again later.")

try:
    # Get curated article selection
    response = generate_with_retry()
    
    # Parse the selected articles from response
    selected_articles = []
    lines = response.text.split('\n')
    
    for line in lines:
        if '|' in line and ('http' in line or 'www' in line):
            try:
                parts = line.split('|')
                if len(parts) >= 2:
                    title = parts[0].strip()
                    url = parts[1].strip()
                    # Remove numbering if present
                    if title.startswith(tuple('123456789')):
                        title = '. '.join(title.split('. ')[1:])
                    selected_articles.append({'title': title, 'url': url})
            except:
                continue
    
    print(f"✅ Selected {len(selected_articles)} articles for detailed analysis")
    
    # Save the curated results with detailed summaries
    output_filename = f"curated_news_{news_number}_articles.txt"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write("="*80 + "\n")
        f.write("EXPERT NEWS CURATION RESULTS (Enhanced with Detailed Summaries)\n")
        f.write("="*80 + "\n")
        f.write(f"Original Query: {user_query}\n")
        f.write(f"Requested Articles: {news_number}\n")
        f.write(f"Selected Articles: {len(selected_articles)}\n")
        f.write(f"Research Sources: Original Document + Google Search + Article Analysis\n")
        f.write("="*80 + "\n\n")
        
        f.write("🎯 CURATION METHODOLOGY\n")
        f.write("-" * 40 + "\n")
        f.write("Each article was selected based on relevance, quality, recency, source credibility, and uniqueness.\n")
        f.write("Detailed summaries were extracted directly from article content using advanced text analysis.\n\n")
        
        # Process each selected article with detailed summary
        for idx, article in enumerate(selected_articles, 1):
            print(f"📖 Extracting detailed summary for article {idx}/{len(selected_articles)}: {article['title'][:50]}...")
            
            # Extract detailed summary
            detailed_info = extract_detailed_summary(article['url'])
            
            f.write(f"📰 ARTICLE {idx}\n")
            f.write("=" * 50 + "\n")
            f.write(f"🏆 RANK: {idx}/{len(selected_articles)}\n")
            f.write(f"📰 TITLE: {article['title']}\n")
            f.write(f"🔗 URL: {article['url']}\n")
            
            if detailed_info['authors']:
                f.write(f"✍️  AUTHORS: {', '.join(detailed_info['authors'])}\n")
            
            if detailed_info['publish_date']:
                f.write(f"📅 PUBLISHED: {detailed_info['publish_date']}\n")
            
            if detailed_info['keywords']:
                f.write(f"🔍 KEY TOPICS: {', '.join(detailed_info['keywords'])}\n")
            
            f.write("\n📋 DETAILED SUMMARY:\n")
            f.write("-" * 30 + "\n")
            f.write(f"{detailed_info['summary']}\n\n")
            
            f.write("📄 ARTICLE EXCERPT:\n")
            f.write("-" * 30 + "\n")
            f.write(f"{detailed_info['full_text']}\n\n")
            
            f.write("🎯 WHY THIS ARTICLE WAS SELECTED:\n")
            f.write("-" * 30 + "\n")
            f.write(f"This article was selected for its high relevance to '{user_query}', ")
            f.write("comprehensive coverage, credible source, and unique insights that contribute to a well-rounded understanding of the topic.\n\n")
            
            f.write("="*80 + "\n\n")
            
            # Add small delay to avoid overwhelming servers
            time.sleep(0.5)
        
        f.write("🎯 CURATION SUMMARY\n")
        f.write("="*50 + "\n")
        f.write(f"Total articles analyzed: Multiple sources\n")
        f.write(f"Articles selected: {len(selected_articles)}\n")
        f.write(f"Selection criteria: Relevance (40%), Quality (25%), Recency (20%), Credibility (10%), Uniqueness (5%)\n")
        f.write(f"Enhanced with: Google Search + Detailed Article Analysis\n")
        f.write("="*80 + "\n")

    print(f"\n✅ Expert curation completed with detailed summaries!")
    print(f"📄 Results saved to: {output_filename}")
    print(f"🎯 Processed {len(selected_articles)} curated articles with detailed analysis")
    print(f"🔍 Enhanced with Google Search and full article content extraction")

except Exception as e:
    print(f"❌ Failed to complete curation: {e}")
    print("💡 Try again in a few minutes when the model is less busy.")