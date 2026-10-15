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

This project helped me understand how to build an AI customer support agent using Amazon Bedrock AgentCore, Strands Agents, and the MCP Gateway. One of the key design decisions was using the MCP Gateway to connect the agent to customer support tools for order tracking, refunds, and returns. This allows the agent to retrieve relevant information and perform customer support tasks instead of relying only on general model knowledge.

The MemoryHook was another important part of the project. It allows the agent to retrieve customer context before responding and save interactions for future conversations. This makes the agent more useful by supporting personalized responses based on previous interactions.

## Challenges & Solutions

One of the main challenges was troubleshooting MCP Gateway tool calls and resolving errors during agent invocation. Some requests failed because of tool execution and model tool-use errors. I investigated the terminal output and CloudWatch logs to identify the problems and test the agent again.

Another challenge was configuring AWS IAM permissions for the agent to access the required resources. I resolved this by running the permissions setup script and verifying that the necessary policies were added. I also worked through memory-related issues by checking the memory namespaces and testing how customer context was retrieved and saved.

During final testing, the refund policy test returned an error. I continued testing until I obtained a successful response and updated the screenshot used as test evidence. This showed the importance of checking actual outputs rather than assuming that the agent works correctly.

## Production Considerations

For production use, the agent needs reliable error handling, secure IAM permissions, and careful protection of customer information. For example, if the MCP Gateway is temporarily unavailable during an order-tracking request, the agent should inform the customer that the service is unavailable instead of inventing an order status. Memory access should also be restricted to the appropriate customer to prevent information from being exposed across accounts.

## Conclusion

This project gave me practical experience in building, deploying, and troubleshooting an AI agent that integrates multiple AWS services. I learned that successful agent development involves more than writing code; it also requires configuring permissions, testing integrations, managing memory, and verifying results. Overcoming these challenges helped me better understand how to build a reliable, secure, and useful customer support agent.