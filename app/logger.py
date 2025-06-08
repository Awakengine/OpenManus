"""日志配置模块

该模块使用 loguru 库配置应用程序的日志记录功能，
支持控制台输出和文件输出的不同日志级别。
"""
import sys
from datetime import datetime

from loguru import logger as _logger

from app.config import PROJECT_ROOT


_print_level = "INFO"  # 全局打印日志级别


def define_log_level(print_level="INFO", logfile_level="DEBUG", name: str = None):
    """配置日志级别和输出目标
    
    Args:
        print_level: 控制台输出的日志级别，默认为 "INFO"
        logfile_level: 文件输出的日志级别，默认为 "DEBUG"
        name: 日志文件名前缀，可选
    
    Returns:
        配置好的 logger 实例
    """
    global _print_level
    _print_level = print_level

    # 生成带时间戳的日志文件名
    current_date = datetime.now()
    formatted_date = current_date.strftime("%Y%m%d%H%M%S")
    log_name = (
        f"{name}_{formatted_date}" if name else formatted_date
    )  # 使用前缀名称命名日志

    # 移除默认处理器并添加新的处理器
    _logger.remove()
    _logger.add(sys.stderr, level=print_level)  # 控制台输出
    _logger.add(PROJECT_ROOT / f"logs/{log_name}.log", level=logfile_level)  # 文件输出
    return _logger


# 创建默认的 logger 实例
logger = define_log_level()


if __name__ == "__main__":
    # 测试不同级别的日志输出
    logger.info("应用程序启动")
    logger.debug("调试信息")
    logger.warning("警告信息")
    logger.error("错误信息")
    logger.critical("严重错误信息")

    # 测试异常日志记录
    try:
        raise ValueError("测试错误")
    except Exception as e:
        logger.exception(f"发生错误: {e}")
