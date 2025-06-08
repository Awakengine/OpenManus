"""异常定义模块

定义了系统中使用的各种自定义异常类。
"""


class ToolError(Exception):
    """工具遇到错误时抛出的异常"""

    def __init__(self, message):
        """初始化工具错误
        
        Args:
            message: 错误消息
        """
        self.message = message


class OpenManusError(Exception):
    """所有 OpenManus 错误的基础异常类"""


class TokenLimitExceeded(OpenManusError):
    """当超过令牌限制时抛出的异常"""
