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
    """Extract summary from article URL using newspaper3k"""
    try:
        article = Article(url)
        article.download()
        article.parse()
        article.nlp()
        
        return article.summary or "Summary not available"
    except Exception as e:
        print(f"Error extracting summary from {url}: {e}")
        return "Could not extract summary from this article."

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
You MUST return exactly {news_number} articles in this EXACT format:

SELECTED_ARTICLES:
Article 1
Title: [Complete article title]
Description / Summary: [Brief description or summary of the article - keep it concise]
URL: [Complete URL of the article]
Published At: [Date and time in IST format if available, otherwise "Date not available"]
Source: [Name of the source/website]

Article 2
Title: [Complete article title]
Description / Summary: [Brief description or summary of the article - keep it concise]
URL: [Complete URL of the article]
Published At: [Date and time in IST format if available, otherwise "Date not available"]
Source: [Name of the source/website]

...continue for all {news_number} articles

**CRITICAL FORMATTING RULES:**
- Start with "SELECTED_ARTICLES:" exactly as shown
- Each article must start with "Article X" (where X is the number)
- Follow the exact field format: "Title:", "Description / Summary:", "URL:", "Published At:", "Source:"
- Leave a blank line between articles
- Include exactly {news_number} articles
- If summary/description is not available, write "Summary not available"
- For dates, convert to IST if possible, otherwise write "Date not available"

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

def generate_with_retry(max_retries=3, model="gemini-2.0-flash", contents=None, config=None):
    for attempt in range(max_retries):
        try:
            print(f"🔄 Generating curated selection... (Attempt {attempt + 1})")
            
            response = client.models.generate_content(
                model=model,
                contents=contents,
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
    response = generate_with_retry(
        contents=[
            types.Part.from_bytes(
                data=filepath.read_bytes(),
                mime_type='text/plain',
            ),
            prompt
        ],
        config=config
    )
    
    # Debug: Print the raw response to see what LLM returned
    print("🔍 Raw LLM Response:")
    print("-" * 50)
    print(response.text)
    print("-" * 50)
    
    # Parse the selected articles from response
    selected_articles = []
    lines = response.text.split('\n')
    
    # Find the SELECTED_ARTICLES section and parse the structured format
    found_articles_section = False
    current_article = {}
    
    for line in lines:
        line = line.strip()
        
        if line == "SELECTED_ARTICLES:":
            found_articles_section = True
            continue
            
        if found_articles_section:
            if line.startswith("Article "):
                # If we have a complete article, save it
                if current_article and 'title' in current_article and 'url' in current_article:
                    selected_articles.append(current_article)
                # Start a new article
                current_article = {}
                
            elif line.startswith("Title:"):
                current_article['title'] = line.replace("Title:", "").strip()
                
            elif line.startswith("Description / Summary:"):
                current_article['llm_summary'] = line.replace("Description / Summary:", "").strip()
                
            elif line.startswith("URL:"):
                current_article['url'] = line.replace("URL:", "").strip()
                
            elif line.startswith("Published At:"):
                current_article['published_at'] = line.replace("Published At:", "").strip()
                
            elif line.startswith("Source:"):
                current_article['source'] = line.replace("Source:", "").strip()
    
    # Don't forget the last article
    if current_article and 'title' in current_article and 'url' in current_article:
        selected_articles.append(current_article)
    
    print(f"Parsed {len(selected_articles)} articles from LLM response")
    
    # Now extract detailed summaries using newspaper3k for each article
    for idx, article in enumerate(selected_articles):
        print(f"Extracting newspaper3k summary for article {idx+1}/{len(selected_articles)}: {article['title'][:50]}...")
        article['newspaper_summary'] = extract_detailed_summary(article['url'])
        time.sleep(0.5)  # Small delay to avoid overwhelming servers
    
    print(f"Selected {len(selected_articles)} articles for detailed analysis")
    
    # Save the curated results with detailed summaries
    output_filename = f"curated_news_{news_number}_articles.txt"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write("="*80 + "\n")
        f.write("EXPERT NEWS CURATION RESULTS\n")
        f.write("="*80 + "\n")
        f.write(f"Original Query: {user_query}\n")
        f.write(f"Requested Articles: {news_number}\n")
        f.write(f"Selected Articles: {len(selected_articles)}\n")
        f.write(f"Research Sources: Original Document + Google Search + Newspaper3k Analysis\n")
        f.write("="*80 + "\n\n")
        
        f.write("CURATION METHODOLOGY\n")
        f.write("-" * 40 + "\n")
        f.write("Each article was selected based on relevance, quality, recency, source credibility, and uniqueness.\n")
        f.write("Summaries were extracted using newspaper3k for accurate content analysis.\n\n")
        
        # Process each selected article
        for idx, article in enumerate(selected_articles, 1):
            f.write(f"📰 ARTICLE {idx}\n")
            f.write("=" * 50 + "\n")
            f.write(f"🏆 RANK: {idx}/{len(selected_articles)}\n")
            f.write(f"📰 TITLE: {article['title']}\n")
            f.write(f"🔗 URL: {article['url']}\n")
            
            if article.get('source'):
                f.write(f"📰 SOURCE: {article['source']}\n")
            
            if article.get('published_at'):
                f.write(f"📅 PUBLISHED: {article['published_at']}\n")
            
            f.write("\n📋 LLM SUMMARY:\n")
            f.write("-" * 30 + "\n")
            f.write(f"{article.get('llm_summary', 'No summary provided')}\n\n")
            
            f.write("� NEWSPAPER3K SUMMARY:\n")
            f.write("-" * 30 + "\n")
            f.write(f"{article.get('newspaper_summary', 'Could not extract summary')}\n\n")
            
            f.write("🎯 WHY THIS ARTICLE WAS SELECTED:\n")
            f.write("-" * 30 + "\n")
            f.write(f"This article was selected for its high relevance to '{user_query}', ")
            f.write("comprehensive coverage, credible source, and unique insights.\n\n")
            
            f.write("="*80 + "\n\n")
        
        f.write("🎯 CURATION SUMMARY\n")
        f.write("="*50 + "\n")
        f.write(f"Total articles analyzed: Multiple sources\n")
        f.write(f"Articles selected: {len(selected_articles)}\n")
        f.write(f"Selection criteria: Relevance (40%), Quality (25%), Recency (20%), Credibility (10%), Uniqueness (5%)\n")
        f.write(f"Enhanced with: Google Search + Newspaper3k Summary Extraction\n")
        f.write("="*80 + "\n")

    print(f"\n Expert curation completed!")
    print(f"Results saved to: {output_filename}")
    print(f"Processed {len(selected_articles)} curated articles")
    print(f"Enhanced with Google Search and Newspaper3k summary extraction")
    
    prompt_1 = '''
You are a professional news article formatter and content curator. Your task is to extract and format news articles from raw text content to a format of a message.  

For each article you identify, you must:
1. Create a concise 2-3 sentence summary capturing the key points and main story
2. Identify and extract the source publication or website name
3. Find and include the complete URL/link to the article

Format each article exactly as follows:
[Article Summary - 2-3 sentences describing the key points]
[Source/Website - the name of the publication or website]  
[Link - the URL of the article]

Requirements:
- Only include articles that have clear source information and valid links
- Separate each formatted article with a blank line
- Ensure summaries are informative and capture the essence of the story
- Extract exact source names (e.g., 'TechCrunch', 'BBC News', 'Reuters')
- Include complete, functional URLs
- Skip any content that doesn't appear to be a proper news article
- Maintain accuracy and avoid adding information not present in the original text
'''
    
    new_filepath = pathlib.Path(output_filename)
    formatted_response = generate_with_retry(
        contents=[
            types.Part.from_bytes(
                data=new_filepath.read_bytes(),
                mime_type='text/plain',
            ),
            prompt_1
        ],
        config=config
    )
    
    # Save the formatted message version
    message_filename = f"formatted_message_{news_number}_articles.txt"
    with open(message_filename, "w", encoding="utf-8") as f:
        f.write(formatted_response.text)
    
    print(f"Formatted message version saved to: {message_filename}")

except Exception as e:
    print(f"Failed to complete curation: {e}")
    print("Try again in a few minutes when the model is less busy.")