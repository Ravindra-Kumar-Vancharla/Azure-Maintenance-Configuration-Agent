"""
Configuration Management for Azure Function App
Centralized configuration with environment variables and validation
"""
import os
import logging

logger = logging.getLogger(__name__)


class Config:
    """Application configuration with validation"""
    
    # Azure AI Agent Configuration
    PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")
    AGENT_ID = os.getenv("AGENT_ID")
    
    # Azure Resources
    AZURE_SUBSCRIPTION_ID = os.getenv("AZURE_SUBSCRIPTION_ID")
    AZURE_RESOURCE_GROUP = os.getenv("AZURE_RESOURCE_GROUP")
    
    # Knowledge Base / Response Logging
    ENABLE_RESPONSE_LOGGING = os.getenv("ENABLE_RESPONSE_LOGGING", "true").lower() == "true"
    STORAGE_ACCOUNT_NAME = os.getenv("AZURE_STORAGE_ACCOUNT_NAME", "azurepatchautomation")
    STORAGE_CONNECTION_STRING = os.getenv("AzureWebJobsStorage")  # Reuse function app storage
    KNOWLEDGE_BASE_CONTAINER = os.getenv("KNOWLEDGE_BASE_CONTAINER", "agent-knowledge-workspace-postpatch")
    LOG_SCHEMA_VERSION = os.getenv("LOG_SCHEMA_VERSION", "1.0")
    
    # Application Metadata
    FUNCTION_VERSION = "1.0.0"
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        required = {
            "PROJECT_ENDPOINT": cls.PROJECT_ENDPOINT,
            "AGENT_ID": cls.AGENT_ID,
        }
        
        missing = [key for key, value in required.items() if not value]
        
        if missing:
            logger.warning(f"Missing required configuration: {', '.join(missing)}")
            return False
        
        # Validate optional logging config
        if cls.ENABLE_RESPONSE_LOGGING:
            if not cls.STORAGE_CONNECTION_STRING:
                logger.warning("Response logging enabled but no storage connection string found")
                cls.ENABLE_RESPONSE_LOGGING = False
            else:
                logger.info(f"Response logging enabled: container='{cls.KNOWLEDGE_BASE_CONTAINER}'")
        else:
            logger.info("Response logging disabled")
        
        return True
    
    @classmethod
    def get_logging_config(cls):
        """Get logging-specific configuration"""
        return {
            "enabled": cls.ENABLE_RESPONSE_LOGGING,
            "container": cls.KNOWLEDGE_BASE_CONTAINER,
            "connection_string": cls.STORAGE_CONNECTION_STRING,
            "schema_version": cls.LOG_SCHEMA_VERSION,
            "function_version": cls.FUNCTION_VERSION
        }
