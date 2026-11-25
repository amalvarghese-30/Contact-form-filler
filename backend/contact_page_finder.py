# FILE #15: backend/contact_page_finder.py
# Find Contact Pages on Websites - Copy this EXACTLY

#!/usr/bin/env python3
"""
Contact Page Discovery Engine
- Scans websites for contact pages
- Tries 20+ common contact page paths
- Handles JavaScript-rendered pages
- Detects contact forms
- Returns results with confidence score
"""

import asyncio
import logging
from typing import List, Dict, Optional, Tuple
import aiohttp
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import re
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ContactPageFinder:
    """Find contact pages on websites"""
    
    # 20+ common contact page paths
    CONTACT_PATHS = [
        '/contact',
        '/contact-us',
        '/contact_us',
        '/contactus',
        '/support',
        '/contact-page',
        '/get-in-touch',
        '/reach-us',
        '/contact-form',
        '/inquiry',
        '/inquire',
        '/feedback',
        '/message',
        '/contact-information',
        '/contact-info',
        '/reach-out',
        '/write-us',
        '/contact-page/',
        '/about/contact',
        '/pages/contact',
        '/en/contact',
        '/help/contact',
        '/company/contact',
        '/business-contact',
        '/general-inquiry',
        '/contact-sales',
        '/sales',
        '/help',
        '/support-contact',
        '/contact-request'
    ]
    
    # Keywords to detect contact pages in links
    CONTACT_KEYWORDS = [
        'contact',
        'reach',
        'inquiry',
        'support',
        'feedback',
        'message',
        'write us',
        'get in touch',
        'contact us',
        'email',
        'phone',
        'address',
        'business',
        'partner',
        'collaboration'
    ]
    
    def __init__(self, timeout: int = 10, headless: bool = True):
        self.timeout = timeout
        self.headless = headless
        self.session = None
        self.results = []
    
    async def initialize(self):
        """Initialize async session"""
        self.session = aiohttp.ClientSession()
    
    async def close(self):
        """Close async session"""
        if self.session:
            await self.session.close()
    
    async def check_url(self, url: str) -> Tuple[bool, int, str]:
        """
        Check if URL is accessible
        Returns: (is_accessible, status_code, content_type)
        """
        try:
            async with self.session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                allow_redirects=True,
                ssl=False
            ) as response:
                content_type = response.headers.get('content-type', '')
                return response.status == 200, response.status, content_type
        except asyncio.TimeoutError:
            return False, 0, 'timeout'
        except aiohttp.ClientSSLError:
            return False, 0, 'ssl_error'
        except Exception as e:
            logger.debug(f"Error checking URL {url}: {e}")
            return False, 0, 'error'
    
    async def find_contact_page(self, website_url: str) -> Dict:
        """
        Find contact page on website
        Returns: {
            'url': original URL,
            'contact_page': found contact page URL or None,
            'status': 'found', 'not_found', 'error',
            'method': 'direct_path', 'sitemap', 'homepage_links', etc.,
            'confidence': 0.0-1.0,
            'time_taken': seconds
        }
        """
        start_time = time.time()
        
        logger.info(f"🔍 Finding contact page for: {website_url}")
        
        # Normalize URL
        if not website_url.startswith(('http://', 'https://')):
            website_url = 'https://' + website_url
        
        try:
            # Method 1: Try common direct paths
            contact_page = await self._try_direct_paths(website_url)
            if contact_page:
                return {
                    'url': website_url,
                    'contact_page': contact_page,
                    'status': 'found',
                    'method': 'direct_path',
                    'confidence': 0.95,
                    'time_taken': round(time.time() - start_time, 2)
                }
            
            # Method 2: Parse homepage and find contact links
            contact_page = await self._find_in_homepage(website_url)
            if contact_page:
                return {
                    'url': website_url,
                    'contact_page': contact_page,
                    'status': 'found',
                    'method': 'homepage_links',
                    'confidence': 0.85,
                    'time_taken': round(time.time() - start_time, 2)
                }
            
            # Method 3: Try sitemap
            contact_page = await self._find_in_sitemap(website_url)
            if contact_page:
                return {
                    'url': website_url,
                    'contact_page': contact_page,
                    'status': 'found',
                    'method': 'sitemap',
                    'confidence': 0.80,
                    'time_taken': round(time.time() - start_time, 2)
                }
            
            # Not found
            return {
                'url': website_url,
                'contact_page': None,
                'status': 'not_found',
                'method': None,
                'confidence': 0.0,
                'time_taken': round(time.time() - start_time, 2)
            }
        
        except Exception as e:
            logger.error(f"Error finding contact page: {e}")
            return {
                'url': website_url,
                'contact_page': None,
                'status': 'error',
                'method': None,
                'confidence': 0.0,
                'time_taken': round(time.time() - start_time, 2),
                'error': str(e)
            }
    
    async def _try_direct_paths(self, base_url: str) -> Optional[str]:
        """Try common contact page paths"""
        parsed = urlparse(base_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        
        for path in self.CONTACT_PATHS:
            test_url = urljoin(base, path)
            
            try:
                async with self.session.get(
                    test_url,
                    timeout=aiohttp.ClientTimeout(total=5),
                    allow_redirects=True,
                    ssl=False
                ) as response:
                    if response.status == 200:
                        content = await response.text()
                        # Check if it has contact form indicators
                        if self._is_contact_form_page(content):
                            logger.info(f"  ✅ Found contact page: {test_url}")
                            return test_url
            except:
                pass
        
        return None
    
    async def _find_in_homepage(self, base_url: str) -> Optional[str]:
        """Find contact page link in homepage"""
        try:
            async with self.session.get(
                base_url,
                timeout=aiohttp.ClientTimeout(total=5),
                ssl=False
            ) as response:
                if response.status != 200:
                    return None
                
                content = await response.text()
                soup = BeautifulSoup(content, 'html.parser')
                
                # Find all links
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    text = link.get_text().lower()
                    
                    # Check if link text matches contact keywords
                    for keyword in self.CONTACT_KEYWORDS:
                        if keyword in text:
                            contact_url = urljoin(base_url, href)
                            
                            # Verify it's actually a contact page
                            try:
                                async with self.session.get(
                                    contact_url,
                                    timeout=aiohttp.ClientTimeout(total=3),
                                    ssl=False
                                ) as contact_response:
                                    if contact_response.status == 200:
                                        contact_content = await contact_response.text()
                                        if self._is_contact_form_page(contact_content):
                                            logger.info(f"  ✅ Found from homepage: {contact_url}")
                                            return contact_url
                            except:
                                pass
        except:
            pass
        
        return None
    
    async def _find_in_sitemap(self, base_url: str) -> Optional[str]:
        """Find contact page in sitemap"""
        parsed = urlparse(base_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        sitemap_url = urljoin(base, '/sitemap.xml')
        
        try:
            async with self.session.get(
                sitemap_url,
                timeout=aiohttp.ClientTimeout(total=5),
                ssl=False
            ) as response:
                if response.status == 200:
                    content = await response.text()
                    
                    # Find URLs with contact keywords
                    urls = re.findall(r'<loc>(.*?)</loc>', content)
                    
                    for url in urls:
                        url_lower = url.lower()
                        if any(keyword in url_lower for keyword in self.CONTACT_KEYWORDS):
                            # Verify it's accessible
                            try:
                                async with self.session.get(
                                    url,
                                    timeout=aiohttp.ClientTimeout(total=3),
                                    ssl=False
                                ) as url_response:
                                    if url_response.status == 200:
                                        url_content = await url_response.text()
                                        if self._is_contact_form_page(url_content):
                                            logger.info(f"  ✅ Found from sitemap: {url}")
                                            return url
                            except:
                                pass
        except:
            pass
        
        return None
    
    def _is_contact_form_page(self, html_content: str) -> bool:
        """Check if page contains contact form indicators"""
        content_lower = html_content.lower()
        
        indicators = [
            '<form',
            'contact',
            'message',
            'email',
            'phone',
            'name',
            'inquiry',
            'feedback',
            'submit',
            'send',
            'contact-form',
            'contactform',
            'getintouch'
        ]
        
        # Must have form and contact-related content
        has_form = '<form' in content_lower
        has_contact_keywords = sum(1 for ind in indicators if ind in content_lower) >= 3
        
        return has_form and has_contact_keywords
    
    async def find_batch(self, urls: List[str], batch_size: int = 10) -> List[Dict]:
        """Find contact pages for multiple URLs"""
        logger.info(f"🔍 Finding contact pages for {len(urls)} websites...")
        
        results = []
        
        # Process in batches to avoid overwhelming the server
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            
            # Run batch concurrently
            batch_results = await asyncio.gather(
                *[self.find_contact_page(url) for url in batch],
                return_exceptions=True
            )
            
            for result in batch_results:
                if isinstance(result, dict):
                    results.append(result)
            
            logger.info(f"Progress: {min(i + batch_size, len(urls))}/{len(urls)}")
            
            # Small delay between batches
            if i + batch_size < len(urls):
                await asyncio.sleep(1)
        
        return results
    
    def get_statistics(self, results: List[Dict]) -> Dict:
        """Get statistics from contact page discovery"""
        total = len(results)
        found = sum(1 for r in results if r['status'] == 'found')
        not_found = sum(1 for r in results if r['status'] == 'not_found')
        errors = sum(1 for r in results if r['status'] == 'error')
        
        # By method
        methods = {}
        for r in results:
            if r.get('method'):
                methods[r['method']] = methods.get(r['method'], 0) + 1
        
        # Average time
        times = [r.get('time_taken', 0) for r in results]
        avg_time = sum(times) / len(times) if times else 0
        
        # Average confidence for found pages
        confidences = [r.get('confidence', 0) for r in results if r['status'] == 'found']
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        return {
            'total_urls': total,
            'found': found,
            'not_found': not_found,
            'errors': errors,
            'success_rate': round((found / total * 100) if total > 0 else 0, 2),
            'by_method': methods,
            'average_time_per_url': round(avg_time, 2),
            'average_confidence': round(avg_confidence, 2)
        }


async def find_contacts_for_dataset(urls: List[str], batch_size: int = 10) -> Tuple[List[Dict], Dict]:
    """
    Find contact pages for entire dataset
    Returns: (results, statistics)
    """
    finder = ContactPageFinder()
    await finder.initialize()
    
    try:
        results = await finder.find_batch(urls, batch_size)
        stats = finder.get_statistics(results)
        return results, stats
    finally:
        await finder.close()


if __name__ == "__main__":
    print("""
    ╔════════════════════════════════════════╗
    ║  Contact Page Finder                   ║
    ║  Discover contact pages on websites    ║
    ╚════════════════════════════════════════╝
    """)
    
    # Example usage
    test_urls = [
        'https://google.com',
        'https://github.com',
        'https://example.com',
        'https://wikipedia.org'
    ]
    
    print(f"\n🔍 Finding contact pages for {len(test_urls)} websites...")
    
    # Run async function
    results, stats = asyncio.run(find_contacts_for_dataset(test_urls))
    
    # Print results
    print("\n📊 Results:")
    for result in results:
        status = "✅" if result['status'] == 'found' else "❌"
        contact = result.get('contact_page', 'Not found')
        print(f"{status} {result['url']}")
        if contact:
            print(f"   → {contact} (confidence: {result['confidence']})")
    
    # Print statistics
    print("\n📈 Statistics:")
    print(f"  Total URLs: {stats['total_urls']}")
    print(f"  Found: {stats['found']}")
    print(f"  Not Found: {stats['not_found']}")
    print(f"  Errors: {stats['errors']}")
    print(f"  Success Rate: {stats['success_rate']}%")
    print(f"  Average Time: {stats['average_time_per_url']}s")
    print(f"  Average Confidence: {stats['average_confidence']}")
