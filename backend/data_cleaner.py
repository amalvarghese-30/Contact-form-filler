# FILE #14: backend/data_cleaner.py
# URL Data Cleaning & Validation - Copy this EXACTLY

#!/usr/bin/env python3
"""
Data Cleaning Pipeline for URL datasets
- Remove duplicates
- Remove null/empty values
- Validate URLs
- Remove invalid formats
- Standardize URLs
"""

import json
import csv
import os
import re
from typing import List, Dict, Set, Tuple
from urllib.parse import urlparse, urljoin
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class URLCleaner:
    """Clean and validate URL datasets"""
    
    def __init__(self):
        self.original_count = 0
        self.cleaned_count = 0
        self.removed_duplicates = 0
        self.removed_invalid = 0
        self.removed_null = 0
        self.seen_urls: Set[str] = set()
        
    def is_valid_url(self, url: str) -> bool:
        """Check if URL is valid"""
        if not url or not isinstance(url, str):
            return False
        
        url = url.strip()
        
        # Check for common invalid patterns
        if len(url) < 5:  # Minimum: http://a
            return False
        
        if url.lower() == 'null' or url.lower() == 'none':
            return False
        
        if url.lower() == 'nan' or url == '':
            return False
        
        if '#' in url and not url.startswith('http'):
            return False
        
        # Must start with http or https
        if not (url.startswith('http://') or url.startswith('https://')):
            return False
        
        # Basic URL validation
        try:
            result = urlparse(url)
            # Must have domain
            if not result.netloc:
                return False
            
            # Domain should have at least one dot
            if '.' not in result.netloc:
                return False
            
            return True
        except:
            return False
    
    def normalize_url(self, url: str) -> str:
        """Normalize URL to standard format"""
        if not url:
            return ""
        
        url = url.strip().lower()
        
        # Remove trailing slash
        if url.endswith('/'):
            url = url[:-1]
        
        # Remove query parameters
        if '?' in url:
            url = url.split('?')[0]
        
        # Remove fragments
        if '#' in url:
            url = url.split('#')[0]
        
        # Add https if missing
        if not url.startswith('http'):
            url = 'https://' + url
        
        # Replace http with https
        if url.startswith('http://'):
            url = url.replace('http://', 'https://', 1)
        
        return url
    
    def clean_urls(self, urls: List[Dict]) -> List[Dict]:
        """
        Clean list of URL dictionaries
        Returns cleaned list with statistics
        """
        self.original_count = len(urls)
        self.seen_urls = set()
        cleaned_urls = []
        
        logger.info(f"Starting to clean {self.original_count} URLs...")
        
        for item in urls:
            # Handle both dict and string formats
            if isinstance(item, dict):
                url = item.get('url', '').strip()
                company_name = item.get('company_name', '').strip()
                industry = item.get('industry', '').strip()
                country = item.get('country', '').strip()
            else:
                url = str(item).strip()
                company_name = ''
                industry = ''
                country = ''
            
            # Check for null/empty
            if not url or url.lower() in ['null', 'none', 'nan', '']:
                self.removed_null += 1
                continue
            
            # Validate URL format
            if not self.is_valid_url(url):
                self.removed_invalid += 1
                logger.debug(f"Invalid URL: {url}")
                continue
            
            # Normalize URL
            normalized_url = self.normalize_url(url)
            
            # Check for duplicates
            if normalized_url in self.seen_urls:
                self.removed_duplicates += 1
                logger.debug(f"Duplicate URL: {normalized_url}")
                continue
            
            # Add to cleaned list
            self.seen_urls.add(normalized_url)
            cleaned_urls.append({
                'url': normalized_url,
                'company_name': company_name if company_name else self._extract_domain_name(normalized_url),
                'industry': industry if industry else 'Unknown',
                'country': country if country else 'Unknown'
            })
            
            self.cleaned_count += 1
        
        logger.info(f"Cleaning complete!")
        logger.info(f"  Original: {self.original_count}")
        logger.info(f"  Cleaned: {self.cleaned_count}")
        logger.info(f"  Removed duplicates: {self.removed_duplicates}")
        logger.info(f"  Removed invalid: {self.removed_invalid}")
        logger.info(f"  Removed null: {self.removed_null}")
        
        return cleaned_urls
    
    def _extract_domain_name(self, url: str) -> str:
        """Extract domain name from URL"""
        try:
            domain = urlparse(url).netloc
            domain = domain.replace('www.', '')
            return domain.split('.')[0].capitalize()
        except:
            return 'Unknown'
    
    def get_statistics(self) -> Dict:
        """Get cleaning statistics"""
        return {
            'original_count': self.original_count,
            'cleaned_count': self.cleaned_count,
            'removed_duplicates': self.removed_duplicates,
            'removed_invalid': self.removed_invalid,
            'removed_null': self.removed_null,
            'total_removed': self.removed_duplicates + self.removed_invalid + self.removed_null,
            'retention_rate': round((self.cleaned_count / self.original_count * 100) if self.original_count > 0 else 0, 2)
        }


class DataLoader:
    """Load data from various formats"""
    
    @staticmethod
    def load_json(file_path: str) -> List[Dict]:
        """Load URLs from JSON file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle different JSON structures
            if isinstance(data, dict):
                if 'companies' in data:
                    return data['companies']
                elif 'urls' in data:
                    return data['urls']
                else:
                    return list(data.values())
            elif isinstance(data, list):
                return data
            
            return []
        except Exception as e:
            logger.error(f"Error loading JSON: {e}")
            return []
    
    @staticmethod
    def load_csv(file_path: str) -> List[Dict]:
        """Load URLs from CSV file"""
        try:
            urls = []
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    urls.append(row)
            
            return urls
        except Exception as e:
            logger.error(f"Error loading CSV: {e}")
            return []
    
    @staticmethod
    def load_txt(file_path: str) -> List[Dict]:
        """Load URLs from text file (one URL per line)"""
        try:
            urls = []
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    url = line.strip()
                    if url:
                        urls.append({'url': url})
            
            return urls
        except Exception as e:
            logger.error(f"Error loading TXT: {e}")
            return []
    
    @staticmethod
    def load_from_zip(zip_path: str) -> Tuple[List[Dict], str]:
        """
        Load URLs from ZIP file containing various formats
        Returns: (urls list, detected format)
        """
        import zipfile
        
        try:
            urls = []
            detected_format = None
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # List all files
                files = zip_ref.namelist()
                logger.info(f"ZIP contains {len(files)} files:")
                for f in files:
                    logger.info(f"  - {f}")
                
                # Look for data files
                for file_name in files:
                    if file_name.endswith('.json'):
                        logger.info(f"Loading JSON: {file_name}")
                        with zip_ref.open(file_name) as f:
                            data = json.load(f)
                            if isinstance(data, list):
                                urls.extend(data)
                            elif isinstance(data, dict):
                                if 'companies' in data:
                                    urls.extend(data['companies'])
                                elif 'urls' in data:
                                    urls.extend(data['urls'])
                                else:
                                    urls.extend(list(data.values()))
                        detected_format = 'JSON'
                    
                    elif file_name.endswith('.csv'):
                        logger.info(f"Loading CSV: {file_name}")
                        with zip_ref.open(file_name) as f:
                            reader = csv.DictReader([line.decode('utf-8') for line in f])
                            urls.extend(list(reader))
                        detected_format = 'CSV'
                    
                    elif file_name.endswith('.txt'):
                        logger.info(f"Loading TXT: {file_name}")
                        with zip_ref.open(file_name) as f:
                            for line in f:
                                url = line.decode('utf-8').strip()
                                if url:
                                    urls.append({'url': url})
                        detected_format = 'TXT'
            
            logger.info(f"Loaded {len(urls)} URLs from ZIP ({detected_format})")
            return urls, detected_format
        
        except Exception as e:
            logger.error(f"Error loading ZIP: {e}")
            return [], None


class DataSaver:
    """Save cleaned data in various formats"""
    
    @staticmethod
    def save_json(urls: List[Dict], output_path: str):
        """Save cleaned URLs to JSON"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump({'companies': urls}, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(urls)} URLs to: {output_path}")
        except Exception as e:
            logger.error(f"Error saving JSON: {e}")
    
    @staticmethod
    def save_csv(urls: List[Dict], output_path: str):
        """Save cleaned URLs to CSV"""
        try:
            if not urls:
                logger.warning("No URLs to save")
                return
            
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=urls[0].keys())
                writer.writeheader()
                writer.writerows(urls)
            
            logger.info(f"Saved {len(urls)} URLs to: {output_path}")
        except Exception as e:
            logger.error(f"Error saving CSV: {e}")
    
    @staticmethod
    def save_txt(urls: List[Dict], output_path: str):
        """Save cleaned URLs to TXT (one per line)"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                for item in urls:
                    url = item.get('url', '') if isinstance(item, dict) else item
                    if url:
                        f.write(url + '\n')
            
            logger.info(f"Saved {len(urls)} URLs to: {output_path}")
        except Exception as e:
            logger.error(f"Error saving TXT: {e}")


if __name__ == "__main__":
    print("""
    ╔════════════════════════════════════════╗
    ║  URL Data Cleaner                      ║
    ║  Remove duplicates, nulls, invalid URLs║
    ╚════════════════════════════════════════╝
    """)
    
    # Example usage:
    # 1. Load from ZIP
    print("\n📂 Loading from ZIP file...")
    urls, format = DataLoader.load_from_zip('your_urls.zip')
    
    # 2. Clean data
    print("🧹 Cleaning data...")
    cleaner = URLCleaner()
    cleaned = cleaner.clean_urls(urls)
    stats = cleaner.get_statistics()
    
    # 3. Print statistics
    print("\n📊 Cleaning Statistics:")
    print(f"  Original URLs: {stats['original_count']}")
    print(f"  Cleaned URLs: {stats['cleaned_count']}")
    print(f"  Removed Duplicates: {stats['removed_duplicates']}")
    print(f"  Removed Invalid: {stats['removed_invalid']}")
    print(f"  Removed Null/Empty: {stats['removed_null']}")
    print(f"  Retention Rate: {stats['retention_rate']}%")
    
    # 4. Save cleaned data
    print("\n💾 Saving cleaned data...")
    DataSaver.save_json(cleaned, 'data/cleaned_urls.json')
    DataSaver.save_csv(cleaned, 'data/cleaned_urls.csv')
    DataSaver.save_txt(cleaned, 'data/cleaned_urls.txt')
    
    print("\n✅ Done!")
