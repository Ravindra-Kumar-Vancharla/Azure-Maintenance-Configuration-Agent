# agent.py
"""
Azure Maintenance Configuration Agent Runner

This module provides the runtime execution logic for the maintenance configuration agent.
It handles agent initialization, function attachment, thread management, and message processing.
"""
import os
import logging
from typing import List, Callable, Dict, Any
from dotenv import load_dotenv

from azure.identity import DefaultAzureCredential
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import ToolSet, FunctionTool, MessageRole

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ------------------------------------------------
# Cached Client (Singleton Pattern)
# ------------------------------------------------
_credential = None
_client = None


def get_agents_client() -> AgentsClient:
    """
    Get or create a cached AgentsClient instance.
    Uses DefaultAzureCredential for authentication.
    
    Returns:
        AgentsClient: Initialized Azure AI Agents client
        
    Raises:
        ValueError: If PROJECT_ENDPOINT is not set in environment
    """
    global _credential, _client

    if _credential is None:
        _credential = DefaultAzureCredential()

    if _client is None:
        endpoint = os.getenv("PROJECT_ENDPOINT")
        if not endpoint:
            raise ValueError("PROJECT_ENDPOINT environment variable must be set")
        _client = AgentsClient(endpoint=endpoint, credential=_credential)
        logger.info("Initialized AgentsClient for endpoint: %s", endpoint)

    return _client


# ------------------------------------------------
# Toolset Builder
# ------------------------------------------------
def build_toolset(functions: List[Callable]) -> ToolSet:
    """
    Build a ToolSet with FunctionTool from provided callable functions.
    
    Args:
        functions: List of callable functions to be used as tools
        
    Returns:
        ToolSet: Configured toolset with function tools
    """
    toolset = ToolSet()

    # Ensure stable function names for proper tool registration
    for i, fn in enumerate(functions):
        if not hasattr(fn, "__name__") or not fn.__name__:
            fn.__name__ = f"function_{i}"
            logger.warning("Function at index %d missing __name__, assigned: %s", i, fn.__name__)

    toolset.add(FunctionTool(functions=functions))
    logger.info("Built toolset with %d function(s)", len(functions))

    return toolset


# ------------------------------------------------
# Agent Execution
# ------------------------------------------------
def run_agent(
    user_message: str,
    functions: List[Callable],
) -> Dict[str, Any]:
    """
    Execute the agent with a user message and function tools.
    
    This function:
    1. Validates required environment variables
    2. Creates a new conversation thread
    3. Attaches function tools to the agent
    4. Sends the user message
    5. Processes the agent's response
    6. Returns the result
    
    Args:
        user_message: The user's query or instruction
        functions: List of callable functions available to the agent
        
    Returns:
        Dict containing:
            - thread_id: Unique thread identifier
            - run_status: Execution status (COMPLETED, FAILED, etc.)
            - agent_text: The agent's response text
            
    Raises:
        ValueError: If AGENT_ID is not set in environment
    """
    agent_id = os.getenv("AGENT_ID")
    if not agent_id:
        raise ValueError("AGENT_ID environment variable must be set")

    logger.info("Starting agent execution for agent_id: %s", agent_id)
    
    # Initialize client
    client = get_agents_client()

    # Build and attach tools to agent
    toolset = build_toolset(functions)
    client.update_agent(
        agent_id=agent_id,
        tools=toolset.definitions,
        tool_resources=toolset.resources,
    )
    client.enable_auto_function_calls(toolset)
    logger.info("Updated agent with %d tool(s)", len(functions))

    # Create conversation thread
    thread = client.threads.create()
    logger.info("Created thread: %s", thread.id)

    # Send user message
    client.messages.create(
        thread_id=thread.id,
        role="user",
        content=user_message
    )
    logger.info("Sent user message to thread")

    # Execute agent (blocking call)
    run = client.runs.create_and_process(
        thread_id=thread.id,
        agent_id=agent_id
    )
    logger.info("Agent run completed with status: %s", run.status)

    # Retrieve agent's response
    msg = client.messages.get_last_message_text_by_role(
        thread_id=thread.id,
        role=MessageRole.AGENT
    )

    result = {
        "thread_id": thread.id,
        "run_status": run.status,
        "agent_text": msg.text.value if msg and msg.text else None
    }
    
    return result


# ------------------------------------------------
# CLI Entry Point (for testing/demo)
# ------------------------------------------------
def main():
    """
    Interactive CLI for testing the maintenance configuration agent.
    """
    from vmstatusagent.user_functions import user_functions
    
    print("\n" + "=" * 80)
    print("Azure Maintenance Configuration Agent - Interactive Mode")
    print("=" * 80)
    
    # Validate required environment variables
    required_vars = {
        "PROJECT_ENDPOINT": "Azure AI Foundry project endpoint",
        "AGENT_ID": "Agent identifier",
        "AZURE_SUBSCRIPTION_ID": "Azure subscription ID",
        "AZURE_RESOURCE_GROUP": "Azure resource group name"
    }
    
    missing_vars = {var: desc for var, desc in required_vars.items() if not os.getenv(var)}
    
    if missing_vars:
        print(f"\n❌ Missing required environment variables:")
        for var, desc in missing_vars.items():
            print(f"   - {var}: {desc}")
        print("\nPlease set them in your .env file")
        exit(1)
    
    resource_group = os.getenv("AZURE_RESOURCE_GROUP")
    subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
    
    # Display example queries
    print("\n📋 Example queries:")
    print(f"  1. Show me maintenance configurations in resource group {resource_group}")
    print(f"  2. List all maintenance configurations in subscription")
    print(f"  3. Get maintenance configuration 'config-name' in resource group {resource_group}")
    print("\n" + "-" * 80)
    
    # Get user input
    try:
        query = input("\n💬 Enter your query (or press Enter for default): ").strip()
        if not query:
            query = f"Show me maintenance configurations in resource group {resource_group}"
            print(f"Using default: {query}")
    except (KeyboardInterrupt, EOFError):
        print("\n\n👋 Exiting...")
        exit(0)
    
    # Prepare query with context
    full_query = (
        f"{query}\n\n"
        f"Context: subscription_id={subscription_id}, resource_group={resource_group}"
    )
    
    print("\n" + "-" * 80)
    print(f"🔍 Query: {query}")
    print(f"📦 Context: subscription_id={subscription_id}, resource_group={resource_group}")
    print("-" * 80)
    
    # Execute agent
    try:
        result = run_agent(
            user_message=full_query,
            functions=list(user_functions.values())
        )
        
        print("\n" + "=" * 80)
        print("🤖 AGENT RESPONSE")
        print("=" * 80)
        print(f"\n{result.get('agent_text', 'No response')}\n")
        print("-" * 80)
        print(f"🔗 Thread ID: {result.get('thread_id')}")
        print(f"✅ Status: {result.get('run_status')}")
        print("=" * 80 + "\n")
        
    except Exception as e:
        logger.exception("Agent execution failed")
        print(f"\n❌ Error: {e}")
        print("\n🔧 Troubleshooting:")
        print("  1. Ensure you're authenticated: az login")
        print("  2. Check your .env file has correct values")
        print("  3. Verify AGENT_ID matches your Azure AI Foundry agent")
        print("  4. Confirm Azure subscription and resource group exist")
        exit(1)


if __name__ == "__main__":
    main()
