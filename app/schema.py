"""数据模式定义模块

定义了聊天消息、角色、工具调用等核心数据结构。
为整个系统提供统一的数据模型和类型定义。
"""
from enum import Enum
from typing import Any, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class Role(str, Enum):
    """消息角色选项"""

    SYSTEM = "system"  # 系统消息
    USER = "user"  # 用户消息
    ASSISTANT = "assistant"  # 助手消息
    TOOL = "tool"  # 工具消息


ROLE_VALUES = tuple(role.value for role in Role)  # 角色值元组
ROLE_TYPE = Literal[ROLE_VALUES]  # type: ignore  # 角色类型字面量


class ToolChoice(str, Enum):
    """工具选择选项"""

    NONE = "none"  # 不使用工具
    AUTO = "auto"  # 自动选择工具
    REQUIRED = "required"  # 必须使用工具


TOOL_CHOICE_VALUES = tuple(choice.value for choice in ToolChoice)  # 工具选择值元组
TOOL_CHOICE_TYPE = Literal[TOOL_CHOICE_VALUES]  # type: ignore  # 工具选择类型字面量


class AgentState(str, Enum):
    """智能体执行状态"""

    IDLE = "IDLE"  # 空闲状态
    RUNNING = "RUNNING"  # 运行状态
    FINISHED = "FINISHED"  # 完成状态
    ERROR = "ERROR"  # 错误状态


class Function(BaseModel):
    """函数调用信息"""
    name: str  # 函数名称
    arguments: str  # 函数参数（JSON 字符串）


class ToolCall(BaseModel):
    """表示消息中的工具/函数调用"""

    id: str  # 工具调用 ID
    type: str = "function"  # 调用类型
    function: Function  # 函数信息


class Message(BaseModel):
    """表示对话中的聊天消息"""

    role: ROLE_TYPE = Field(..., description="消息角色")  # type: ignore
    content: Optional[str] = Field(default=None, description="消息内容")
    tool_calls: Optional[List[ToolCall]] = Field(default=None, description="工具调用列表")
    name: Optional[str] = Field(default=None, description="消息名称")
    tool_call_id: Optional[str] = Field(default=None, description="工具调用 ID")
    base64_image: Optional[str] = Field(default=None, description="Base64 编码的图片")

    def __add__(self, other) -> List["Message"]:
        """支持 Message + list 或 Message + Message 的操作"""
        if isinstance(other, list):
            return [self] + other
        elif isinstance(other, Message):
            return [self, other]
        else:
            raise TypeError(
                f"不支持的操作数类型: '{type(self).__name__}' 和 '{type(other).__name__}'"
            )

    def __radd__(self, other) -> List["Message"]:
        """支持 list + Message 的操作"""
        if isinstance(other, list):
            return other + [self]
        else:
            raise TypeError(
                f"不支持的操作数类型: '{type(other).__name__}' 和 '{type(self).__name__}'"
            )

    def to_dict(self) -> dict:
        """将消息转换为字典格式"""
        message = {"role": self.role}
        if self.content is not None:
            message["content"] = self.content
        if self.tool_calls is not None:
            message["tool_calls"] = [tool_call.dict() for tool_call in self.tool_calls]
        if self.name is not None:
            message["name"] = self.name
        if self.tool_call_id is not None:
            message["tool_call_id"] = self.tool_call_id
        if self.base64_image is not None:
            message["base64_image"] = self.base64_image
        return message

    @classmethod
    def user_message(
        cls, content: str, base64_image: Optional[str] = None
    ) -> "Message":
        """创建用户消息"""
        return cls(role=Role.USER, content=content, base64_image=base64_image)

    @classmethod
    def system_message(cls, content: str) -> "Message":
        """创建系统消息"""
        return cls(role=Role.SYSTEM, content=content)

    @classmethod
    def assistant_message(
        cls, content: Optional[str] = None, base64_image: Optional[str] = None
    ) -> "Message":
        """创建助手消息"""
        return cls(role=Role.ASSISTANT, content=content, base64_image=base64_image)

    @classmethod
    def tool_message(
        cls, content: str, name, tool_call_id: str, base64_image: Optional[str] = None
    ) -> "Message":
        """创建工具消息"""
        return cls(
            role=Role.TOOL,
            content=content,
            name=name,
            tool_call_id=tool_call_id,
            base64_image=base64_image,
        )

    @classmethod
    def from_tool_calls(
        cls,
        tool_calls: List[Any],
        content: Union[str, List[str]] = "",
        base64_image: Optional[str] = None,
        **kwargs,
    ):
        """从原始工具调用创建工具调用消息。

        Args:
            tool_calls: 来自 LLM 的原始工具调用
            content: 可选的消息内容
            base64_image: 可选的 base64 编码图片
        """
        formatted_calls = [
            {"id": call.id, "function": call.function.model_dump(), "type": "function"}
            for call in tool_calls
        ]
        return cls(
            role=Role.ASSISTANT,
            content=content,
            tool_calls=formatted_calls,
            base64_image=base64_image,
            **kwargs,
        )


class Memory(BaseModel):
    """对话记忆类
    
    管理对话历史消息，支持消息限制和检索功能。
    """
    messages: List[Message] = Field(default_factory=list, description="消息列表")
    max_messages: int = Field(default=100, description="最大消息数量")

    def add_message(self, message: Message) -> None:
        """向记忆中添加一条消息"""
        self.messages.append(message)
        # 可选：实现消息限制
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages :]

    def add_messages(self, messages: List[Message]) -> None:
        """向记忆中添加多条消息"""
        self.messages.extend(messages)
        # 可选：实现消息限制
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages :]

    def clear(self) -> None:
        """清除所有消息"""
        self.messages.clear()

    def get_recent_messages(self, n: int) -> List[Message]:
        """获取最近的 n 条消息"""
        return self.messages[-n:]

    def to_dict_list(self) -> List[dict]:
        """将消息转换为字典列表"""
        return [msg.to_dict() for msg in self.messages]
