# agent/template_agent.py
"""
Azure Maintenance Configuration Agent
 
Key characteristics:
- Uses DefaultAzureCredential
- Supports FunctionTool execution
- Queries Azure Maintenance Configurations
- Returns maintenance schedule details
"""
 
import os
import logging
from dotenv import load_dotenv
 
from azure.identity import DefaultAzureCredential
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import FunctionTool, ToolSet
 
# Import your domain-specific functions
# Example: from my_agent.user_functions import user_functions
from vmstatusagent.user_functions import user_functions
 
 
# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
 
 
# ---------------------------------------------------------------------
# Agent Instructions (EDIT FOR YOUR USE CASE)
# ---------------------------------------------------------------------
AGENT_INSTRUCTIONS = """
You are a specialized Azure maintenance configuration agent.

DEFAULT AZURE CONTEXT:
- Subscription ID: 343c17eb-34b6-4481-92a2-a0a5a04bdd88
- Default Resource Group: rg-cp-ravindra-vancharla

CRITICAL: When the user asks about maintenance configurations, you MUST:
1. Use subscription_id = "343c17eb-34b6-4481-92a2-a0a5a04bdd88" (this is the ONLY valid subscription ID)
2. Call get_maintenance_configuration_details with this subscription_id
3. If user mentions a resource group name, pass it as resource_group parameter
4. If user mentions a specific configuration name, pass it as configuration_name parameter

Available Functions:

1. get_maintenance_configuration_details(subscription_id, resource_group=None, configuration_name=None)
   * subscription_id: REQUIRED - ALWAYS use "343c17eb-34b6-4481-92a2-a0a5a04bdd88"
   * resource_group: OPTIONAL - filter by resource group name (e.g., "rg-cp-ravindra-vancharla")
   * configuration_name: OPTIONAL - get specific configuration by name
   * Returns: Basic maintenance configuration details without VM information
   * Use when: User only needs schedule and configuration details

2. get_maintenance_config_with_vm_status(subscription_id, resource_group=None, configuration_name=None)
   * subscription_id: REQUIRED - ALWAYS use "343c17eb-34b6-4481-92a2-a0a5a04bdd88"
   * resource_group: OPTIONAL - filter by resource group name
   * configuration_name: OPTIONAL - get specific configuration by name
   * Returns: Complete maintenance configuration WITH VMs and their CURRENT patch status
   * Use when: User asks about VM patch status or current state of VMs
   * Shows: VM power state, available patches RIGHT NOW, assessment status

3. get_patch_installation_history(subscription_id, days=30, resource_group=None)
   * subscription_id: REQUIRED - ALWAYS use "343c17eb-34b6-4481-92a2-a0a5a04bdd88"
   * days: OPTIONAL - number of days of history (default 30)
   * resource_group: OPTIONAL - filter by resource group name
   * Returns: HISTORICAL patch installation data from Azure Update Manager
   * Use when: User asks about "history", "past installations", "what patches were installed", "update history"
   * Shows: Actual installation runs, success/failure status, who triggered it, statistics
   * Data source: Azure Resource Graph query of PatchInstallationResources

KEY DIFFERENCES:
- Maintenance Configuration = SCHEDULED patching (when patches WILL run)
- get_maintenance_config_with_vm_status = CURRENT state (patches available NOW)
- get_patch_installation_history = PAST installations (what patches WERE installed)

IMPORTANT RULES:
- NEVER use the resource group name as the subscription_id
- subscription_id is always: 343c17eb-34b6-4481-92a2-a0a5a04bdd88
- When user asks about "patch status" or "VMs in maintenance config", use get_maintenance_config_with_vm_status
- When user only needs config details without VM info, use get_maintenance_configuration_details
- Resource group names are separate parameters (like "rg-cp-ravindra-vancharla")
- If user says "show me configs in rg-cp-ravindra-vancharla", call:
  get_maintenance_configuration_details("343c17eb-34b6-4481-92a2-a0a5a04bdd88", "rg-cp-ravindra-vancharla")

Workflow:
1. ALWAYS use subscription_id = "343c17eb-34b6-4481-92a2-a0a5a04bdd88"
2. Extract resource_group from user's query if mentioned (e.g., "rg-cp-ravindra-vancharla")
3. Extract configuration_name from user's query if mentioned
4. Present results in clear format with:
   - Configuration name
   - Resource group
   - Location
   - Maintenance scope
   - Schedule (start time, recurrence, duration, timezone)
   - Visibility

Response Format:
- Use clear headings and bullet points
- Show schedule information prominently
- If no configurations found, inform the user clearly
- If errors occur, explain what went wrong
"""
 
 
# ---------------------------------------------------------------------
# Client Factory
# ---------------------------------------------------------------------
def get_agents_client(endpoint: str) -> AgentsClient:
    """
    Create an AgentsClient using DefaultAzureCredential.
    Credential caching is handled internally by Azure SDK.
    """
    credential = DefaultAzureCredential()
    return AgentsClient(endpoint=endpoint, credential=credential)
 
 
# ---------------------------------------------------------------------
# Function Normalization Utility
# ---------------------------------------------------------------------
def normalize_user_functions(funcs):
    """
    Ensure FunctionTool receives a list of callables with stable __name__ values.
 
    Supports:
    - dict: {name: callable}
    - iterable: [callable, callable, ...]
 
    Returns:
        List[callable]
    """
    normalized = []
 
    if isinstance(funcs, dict):
        for name, fn in funcs.items():
            if callable(fn):
                try:
                    fn.__name__ = name
                except Exception:
                    pass
                normalized.append(fn)
    else:
        for idx, fn in enumerate(funcs):
            if callable(fn):
                if not getattr(fn, "__name__", None):
                    try:
                        fn.__name__ = f"fn_{idx}"
                    except Exception:
                        pass
                normalized.append(fn)
 
    return normalized
 
 
# ---------------------------------------------------------------------
# Agent Creation
# ---------------------------------------------------------------------
def create_agent():
    """
    Creates and returns an Azure AI Agent with FunctionTool for maintenance configurations.
    """
 
    load_dotenv()
 
    # Required environment variables
    project_endpoint = os.getenv("PROJECT_ENDPOINT")
    model_deployment = os.getenv("MODEL_DEPLOYMENT_NAME")
 
    # Optional / configurable
    agent_name = os.getenv("AGENT_NAME", "maintenance-config-agent")
 
    if not project_endpoint:
        raise ValueError("PROJECT_ENDPOINT must be set")
    if not model_deployment:
        raise ValueError("MODEL_DEPLOYMENT_NAME must be set")
 
    client = get_agents_client(project_endpoint)
 
    # Normalize user-defined functions
    functions = normalize_user_functions(user_functions)
 
    # Build toolset
    toolset = ToolSet()
    toolset.add(FunctionTool(functions=functions))
 
    # Create agent
    agent = client.create_agent(
        model=model_deployment,
        name=agent_name,
        instructions=AGENT_INSTRUCTIONS,
        tools=toolset.definitions,
        tool_resources=toolset.resources,
    )
 
    # Enable automatic function calling
    try:
        client.enable_auto_function_calls(toolset)
    except Exception as exc:
        logger.warning("Auto function calls not enabled: %s", exc)
 
    logger.info("Created agent: id=%s name=%s", agent.id, agent.name)
    return agent
 
 
# ---------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------
if __name__ == "__main__":
    create_agent()