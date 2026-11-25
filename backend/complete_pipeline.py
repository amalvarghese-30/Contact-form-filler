# FILE #16: backend/complete_pipeline.py
# Complete Data Processing Pipeline - Copy this EXACTLY

#!/usr/bin/env python3
"""
Complete Data Processing Pipeline
1. Clean data (remove duplicates, invalid URLs)
2. Find contact pages
3. Load into database
4. Generate statistics
"""

import asyncio
import json
import sys
import os
from typing import List, Dict, Tuple
import logging
from datetime import datetime

from data_cleaner import URLCleaner, DataLoader, DataSaver
from contact_page_finder import find_contacts_for_dataset
from database import URLDatabase

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DataPipeline:
    """Complete pipeline for data processing"""
    
    def __init__(self):
        self.raw_data = []
        self.cleaned_data = []
        self.contact_pages_data = []
        self.db = URLDatabase()
        self.statistics = {}
    
    def step_1_load_data(self, file_path: str) -> bool:
        """Step 1: Load data from ZIP, JSON, CSV, or TXT"""
        print("\n" + "="*60)
        print("STEP 1: Loading Data")
        print("="*60)
        
        try:
            if file_path.endswith('.zip'):
                print(f"📂 Loading from ZIP: {file_path}")
                self.raw_data, format = DataLoader.load_from_zip(file_path)
                print(f"✅ Loaded {len(self.raw_data)} URLs ({format})")
            
            elif file_path.endswith('.json'):
                print(f"📂 Loading from JSON: {file_path}")
                self.raw_data = DataLoader.load_json(file_path)
                print(f"✅ Loaded {len(self.raw_data)} URLs")
            
            elif file_path.endswith('.csv'):
                print(f"📂 Loading from CSV: {file_path}")
                self.raw_data = DataLoader.load_csv(file_path)
                print(f"✅ Loaded {len(self.raw_data)} URLs")
            
            elif file_path.endswith('.txt'):
                print(f"📂 Loading from TXT: {file_path}")
                self.raw_data = DataLoader.load_txt(file_path)
                print(f"✅ Loaded {len(self.raw_data)} URLs")
            
            else:
                print(f"❌ Unsupported file format: {file_path}")
                return False
            
            if not self.raw_data:
                print("❌ No data loaded!")
                return False
            
            return True
        
        except Exception as e:
            print(f"❌ Error loading data: {e}")
            return False
    
    def step_2_clean_data(self) -> bool:
        """Step 2: Clean data - remove duplicates, invalid URLs, nulls"""
        print("\n" + "="*60)
        print("STEP 2: Cleaning Data")
        print("="*60)
        
        try:
            print(f"🧹 Cleaning {len(self.raw_data)} URLs...")
            
            cleaner = URLCleaner()
            self.cleaned_data = cleaner.clean_urls(self.raw_data)
            stats = cleaner.get_statistics()
            
            # Store statistics
            self.statistics['cleaning'] = stats
            
            # Print statistics
            print("\n📊 Cleaning Statistics:")
            print(f"  Original URLs: {stats['original_count']}")
            print(f"  Cleaned URLs: {stats['cleaned_count']}")
            print(f"  Removed Duplicates: {stats['removed_duplicates']}")
            print(f"  Removed Invalid: {stats['removed_invalid']}")
            print(f"  Removed Null/Empty: {stats['removed_null']}")
            print(f"  Retention Rate: {stats['retention_rate']}%")
            
            if not self.cleaned_data:
                print("❌ No data after cleaning!")
                return False
            
            return True
        
        except Exception as e:
            print(f"❌ Error cleaning data: {e}")
            return False
    
    async def step_3_find_contact_pages(self, batch_size: int = 10) -> bool:
        """Step 3: Find contact pages for all URLs"""
        print("\n" + "="*60)
        print("STEP 3: Finding Contact Pages")
        print("="*60)
        
        try:
            urls = [item['url'] for item in self.cleaned_data]
            
            print(f"🔍 Finding contact pages for {len(urls)} websites...")
            print(f"   (Processing in batches of {batch_size})")
            
            results, stats = await find_contacts_for_dataset(urls, batch_size)
            
            # Store statistics
            self.statistics['contact_finder'] = stats
            
            # Merge contact page data with cleaned data
            self.contact_pages_data = []
            for i, cleaned_item in enumerate(self.cleaned_data):
                if i < len(results):
                    contact_result = results[i]
                    merged_item = {
                        **cleaned_item,
                        'contact_page': contact_result.get('contact_page'),
                        'contact_found': contact_result['status'] == 'found',
                        'contact_method': contact_result.get('method'),
                        'contact_confidence': contact_result.get('confidence', 0),
                        'contact_discovery_time': contact_result.get('time_taken', 0)
                    }
                    self.contact_pages_data.append(merged_item)
            
            # Print statistics
            print("\n📊 Contact Page Discovery Statistics:")
            print(f"  Total URLs: {stats['total_urls']}")
            print(f"  Found: {stats['found']}")
            print(f"  Not Found: {stats['not_found']}")
            print(f"  Errors: {stats['errors']}")
            print(f"  Success Rate: {stats['success_rate']}%")
            print(f"  Average Time: {stats['average_time_per_url']}s per URL")
            print(f"  Average Confidence: {stats['average_confidence']}")
            print(f"  Discovery Methods:")
            for method, count in stats.get('by_method', {}).items():
                print(f"    - {method}: {count}")
            
            return True
        
        except Exception as e:
            print(f"❌ Error finding contact pages: {e}")
            return False
    
    def step_4_load_to_database(self) -> bool:
        """Step 4: Load cleaned data with contact pages into database"""
        print("\n" + "="*60)
        print("STEP 4: Loading to Database")
        print("="*60)
        
        try:
            print(f"💾 Loading {len(self.contact_pages_data)} URLs to database...")
            
            added = self.db.add_urls_batch(self.contact_pages_data)
            
            print(f"✅ Successfully added {added} URLs to database")
            
            # Get database stats
            db_stats = self.db.get_database_stats()
            self.statistics['database'] = db_stats
            
            print("\n📊 Database Statistics:")
            print(f"  Total URLs: {db_stats['total_urls']}")
            print(f"  Processed: {db_stats['processed_urls']}")
            print(f"  Pending: {db_stats['pending_urls']}")
            print(f"  With Contact Pages: {db_stats['with_contact_pages']}")
            print(f"  Completion: {db_stats['percentage_complete']}%")
            
            return True
        
        except Exception as e:
            print(f"❌ Error loading to database: {e}")
            return False
    
    def step_5_generate_reports(self, output_dir: str = 'data/reports') -> bool:
        """Step 5: Generate reports and statistics"""
        print("\n" + "="*60)
        print("STEP 5: Generating Reports")
        print("="*60)
        
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Save cleaned data
            print("💾 Saving cleaned data...")
            cleaned_json = os.path.join(output_dir, f'cleaned_urls_{timestamp}.json')
            DataSaver.save_json(self.cleaned_data, cleaned_json)
            
            cleaned_csv = os.path.join(output_dir, f'cleaned_urls_{timestamp}.csv')
            DataSaver.save_csv(self.cleaned_data, cleaned_csv)
            
            # Save contact page results
            print("💾 Saving contact page discovery results...")
            contacts_json = os.path.join(output_dir, f'contact_pages_{timestamp}.json')
            DataSaver.save_json(self.contact_pages_data, contacts_json)
            
            contacts_csv = os.path.join(output_dir, f'contact_pages_{timestamp}.csv')
            DataSaver.save_csv(self.contact_pages_data, contacts_csv)
            
            # Save comprehensive statistics
            print("📊 Saving statistics...")
            stats_file = os.path.join(output_dir, f'statistics_{timestamp}.json')
            with open(stats_file, 'w') as f:
                json.dump(self.statistics, f, indent=2)
            
            print(f"\n✅ Reports saved to: {output_dir}")
            print(f"  - Cleaned URLs: cleaned_urls_{timestamp}.*")
            print(f"  - Contact Pages: contact_pages_{timestamp}.*")
            print(f"  - Statistics: statistics_{timestamp}.json")
            
            return True
        
        except Exception as e:
            print(f"❌ Error generating reports: {e}")
            return False
    
    async def run_complete_pipeline(self, file_path: str, batch_size: int = 10) -> bool:
        """Run complete pipeline"""
        print("""
        ╔════════════════════════════════════════════════════╗
        ║  Complete Data Processing Pipeline                ║
        ║  1. Load Data                                      ║
        ║  2. Clean Data                                     ║
        ║  3. Find Contact Pages                             ║
        ║  4. Load to Database                               ║
        ║  5. Generate Reports                               ║
        ╚════════════════════════════════════════════════════╝
        """)
        
        # Step 1: Load
        if not self.step_1_load_data(file_path):
            return False
        
        # Step 2: Clean
        if not self.step_2_clean_data():
            return False
        
        # Step 3: Find contacts
        if not await self.step_3_find_contact_pages(batch_size):
            return False
        
        # Step 4: Load to database
        if not self.step_4_load_to_database():
            return False
        
        # Step 5: Generate reports
        if not self.step_5_generate_reports():
            return False
        
        print("\n" + "="*60)
        print("✅ PIPELINE COMPLETE!")
        print("="*60)
        
        return True


async def main():
    """Main entry point"""
    
    if len(sys.argv) < 2:
        print("""
Usage:
  python complete_pipeline.py <file_path> [batch_size]

Examples:
  python complete_pipeline.py urls.zip
  python complete_pipeline.py urls.json 20
  python complete_pipeline.py urls.csv 10
  python complete_pipeline.py urls.txt 5

Supported formats:
  - ZIP files containing JSON/CSV/TXT
  - JSON files
  - CSV files
  - TXT files (one URL per line)

Options:
  batch_size: Number of URLs to process concurrently (default: 10)
        """)
        return
    
    file_path = sys.argv[1]
    batch_size = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return
    
    # Run pipeline
    pipeline = DataPipeline()
    success = await pipeline.run_complete_pipeline(file_path, batch_size)
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
