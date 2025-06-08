"""工具基础类模块

定义了工具系统的基础抽象类和结果类，
为所有工具提供统一的接口和行为规范。
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class BaseTool(ABC, BaseModel):
    """工具基础抽象类
    
    所有工具都必须继承此类并实现 execute 方法。
    提供了工具的基本属性和统一的调用接口。
    """
    name: str  # 工具名称
    description: str  # 工具描述
    parameters: Optional[dict] = None  # 工具参数定义

    class Config:
        arbitrary_types_allowed = True

    async def __call__(self, **kwargs) -> Any:
        """使用给定参数执行工具"""
        return await self.execute(**kwargs)

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """使用给定参数执行工具（抽象方法，子类必须实现）"""

    def to_param(self) -> Dict:
        """将工具转换为函数调用格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolResult(BaseModel):
    """表示工具执行结果的类"""

    output: Any = Field(default=None, description="工具输出结果")
    error: Optional[str] = Field(default=None, description="错误信息")
    base64_image: Optional[str] = Field(default=None, description="Base64 编码的图片")
    system: Optional[str] = Field(default=None, description="系统信息")

    class Config:
        arbitrary_types_allowed = True

    def __bool__(self):
        """检查结果是否包含任何内容"""
        return any(getattr(self, field) for field in self.__fields__)

    def __add__(self, other: "ToolResult"):
        """合并两个工具结果"""
        def combine_fields(
            field: Optional[str], other_field: Optional[str], concatenate: bool = True
        ):
            if field and other_field:
                if concatenate:
                    return field + other_field
                raise ValueError("无法合并工具结果")
            return field or other_field

        return ToolResult(
            output=combine_fields(self.output, other.output),
            error=combine_fields(self.error, other.error),
            base64_image=combine_fields(self.base64_image, other.base64_image, False),
            system=combine_fields(self.system, other.system),
        )

    def __str__(self):
        """返回结果的字符串表示"""
        return f"错误: {self.error}" if self.error else self.output

    def replace(self, **kwargs):
        """返回一个新的 ToolResult，其中给定字段被替换"""
        # return self.copy(update=kwargs)
        return type(self)(**{**self.dict(), **kwargs})


class CLIResult(ToolResult):
    """可以渲染为 CLI 输出的工具结果"""


class ToolFailure(ToolResult):
    """表示失败的工具结果"""
