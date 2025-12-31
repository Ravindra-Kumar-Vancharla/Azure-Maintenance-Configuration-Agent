"""
Response Logger for Knowledge Base
Stores agent responses in Azure Blob Storage for future analysis and AI Search indexing
"""
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import re

logger = logging.getLogger(__name__)

# Try to import Azure Storage dependencies
try:
    from azure.storage.blob import BlobServiceClient, ContainerClient
    from azure.core.exceptions import ResourceExistsError, AzureError
    from config import Config
    AZURE_STORAGE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Azure Storage blob dependencies not available: {e}")
    AZURE_STORAGE_AVAILABLE = False
    Config = None


class ResponseLogger:
    """Logs agent responses to Azure Blob Storage"""
    
    def __init__(self):
        """Initialize blob storage client"""
        if not AZURE_STORAGE_AVAILABLE:
            self.enabled = False
            logger.info("ResponseLogger disabled - Azure Storage dependencies not available")
            return
            
        self.config = Config.get_logging_config()
        self.enabled = self.config["enabled"]
        self._container_client: Optional[ContainerClient] = None
        
        if self.enabled:
            try:
                blob_service_client = BlobServiceClient.from_connection_string(
                    self.config["connection_string"]
                )
                self._container_client = blob_service_client.get_container_client(
                    self.config["container"]
                )
                # Ensure container exists
                self._ensure_container()
                logger.info(f"ResponseLogger initialized: container='{self.config['container']}'")
            except Exception as e:
                logger.error(f"Failed to initialize ResponseLogger: {e}")
                self.enabled = False
    
    def _ensure_container(self):
        """Ensure the blob container exists"""
        try:
            self._container_client.create_container()
            logger.info(f"Created container: {self.config['container']}")
        except ResourceExistsError:
            logger.debug(f"Container already exists: {self.config['container']}")
        except Exception as e:
            logger.error(f"Error ensuring container exists: {e}")
            raise
    
    def _extract_metadata(self, query: str, response: str) -> Dict[str, Any]:
        """Extract metadata from query and response for indexing"""
        metadata = {
            "maintenance_configs": [],
            "vms": [],
            "resource_group": None,
            "subscription_id": None,
            "patch_keywords": []
        }
        
        # Extract maintenance configuration names (pattern: alphanumeric + hyphens)
        config_pattern = r'\b([a-z0-9]+-?[a-z0-9]+(?:patchschedule|schedule|config))\b'
        configs = re.findall(config_pattern, response.lower())
        metadata["maintenance_configs"] = list(set(configs))
        
        # Extract VM names (common patterns)
        vm_patterns = [
            r'\*\*([a-z0-9-]+server[a-z0-9]*)\*\*',  # **vmname**
            r'VM:\s*([a-z0-9-]+)',  # VM: vmname
        ]
        vms = []
        for pattern in vm_patterns:
            vms.extend(re.findall(pattern, response.lower()))
        metadata["vms"] = list(set(vms))
        
        # Extract resource group
        rg_match = re.search(r'rg-[a-z0-9-]+', response.lower())
        if rg_match:
            metadata["resource_group"] = rg_match.group(0)
        
        # Extract subscription ID
        sub_match = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', response.lower())
        if sub_match:
            metadata["subscription_id"] = sub_match.group(0)
        
        # Extract patch-related keywords
        keywords = ["failed", "succeeded", "pending", "critical", "security", "reboot", "available patches"]
        for keyword in keywords:
            if keyword in response.lower():
                metadata["patch_keywords"].append(keyword)
        
        return metadata
    
    def _create_blob_path(self, timestamp: datetime, conversation_id: str) -> str:
        """Create hierarchical blob path: responses/YYYY/MM/DD/timestamp-conversation_id.json"""
        date_path = timestamp.strftime("%Y/%m/%d")
        timestamp_str = timestamp.strftime("%Y%m%d-%H%M%S-%f")[:-3]  # milliseconds
        filename = f"{timestamp_str}-{conversation_id}.json"
        return f"responses/{date_path}/{filename}"
    
    async def log_response_async(
        self,
        query: str,
        response: str,
        conversation_id: str,
        status: str,
        execution_time_ms: Optional[int] = None
    ) -> bool:
        """
        Log agent response to blob storage (async version)
        
        Args:
            query: User's query
            response: Agent's response
            conversation_id: Thread/conversation ID
            status: Response status (e.g., 'RunStatus.COMPLETED')
            execution_time_ms: Execution time in milliseconds
            
        Returns:
            bool: True if logged successfully, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            timestamp = datetime.now(timezone.utc)
            metadata = self._extract_metadata(query, response)
            
            # Create log entry
            log_entry = {
                "version": self.config["schema_version"],
                "timestamp": timestamp.isoformat(),
                "conversation_id": conversation_id,
                "request": {
                    "query": query,
                    "user_id": None,  # Future enhancement
                    "session_id": None  # Future enhancement
                },
                "response": {
                    "content": response,
                    "status": status,
                    "tokens_used": None  # Future enhancement
                },
                "metadata": {
                    "function_version": self.config["function_version"],
                    "execution_time_ms": execution_time_ms,
                    "extracted_entities": metadata
                },
                "indexing": {
                    "indexed": False,  # Future: AI Search integration
                    "index_version": None
                }
            }
            
            # Create blob path and upload
            blob_path = self._create_blob_path(timestamp, conversation_id)
            blob_client = self._container_client.get_blob_client(blob_path)
            
            # Upload as JSON
            json_data = json.dumps(log_entry, indent=2, ensure_ascii=False)
            await blob_client.upload_blob(json_data, overwrite=False)
            
            logger.info(f"Response logged successfully: {blob_path}")
            return True
            
        except AzureError as e:
            logger.error(f"Azure error logging response: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error logging response: {e}")
            return False
    
    def log_response(
        self,
        query: str,
        response: str,
        conversation_id: str,
        status: str,
        execution_time_ms: Optional[int] = None
    ) -> bool:
        """
        Log agent response to blob storage (sync version)
        
        Args:
            query: User's query
            response: Agent's response
            conversation_id: Thread/conversation ID
            status: Response status
            execution_time_ms: Execution time in milliseconds
            
        Returns:
            bool: True if logged successfully, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            timestamp = datetime.now(timezone.utc)
            metadata = self._extract_metadata(query, response)
            
            log_entry = {
                "version": self.config["schema_version"],
                "timestamp": timestamp.isoformat(),
                "conversation_id": conversation_id,
                "request": {
                    "query": query,
                    "user_id": None,
                    "session_id": None
                },
                "response": {
                    "content": response,
                    "status": status,
                    "tokens_used": None
                },
                "metadata": {
                    "function_version": self.config["function_version"],
                    "execution_time_ms": execution_time_ms,
                    "extracted_entities": metadata
                },
                "indexing": {
                    "indexed": False,
                    "index_version": None
                }
            }
            
            blob_path = self._create_blob_path(timestamp, conversation_id)
            blob_client = self._container_client.get_blob_client(blob_path)
            json_data = json.dumps(log_entry, indent=2, ensure_ascii=False)
            blob_client.upload_blob(json_data, overwrite=False)
            
            logger.info(f"Response logged: {blob_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error logging response: {e}")
            return False


# Global instance
_logger_instance: Optional[ResponseLogger] = None


def get_response_logger() -> ResponseLogger:
    """Get or create the global ResponseLogger instance"""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = ResponseLogger()
    return _logger_instance
