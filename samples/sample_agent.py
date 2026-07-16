"""
Sample Customer Service Agent
一个模拟的客户服务 Agent，用于测试 Agent Flow Visualizer。
包含：LLM 调用、工具使用、决策分支、子 Agent 等常见模式。
"""

# === 工具定义 ===

def search_knowledge_base(query: str) -> str:
    """从知识库中搜索相关信息。"""
    # 模拟知识库搜索
    return f"知识库搜索结果: {query}"


def create_ticket(title: str, description: str, priority: str = "medium") -> dict:
    """创建工单。"""
    return {
        "ticket_id": "TK-001",
        "title": title,
        "description": description,
        "priority": priority,
        "status": "created",
    }


def get_user_info(user_id: str) -> dict:
    """获取用户信息。"""
    return {
        "user_id": user_id,
        "name": "张三",
        "level": "VIP",
        "history": ["咨询产品", "退货申请"],
    }


def send_notification(user_id: str, message: str) -> bool:
    """发送通知给用户。"""
    return True


# === LLM 调用封装 ===

class LLMClient:
    """LLM 客户端封装。"""

    def __init__(self, model: str = "gpt-4"):
        self.model = model

    def chat_completions_create(self, messages: list, temperature: float = 0.7) -> str:
        """调用 LLM 生成回复。

        System: You are a helpful customer service assistant.
        You should classify the user's intent and respond accordingly.
        """
        # 模拟 LLM 调用
        return "LLM 响应内容"

    def classify_intent(self, user_message: str) -> str:
        """使用 LLM 分类用户意图。

        System: Classify the user's message into one of these categories:
        - FAQ: General questions about products or services
        - COMPLAINT: User is reporting a problem or complaint
        - TICKET: User needs to create a support ticket
        - ESCALATE: Issue needs human agent escalation
        """
        prompt = f"""请将以下用户消息分类为以下类别之一:
        - FAQ: 常见问题咨询
        - COMPLAINT: 投诉和问题反馈
        - TICKET: 需要创建工单
        - ESCALATE: 需要人工处理

        用户消息: {user_message}
        """
        return self.chat_completions_create([{"role": "user", "content": prompt}])

    def generate_response(self, context: str, user_message: str) -> str:
        """根据上下文生成回复。

        System: Generate a helpful response based on the provided context.
        Be polite, concise, and accurate.
        """
        messages = [
            {"role": "system", "content": f"上下文信息: {context}"},
            {"role": "user", "content": user_message},
        ]
        return self.chat_completions_create(messages)


# === 处理器 ===

class FAQHandler:
    """处理常见问题。"""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def handle(self, user_message: str) -> str:
        """处理 FAQ 类型的问题。"""
        # 先搜索知识库
        kb_result = search_knowledge_base(user_message)

        # 用 LLM 生成回答
        response = self.llm.generate_response(kb_result, user_message)
        return response


class ComplaintHandler:
    """处理投诉。"""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def handle(self, user_message: str, user_id: str) -> str:
        """处理投诉类型的问题。"""
        # 获取用户信息
        user_info = get_user_info(user_id)

        # 创建工单
        ticket = create_ticket(
            title=f"投诉 - {user_id}",
            description=user_message,
            priority="high" if user_info["level"] == "VIP" else "medium",
        )

        # 生成安抚回复
        context = f"用户等级: {user_info['level']}, 工单号: {ticket['ticket_id']}"
        response = self.llm.generate_response(context, user_message)

        # 发送通知
        send_notification(user_id, f"您的投诉已受理，工单号: {ticket['ticket_id']}")

        return response


class EscalationHandler:
    """处理需要人工升级的请求。"""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def handle(self, user_message: str, user_id: str) -> str:
        """将问题升级到人工客服。"""
        user_info = get_user_info(user_id)

        ticket = create_ticket(
            title=f"升级处理 - {user_info['level']} - {user_id}",
            description=user_message,
            priority="urgent",
        )

        send_notification(user_id, "您的问题已转交人工客服处理")

        return f"已为您转接人工客服，工单号: {ticket['ticket_id']}"


# === 主 Agent ===

class CustomerServiceAgent:
    """客户服务 Agent - 自动处理用户咨询。"""

    def __init__(self):
        self.llm = LLMClient(model="gpt-4")
        self.faq_handler = FAQHandler(self.llm)
        self.complaint_handler = ComplaintHandler(self.llm)
        self.escalation_handler = EscalationHandler(self.llm)

    def run(self, user_message: str, user_id: str = "anonymous") -> str:
        """Agent 主入口 - 处理用户消息。"""
        # Step 1: 分类用户意图
        intent = self.llm.classify_intent(user_message)

        # Step 2: 根据意图路由到对应处理器
        response = self.route_to_handler(intent, user_message, user_id)

        # Step 3: 格式化输出
        return self.format_response(response, intent)

    def route_to_handler(self, intent: str, user_message: str, user_id: str) -> str:
        """根据意图路由到不同处理器。"""
        if intent == "FAQ":
            return self.faq_handler.handle(user_message)
        elif intent == "COMPLAINT":
            return self.complaint_handler.handle(user_message, user_id)
        elif intent == "TICKET":
            ticket = create_ticket(
                title=f"用户请求 - {user_id}",
                description=user_message,
            )
            return f"工单已创建: {ticket['ticket_id']}"
        elif intent == "ESCALATE":
            return self.escalation_handler.handle(user_message, user_id)
        else:
            # 默认走 FAQ 处理
            return self.faq_handler.handle(user_message)

    def format_response(self, response: str, intent: str) -> str:
        """格式化最终回复。"""
        return f"[{intent}] {response}"


# === 入口 ===

def main():
    """程序主入口。"""
    agent = CustomerServiceAgent()

    # 测试不同类型的输入
    test_messages = [
        ("你们的退货政策是什么？", "user_001"),
        ("产品质量太差了，我要投诉！", "user_002"),
        ("我需要人工客服", "user_003"),
    ]

    for message, user_id in test_messages:
        result = agent.run(message, user_id)
        print(f"输入: {message}")
        print(f"输出: {result}")
        print("---")


if __name__ == "__main__":
    main()
