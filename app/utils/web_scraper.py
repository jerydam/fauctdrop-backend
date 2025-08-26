from fastapi import HTTPException
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def extract_article_content(url: str) -> dict:
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        title = None
        title_selectors = ['h1', 'title', '.entry-title', '.post-title', '.article-title']
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                title = title_elem.get_text().strip()
                break
        
        content = ""
        content_selectors = ['.post-content', '.entry-content', '.article-content', '.content', 'article', '.main-content']
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                for script in content_elem(["script", "style"]):
                    script.decompose()
                content = content_elem.get_text().strip()
                break
        
        if not content:
            paragraphs = soup.find_all('p')
            content = '\n\n'.join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
        
        excerpt = content[:200] + "..." if len(content) > 200 else content
        
        image = None
        img_selectors = ['meta[property="og:image"]', 'meta[name="twitter:image"]', '.featured-image img', 'article img']
        for selector in img_selectors:
            img_elem = soup.select_one(selector)
            if img_elem:
                if img_elem.name == 'meta':
                    image = img_elem.get('content')
                else:
                    image = img_elem.get('src')
                if image:
                    image = urljoin(url, image)
                    break
        
        return {
            'title': title or 'Untitled',
            'excerpt': excerpt,
            'content': content,
            'image': image
        }
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to extract content from URL: {str(e)}")
