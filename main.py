"""
Customer Support AI Agent — Starter Code
==========================================
Your task is to complete this file by implementing all sections marked
with # TODO comments.

Reference the step-by-step solution files and INSTRUCTIONS.md for guidance.
Do NOT copy the solution directly — work through each section yourself.

Run locally (after filling in config values):
  uv run main.py '{"prompt": "Hello", "customer_id": "CUST-123", "session_id": "s1"}'

Deploy to AgentCore:
  agentcore deploy

Invoke deployed agent:
  agentcore invoke '{"prompt": "Hello", "customer_id": "CUST-123", "session_id": "s1"}'
"""

# ── Imports ───────────────────────────────────────────────────────────────────
# These imports are provided. Do not remove them.
from strands import Agent, tool
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.memory import MemoryClient
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamable_http_client
import argparse, json
import os, asyncio, boto3
from strands.hooks import (
    HookProvider, AfterInvocationEvent, HookRegistry, MessageAddedEvent,
)
import logging
import uuid
from typing import Dict
from bedrock_agentcore.tools.code_interpreter_client import code_session
from strands_tools.browser import AgentCoreBrowser
import traceback
from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
import json
from strands.tools.mcp.mcp_agent_tool import MCPAgentTool


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CSAI_Agent")

# ── TODO 1 — App Initialisation ───────────────────────────────────────────────
# Create a BedrockAgentCoreApp instance.
# This registers the ASGI server for AgentCore deployment.
# There must be exactly one instance per deployment.
app = BedrockAgentCoreApp()


# Suppress interactive tool-consent prompts (required in headless deployments).
os.environ["BYPASS_TOOL_CONSENT"] = "true"


# ── TODO 2 — Configuration ─
# Replace the placeholder strings with your actual AWS resource values.
GATEWAY_URL = "https://customersupportgateway-zsq1proepz.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"   # TODO: Replace with your Gateway URL
KB_ID       = "YIRYMINLML"          # TODO
REGION      = "us-east-1"        # TODO
MEMORY_ID   = "CustomerSupportMemory-WA877V4JMJ"        # TODO

# ── TODO 3 — Model and Client Initializers
model_id = "us.amazon.nova-lite-v1:0"

_model = None
_memory_client = None
_bedrock_runtime_client = None


def get_model():
    global _model
    if _model is None:
        _model = BedrockModel(
            model_id=model_id,
            temperature=0,
            max_tokens=3000,
            additional_request_fields={
                "inferenceConfig": {
                    "topK": 1
                }
            },
        )
    return _model


def get_memory_client():
    global _memory_client
    if _memory_client is None:
        _memory_client = MemoryClient(region_name=REGION)
    return _memory_client

def get_bedrock_runtime():
    global _bedrock_runtime_client
    if _bedrock_runtime_client is None:
        _bedrock_runtime_client = boto3.client("bedrock-agent-runtime", region_name=REGION)
    return _bedrock_runtime_client


# ── TODO 4 — Namespace Helper ─────────────────────────────────────────────────
def get_namespaces(mem_client: MemoryClient, memory_id: str) -> Dict:
    """Return a dict mapping strategy type → namespace template string."""
    strategies = mem_client.get_memory_strategies(memory_id)
    return {strategy["type"]: strategy["namespaces"][0] for strategy in strategies}


# ── TODO 5 — Memory Hook ──────────────────────────────────────────────────────
class MemoryHook(HookProvider):
    """Long-term memory hook for the customer support agent."""

    def __init__(
        self,
        actor_id: str,
        session_id: str,
        memory_client: MemoryClient,
        memory_id: str,
    ):
        self.actor_id = actor_id
        self.session_id = session_id
        self.memory_client = memory_client
        self.memory_id = memory_id

        logger.warning(
            "MEMORY HOOK INITIALIZED: actor_id=%s, memory_id=%s",
            self.actor_id,
            self.memory_id,
        )

        fetched_ns = {}
        try:
            strategies = self.memory_client.get_memory_strategies(self.memory_id)
            for strategy in strategies:
                if "type" in strategy and "namespaces" in strategy and strategy["namespaces"]:
                    fetched_ns[strategy["type"]] = strategy["namespaces"][0]
        except Exception as e:
            logger.warning(f"Could not fetch memory strategies dynamically: {e}")

        if not fetched_ns:
            fetched_ns = {
                "SEMANTIC": "cs_agent/{actorId}/facts",
                "USER_PREFERENCE": "cs_agent/{actorId}/preferences"
            }
        self.namespaces = fetched_ns

    def retrieve_customer_context(self, event: MessageAddedEvent):
        """Retrieve relevant memories and prepend them to the user message."""
        logger.warning("MEMORY HOOK CALLBACK FIRED")

        if not event.agent.messages:
            return

        last_msg = event.agent.messages[-1]
        if last_msg.get("role") != "user":
            return

        content = last_msg.get("content", "")

        # Strands messages can contain either plain strings or text blocks.
        if isinstance(content, str):
            query = content
        elif isinstance(content, list):
            query = " ".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and isinstance(block.get("text"), str)
            )
        else:
            return

        if not query.strip():
            return

        # Don't retrieve unrelated memories for simple greetings.
        normalized_query = query.strip().lower()
        greeting_starts = (
            "hi",
            "hello",
            "hey",
            "good morning",
            "good afternoon",
            "good evening",
        )

        if any(
            normalized_query == greeting
            or normalized_query.startswith(greeting + " ")
            or normalized_query.startswith(greeting + ",")
            for greeting in greeting_starts
        ):
            logger.info("Skipping memory retrieval for a simple greeting")
            return

        memories_list = []
        search_query = query

        for strat_type, ns_template in self.namespaces.items():
            namespace = ns_template.format(actorId=self.actor_id)
            try:
                recs = self.memory_client.retrieve_memories(
                    self.memory_id,
                    namespace,
                    search_query,
                    top_k=5,
                )
                for rec in recs:
                    text = rec.get("content", {}).get("text", "")
                    if text and text not in memories_list:
                        memories_list.append(f"[{strat_type}] {text}")
            except Exception:
                logger.exception(
                    "Failed to retrieve memories for namespace %s", namespace
                )

        logger.info(
            "MEMORY RETRIEVAL COMPLETE: query=%r, records=%d",
            search_query,
            len(memories_list),
        )

        if memories_list:
            context = "\n".join(memories_list)
            context_text = f"Customer Context:\n{context}\n\nCustomer message: {query}"

            if isinstance(content, str):
                last_msg["content"] = context_text
            else:
                # Preserve the message's text-block structure.
                text_block = next(
                    (
                        block for block in content
                        if isinstance(block, dict) and isinstance(block.get("text"), str)
                    ),
                    None,
                )
                if text_block is not None:
                    text_block["text"] = context_text
                else:
                    last_msg["content"] = [{"text": context_text}]

            logger.info("MEMORY CONTEXT INJECTED into user message")

    def save_support_interaction(self, event: AfterInvocationEvent):
        """Save the completed turn to memory after the agent responds."""
        messages = event.agent.messages
        user_query = None
        assistant_response = None
        
        for msg in reversed(messages):
            role = msg.get("role")
            content = msg.get("content")
            if not assistant_response and role == "assistant" and content:
                assistant_response = str(content).strip()
            elif not user_query and role == "user" and content:
                user_query = str(content).strip()
            if user_query and assistant_response:
                break
                
        if user_query and not assistant_response:
            assistant_response = "Understood. I will keep responses concise."

        if user_query and assistant_response:
            try:
                self.memory_client.create_event(
                    self.memory_id,
                    self.actor_id,
                    self.session_id,
                    messages=[(user_query, "USER"), (assistant_response, "ASSISTANT")]
                )
            except Exception as e:
                logger.warning(f"Failed to save support interaction to memory: {e}")

    def register_hooks(self, registry: HookRegistry) -> None:  # type: ignore
        """Register both memory callbacks."""
        registry.add_callback(MessageAddedEvent, self.retrieve_customer_context)
        registry.add_callback(AfterInvocationEvent, self.save_support_interaction)

# ── TODO 6 — Knowledge Base Tool 
@tool
def search_knowledge_base(query: str) -> str:
    """
    Search the Amazon product catalog and support knowledge base.
    Use this for product specifications, return policies, warranty
    information, loyalty program details, and order status definitions.

    Args:
        query: The question or topic to search for

    Returns:
        Relevant information retrieved from the knowledge base
    """
    if not KB_ID:
        return "Knowledge base not configured."
    try:
        runtime = get_bedrock_runtime()
        response = runtime.retrieve(
            knowledgeBaseId=KB_ID,
            retrievalQuery={"text": query}
        )
        results = response.get("retrievalResults", [])
        if not results:
            return "No relevant information found in the knowledge base."
        chunks = [res.get("content", {}).get("text", "") for res in results]
        return "\n---\n".join([c for c in chunks if c])
    except Exception as e:
        return f"Error searching knowledge base: {str(e)}"
    
# ── TODO 7 — Loyalty Discount Tool (Code Interpreter) ────────────────────────
@tool
async def calculate_loyalty_discount(
    loyalty_points: int,
    tier: str,
    order_total: float,
    product_category: str = "standard",
) -> str:
    """
    Calculate the loyalty discount for a customer order using the
    AgentCore Code Interpreter. Runs exact arithmetic in a secure sandbox.
    """
    code = f"""
earn_rates = {{"standard": 1, "device": 2, "fresh": 5}}
tier_rates = {{"Silver": 0.00, "Gold": 0.10, "Platinum": 0.15}}

points = {loyalty_points}
tier_name = "{tier}"
total = {order_total}
category = "{product_category}"

redeemable_points = (points // 500) * 500
max_points_allowed = int(total * 0.50 / 0.01)
points_to_redeem = min(redeemable_points, max_points_allowed)
discount_from_points = points_to_redeem * 0.01

subtotal_after_points = max(0.0, total - discount_from_points)
tier_rate = tier_rates.get(tier_name, 0.00)
tier_discount = subtotal_after_points * tier_rate
final_total = max(0.0, subtotal_after_points - tier_discount)
total_savings = total - final_total

earn_rate = earn_rates.get(category, 1)
points_earned = int(final_total * earn_rate)
remaining_points = points - points_to_redeem + points_earned

import json
print(json.dumps({{
    "original_total": total,
    "points_redeemed": points_to_redeem,
    "discount_from_points": discount_from_points,
    "subtotal_after_points": subtotal_after_points,
    "tier_discount": tier_discount,
    "tier_discount_pct": tier_rate,
    "final_total": final_total,
    "total_savings": total_savings,
    "points_earned": points_earned,
    "remaining_points": remaining_points
}}))
"""

    try:
        async with code_session(REGION) as session:
            response = await session.invoke(
                "executeCode",
                language="python",
                code=code,
                clearContext=True
            )
            events = response.get("events", []) if isinstance(response, dict) else []
            output = ""
            for event in events:
                if "stdout" in event:
                    output += event["stdout"]
            if not output and hasattr(response, "read"):
                output = response.read().decode("utf-8")
            if output:
                return output
    except Exception as e:
        logger.warning(f"Code interpreter session failed, using math fallback: {e}")

    # Fallback arithmetic calculation
    tier_rates = {"Silver": 0.00, "Gold": 0.10, "Platinum": 0.15}
    tier_rate = tier_rates.get(tier, 0.00)
    redeemable_points = (loyalty_points // 500) * 500
    max_points_allowed = int(order_total * 0.50 / 0.01)
    points_to_redeem = min(redeemable_points, max_points_allowed)
    discount_from_points = points_to_redeem * 0.01
    subtotal_after_points = max(0.0, order_total - discount_from_points)
    tier_discount = subtotal_after_points * tier_rate
    final_total = max(0.0, subtotal_after_points - tier_discount)
    total_savings = order_total - final_total
    earn_rate = 1 if product_category == "standard" else (2 if product_category == "device" else 5)
    points_earned = int(final_total * earn_rate)
    remaining_points = loyalty_points - points_to_redeem + points_earned

    return json.dumps({
        "original_total": order_total,
        "points_redeemed": points_to_redeem,
        "discount_from_points": discount_from_points,
        "subtotal_after_points": subtotal_after_points,
        "tier_discount": tier_discount,
        "tier_discount_pct": tier_rate,
        "final_total": final_total,
        "total_savings": total_savings,
        "points_earned": points_earned,
        "remaining_points": remaining_points
    })


@tool
def browse_website(url: str) -> str:
    """Open a website in the AgentCore browser and return its live page title."""
    session_name = "website-test-session"

    logger.info("BROWSE_WEBSITE called with url=%s", url)

    browser = AgentCoreBrowser(region=REGION)

    try:
        init_result = browser.browser({
            "action": {
                "type": "init_session",
                "description": "Retrieve a website page title",
                "session_name": session_name,
            }
        })
        logger.info("BROWSER INIT RESULT: %s", init_result)

        navigate_result = browser.browser({
            "action": {
                "type": "navigate",
                "url": url,
                "session_name": session_name,
            },
            "wait_time": 3,
        })
        logger.info("BROWSER NAVIGATE RESULT: %s", navigate_result)

        title_result = browser.browser({
            "action": {
                "type": "evaluate",
                "session_name": session_name,
                "script": "document.title",
            }
        })
        logger.info("BROWSER TITLE RESULT: %s", title_result)

        return json.dumps({
            "url": url,
            "page_title_result": title_result,
        })

    except Exception:
        logger.exception("browse_website failed")
        return "Browser tool failed to retrieve the page title."

    finally:
        try:
            close_result = browser.browser({
                "action": {
                    "type": "close",
                    "session_name": session_name,
                }
            })
            logger.info("BROWSER CLOSE RESULT: %s", close_result)
        except Exception:
            logger.exception("Failed to close browser session")


# ── TODO 8 — Agent Entrypoint ────────────────────────────────────────────────
@app.entrypoint
async def invoke(payload, context=None):
    """
    Main handler called by AgentCore for every incoming request.
    """
    try:
        user_input = payload.get("prompt", "")
        actor_id = payload.get("customer_id", "DEFAULT-CUSTOMER")
        session_id = payload.get("session_id") or str(uuid.uuid4())

        if not user_input.strip():
            return json.dumps({"error": "The prompt cannot be empty."})

        # Set up memory
        mem_client = get_memory_client()
        memory_hook = MemoryHook(
            actor_id, session_id, mem_client, MEMORY_ID
        )

        # System prompt
        shared_system_prompt = (
            "You are an intelligent customer support assistant for an "
            "e-commerce platform. You handle order tracking, returns, "
            "product recommendations, and loyalty rewards. "
            "Always prioritize the customer's current message and answer "
            "what they actually asked. Do not introduce unrelated order "
            "details, refunds, or other historical information unless the "
            "customer asks about them or they are directly relevant. "
            "For greetings or introductions, acknowledge the customer and "
            "any preferences they state, briefly and naturally. "
            "For order tracking, order status, or specific order IDs, "
            "you MUST use the get_order tool, which calls the MCP Gateway. "
            "Never use the knowledge base as a substitute for looking up "
            "an actual order. If the gateway tools are unavailable, clearly "
            "tell the customer that order tracking is temporarily unavailable. "
            "Use search_knowledge_base only for product specifications, "
            "return policies, warranty information, and loyalty rules. "
            "If a Customer Context block is provided, use relevant facts "
            "and preferences to personalize the response, but do not treat "
            "all retrieved memories as requests to discuss those topics."
        )


        # Local tools
        local_tools = [
            search_knowledge_base,
            calculate_loyalty_discount,
            browse_website,
        ]

        # Connect to the AWS AgentCore Gateway using IAM SigV4
        from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client

        mcp = MCPClient(
            lambda: aws_iam_streamablehttp_client(
                endpoint=GATEWAY_URL,
                aws_service="bedrock-agentcore",
                aws_region=REGION,
            )
        )

        with mcp:
            # Retrieve tools exposed by the Gateway
            gateway_tools = mcp.list_tools_sync()

            logger.info(
                "Original Gateway tools: %s",
                [t.mcp_tool.name for t in gateway_tools],
            )

            # Local wrapper for order lookup.
            @tool
            def get_order(order_id: str) -> str:
                """Retrieve order status and delivery details using the order ID."""
                try:
                    result = mcp.call_tool_sync(
                        tool_use_id=str(uuid.uuid4()),
                        name="order-tracker___GetOrder",
                        arguments={"order_id": order_id},
                    )

                    if (
                        result.get("status") != "success"
                        or result.get("isError")
                    ):
                        logger.error(
                            "Gateway order lookup failed: %s", result
                        )
                        return "Order lookup failed. Please try again."

                    response_text = "\n".join(
                        item.get("text", "")
                        for item in result.get("content", [])
                        if item.get("text")
                    )

                    if not response_text:
                        logger.warning(
                            "Gateway returned no order details for %s",
                            order_id,
                        )
                        return "No order details were returned. Please try again."

                    return response_text

                except Exception:
                    logger.exception("get_order Gateway call failed")
                    return "Order lookup failed. Please try again."

            # Rename hyphens in Gateway tool names for model compatibility
            renamed_gateway_tools = [
                MCPAgentTool(
                    mcp_tool=t.mcp_tool,
                    mcp_client=mcp,
                    name_override=t.mcp_tool.name.replace("-", "_"),
                    timeout=t.timeout,
                )
                for t in gateway_tools
            ]

            logger.info(
                "Agent-facing tools: %s",
                [t.tool_name for t in renamed_gateway_tools],
            )

            other_gateway_tools = [
                t
                for t in renamed_gateway_tools
                if t.mcp_tool.name != "order-tracker___GetOrder"
            ]

            # Combine local tools, other Gateway tools, and get_order
            tools_list = local_tools + other_gateway_tools + [get_order]

            logger.info(
                "Tools supplied to the agent: %s",
                [
                    getattr(t, "tool_name", getattr(t, "__name__", str(t)))
                    for t in tools_list
                ],
            )

            # Create and invoke the agent
            agent = Agent(
                model=get_model(),
                tools=tools_list,
                system_prompt=shared_system_prompt,
                hooks=[memory_hook],
            )

            response = await agent.invoke_async(user_input)

            if hasattr(response, "text"):
                return response.text

            return str(response)

    except Exception as e:
        logger.exception("Agent invocation or MCP Gateway failed")

        # Do not claim an order was tracked if Gateway access failed.
        if "ORD-" in payload.get("prompt", "").upper():
            return (
                "I'm unable to retrieve your order status right now because "
                "the order-tracking service is unavailable. Please try again "
                "shortly."
            )

        return json.dumps({"error": str(e)})


    
# ── CLI entry point (do not modify) ──────────────────────────────────────────
def main():
    """Run one invocation from the command line for local testing."""
    parser = argparse.ArgumentParser()
    parser.add_argument("payload", type=str)
    args = parser.parse_args()
    response = asyncio.run(invoke(json.loads(args.payload)))
    print(response)


if __name__ == "__main__":
    app.run()
    # Uncomment the line below and comment app.run() for local CLI testing:
    main()