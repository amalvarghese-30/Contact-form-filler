# FILE #9: backend/database_api.py
# Database REST API Endpoints - Copy this EXACTLY

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Optional
import logging
from database import URLDatabase, FieldAnalyzer

logger = logging.getLogger(__name__)

# Initialize database
db = URLDatabase()


# ============= DATA MODELS =============

class URLItem(BaseModel):
    """Single URL item"""
    url: str
    company_name: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None


class URLBatch(BaseModel):
    """Batch of URLs to import"""
    urls: List[URLItem]


class URLResponse(BaseModel):
    """Response for URL operations"""
    success: bool
    message: str
    data: Optional[Dict] = None


# ============= DATABASE ROUTES =============

def setup_database_routes(app: FastAPI):
    """Setup all database-related API routes"""
    
    @app.post("/api/db/add-url")
    async def add_single_url(item: URLItem):
        """Add a single URL to database"""
        try:
            url_id = db.add_url(
                url=item.url,
                company_name=item.company_name,
                industry=item.industry,
                country=item.country
            )
            
            if url_id:
                return {
                    "success": True,
                    "message": "URL added successfully",
                    "url_id": url_id
                }
            else:
                return {
                    "success": False,
                    "message": "URL already exists or error occurred"
                }
        
        except Exception as e:
            logger.error(f"Error adding URL: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    
    @app.post("/api/db/add-urls-batch")
    async def add_urls_batch(batch: URLBatch):
        """Add multiple URLs at once"""
        try:
            urls_data = [item.dict() for item in batch.urls]
            added_count = db.add_urls_batch(urls_data)
            
            return {
                "success": True,
                "message": f"Added {added_count} URLs",
                "added": added_count
            }
        
        except Exception as e:
            logger.error(f"Error adding batch: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    
    @app.post("/api/db/import-csv")
    async def import_csv(file_path: str):
        """Import URLs from CSV file"""
        try:
            import csv
            urls = []
            
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    urls.append({
                        'url': row.get('url'),
                        'company_name': row.get('company_name'),
                        'industry': row.get('industry'),
                        'country': row.get('country')
                    })
            
            added = db.add_urls_batch(urls)
            
            return {
                "success": True,
                "message": f"Imported {added} URLs from CSV",
                "imported": added
            }
        
        except Exception as e:
            logger.error(f"Error importing CSV: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    
    @app.get("/api/db/urls/pending")
    async def get_pending_urls(limit: int = Query(50, ge=1, le=500)):
        """Get pending (unprocessed) URLs"""
        try:
            urls = db.get_pending_urls(limit=limit)
            
            return {
                "success": True,
                "count": len(urls),
                "urls": urls
            }
        
        except Exception as e:
            logger.error(f"Error getting pending URLs: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    
    @app.get("/api/db/urls/all")
    async def get_all_urls(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
        """Get all URLs with pagination"""
        try:
            urls = db.get_all_urls(limit=limit, offset=offset)
            
            return {
                "success": True,
                "count": len(urls),
                "limit": limit,
                "offset": offset,
                "urls": urls
            }
        
        except Exception as e:
            logger.error(f"Error getting all URLs: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    
    @app.get("/api/db/stats")
    async def get_database_stats():
        """Get overall database statistics"""
        try:
            stats = db.get_database_stats()
            
            return {
                "success": True,
                "statistics": stats
            }
        
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    
    @app.get("/api/db/field-mapping")
    async def get_field_mapping():
        """Get field mapping summary from database"""
        try:
            mapping = db.get_field_mapping_summary()
            
            return {
                "success": True,
                "total_unique_fields": len(mapping),
                "field_mapping": mapping
            }
        
        except Exception as e:
            logger.error(f"Error getting field mapping: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    
    @app.get("/api/field-groups/all")
    async def get_all_field_groups():
        """Get all predefined field groups"""
        try:
            groups = FieldAnalyzer.get_all_field_groups()
            
            # Convert to list format for JSON
            groups_list = [
                {
                    'name': name,
                    'variations': config['variations'],
                    'description': config['description'],
                    'data_type': config['data_type'],
                    'example': config['example']
                }
                for name, config in groups.items()
            ]
            
            return {
                "success": True,
                "total_groups": len(groups_list),
                "field_groups": groups_list
            }
        
        except Exception as e:
            logger.error(f"Error getting field groups: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    
    @app.get("/api/field-groups/{field_name}")
    async def get_field_group(field_name: str):
        """Get specific field group details"""
        try:
            groups = FieldAnalyzer.get_all_field_groups()
            
            if field_name not in groups:
                raise HTTPException(status_code=404, detail=f"Field group '{field_name}' not found")
            
            config = groups[field_name]
            
            return {
                "success": True,
                "name": field_name,
                "variations": config['variations'],
                "description": config['description'],
                "data_type": config['data_type'],
                "example": config['example']
            }
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting field group: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    
    @app.post("/api/field-normalize")
    async def normalize_field(field_name: str = Query(...)):
        """Normalize a field name to standard format"""
        try:
            normalized = FieldAnalyzer.normalize_field_name(field_name)
            
            groups = FieldAnalyzer.get_all_field_groups()
            
            if normalized in groups:
                group_info = groups[normalized]
                return {
                    "success": True,
                    "original": field_name,
                    "normalized": normalized,
                    "description": group_info['description'],
                    "variations": group_info['variations'],
                    "data_type": group_info['data_type'],
                    "example": group_info['example']
                }
            else:
                return {
                    "success": True,
                    "original": field_name,
                    "normalized": normalized,
                    "description": "Unknown field - no predefined group",
                    "variations": [],
                    "data_type": "text"
                }
        
        except Exception as e:
            logger.error(f"Error normalizing field: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    
    @app.post("/api/urls/{url_id}/mark-processed")
    async def mark_url_processed(url_id: int, status: str = Query(...)):
        """Mark URL as processed"""
        try:
            db.update_url_status(url_id, status)
            
            return {
                "success": True,
                "message": f"URL {url_id} marked as {status}",
                "url_id": url_id,
                "status": status
            }
        
        except Exception as e:
            logger.error(f"Error marking URL: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    
    @app.get("/api/db/export")
    async def export_database(format: str = Query("json")):
        """Export database in various formats"""
        try:
            urls = db.get_all_urls()
            stats = db.get_database_stats()
            fields = db.get_field_mapping_summary()
            
            if format == "json":
                return {
                    "success": True,
                    "format": "json",
                    "statistics": stats,
                    "urls_count": len(urls),
                    "urls": urls,
                    "field_mapping": fields
                }
            else:
                raise HTTPException(status_code=400, detail="Unsupported format")
        
        except Exception as e:
            logger.error(f"Error exporting: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    
    @app.delete("/api/db/clear")
    async def clear_database():
        """Clear all database data (CAUTION!)"""
        try:
            # This is dangerous - uncomment only if needed
            # db.clear_all_data()
            
            return {
                "success": False,
                "message": "Database clearing disabled for safety. Manual intervention required."
            }
        
        except Exception as e:
            logger.error(f"Error clearing database: {e}")
            raise HTTPException(status_code=500, detail=str(e))
