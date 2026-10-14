import json
import boto3

# Resource IDs from this project
KB_ID = "YIRYMINLML"
MEMORY_ID = "CustomerSupportMemory-WA877V4JMJ"
REGION = "us-east-1"

ROLE_NAME = "AmazonBedrockAgentCoreSDKRuntime-us-east-1-aa96c3a063"
POLICY_NAME = "CustomerSupportAgentResourceAccess"

ACCOUNT_ID = boto3.client("sts").get_caller_identity()["Account"]

policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "KnowledgeBaseRetrieval",
            "Effect": "Allow",
            "Action": ["bedrock:Retrieve"],
            "Resource": (
                f"arn:aws:bedrock:{REGION}:{ACCOUNT_ID}:"
                f"knowledge-base/{KB_ID}"
            ),
        },
        {
            "Sid": "CustomerSupportMemoryAccess",
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:GetMemory",
                "bedrock-agentcore:CreateEvent",
                "bedrock-agentcore:ListEvents",
                "bedrock-agentcore:RetrieveMemoryRecords",
                "bedrock-agentcore:GetEvent",
                "bedrock-agentcore:ListActors",
                "bedrock-agentcore:ListSessions",
                "bedrock-agentcore:GetMemoryRecord",
                "bedrock-agentcore:ListMemoryRecords",
            ],
            "Resource": (
                f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT_ID}:"
                f"memory/{MEMORY_ID}"
            ),
        },


        {
            "Sid": "AgentCoreBrowserAccess",
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:StartBrowserSession",
                "bedrock-agentcore:StopBrowserSession",
                "bedrock-agentcore:GetBrowserSession",
                "bedrock-agentcore:ListBrowserSessions",
                "bedrock-agentcore:UpdateBrowserStream",
                "bedrock-agentcore:ConnectBrowserAutomationStream",
                "bedrock-agentcore:ConnectBrowserLiveViewStream",
                "bedrock-agentcore:GetBrowser",
                "bedrock-agentcore:ListBrowsers",
            ],
            "Resource": "arn:aws:bedrock-agentcore:us-east-1:aws:browser/aws.browser.v1",
        },

    ],
}

iam = boto3.client("iam")

print(f"Adding policy {POLICY_NAME} to role {ROLE_NAME}...")
iam.put_role_policy(
    RoleName=ROLE_NAME,
    PolicyName=POLICY_NAME,
    PolicyDocument=json.dumps(policy),
)
print("Policy added successfully.")
print("Knowledge Base and Memory permissions have been configured.")
