# vmstatusagent/remediation_functions.py
"""
Remediation Agent Functions - Knowledge-based solutions for patch failures

These functions search the knowledge base for similar issues and generate remediation solutions.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import re

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContainerClient
from azure.core.exceptions import ResourceNotFoundError, AzureError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Shared credential function (avoid circular import)
_credential: Optional[DefaultAzureCredential] = None

def get_credential() -> DefaultAzureCredential:
    """
    Lazily create and cache Azure credential.
    """
    global _credential
    if _credential is None:
        _credential = DefaultAzureCredential()
    return _credential


def _get_blob_storage_client(connection_string: str, container_name: str) -> ContainerClient:
    """
    Get blob storage container client.
    
    Args:
        connection_string: Azure Storage connection string
        container_name: Container name
    
    Returns:
        ContainerClient instance
    """
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    return blob_service_client.get_container_client(container_name)


def search_knowledge_base(
    vm_name: str = None,
    resource_group: str = None,
    assessment_status: str = None,
    error_keywords: List[str] = None,
    max_results: int = 10
) -> Dict[str, Any]:
    """
    Search the knowledge base (blob storage) for similar patch failure cases.
    
    Args:
        vm_name: Optional VM name to filter
        resource_group: Optional resource group to filter
        assessment_status: Optional status to filter (Failed, InProgress, etc.)
        error_keywords: Optional list of keywords to search in responses
        max_results: Maximum number of results to return
    
    Returns:
        Dict with search results from knowledge base
    """
    logger.info(
        "Searching knowledge base: vm=%s rg=%s status=%s keywords=%s",
        vm_name, resource_group, assessment_status, error_keywords
    )
    
    try:
        # Get connection string from environment or config
        import os
        connection_string = os.environ.get("AzureWebJobsStorage")
        container_name = os.environ.get("KB_CONTAINER_NAME", "agent-knowledge-workspace-postpatch")
        
        if not connection_string:
            return {
                "error": "Storage connection string not configured",
                "results": []
            }
        
        container_client = _get_blob_storage_client(connection_string, container_name)
        
        # List all blobs in the responses directory
        blob_list = container_client.list_blobs(name_starts_with="responses/")
        
        matching_responses = []
        for blob in blob_list:
            try:
                # Download and parse blob content
                blob_client = container_client.get_blob_client(blob.name)
                blob_data = blob_client.download_blob().readall()
                response_data = json.loads(blob_data.decode('utf-8'))
                
                # Apply filters
                matches = True
                
                # Filter by VM name
                if vm_name and response_data.get("metadata", {}).get("vm_names"):
                    if vm_name.lower() not in [v.lower() for v in response_data["metadata"]["vm_names"]]:
                        matches = False
                
                # Filter by resource group
                if resource_group and response_data.get("metadata", {}).get("resource_group"):
                    if resource_group.lower() != response_data["metadata"]["resource_group"].lower():
                        matches = False
                
                # Filter by assessment status (search in response text)
                if assessment_status:
                    response_text = response_data.get("response", "").lower()
                    if assessment_status.lower() not in response_text:
                        matches = False
                
                # Filter by error keywords
                if error_keywords:
                    response_text = response_data.get("response", "").lower()
                    keyword_found = any(kw.lower() in response_text for kw in error_keywords)
                    if not keyword_found:
                        matches = False
                
                if matches:
                    matching_responses.append({
                        "blob_name": blob.name,
                        "timestamp": response_data.get("timestamp"),
                        "query": response_data.get("query"),
                        "response": response_data.get("response"),
                        "metadata": response_data.get("metadata", {}),
                        "conversation_id": response_data.get("conversation_id")
                    })
                    
                    if len(matching_responses) >= max_results:
                        break
                        
            except Exception as e:
                logger.warning(f"Error processing blob {blob.name}: {str(e)}")
                continue
        
        # Sort by timestamp (most recent first)
        matching_responses.sort(
            key=lambda x: x.get("timestamp", ""), 
            reverse=True
        )
        
        return {
            "total_results": len(matching_responses),
            "results": matching_responses,
            "search_criteria": {
                "vm_name": vm_name,
                "resource_group": resource_group,
                "assessment_status": assessment_status,
                "error_keywords": error_keywords
            }
        }
        
    except Exception as e:
        logger.error("Error searching knowledge base: %s", str(e), exc_info=True)
        return {
            "error": f"Failed to search knowledge base: {str(e)}",
            "results": []
        }


def extract_remediation_steps(kb_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract common remediation steps from knowledge base search results.
    
    Args:
        kb_results: List of knowledge base search results
    
    Returns:
        Dict with extracted remediation patterns and recommendations
    """
    logger.info("Extracting remediation steps from %d KB results", len(kb_results))
    
    # Common patterns to look for in responses
    remediation_patterns = {
        "reboot_required": r"reboot|restart.*vm|pending.*reboot",
        "disk_space": r"disk.*space|storage.*full|insufficient.*space",
        "network_issue": r"network|connectivity|endpoint|proxy",
        "agent_issue": r"agent.*not.*ready|agent.*failed|extension.*error",
        "permission_issue": r"permission|unauthorized|access.*denied",
        "patch_conflict": r"conflict|dependency|package.*error"
    }
    
    identified_issues = {}
    remediation_steps = []
    
    for result in kb_results:
        response_text = result.get("response", "").lower()
        
        # Check for each pattern
        for issue_type, pattern in remediation_patterns.items():
            if re.search(pattern, response_text, re.IGNORECASE):
                if issue_type not in identified_issues:
                    identified_issues[issue_type] = 0
                identified_issues[issue_type] += 1
    
    # Generate recommendations based on identified patterns
    if identified_issues.get("reboot_required", 0) > 0:
        remediation_steps.append({
            "priority": "high",
            "issue": "Reboot Required",
            "action": "Schedule VM reboot to complete pending updates",
            "occurrences": identified_issues["reboot_required"]
        })
    
    if identified_issues.get("disk_space", 0) > 0:
        remediation_steps.append({
            "priority": "high",
            "issue": "Insufficient Disk Space",
            "action": "Free up disk space or expand disk size",
            "occurrences": identified_issues["disk_space"]
        })
    
    if identified_issues.get("agent_issue", 0) > 0:
        remediation_steps.append({
            "priority": "high",
            "issue": "VM Agent Issues",
            "action": "Check VM Guest Agent status and reinstall if necessary",
            "occurrences": identified_issues["agent_issue"]
        })
    
    if identified_issues.get("network_issue", 0) > 0:
        remediation_steps.append({
            "priority": "medium",
            "issue": "Network Connectivity",
            "action": "Verify VM can reach Azure Update Management endpoints",
            "occurrences": identified_issues["network_issue"]
        })
    
    if identified_issues.get("permission_issue", 0) > 0:
        remediation_steps.append({
            "priority": "high",
            "issue": "Permission Issues",
            "action": "Review and update VM managed identity permissions",
            "occurrences": identified_issues["permission_issue"]
        })
    
    if identified_issues.get("patch_conflict", 0) > 0:
        remediation_steps.append({
            "priority": "medium",
            "issue": "Patch Conflicts",
            "action": "Review package dependencies and resolve conflicts",
            "occurrences": identified_issues["patch_conflict"]
        })
    
    # Sort by priority and occurrences
    priority_order = {"high": 0, "medium": 1, "low": 2}
    remediation_steps.sort(
        key=lambda x: (priority_order.get(x["priority"], 3), -x["occurrences"])
    )
    
    return {
        "total_kb_results_analyzed": len(kb_results),
        "issues_identified": identified_issues,
        "remediation_steps": remediation_steps,
        "has_recommendations": len(remediation_steps) > 0
    }


def generate_remediation_plan(
    vm_name: str,
    resource_group: str,
    diagnostic_results: Dict[str, Any],
    kb_search_results: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Generate a comprehensive remediation plan based on diagnostics and KB search.
    
    Args:
        vm_name: Virtual machine name
        resource_group: Resource group name
        diagnostic_results: Results from diagnostic_functions.diagnose_patch_failure()
        kb_search_results: Optional results from search_knowledge_base()
    
    Returns:
        Dict with comprehensive remediation plan
    """
    logger.info(
        "Generating remediation plan for VM: %s in RG: %s",
        vm_name, resource_group
    )
    
    plan = {
        "vm_name": vm_name,
        "resource_group": resource_group,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "remediation_actions": [],
        "kb_recommendations": [],
        "priority_order": []
    }
    
    # 1. Extract issues from diagnostic results
    diagnostic_issues = diagnostic_results.get("issues_found", [])
    diagnostic_recommendations = diagnostic_results.get("recommendations", [])
    
    # Add diagnostic-based actions
    for idx, issue in enumerate(diagnostic_issues):
        plan["remediation_actions"].append({
            "step": idx + 1,
            "source": "diagnostics",
            "issue": issue,
            "action": "Investigate and resolve",
            "priority": "high"
        })
    
    for idx, recommendation in enumerate(diagnostic_recommendations):
        plan["remediation_actions"].append({
            "step": len(diagnostic_issues) + idx + 1,
            "source": "diagnostics",
            "recommendation": recommendation,
            "priority": "medium"
        })
    
    # 2. Extract KB-based recommendations
    if kb_search_results and kb_search_results.get("results"):
        kb_analysis = extract_remediation_steps(kb_search_results["results"])
        
        for step in kb_analysis.get("remediation_steps", []):
            plan["kb_recommendations"].append({
                "issue": step["issue"],
                "action": step["action"],
                "priority": step["priority"],
                "kb_occurrences": step["occurrences"]
            })
    
    # 3. Prioritize actions
    high_priority = [
        action for action in plan["remediation_actions"] 
        if action.get("priority") == "high"
    ]
    medium_priority = [
        action for action in plan["remediation_actions"]
        if action.get("priority") == "medium"
    ]
    
    plan["priority_order"] = high_priority + medium_priority
    
    # 4. Generate summary
    plan["summary"] = {
        "total_actions": len(plan["remediation_actions"]),
        "high_priority_count": len(high_priority),
        "kb_recommendations_count": len(plan["kb_recommendations"]),
        "estimated_resolution_time": f"{len(high_priority) * 15}-{len(plan['remediation_actions']) * 10} minutes"
    }
    
    return plan


def save_remediation_result(
    vm_name: str,
    resource_group: str,
    remediation_plan: Dict[str, Any],
    outcome: str,
    notes: str = None
) -> Dict[str, Any]:
    """
    Save remediation results back to knowledge base for future reference.
    
    Args:
        vm_name: Virtual machine name
        resource_group: Resource group name
        remediation_plan: The remediation plan that was executed
        outcome: Outcome of remediation (success, partial, failed)
        notes: Optional notes about the remediation
    
    Returns:
        Dict with save confirmation
    """
    logger.info(
        "Saving remediation result: vm=%s rg=%s outcome=%s",
        vm_name, resource_group, outcome
    )
    
    try:
        import os
        connection_string = os.environ.get("AzureWebJobsStorage")
        container_name = os.environ.get("KB_CONTAINER_NAME", "agent-knowledge-workspace-postpatch")
        
        if not connection_string:
            return {
                "error": "Storage connection string not configured",
                "saved": False
            }
        
        container_client = _get_blob_storage_client(connection_string, container_name)
        
        # Create remediation record
        remediation_record = {
            "vm_name": vm_name,
            "resource_group": resource_group,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "remediation_plan": remediation_plan,
            "outcome": outcome,
            "notes": notes,
            "type": "remediation_result"
        }
        
        # Generate blob path: remediations/YYYY/MM/DD/vm_name_timestamp.json
        now = datetime.now(timezone.utc)
        blob_path = (
            f"remediations/{now.year}/{now.month:02d}/{now.day:02d}/"
            f"{vm_name}_{now.strftime('%Y%m%d_%H%M%S')}.json"
        )
        
        # Upload to blob storage
        blob_client = container_client.get_blob_client(blob_path)
        blob_client.upload_blob(
            json.dumps(remediation_record, indent=2),
            overwrite=True,
            metadata={
                "vm_name": vm_name,
                "resource_group": resource_group,
                "outcome": outcome,
                "timestamp": now.isoformat()
            }
        )
        
        logger.info(f"Saved remediation result to: {blob_path}")
        
        return {
            "saved": True,
            "blob_path": blob_path,
            "timestamp": now.isoformat()
        }
        
    except Exception as e:
        logger.error("Error saving remediation result: %s", str(e), exc_info=True)
        return {
            "error": f"Failed to save remediation result: {str(e)}",
            "saved": False
        }


def get_remediation_history(
    vm_name: str = None,
    resource_group: str = None,
    days: int = 30,
    max_results: int = 20
) -> Dict[str, Any]:
    """
    Get historical remediation attempts for a VM or resource group.
    
    Args:
        vm_name: Optional VM name to filter
        resource_group: Optional resource group to filter
        days: Number of days to look back (default 30)
        max_results: Maximum number of results to return
    
    Returns:
        Dict with historical remediation records
    """
    logger.info(
        "Getting remediation history: vm=%s rg=%s days=%d",
        vm_name, resource_group, days
    )
    
    try:
        import os
        connection_string = os.environ.get("AzureWebJobsStorage")
        container_name = os.environ.get("KB_CONTAINER_NAME", "agent-knowledge-workspace-postpatch")
        
        if not connection_string:
            return {
                "error": "Storage connection string not configured",
                "results": []
            }
        
        container_client = _get_blob_storage_client(connection_string, container_name)
        
        # List all blobs in the remediations directory
        blob_list = container_client.list_blobs(name_starts_with="remediations/")
        
        matching_remediations = []
        cutoff_date = datetime.now(timezone.utc).timestamp() - (days * 24 * 60 * 60)
        
        for blob in blob_list:
            try:
                # Check timestamp
                if blob.last_modified.timestamp() < cutoff_date:
                    continue
                
                # Download and parse blob content
                blob_client = container_client.get_blob_client(blob.name)
                blob_data = blob_client.download_blob().readall()
                remediation_data = json.loads(blob_data.decode('utf-8'))
                
                # Apply filters
                if vm_name and remediation_data.get("vm_name", "").lower() != vm_name.lower():
                    continue
                
                if resource_group and remediation_data.get("resource_group", "").lower() != resource_group.lower():
                    continue
                
                matching_remediations.append({
                    "blob_name": blob.name,
                    "vm_name": remediation_data.get("vm_name"),
                    "resource_group": remediation_data.get("resource_group"),
                    "timestamp": remediation_data.get("timestamp"),
                    "outcome": remediation_data.get("outcome"),
                    "notes": remediation_data.get("notes"),
                    "actions_taken": len(remediation_data.get("remediation_plan", {}).get("remediation_actions", []))
                })
                
                if len(matching_remediations) >= max_results:
                    break
                    
            except Exception as e:
                logger.warning(f"Error processing blob {blob.name}: {str(e)}")
                continue
        
        # Sort by timestamp (most recent first)
        matching_remediations.sort(
            key=lambda x: x.get("timestamp", ""),
            reverse=True
        )
        
        # Calculate statistics
        if matching_remediations:
            success_count = sum(1 for r in matching_remediations if r.get("outcome") == "success")
            success_rate = (success_count / len(matching_remediations)) * 100
        else:
            success_rate = 0
        
        return {
            "total_results": len(matching_remediations),
            "results": matching_remediations,
            "statistics": {
                "success_rate": f"{success_rate:.1f}%",
                "total_remediations": len(matching_remediations),
                "days_analyzed": days
            }
        }
        
    except Exception as e:
        logger.error("Error getting remediation history: %s", str(e), exc_info=True)
        return {
            "error": f"Failed to get remediation history: {str(e)}",
            "results": []
        }
