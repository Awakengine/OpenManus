# -*- coding: utf-8 -*-
"""
OpenManus 主程序入口

这是 OpenManus AI 智能体系统的主要入口点，提供命令行交互界面。
用户可以通过此程序直接与 OpenManus 智能体进行对话和交互。
"""

import asyncio

from app.agent.manus import Manus
from app.logger import logger


async def main():
    """主函数 - 创建并运行 OpenManus 智能体"""
    # 创建并初始化 Manus 智能体
    agent = await Manus.create()
    try:
        # 获取用户输入的提示词
        prompt = input("请输入您的提示词: ")
        if not prompt.strip():
            logger.warning("提供的提示词为空。")
            return

        logger.warning("正在处理您的请求...")
        # 运行智能体处理用户请求
        await agent.run(prompt)
        logger.info("请求处理完成。")
    except KeyboardInterrupt:
        logger.warning("操作被中断。")
    finally:
        # 确保在退出前清理智能体资源
        await agent.cleanup()


if __name__ == "__main__":
    # 运行主程序
    asyncio.run(main())
