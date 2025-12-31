"""
Azure Functions v2 - Agent Gateway
Routes HTTP requests to Azure AI Foundry Agent
"""
import logging
import json
import os
import sys
import time
import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import ToolSet, FunctionTool, MessageRole

# Add parent directory to path to import agent functions
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Lazy import to avoid startup errors
user_functions = None

# Optional: Knowledge base logging (gracefully handles missing dependencies)
_response_logger = None
try:
    from response_logger import get_response_logger
    LOGGING_AVAILABLE = True
    logging.info("Knowledge base logging module loaded")
except Exception as e:
    LOGGING_AVAILABLE = False
    logging.info(f"Knowledge base logging not available: {e}")

app = func.FunctionApp()

_credential = None
_client = None

def get_user_functions():
    """Lazy load user functions"""
    global user_functions
    if user_functions is None:
        from vmstatusagent.user_functions import user_functions as uf
        user_functions = uf
    return user_functions

def get_agents_client():
    global _credential, _client
    if _client is None:
        _credential = DefaultAzureCredential()
        _client = AgentsClient(
            endpoint=os.getenv("PROJECT_ENDPOINT"),
            credential=_credential
        )
    return _client


@app.route(route="query", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def query_agent(req: func.HttpRequest) -> func.HttpResponse:
    """POST /api/query - Send query to agent"""
    start_time = time.time()
    
    try:
        req_body = req.get_json()
        user_query = req_body.get('query')
        thread_id = req_body.get('conversation_id')
        
        if not user_query:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'query' field"}),
                status_code=400,
                mimetype="application/json"
            )
        
        agent_id = os.getenv("AGENT_ID")
        subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID", "")
        resource_group = os.getenv("AZURE_RESOURCE_GROUP", "")
        
        # Add context
        full_query = user_query
        if subscription_id:
            full_query += f"\n\nContext: subscription_id={subscription_id}"
            if resource_group:
                full_query += f", resource_group={resource_group}"
        
        # Run agent
        client = get_agents_client()
        toolset = ToolSet()
        toolset.add(FunctionTool(functions=list(get_user_functions().values())))
        
        client.update_agent(agent_id=agent_id, tools=toolset.definitions, tool_resources=toolset.resources)
        client.enable_auto_function_calls(toolset)
        
        if thread_id:
            thread = client.threads.get(thread_id)
        else:
            thread = client.threads.create()
        
        client.messages.create(thread_id=thread.id, role="user", content=full_query)
        run = client.runs.create_and_process(thread_id=thread.id, agent_id=agent_id)
        msg = client.messages.get_last_message_text_by_role(thread_id=thread.id, role=MessageRole.AGENT)
        
        # Prepare response
        response_text = msg.text.value if msg and msg.text else "No response"
        response_status = str(run.status)
        execution_time = int((time.time() - start_time) * 1000)  # milliseconds
        
        # Log response to knowledge base (non-blocking, graceful failure)
        if LOGGING_AVAILABLE:
            try:
                logger = get_response_logger()
                logger.log_response(
                    query=user_query,
                    response=response_text,
                    conversation_id=thread.id,
                    status=response_status,
                    execution_time_ms=execution_time
                )
                logging.info(f"Response logged to knowledge base")
            except Exception as log_error:
                logging.warning(f"Failed to log response: {log_error}")
                # Continue - logging should never break the function
        
        return func.HttpResponse(
            json.dumps({
                "response": response_text,
                "conversation_id": thread.id,
                "status": response_status
            }, indent=2),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.exception("Error")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )


@app.route(route="multiagent", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def multiagent_query(req: func.HttpRequest) -> func.HttpResponse:
    """POST /api/multiagent - Multi-agent orchestration for patch diagnostics and remediation"""
    start_time = time.time()
    
    try:
        req_body = req.get_json()
        subscription_id = req_body.get('subscription_id', os.getenv("AZURE_SUBSCRIPTION_ID"))
        resource_group = req_body.get('resource_group', os.getenv("AZURE_RESOURCE_GROUP"))
        configuration_name = req_body.get('configuration_name')
        enable_diagnostics = req_body.get('enable_diagnostics', True)
        enable_remediation = req_body.get('enable_remediation', True)
        
        if not subscription_id:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'subscription_id' field"}),
                status_code=400,
                mimetype="application/json"
            )
        
        orchestration_result = {
            "subscription_id": subscription_id,
            "resource_group": resource_group,
            "configuration_name": configuration_name,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "agents_executed": [],
            "execution_flow": []
        }
        
        # PHASE 1: Patch Status Agent
        logging.info("Phase 1: Running Patch Status Agent - Getting structured VM status")
        orchestration_result["execution_flow"].append("Phase 1: Patch Status Assessment")
        
        # Step 1: Get structured JSON data directly from function
        from vmstatusagent.user_functions import get_vm_patch_status_json
        
        vm_status_data = get_vm_patch_status_json(
            subscription_id=subscription_id,
            resource_group=resource_group,
            configuration_name=configuration_name
        )
        
        # Check for errors in structured data
        if "error" in vm_status_data:
            return func.HttpResponse(
                json.dumps({
                    "error": "Failed to get VM patch status",
                    "details": vm_status_data.get("error")
                }),
                status_code=500,
                mimetype="application/json"
            )
        
        # Extract failed VMs from structured data
        failed_vms = vm_status_data.get("failed_vms", [])
        orchestration_result["failed_vms_detected"] = len(failed_vms)
        orchestration_result["failed_vms"] = failed_vms
        orchestration_result["vm_status_summary"] = {
            "total_vms": vm_status_data.get("total_vms", 0),
            "failed_count": len(failed_vms),
            "succeeded_count": vm_status_data.get("total_vms", 0) - len(failed_vms)
        }
        
        # Step 2: Also get human-readable response from agent for logging
        patch_query = f"Show me the patch assessment status for all VMs"
        if configuration_name:
            patch_query += f" in {configuration_name} maintenance configuration"
        else:
            patch_query += f" in subscription {subscription_id}"
            if resource_group:
                patch_query += f" in resource group {resource_group}"
        
        client = get_agents_client()
        agent_id = os.getenv("AGENT_ID")
        toolset = ToolSet()
        toolset.add(FunctionTool(functions=list(get_user_functions().values())))
        
        client.update_agent(agent_id=agent_id, tools=toolset.definitions, tool_resources=toolset.resources)
        client.enable_auto_function_calls(toolset)
        
        thread = client.threads.create()
        client.messages.create(thread_id=thread.id, role="user", content=patch_query)
        run = client.runs.create_and_process(thread_id=thread.id, agent_id=agent_id)
        msg = client.messages.get_last_message_text_by_role(thread_id=thread.id, role=MessageRole.AGENT)
        
        patch_status_response = msg.text.value if msg and msg.text else "No response"
        orchestration_result["patch_status_response"] = patch_status_response
        orchestration_result["agents_executed"].append("Patch Status Agent")
        
        # PHASE 2: Diagnostic Agent (if failures detected and enabled)
        if failed_vms and enable_diagnostics:
            logging.info("Phase 2: Running Diagnostic Agent for %d failed VMs", len(failed_vms))
            orchestration_result["execution_flow"].append(f"Phase 2: Diagnostics for {len(failed_vms)} failed VM(s)")
            orchestration_result["agents_executed"].append("Diagnostic Agent")
            
            diagnostic_results = []
            for vm_info in failed_vms[:5]:  # Limit to first 5 VMs to avoid timeout
                vm_name = vm_info.get("vm_name")
                vm_rg = vm_info.get("resource_group", resource_group)
                assessment_status = vm_info.get("assessment_status")
                
                diag_query = f"Run comprehensive diagnostics on VM {vm_name} in resource group {vm_rg} with assessment status {assessment_status}"
                
                # Create new thread for diagnostic agent
                diag_thread = client.threads.create()
                client.messages.create(thread_id=diag_thread.id, role="user", content=diag_query)
                diag_run = client.runs.create_and_process(thread_id=diag_thread.id, agent_id=agent_id)
                diag_msg = client.messages.get_last_message_text_by_role(thread_id=diag_thread.id, role=MessageRole.AGENT)
                
                diagnostic_results.append({
                    "vm_name": vm_name,
                    "resource_group": vm_rg,
                    "diagnostic_response": diag_msg.text.value if diag_msg and diag_msg.text else "No response"
                })
            
            orchestration_result["diagnostic_results"] = diagnostic_results
        
        # PHASE 3: Remediation Agent (if diagnostics ran and enabled)
        if failed_vms and enable_remediation:
            logging.info("Phase 3: Running Remediation Agent with KB search")
            orchestration_result["execution_flow"].append("Phase 3: Remediation Planning with Knowledge Base")
            orchestration_result["agents_executed"].append("Remediation Agent")
            
            remediation_plans = []
            for vm_info in failed_vms[:5]:  # Limit to first 5 VMs
                vm_name = vm_info.get("vm_name")
                vm_rg = vm_info.get("resource_group", resource_group)
                assessment_status = vm_info.get("assessment_status")
                
                remediation_query = (
                    f"Search knowledge base for similar patch failures on VM {vm_name} "
                    f"with status {assessment_status} and generate remediation plan"
                )
                
                # Create new thread for remediation agent
                rem_thread = client.threads.create()
                client.messages.create(thread_id=rem_thread.id, role="user", content=remediation_query)
                rem_run = client.runs.create_and_process(thread_id=rem_thread.id, agent_id=agent_id)
                rem_msg = client.messages.get_last_message_text_by_role(thread_id=rem_thread.id, role=MessageRole.AGENT)
                
                remediation_plans.append({
                    "vm_name": vm_name,
                    "resource_group": vm_rg,
                    "remediation_response": rem_msg.text.value if rem_msg and rem_msg.text else "No response"
                })
            
            orchestration_result["remediation_plans"] = remediation_plans
        
        # Log orchestration result to knowledge base
        if LOGGING_AVAILABLE:
            try:
                logger = get_response_logger()
                logger.log_response(
                    query=f"Multi-agent orchestration: {subscription_id}/{resource_group}/{configuration_name}",
                    response=json.dumps(orchestration_result),
                    conversation_id=f"multiagent_{thread.id}",
                    status="completed",
                    execution_time_ms=int((time.time() - start_time) * 1000)
                )
            except Exception as log_error:
                logging.warning(f"Failed to log orchestration result: {log_error}")
        
        execution_time = int((time.time() - start_time) * 1000)
        orchestration_result["execution_time_ms"] = execution_time
        orchestration_result["execution_time"] = f"{execution_time / 1000:.2f}s"
        
        return func.HttpResponse(
            json.dumps(orchestration_result, indent=2),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.exception("Error in multi-agent orchestration")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )


def _extract_failed_vms_from_response(response_text: str) -> list:
    """
    Extract failed VMs from patch status agent response.
    Handles both table format and numbered list format.
    Returns list of dicts with vm_name, resource_group, assessment_status
    """
    import re
    failed_vms = []
    lines = response_text.split('\n')
    
    # Strategy 1: Parse markdown table format
    # Look for lines with pipe separators and "Failed" status
    for line in lines:
        if '|' in line and 'Failed' in line:
            # Skip header rows
            if '---' in line or 'VM Name' in line or 'Assessment Status' in line:
                continue
            cells = [cell.strip() for cell in line.split('|')]
            cells = [c for c in cells if c]  # Remove empty cells
            
            if len(cells) >= 3:
                vm_name = cells[0]
                # Check if assessment status column (usually 3rd) contains "Failed"
                if 'Failed' in cells[2]:
                    if not any(vm['vm_name'] == vm_name for vm in failed_vms):
                        failed_vms.append({
                            "vm_name": vm_name,
                            "resource_group": None,
                            "assessment_status": "Failed"
                        })
    
    # Strategy 2: Parse numbered list format and markdown headers
    # Look for "1. **VM Name:** vmname" or "#### 1. vmname" followed by "Patch Assessment Status: **Failed**"
    current_vm = None
    current_rg = None
    
    for i, line in enumerate(lines):
        # Match: "1. **VM Name:** ubuntutestserver"
        vm_match = re.search(r'^\d+\.\s+\*\*VM Name:\*\*\s+(.+?)\s*$', line)
        if vm_match:
            current_vm = vm_match.group(1).strip()
            current_rg = None  # Reset RG for new VM
        
        # Match: "#### 1. VM: **ubuntutestserver**" or "#### 1. ubuntutestserver"
        vm_header_match = re.search(r'^#{2,4}\s+(?:\d+\.\s+)?(?:VM:\s+)?\*?\*?([a-zA-Z0-9][\w\-]+)\*?\*?\s*$', line)
        if vm_header_match:
            potential_vm = vm_header_match.group(1).strip()
            # VM name extracted, set as current
            current_vm = potential_vm
            current_rg = None  # Reset RG for new VM
        
        # Try to extract Resource Group if mentioned near VM
        if current_vm and not current_rg:
            rg_match = re.search(r'Resource Group:\s*([A-Za-z0-9\-_]+)', line, re.IGNORECASE)
            if rg_match:
                current_rg = rg_match.group(1).strip()
        
        # Match: "- **Assessment Status:** **Failed**" or "- Patch Assessment Status: **Failed**"
        if current_vm and re.search(r'(?:-\s+)?\*?\*?(?:Last\s+)?(?:Patch\s+)?Assessment Status:\*?\*?\s+\*\*Failed\*\*', line):
            if not any(vm['vm_name'] == current_vm for vm in failed_vms):
                failed_vms.append({
                    "vm_name": current_vm,
                    "resource_group": current_rg,
                    "assessment_status": "Failed"
                })
            current_vm = None  # Reset after finding
            current_rg = None
    
    return failed_vms


@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    """GET /api/health - Health check"""
    return func.HttpResponse(
        json.dumps({"status": "healthy"}),
        status_code=200,
        mimetype="application/json"
    )
