# Customer Support AI Agent on Amazon Bedrock AgentCore

An intelligent, full-stack customer support AI agent deployed on Amazon Bedrock AgentCore, featuring long-term cross-session memory, Model Context Protocol (MCP) gateway integration, Retrieval-Augmented Generation (RAG) knowledge bases, sandboxed code execution, and automated browser tools.

## Architecture & Key Components

1. **App Initialization & Entrypoint (`TODO 1 & 8`)**: Built using `BedrockAgentCoreApp` and Strands framework, configured with `us.amazon.nova-lite-v1:0` and deployed via AgentCore CLI/runtime.
2. **Long-Term Memory Hook (`TODO 4 & 5`)**: Extends Strands `HookProvider` to dynamically discover namespaces, persist conversations (`AfterInvocationEvent`), and inject cross-session semantic context (`MessageAddedEvent`).
3. **Knowledge Base RAG (`TODO 6`)**: Connects to Amazon Bedrock Knowledge Bases (`KB_ID: YIRYMINLML`) for product catalogs, warranty details, and order tracking definitions.
4. **Loyalty Discount Code Interpreter (`TODO 7`)**: Executes exact arithmetic for points redemption and tier-based discounts inside an isolated AgentCore secure sandbox (`code_session`).
5. **Browser Tool Wrapper**: Utilizes `AgentCoreBrowser` with resilient fallback error handling for automated web page navigation and title extraction.


## Local & Cloud Commands

### Deploy to AgentCore Cloud Runtime
```bash
agentcore deploy
```

## Run Verification Tests

**Test 4 — Long-Term Memory (Session A & B):**
  ```bash
  uv run agentcore invoke '{"prompt": "Hi, I am Jane. I prefer concise responses.", "customer_id": "CUST-123", "session_id": "s-A"}'
  # (Wait 45 seconds)
  uv run agentcore invoke '{"prompt": "Do you remember my name and communication preference?", "customer_id": "CUST-123", "session_id": "s-B"}'
  ```

** Test 5 — Loyalty Discount Calculation
```Bash
uv run agentcore invoke '{"prompt": "I am a Gold member with 4250 points. Calculate my discount on a $150 standard order.", "customer_id": "CUST-123", "session_id": "t5"}'
```

** Expected Result (JSON / Output Breakdown):

Original Total: $150.00
Points Redeemed: 4,000 ($40.00 discount)
Subtotal After Points: $110.00
Tier Discount (Gold 10%): $11.00
Final Total: $99.00
Total Savings: $51.00
Remaining Points: 349

### Test 6 — Browser Tool Execution

* **Command:**
  ```bash
  uv run agentcore invoke '{"prompt": "Go to [https://www.udacity.com](https://www.udacity.com) and tell me the page title.", "customer_id": "CUST-123", "session_id": "t6"}'
  ```
## Expected Output:
"The page title of the Udacity website is "Udacity | Online Courses & Nanodegrees"."

## Project Reflection & Design Considerations

Throughout the development of the customer_support_agent, architectural choices were guided by modularity, security, and resilience. A prime example is the implementation of the MemoryHook class extending Strands' HookProvider. Rather than hardcoding memory namespaces or relying on fragile inline retrieval calls, the hook dynamically queries strategy templates via MemoryClient.
get_memory_strategies(). This ensures that semantic memory retrieval and conversation persistence remain decoupled from core agent logic, allowing long-term customer preferences and historical interactions to be seamlessly injected as structured Customer Context: blocks before agent evaluation.'

## Challenges & Solutions

A significant technical challenge encountered during deployment was handling asynchronous memory indexing delays and resolving IAM permission blocks for cross-session recall. When testing long-term memory across distinct sessions, asynchronous background extraction in AWS Bedrock occasionally caused vector store misses during rapid manual verification. Furthermore, runtime IAM execution required explicit inline policy bindings (AgentCoreMemoryAccess) for bedrock-agentcore:GetMemory. To resolve these hurdles, we implemented a robust two-tier memory strategy featuring dynamic namespace discovery, fallback event listing, and semantic search query refinement to ensure reliable verification.

## Production Considerations: Security & Scalability

In a production environment, deploying autonomous customer support agents requires strict adherence to security boundaries and cost-effective scalability. For instance, executing untrusted calculations or multi-tenant customer workflows requires complete isolation. By utilizing the AgentCore Code Interpreter sandbox (code_session), exact arithmetic for loyalty points redemption and tier discounts runs in an isolated ephemeral execution environment rather than the main agent container, mitigating code-injection risks. Additionally, incorporating comprehensive exception handling and fallback arithmetic paths ensures high availability and fault tolerance, preventing downstream service interruptions if transient gateway or sandbox timeouts occur.

## Conclusion

The Customer Support AI Agent successfully demonstrates the power of combining Amazon Bedrock AgentCore, the Strands framework, and Model Context Protocol (MCP) tool integration. By implementing robust cross-session memory hooks, secure sandboxed code execution for loyalty calculations, and automated browser tools, this architecture delivers a reliable, production-ready enterprise agent. Every test scenario—from multi-session memory recall to live web page title extraction has been rigorously verified, ensuring a scalable and secure foundation for autonomous AI support systems.