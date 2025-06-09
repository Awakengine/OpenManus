#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenManus Web UI 应用程序

为 OpenManus AI 代理系统提供 Web 界面，支持 SQLite 数据库
用于用户管理和对话历史记录。
"""

import asyncio
import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from flask import Flask, jsonify, redirect, render_template, request, session, url_for, Response
from werkzeug.security import check_password_hash, generate_password_hash

from app.agent.manus import Manus
from app.config import config
from app.logger import logger
from app.schema import Message, Role, AgentState


class DatabaseManager:
    """管理用户和对话的 SQLite 数据库操作。"""

    def __init__(self, db_path: str = "openmanus_webui.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """初始化数据库并创建所需的表。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 用户表
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT DEFAULT 'user',
                    created_at DATETIME DEFAULT (datetime('now', 'localtime')),
                    last_login DATETIME,
                    is_active BOOLEAN DEFAULT 1,
                    created_by INTEGER,
                    updated_by INTEGER,
                    updated_at DATETIME,
                    FOREIGN KEY (created_by) REFERENCES users(id),
                    FOREIGN KEY (updated_by) REFERENCES users(id)
                )
            """
            )

            # 如果角色列不存在则添加（用于现有数据库）
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
                conn.commit()
            except sqlite3.OperationalError:
                # 列已存在
                pass

            # 如果昵称列不存在则添加（用于现有数据库）
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN nickname TEXT")
                conn.commit()
            except sqlite3.OperationalError:
                # 列已存在
                pass

            # 如果创建人ID列不存在则添加（用于现有数据库）
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN created_by INTEGER")
                conn.commit()
            except sqlite3.OperationalError:
                # 列已存在
                pass

            # 如果修改人ID列不存在则添加（用于现有数据库）
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN updated_by INTEGER")
                conn.commit()
            except sqlite3.OperationalError:
                # 列已存在
                pass

            # 如果修改时间列不存在则添加（用于现有数据库）
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN updated_at DATETIME")
                conn.commit()
            except sqlite3.OperationalError:
                # 列已存在
                pass

            # 注意：已移除自动创建admin默认管理员用户的逻辑
            # 系统将只保留awakengine作为超级管理员账户

            # 检查 awakengine 用户是否存在并设置为超级管理员
            cursor.execute(
                "SELECT id, role FROM users WHERE username = ?", ("awakengine",)
            )
            awakengine_user = cursor.fetchone()

            if awakengine_user:
                if awakengine_user[1] != "super_admin":
                    cursor.execute(
                        "UPDATE users SET role = 'super_admin' WHERE username = ?",
                        ("awakengine",),
                    )
                    conn.commit()
                    logger.info("已将 awakengine 用户更新为超级管理员角色")
            else:
                # 如果 awakengine 用户不存在，则创建为超级管理员
                awakengine_password_hash = generate_password_hash("awakengine123")
                cursor.execute(
                    """
                    INSERT INTO users (username, email, password_hash, role)
                    VALUES (?, ?, ?, ?)
                """,
                    (
                        "awakengine",
                        "awakengine@openmanus.local",
                        awakengine_password_hash,
                        "super_admin",
                    ),
                )
                conn.commit()
                logger.info(
                    "已创建 awakengine 超级管理员用户: username=awakengine, password=awakengine123"
                )

            # 检查 admin 用户是否存在并创建为超级管理员
            cursor.execute(
                "SELECT id, role FROM users WHERE username = ?", ("admin",)
            )
            admin_user = cursor.fetchone()

            if admin_user:
                if admin_user[1] != "super_admin":
                    cursor.execute(
                        "UPDATE users SET role = 'super_admin' WHERE username = ?",
                        ("admin",),
                    )
                    conn.commit()
                    logger.info("已将 admin 用户更新为超级管理员角色")
            else:
                # 如果 admin 用户不存在，则创建为超级管理员
                admin_password_hash = generate_password_hash("admin123")
                cursor.execute(
                    """
                    INSERT INTO users (username, email, password_hash, role)
                    VALUES (?, ?, ?, ?)
                """,
                    (
                        "admin",
                        "admin@openmanus.local",
                        admin_password_hash,
                        "super_admin",
                    ),
                )
                conn.commit()
                logger.info(
                    "已创建 admin 超级管理员用户: username=admin, password=admin123"
                )

            # 对话表
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    created_at DATETIME DEFAULT (datetime('now', 'localtime')),
                    updated_at DATETIME DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """
            )

            # 消息表
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tool_calls TEXT,
                    tool_call_id TEXT,
                    timestamp DATETIME DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY (conversation_id) REFERENCES conversations (id)
                )
            """
            )

            # 角色表
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS roles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role_name TEXT UNIQUE NOT NULL,
                    role_display_name TEXT NOT NULL,
                    description TEXT,
                    permissions TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT (datetime('now', 'localtime')),
                    updated_at DATETIME DEFAULT (datetime('now', 'localtime')),
                    created_by INTEGER,
                    updated_by INTEGER,
                    FOREIGN KEY (created_by) REFERENCES users(id),
                    FOREIGN KEY (updated_by) REFERENCES users(id)
                )
            """
            )

            # 初始化默认角色数据
            default_roles = [
                ('user', '普通用户', '基本聊天功能', '["chat", "view_history", "edit_profile"]'),
                ('admin', '管理员', '基础管理权限', '["chat", "view_history", "edit_profile", "view_users", "view_stats"]'),
                ('user_admin', '用户管理员', '用户管理权限', '["chat", "view_history", "edit_profile", "view_users", "view_stats", "create_user", "delete_user", "manage_user_status"]'),
                ('role_admin', '角色管理员', '角色管理权限', '["chat", "view_history", "edit_profile", "view_users", "view_stats", "view_roles", "edit_user_role"]'),
                ('super_admin', '超级管理员', '完全管理权限', '["all"]')
            ]
            
            for role_name, display_name, description, permissions in default_roles:
                cursor.execute(
                    "SELECT id FROM roles WHERE role_name = ?", (role_name,)
                )
                if not cursor.fetchone():
                    cursor.execute(
                        "INSERT INTO roles (role_name, role_display_name, description, permissions) VALUES (?, ?, ?, ?)",
                        (role_name, display_name, description, permissions)
                    )

            conn.commit()

    def create_user(self, username: str, email: str, password: str) -> bool:
        """创建新用户账户。"""
        try:
            password_hash = generate_password_hash(password)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                    (username, email, password_hash),
                )
                # 获取新创建用户的ID
                user_id = cursor.lastrowid
                # 设置创建人为自己
                cursor.execute(
                    "UPDATE users SET created_by = ? WHERE id = ?",
                    (user_id, user_id),
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        """验证用户凭据。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, email, password_hash, role FROM users WHERE username = ? AND is_active = 1",
                (username,),
            )
            user = cursor.fetchone()

            if user and check_password_hash(user[3], password):
                # 更新最后登录时间
                cursor.execute(
                    "UPDATE users SET last_login = datetime('now', 'localtime') WHERE id = ?",
                    (user[0],),
                )
                conn.commit()

                return {
                    "id": user[0],
                    "username": user[1],
                    "email": user[2],
                    "role": user[4],
                }
        return None

    def create_conversation(self, user_id: int, title: str) -> str:
        """创建新对话。"""
        conversation_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO conversations (id, user_id, title) VALUES (?, ?, ?)",
                (conversation_id, user_id, title),
            )
            conn.commit()
        return conversation_id

    def get_user_conversations(self, user_id: int) -> List[Dict]:
        """获取用户的所有对话。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, title, strftime('%Y-%m-%d %H:%M:%S', created_at) as created_at, strftime('%Y-%m-%d %H:%M:%S', updated_at) as updated_at FROM conversations WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,),
            )
            conversations = cursor.fetchall()

            return [
                {
                    "id": conv[0],
                    "title": conv[1],
                    "created_at": conv[2],
                    "updated_at": conv[3],
                }
                for conv in conversations
            ]

    def save_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        tool_calls: Optional[str] = None,
        tool_call_id: Optional[str] = None,
    ):
        """将消息保存到数据库。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO messages (conversation_id, role, content, tool_calls, tool_call_id) VALUES (?, ?, ?, ?, ?)",
                (conversation_id, role, content, tool_calls, tool_call_id),
            )

            # 更新对话时间戳
            cursor.execute(
                "UPDATE conversations SET updated_at = datetime('now', 'localtime') WHERE id = ?",
                (conversation_id,),
            )
            conn.commit()

    def get_conversation_messages(self, conversation_id: str) -> List[Dict]:
        """获取对话的所有消息。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role, content, tool_calls, tool_call_id, strftime('%Y-%m-%d %H:%M:%S', timestamp) as timestamp FROM messages WHERE conversation_id = ? ORDER BY timestamp",
                (conversation_id,),
            )
            messages = cursor.fetchall()

            return [
                {
                    "role": msg[0],
                    "content": msg[1],
                    "tool_calls": json.loads(msg[2]) if msg[2] else None,
                    "tool_call_id": msg[3],
                    "timestamp": msg[4],
                }
                for msg in messages
            ]

    def delete_conversation(self, conversation_id: str, user_id: int) -> bool:
        """删除指定的对话及其所有消息。"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 首先验证对话是否属于该用户
                cursor.execute(
                    "SELECT user_id FROM conversations WHERE id = ?",
                    (conversation_id,)
                )
                result = cursor.fetchone()
                if not result or result[0] != user_id:
                    return False
                
                # 删除对话的所有消息
                cursor.execute(
                    "DELETE FROM messages WHERE conversation_id = ?",
                    (conversation_id,)
                )
                
                # 删除对话
                cursor.execute(
                    "DELETE FROM conversations WHERE id = ? AND user_id = ?",
                    (conversation_id, user_id)
                )
                
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False

    def get_all_users(self, keyword=None, role=None, status=None, date=None) -> List[Dict]:
        """获取所有用户（仅管理员），支持搜索过滤。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 构建基础查询
            query = """SELECT u.id, u.username, u.email, u.role, 
                       strftime('%Y-%m-%d %H:%M:%S', u.created_at) as created_at, 
                       strftime('%Y-%m-%d %H:%M:%S', u.last_login) as last_login, 
                       u.is_active, u.nickname, u.created_by, u.updated_by,
                       strftime('%Y-%m-%d %H:%M:%S', u.updated_at) as updated_at,
                       c.username as created_by_name, up.username as updated_by_name
                       FROM users u 
                       LEFT JOIN users c ON u.created_by = c.id
                       LEFT JOIN users up ON u.updated_by = up.id"""
            conditions = []
            params = []
            
            # 添加搜索条件
            if keyword:
                conditions.append("(u.username LIKE ? OR u.email LIKE ? OR u.nickname LIKE ?)")
                keyword_param = f"%{keyword}%"
                params.extend([keyword_param, keyword_param, keyword_param])
            
            if role:
                conditions.append("u.role = ?")
                params.append(role)
            
            if status:
                if status == 'active':
                    conditions.append("u.is_active = 1")
                elif status == 'disabled':
                    conditions.append("u.is_active = 0")
            
            if date:
                conditions.append("DATE(u.created_at) = ?")
                params.append(date)
            
            # 组合查询条件
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY created_at DESC"
            
            cursor.execute(query, params)
            users = cursor.fetchall()

            return [
                {
                    "id": user[0],
                    "username": user[1],
                    "email": user[2],
                    "role": user[3],
                    "created_at": user[4],
                    "last_login": user[5],
                    "is_active": bool(user[6]),
                    "nickname": user[7],
                    "created_by": user[8],
                    "updated_by": user[9],
                    "updated_at": user[10],
                    "created_by_name": user[11],
                    "updated_by_name": user[12],
                    # 注意：出于安全考虑，不返回password_hash字段
                }
                for user in users
            ]

    def update_user_role(self, user_id: int, role: str, updated_by: int = None) -> bool:
        """更新用户角色（仅管理员）。"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET role = ?, updated_by = ?, updated_at = datetime('now', 'localtime') WHERE id = ?", 
                    (role, updated_by, user_id)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False

    def update_user_status(self, user_id: int, is_active: bool, updated_by: int = None) -> bool:
        """更新用户活跃状态（仅管理员）。"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET is_active = ?, updated_by = ?, updated_at = datetime('now', 'localtime') WHERE id = ?", 
                    (is_active, updated_by, user_id)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False

    def delete_user(self, user_id: int) -> bool:
        """删除用户及所有相关数据（仅管理员）。"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 获取用户的对话
                cursor.execute(
                    "SELECT id FROM conversations WHERE user_id = ?", (user_id,)
                )
                conversation_ids = [row[0] for row in cursor.fetchall()]

                # 删除用户所有对话的消息
                for conv_id in conversation_ids:
                    cursor.execute(
                        "DELETE FROM messages WHERE conversation_id = ?", (conv_id,)
                    )

                # 删除对话
                cursor.execute(
                    "DELETE FROM conversations WHERE user_id = ?", (user_id,)
                )

                # 删除用户
                cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))

                conn.commit()
                return True
        except Exception:
            return False

    def create_user_with_role(
        self, username: str, email: str, password: str, role: str = "user", created_by: int = None
    ) -> bool:
        """创建带有指定角色的新用户账户。"""
        try:
            password_hash = generate_password_hash(password)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO users (username, email, password_hash, role, created_by) VALUES (?, ?, ?, ?, ?)",
                    (username, email, password_hash, role, created_by),
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def reset_user_password(self, user_id: int, new_password: str, updated_by: int = None) -> bool:
        """重置用户密码。"""
        try:
            password_hash = generate_password_hash(new_password)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET password_hash = ?, updated_by = ?, updated_at = datetime('now', 'localtime') WHERE id = ?",
                    (password_hash, updated_by, user_id),
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """根据ID获取用户信息。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, email, password_hash, role, strftime('%Y-%m-%d %H:%M:%S', created_at) as created_at, strftime('%Y-%m-%d %H:%M:%S', last_login) as last_login, is_active, nickname FROM users WHERE id = ?",
                (user_id,),
            )
            user = cursor.fetchone()

            if user:
                return {
                    "id": user[0],
                    "username": user[1],
                    "email": user[2],
                    "password_hash": user[3],
                    "role": user[4],
                    "created_at": user[5],
                    "last_login": user[6],
                    "is_active": bool(user[7]),
                    "nickname": user[8],
                }
        return None

    def update_user_email(self, user_id: int, email: str) -> bool:
        """更新用户邮箱。"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET email = ? WHERE id = ?", (email, user_id)
                )
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.IntegrityError:
            return False

    def update_user_password(self, user_id: int, new_password: str) -> tuple[bool, str]:
        """更新用户密码。
        
        Returns:
            tuple[bool, str]: (是否成功, 错误信息)
        """
        try:
            password_hash = generate_password_hash(new_password)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (password_hash, user_id),
                )
                conn.commit()
                if cursor.rowcount > 0:
                    return True, ""
                else:
                    return False, "用户不存在或密码未发生变化"
        except sqlite3.Error as e:
            return False, f"数据库错误: {str(e)}"
        except Exception as e:
            return False, f"系统错误: {str(e)}"

    def update_user_nickname(self, user_id: int, nickname: str) -> bool:
        """更新用户昵称。"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET nickname = ? WHERE id = ?", (nickname, user_id)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False

    def verify_password(self, password: str, password_hash: str) -> bool:
        """验证密码。"""
        return check_password_hash(password_hash, password)

    def get_user_details(self, user_id: int) -> Optional[Dict]:
        """获取用户详细信息。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT id, username, email, role, strftime('%Y-%m-%d %H:%M:%S', created_at) as created_at, strftime('%Y-%m-%d %H:%M:%S', last_login) as last_login, is_active, nickname,
                   (SELECT COUNT(*) FROM conversations WHERE user_id = ?) as conversation_count,
                   (SELECT COUNT(*) FROM messages WHERE conversation_id IN
                    (SELECT id FROM conversations WHERE user_id = ?)) as message_count
                   FROM users WHERE id = ?""",
                (user_id, user_id, user_id),
            )
            user = cursor.fetchone()

            if user:
                return {
                    "id": user[0],
                    "username": user[1],
                    "email": user[2],
                    "role": user[3],
                    "created_at": user[4],
                    "last_login": user[5],
                    "is_active": bool(user[6]),
                    "nickname": user[7],
                    "conversation_count": user[8],
                    "message_count": user[9],
                }
        return None

    def batch_delete_users(self, user_ids: List[int]) -> int:
        """批量删除用户。"""
        success_count = 0
        for user_id in user_ids:
            if self.delete_user(user_id):
                success_count += 1
        return success_count

    def batch_update_user_status(self, user_ids: List[int], is_active: bool, updated_by: int = None) -> int:
        """批量更新用户状态。"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                placeholders = ",".join("?" * len(user_ids))
                cursor.execute(
                    f"UPDATE users SET is_active = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
                    [is_active, updated_by] + user_ids,
                )
                conn.commit()
                return cursor.rowcount
        except Exception:
            return 0

    def get_system_stats(self) -> Dict:
        """获取系统统计信息。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 用户统计
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
            active_users = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
            admin_users = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'super_admin'")
            super_admin_users = cursor.fetchone()[0]

            # 对话统计
            cursor.execute("SELECT COUNT(*) FROM conversations")
            total_conversations = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM messages")
            total_messages = cursor.fetchone()[0]

            # 最近活跃用户
            cursor.execute(
                "SELECT COUNT(*) FROM users WHERE last_login > datetime('now', '-7 days')"
            )
            recent_active_users = cursor.fetchone()[0]

            return {
                "users": {
                    "total": total_users,
                    "active": active_users,
                    "inactive": total_users - active_users,
                    "admin": admin_users,
                    "super_admin": super_admin_users,
                    "recent_active": recent_active_users,
                },
                "conversations": {"total": total_conversations},
                "messages": {"total": total_messages},
            }

    # 角色管理相关方法
    def get_all_roles(self) -> List[Dict]:
        """获取所有角色。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, role_name, role_display_name, description, permissions, created_at, updated_at FROM roles ORDER BY id"
            )
            roles = cursor.fetchall()
            return [
                {
                    "id": role[0],
                    "name": role[1],
                    "display_name": role[2],
                    "description": role[3],
                    "permissions": role[4].split(',') if role[4] else [],
                    "created_at": role[5],
                    "updated_at": role[6],
                }
                for role in roles
            ]
    
    def get_roles_paginated(self, page: int = 1, page_size: int = 10, search: str = '', status: str = '', role_name: str = '', display_name: str = '', description: str = '') -> Dict:
        """分页获取角色列表，支持按字段分别搜索和状态筛选。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 构建WHERE条件
            where_conditions = []
            params = []
            
            # 支持旧的合并搜索方式（向后兼容）
            if search:
                where_conditions.append("(role_name LIKE ? OR role_display_name LIKE ? OR description LIKE ?)")
                search_param = f"%{search}%"
                params.extend([search_param, search_param, search_param])
            
            # 支持按字段分别搜索
            if role_name:
                where_conditions.append("role_name LIKE ?")
                params.append(f"%{role_name}%")
            
            if display_name:
                where_conditions.append("role_display_name LIKE ?")
                params.append(f"%{display_name}%")
            
            if description:
                where_conditions.append("description LIKE ?")
                params.append(f"%{description}%")
            
            # 注意：由于roles表没有status字段，这里暂时忽略status筛选
            # 如果需要状态筛选，需要先在数据库中添加status字段
            
            where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            # 获取总数
            count_query = f"SELECT COUNT(*) FROM roles{where_clause}"
            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]
            
            # 计算偏移量
            offset = (page - 1) * page_size
            
            # 获取分页数据
            data_query = f"SELECT id, role_name, role_display_name, description, permissions, created_at, updated_at FROM roles{where_clause} ORDER BY id LIMIT ? OFFSET ?"
            cursor.execute(data_query, params + [page_size, offset])
            roles = cursor.fetchall()
            
            roles_list = [
                {
                    "id": role[0],
                    "name": role[1],
                    "display_name": role[2],
                    "description": role[3],
                    "permissions": role[4].split(',') if role[4] else [],
                    "created_at": role[5],
                    "updated_at": role[6],
                }
                for role in roles
            ]
            
            return {
                "roles": roles_list,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size
            }

    def get_role_by_name(self, role_name: str) -> Optional[Dict]:
        """根据角色名称获取角色详细信息（支持模糊查询）。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, role_name, role_display_name, description, permissions, created_at, updated_at FROM roles WHERE role_name LIKE ?",
                (f"%{role_name}%",)
            )
            role = cursor.fetchone()
            if role:
                return {
                    "id": role[0],
                    "name": role[1],
                    "display_name": role[2],
                    "description": role[3],
                    "permissions": role[4].split(',') if role[4] else [],
                    "created_at": role[5],
                    "updated_at": role[6],
                }
            return None

    def create_role(self, name: str, display_name: str, description: str = None, permissions: List[str] = None, created_by: int = None) -> Optional[int]:
        """创建新角色。"""
        try:
            permissions_str = ','.join(permissions) if permissions else ''
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO roles (role_name, role_display_name, description, permissions, created_by) VALUES (?, ?, ?, ?, ?)",
                    (name, display_name, description, permissions_str, created_by),
                )
                conn.commit()
                return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None

    def update_role(self, role_id: int, display_name: str, description: str = None, permissions: List[str] = None, updated_by: int = None) -> bool:
        """更新角色信息。"""
        try:
            permissions_str = ','.join(permissions) if permissions else ''
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE roles SET role_display_name = ?, description = ?, permissions = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (display_name, description, permissions_str, updated_by, role_id),
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False

    def delete_role(self, role_id: int) -> bool:
        """删除角色。"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM roles WHERE id = ?", (role_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False

    def check_role_in_use(self, role_id: int) -> bool:
        """检查角色是否正在被用户使用。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # 获取角色名称
            cursor.execute("SELECT role_name FROM roles WHERE id = ?", (role_id,))
            role = cursor.fetchone()
            if not role:
                return False
            
            role_name = role[0]
            # 检查是否有用户使用此角色
            cursor.execute("SELECT COUNT(*) FROM users WHERE role = ?", (role_name,))
            count = cursor.fetchone()[0]
            return count > 0


class OpenManusWebUI:
    """主要的 Web UI 应用程序类。"""

    def __init__(self):
        self.app = Flask(__name__)
        self.app.secret_key = "openmanus-webui-secret-key-change-in-production"
        self.db = DatabaseManager()
        self.agent_instances = {}  # 存储每个会话的代理实例
        self.conversation_agents = {}  # 存储每个对话的独立代理实例

        self.setup_routes()

    def setup_routes(self):
        """设置 Flask 路由。"""

        @self.app.route("/")
        def index():
            # 首页显示简介页面，不需要登录
            return render_template("intro.html")

        @self.app.route("/chat")
        def chat():
            # 聊天页面，支持游客模式
            return render_template("chat.html")

        @self.app.route("/demo")
        def demo():
            # 重定向到聊天页面的游客模式
            return redirect(url_for("chat", guest="true"))

        @self.app.route("/login", methods=["GET", "POST"])
        def login():
            if request.method == "POST":
                data = request.get_json()
                username = data.get("username")
                password = data.get("password")

                user = self.db.authenticate_user(username, password)
                if user:
                    # 获取完整用户信息包括昵称
                    full_user = self.db.get_user_by_id(user["id"])
                    display_name = full_user.get("nickname") if full_user and full_user.get("nickname") else user["username"]
                    
                    session["user_id"] = user["id"]
                    session["username"] = user["username"]
                    session["display_name"] = display_name
                    session["role"] = user["role"]
                    return jsonify({"success": True, "data": {"user_id": user["id"], "username": user["username"], "display_name": display_name, "role": user["role"]}, "message": "登录成功", "code": 200})
                else:
                    return jsonify({"success": False, "data": None, "message": "用户名或密码错误", "code": 401})

            return render_template("login.html")

        @self.app.route("/register", methods=["GET", "POST"])
        def register():
            if request.method == "POST":
                data = request.get_json()
                username = data.get("username")
                email = data.get("email")
                password = data.get("password")

                if self.db.create_user(username, email, password):
                    return jsonify({"success": True, "data": {"username": username, "email": email}, "message": "注册成功", "code": 200})
                else:
                    return jsonify({"success": False, "data": None, "message": "用户名或邮箱已存在", "code": 400})

            return render_template("register.html")

        @self.app.route("/logout")
        def logout():
            session.clear()
            return redirect(url_for("login"))

        @self.app.route("/settings")
        def settings():
            """设置页面"""
            if "user_id" not in session:
                return redirect(url_for("login"))
            return render_template("settings.html")

        @self.app.route("/management")
        def management():
            """统一管理设置页面"""
            if "user_id" not in session:
                return redirect(url_for("login"))
            return render_template("management.html", session=session)

        @self.app.route("/api/profile", methods=["GET"])
        def get_profile():
            """获取用户个人信息"""
            if "user_id" not in session:
                return jsonify({"error": "未认证"}), 401

            user = self.db.get_user_by_id(session["user_id"])
            if user:
                return jsonify(
                    {
                        "success": True,
                        "data": {
                            "username": user["username"],
                            "email": user["email"],
                            "role": user["role"],
                            "nickname": user.get("nickname", ""),
                        },
                        "message": "获取用户信息成功",
                        "code": 200
                    }
                )
            else:
                return jsonify({"success": False, "data": None, "message": "用户不存在", "code": 404}), 404

        @self.app.route("/api/profile", methods=["PUT"])
        def update_profile():
            """更新用户个人信息"""
            if "user_id" not in session:
                return jsonify({"success": False, "data": None, "message": "未认证", "code": 401}), 401

            data = request.get_json()
            email = data.get("email")
            current_password = data.get("currentPassword")
            new_password = data.get("newPassword")

            if not email:
                return jsonify({"success": False, "data": None, "message": "邮箱不能为空", "code": 400}), 400

            # 验证当前密码
            user = self.db.get_user_by_id(session["user_id"])
            if not user:
                return jsonify({"success": False, "data": None, "message": "用户不存在", "code": 404}), 404

            if not self.db.verify_password(current_password, user["password_hash"]):
                return jsonify({"success": False, "data": None, "message": "当前密码错误", "code": 400}), 400

            # 更新邮箱
            if not self.db.update_user_email(session["user_id"], email):
                return jsonify({"success": False, "data": None, "message": "邮箱更新失败，可能已被其他用户使用", "code": 400}), 400

            # 如果提供了新密码，则更新密码
            if new_password:
                if len(new_password) < 6:
                    return jsonify({"success": False, "data": None, "message": "新密码长度至少6位", "code": 400}), 400

                success, error_msg = self.db.update_user_password(session["user_id"], new_password)
                if not success:
                    return jsonify({"success": False, "data": None, "message": error_msg or "密码更新失败", "code": 500}), 500

            return jsonify({"success": True, "data": {"email": email}, "message": "个人信息更新成功", "code": 200})

        @self.app.route("/api/profile/basic", methods=["PUT"])
        def update_profile_basic():
            """更新用户基本信息（昵称、邮箱）"""
            if "user_id" not in session:
                return jsonify({"success": False, "data": None, "message": "未认证", "code": 401}), 401

            data = request.get_json()
            email = data.get("email")
            nickname = data.get("nickname")

            if not email:
                return jsonify({"success": False, "data": None, "message": "邮箱不能为空", "code": 400}), 400

            # 检查用户是否存在
            user = self.db.get_user_by_id(session["user_id"])
            if not user:
                return jsonify({"success": False, "data": None, "message": "用户不存在", "code": 404}), 404

            # 更新邮箱
            if not self.db.update_user_email(session["user_id"], email):
                return jsonify({"success": False, "data": None, "message": "邮箱更新失败，可能已被其他用户使用", "code": 400}), 400

            # 更新昵称
            if nickname is not None:
                if not self.db.update_user_nickname(session["user_id"], nickname):
                    return jsonify({"success": False, "data": None, "message": "昵称更新失败", "code": 500}), 500
                # 更新session中的display_name
                session["display_name"] = nickname if nickname else session.get("username", "")

            return jsonify({"success": True, "data": {"email": email, "nickname": nickname}, "message": "基本信息更新成功", "code": 200})

        @self.app.route("/api/profile/password", methods=["PUT"])
        def update_profile_password():
            """修改用户密码"""
            if "user_id" not in session:
                return jsonify({"success": False, "data": None, "message": "未认证", "code": 401}), 401

            data = request.get_json()
            current_password = data.get("currentPassword")
            new_password = data.get("newPassword")

            if not current_password:
                return jsonify({"success": False, "data": None, "message": "请输入当前密码", "code": 400}), 400

            if not new_password:
                return jsonify({"success": False, "data": None, "message": "请输入新密码", "code": 400}), 400

            if len(new_password) < 6:
                return jsonify({"success": False, "data": None, "message": "新密码长度至少6位", "code": 400}), 400

            # 验证当前密码
            user = self.db.get_user_by_id(session["user_id"])
            if not user:
                return jsonify({"success": False, "data": None, "message": "用户不存在", "code": 404}), 404

            if not self.db.verify_password(current_password, user["password_hash"]):
                return jsonify({"success": False, "data": None, "message": "当前密码错误", "code": 400}), 400

            # 更新密码
            success, error_msg = self.db.update_user_password(session["user_id"], new_password)
            if not success:
                return jsonify({"success": False, "data": None, "message": error_msg or "密码更新失败", "code": 500}), 500

            # 密码修改成功后清除session，强制重新登录
            session.clear()
            return jsonify({"success": True, "data": {"logout": True}, "message": "密码修改成功，请重新登录", "code": 200})

        @self.app.route("/api/conversations")
        def get_conversations():
            if "user_id" not in session:
                return jsonify({"success": False, "data": None, "message": "未认证", "code": 401}), 401

            conversations = self.db.get_user_conversations(session["user_id"])
            return jsonify({"success": True, "data": {"conversations": conversations}, "message": "获取对话列表成功", "code": 200})

        @self.app.route("/api/conversations", methods=["POST"])
        def create_conversation():
            if "user_id" not in session:
                return jsonify({"success": False, "data": None, "message": "未认证", "code": 401}), 401

            # 支持both JSON and form data
            if request.is_json:
                data = request.get_json()
                title = data.get("title", "New Conversation")
            else:
                title = request.form.get("title", "New Conversation")

            conversation_id = self.db.create_conversation(session["user_id"], title)
            return jsonify({"success": True, "data": {"conversation_id": conversation_id, "title": title}, "message": "创建对话成功", "code": 200})

        @self.app.route("/api/conversations/<conversation_id>/messages")
        def get_messages(conversation_id):
            if "user_id" not in session:
                return jsonify({"success": False, "data": None, "message": "未认证", "code": 401}), 401

            messages = self.db.get_conversation_messages(conversation_id)
            return jsonify({"success": True, "data": {"messages": messages}, "message": "获取消息列表成功", "code": 200})

        @self.app.route("/api/conversations/<conversation_id>", methods=["DELETE"])
        def delete_conversation(conversation_id):
            if "user_id" not in session:
                return jsonify({"success": False, "data": None, "message": "未认证", "code": 401}), 401

            success = self.db.delete_conversation(conversation_id, session["user_id"])
            if success:
                return jsonify({"success": True, "data": None, "message": "删除对话成功", "code": 200})
            else:
                return jsonify({"success": False, "data": None, "message": "删除对话失败，对话不存在或无权限", "code": 404}), 404

        @self.app.route("/api/chat", methods=["POST"])
        def api_chat():
            if "user_id" not in session:
                return jsonify({"success": False, "data": None, "message": "请先登录", "code": 401})

            message = request.form.get("message")
            conversation_id = request.form.get("conversation_id")

            if not message:
                return jsonify({"success": False, "data": None, "message": "消息不能为空", "code": 400})

            try:
                # 如果没有提供conversation_id，创建新对话
                if not conversation_id:
                    conversation_id = self.db.create_conversation(
                        session["user_id"],
                        f"对话 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    )

                # 保存用户消息
                self.db.save_message(conversation_id, "user", message)

                # 调用OpenManus代理
                response = asyncio.run(
                    self.process_with_agent(message, conversation_id)
                )

                # 保存助手回复
                self.db.save_message(conversation_id, "assistant", response)

                return jsonify(
                    {
                        "success": True,
                        "data": {
                            "response": response,
                            "conversation_id": conversation_id,
                        },
                        "message": "聊天成功",
                        "code": 200
                    }
                )

            except Exception as e:
                logger.error(f"Chat error: {e}")
                return jsonify({"success": False, "data": None, "message": "处理消息时发生错误", "code": 500})

        @self.app.route("/api/chat-guest", methods=["POST"])
        def api_chat_guest():
            """游客聊天API，不保存对话记录"""
            message = request.form.get("message")

            if not message:
                return jsonify({"success": False, "data": None, "message": "消息不能为空", "code": 400})

            try:
                # 调用OpenManus代理
                response = asyncio.run(self.process_with_agent(message, None))

                return jsonify({"success": True, "data": {"response": response}, "message": "游客聊天成功", "code": 200})

            except Exception as e:
                logger.error(f"Guest chat error: {e}")
                return jsonify({"success": False, "data": None, "message": "处理消息时发生错误", "code": 500})

        @self.app.route("/api/chat-stream", methods=["POST"])
        def api_chat_stream():
            """流式聊天API，支持实时输出"""
            if "user_id" not in session:
                return jsonify({"success": False, "data": None, "message": "请先登录", "code": 401})

            message = request.form.get("message")
            conversation_id = request.form.get("conversation_id")
            selected_model = request.form.get("model")  # 获取选择的模型

            if not message:
                return jsonify({"success": False, "data": None, "message": "消息不能为空", "code": 400})

            # 在请求上下文中获取用户ID
            user_id = session["user_id"]
            user_session_id = session.get("user_id", "guest")

            def generate():
                try:
                    # 如果没有提供conversation_id，创建新对话
                    if not conversation_id:
                        new_conversation_id = self.db.create_conversation(
                            user_id,
                            f"对话 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                        )
                    else:
                        new_conversation_id = conversation_id

                    # 保存用户消息
                    self.db.save_message(new_conversation_id, "user", message)

                    # 调用OpenManus代理并流式输出
                    full_response = ""
                    for chunk in self.process_with_agent_stream(message, new_conversation_id, user_session_id):
                        if chunk:
                            full_response += chunk
                            yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"

                    # 保存助手回复
                    self.db.save_message(new_conversation_id, "assistant", full_response)

                    # 发送完成信号
                    yield f"data: {json.dumps({'type': 'done', 'conversation_id': new_conversation_id})}\n\n"
                    yield "data: [DONE]\n\n"

                except Exception as e:
                    logger.error(f"Stream chat error: {e}")
                    yield f"data: {json.dumps({'type': 'error', 'message': '处理消息时发生错误'})}\n\n"

            return Response(generate(), mimetype='text/plain')

        @self.app.route("/api/chat-guest-stream", methods=["POST"])
        def api_chat_guest_stream():
            """游客流式聊天API，不保存对话记录"""
            message = request.form.get("message")
            selected_model = request.form.get("model")  # 获取选择的模型

            if not message:
                return jsonify({"success": False, "data": None, "message": "消息不能为空", "code": 400})

            def generate():
                try:
                    # 调用OpenManus代理并流式输出
                    for chunk in self.process_with_agent_stream(message, None, "guest"):
                        if chunk:
                            yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"

                    # 发送完成信号
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    yield "data: [DONE]\n\n"

                except Exception as e:
                    logger.error(f"Guest stream chat error: {e}")
                    yield f"data: {json.dumps({'type': 'error', 'message': '处理消息时发生错误'})}\n\n"

            return Response(generate(), mimetype='text/plain')

        @self.app.route("/api/models", methods=["GET"])
        def api_get_models():
            """获取LM Studio模型列表"""
            try:
                import requests
                # 从配置中获取LM Studio的base_url
                base_url = "http://localhost:1234/v1"  # 默认LM Studio地址
                
                response = requests.get(f"{base_url}/models", timeout=5)
                if response.status_code == 200:
                    return jsonify(response.json())
                else:
                    return jsonify({"error": "Failed to fetch models", "status_code": response.status_code}), response.status_code
            except Exception as e:
                logger.error(f"Error fetching models: {e}")
                return jsonify({"error": "LM Studio connection failed", "message": str(e)}), 500

        @self.app.route("/api/check-auth", methods=["GET"])
        def api_check_auth():
            """检查用户登录状态"""
            # 调试信息
            logger.info(f"API check-auth called - Session: {dict(session)}")
            
            if "user_id" not in session:
                logger.warning("API check-auth: User not authenticated")
                return jsonify({"success": False, "data": None, "message": "未认证", "code": 401}), 401
            
            # 获取用户完整信息包括昵称
            user = self.db.get_user_by_id(session.get("user_id"))
            display_name = user.get("nickname") if user and user.get("nickname") else session.get("username", "")
            
            return jsonify(
                {
                    "success": True,
                    "data": {
                        "authenticated": True,
                        "username": session.get("username", ""),
                        "display_name": display_name,
                        "nickname": user.get("nickname", "") if user else "",
                        "role": session.get("role", "user"),
                        "user_id": session.get("user_id", ""),
                    },
                    "message": "认证状态检查成功",
                    "code": 200
                }
            )

        # 管理员路由
        @self.app.route("/admin")
        def admin_panel():
            """管理员面板"""
            # 调试信息
            logger.info(f"Admin panel access attempt - Session: {dict(session)}")
            logger.info(f"User role from session: {session.get('role', 'None')}")
            logger.info(f"Is admin check result: {self.is_admin()}")
            
            if not self.is_admin():
                logger.warning("Admin access denied, redirecting to login")
                return redirect(url_for("login"))
            return render_template("admin.html", session=session)

        @self.app.route("/admin/users", methods=["GET"])
        def admin_get_users():
            """获取所有用户（管理员），支持搜索过滤"""
            if not self.is_admin():
                return jsonify({"data": None, "message": "权限不足", "code": 403}), 403

            # 获取查询参数
            keyword = request.args.get('keyword')
            role = request.args.get('role')
            status = request.args.get('status')
            date = request.args.get('date')

            users = self.db.get_all_users(keyword=keyword, role=role, status=status, date=date)
            return jsonify({"data": users, "message": "获取用户列表成功", "code": 200})

        @self.app.route("/admin/users/export", methods=["GET"])
        def admin_export_users():
            """导出用户数据（管理员）"""
            if not self.is_admin():
                return jsonify({"data": None, "message": "权限不足", "code": 403}), 403

            # 获取查询参数
            keyword = request.args.get('keyword')
            role = request.args.get('role')
            status = request.args.get('status')
            date = request.args.get('date')

            users = self.db.get_all_users(keyword=keyword, role=role, status=status, date=date)
            
            # 生成CSV内容
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # 写入表头
            writer.writerow(['用户名', '昵称', '邮箱', '角色', '状态', '创建时间'])
            
            # 写入数据
            for user in users:
                writer.writerow([
                    user['username'],
                    user['nickname'] or '',
                    user['email'],
                    user['role'],
                    '激活' if user['is_active'] else '禁用',
                    user['created_at']
                ])
            
            output.seek(0)
            
            # 返回CSV文件
            return Response(
                output.getvalue(),
                mimetype='text/csv',
                headers={"Content-disposition": "attachment; filename=users.csv"}
            )

        @self.app.route("/admin/users/import", methods=["POST"])
        def admin_import_users():
            """导入用户数据（管理员）"""
            if not self.is_admin():
                return jsonify({"data": None, "message": "权限不足", "code": 403}), 403

            if 'file' not in request.files:
                return jsonify({"data": None, "message": "未选择文件", "code": 400}), 400

            file = request.files['file']
            if file.filename == '':
                return jsonify({"data": None, "message": "未选择文件", "code": 400}), 400

            try:
                import csv
                import io
                
                # 读取文件内容
                stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
                csv_input = csv.reader(stream)
                
                # 跳过表头
                next(csv_input)
                
                imported = 0
                skipped = 0
                
                for row in csv_input:
                    if len(row) < 3:  # 至少需要用户名、邮箱、角色
                        continue
                        
                    username = row[0].strip()
                    nickname = row[1].strip() if len(row) > 1 else ''
                    email = row[2].strip()
                    role = row[3].strip() if len(row) > 3 else 'user'
                    
                    # 检查用户是否已存在
                    if self.db.get_user_by_username(username) or self.db.get_user_by_email(email):
                        skipped += 1
                        continue
                    
                    # 生成默认密码
                    default_password = '123456'
                    password_hash = generate_password_hash(default_password)
                    
                    # 创建用户
                    if self.db.create_user(username, email, password_hash, nickname, role):
                        imported += 1
                    else:
                        skipped += 1
                
                return jsonify({
                    "data": {"imported": imported, "skipped": skipped}, 
                    "message": "导入完成", 
                    "code": 200
                })
                
            except Exception as e:
                logger.error(f"导入用户失败: {e}")
                return jsonify({"data": None, "message": f"导入失败: {str(e)}", "code": 500}), 500

        @self.app.route("/admin/users/<int:user_id>/role", methods=["PUT"])
        def admin_update_user_role(user_id):
            """更新用户角色（超级管理员）"""
            if not self.is_super_admin():
                return jsonify({"data": None, "message": "权限不足", "code": 403}), 403

            data = request.get_json()
            role = data.get("role")

            if role not in ["user", "admin", "super_admin"]:
                return jsonify({"data": None, "message": "无效的角色", "code": 400}), 400

            current_user_id = session.get('user_id')
            if self.db.update_user_role(user_id, role, current_user_id):
                return jsonify({"data": {"user_id": user_id, "role": role}, "message": "角色更新成功", "code": 200})
            else:
                return jsonify({"data": None, "message": "更新失败", "code": 500}), 500

        @self.app.route("/admin/users/<int:user_id>/status", methods=["PUT"])
        def admin_update_user_status(user_id):
            """更新用户状态（管理员）"""
            if not self.is_admin():
                return jsonify({"data": None, "message": "权限不足", "code": 403}), 403

            data = request.get_json()
            is_active = data.get("is_active")

            current_user_id = session.get('user_id')
            if self.db.update_user_status(user_id, is_active, current_user_id):
                return jsonify({"data": {"user_id": user_id, "is_active": is_active}, "message": "用户状态更新成功", "code": 200})
            else:
                return jsonify({"data": None, "message": "更新失败", "code": 500}), 500

        @self.app.route("/admin/users/<int:user_id>", methods=["DELETE"])
        def admin_delete_user(user_id):
            """删除用户（超级管理员）"""
            if not self.is_super_admin():
                return jsonify({"data": None, "message": "权限不足", "code": 403}), 403

            # 不能删除自己
            if user_id == session.get("user_id"):
                return jsonify({"data": None, "message": "不能删除自己", "code": 400}), 400

            if self.db.delete_user(user_id):
                return jsonify({"data": {"user_id": user_id}, "message": "用户删除成功", "code": 200})
            else:
                return jsonify({"data": None, "message": "删除失败", "code": 500}), 500

        @self.app.route("/admin/users", methods=["POST"])
        def admin_create_user():
            """创建用户（管理员）"""
            if not self.is_admin():
                return jsonify({"data": None, "message": "权限不足", "code": 403}), 403

            data = request.get_json()
            username = data.get("username")
            email = data.get("email")
            password = data.get("password")
            role = data.get("role", "user")

            if not all([username, email, password]):
                return jsonify({"data": None, "message": "用户名、邮箱和密码不能为空", "code": 400}), 400

            if role not in ["user", "admin", "super_admin"]:
                return jsonify({"data": None, "message": "无效的角色", "code": 400}), 400

            # 只有超级管理员可以创建管理员和超级管理员
            if role in ["admin", "super_admin"] and not self.is_super_admin():
                return jsonify({"data": None, "message": "权限不足，无法创建管理员用户", "code": 403}), 403

            current_user_id = session.get('user_id')
            if self.db.create_user_with_role(username, email, password, role, current_user_id):
                return jsonify({"data": {"username": username, "email": email, "role": role}, "message": "用户创建成功", "code": 200})
            else:
                return jsonify({"data": None, "message": "创建用户失败，用户名或邮箱可能已存在", "code": 400}), 400

        @self.app.route("/admin/users/<int:user_id>/reset-password", methods=["PUT"])
        def admin_reset_password(user_id):
            """重置用户密码（管理员）"""
            if not self.is_admin():
                return jsonify({"data": None, "message": "权限不足", "code": 403}), 403

            data = request.get_json()
            new_password = data.get("new_password")

            if not new_password:
                return jsonify({"data": None, "message": "新密码不能为空", "code": 400}), 400

            current_user_id = session.get('user_id')
            if self.db.reset_user_password(user_id, new_password, current_user_id):
                return jsonify({"data": {"user_id": user_id}, "message": "密码重置成功", "code": 200})
            else:
                return jsonify({"data": None, "message": "重置密码失败", "code": 500}), 500

        @self.app.route("/admin/users/<int:user_id>/details", methods=["GET"])
        def admin_get_user_details(user_id):
            """获取用户详细信息（管理员）"""
            if not self.is_admin():
                return jsonify({"success": False, "data": None, "message": "权限不足", "code": 403}), 403

            user = self.db.get_user_details(user_id)
            if user:
                return jsonify({"success": True, "data": user, "message": "获取用户详细信息成功", "code": 200})
            else:
                return jsonify({"success": False, "data": None, "message": "用户不存在", "code": 404}), 404

        # 角色管理API
        @self.app.route("/admin/roles", methods=["GET"])
        def admin_get_roles():
            """获取所有角色（管理员）"""
            if not self.is_admin():
                return jsonify({"data": None, "message": "权限不足", "code": 403}), 403

            # 获取分页参数
            page = request.args.get('page', 1, type=int)
            page_size = request.args.get('page_size', 10, type=int)
            
            # 获取搜索和筛选参数
            search = request.args.get('search', '').strip()
            status = request.args.get('status', '').strip()
            role_name = request.args.get('role_name', '').strip()
            display_name = request.args.get('display_name', '').strip()
            description = request.args.get('description', '').strip()
            
            # 限制页面大小
            if page_size > 100:
                page_size = 100
            if page_size < 1:
                page_size = 10
            if page < 1:
                page = 1

            # 获取分页数据
            result = self.db.get_roles_paginated(page, page_size, search, status, role_name, display_name, description)
            return jsonify({"data": result, "message": "获取角色列表成功", "code": 200})

        @self.app.route("/admin/roles/<role_name>", methods=["GET"])
        def admin_get_role_by_name(role_name):
            """根据角色名称获取角色详细信息（管理员）"""
            if not self.is_admin():
                return jsonify({"data": None, "message": "权限不足", "code": 403}), 403

            role = self.db.get_role_by_name(role_name)
            if role:
                return jsonify({"data": role, "message": "获取角色信息成功", "code": 200})
            else:
                return jsonify({"data": None, "message": "角色不存在", "code": 404}), 404

        @self.app.route("/admin/roles", methods=["POST"])
        def admin_create_role():
            """创建角色（超级管理员）"""
            if not self.is_super_admin():
                return jsonify({"data": None, "message": "权限不足", "code": 403}), 403

            data = request.get_json()
            name = data.get("name")
            display_name = data.get("display_name")
            description = data.get("description")
            permissions = data.get("permissions", [])

            if not all([name, display_name]):
                return jsonify({"data": None, "message": "角色名称和显示名称不能为空", "code": 400}), 400

            current_user_id = session.get('user_id')
            role_id = self.db.create_role(name, display_name, description, permissions, current_user_id)
            if role_id:
                return jsonify({"data": {"id": role_id, "name": name, "display_name": display_name}, "message": "角色创建成功", "code": 200})
            else:
                return jsonify({"data": None, "message": "创建角色失败，角色名称可能已存在", "code": 400}), 400

        @self.app.route("/admin/roles/<int:role_id>", methods=["PUT"])
        def admin_update_role(role_id):
            """更新角色（超级管理员）"""
            if not self.is_super_admin():
                return jsonify({"data": None, "message": "权限不足", "code": 403}), 403

            data = request.get_json()
            display_name = data.get("display_name")
            description = data.get("description")
            permissions = data.get("permissions", [])

            if not display_name:
                return jsonify({"data": None, "message": "显示名称不能为空", "code": 400}), 400

            current_user_id = session.get('user_id')
            if self.db.update_role(role_id, display_name, description, permissions, current_user_id):
                return jsonify({"data": {"id": role_id}, "message": "角色更新成功", "code": 200})
            else:
                return jsonify({"data": None, "message": "更新角色失败", "code": 500}), 500

        @self.app.route("/admin/roles/<int:role_id>", methods=["DELETE"])
        def admin_delete_role(role_id):
            """删除角色（超级管理员）"""
            if not self.is_super_admin():
                return jsonify({"data": None, "message": "权限不足", "code": 403}), 403

            # 检查是否有用户使用此角色
            if self.db.check_role_in_use(role_id):
                return jsonify({"data": None, "message": "无法删除正在使用的角色", "code": 400}), 400

            if self.db.delete_role(role_id):
                return jsonify({"data": {"id": role_id}, "message": "角色删除成功", "code": 200})
            else:
                return jsonify({"data": None, "message": "删除角色失败", "code": 500}), 500

        @self.app.route("/admin/users/batch", methods=["POST"])
        def admin_batch_user_operation():
            """批量用户操作（管理员）"""
            if not self.is_admin():
                return jsonify({"success": False, "data": None, "message": "权限不足", "code": 403}), 403

            data = request.get_json()
            operation = data.get("operation")
            user_ids = data.get("user_ids", [])

            if not user_ids:
                return jsonify({"success": False, "data": None, "message": "请选择要操作的用户", "code": 400}), 400

            # 检查是否包含当前用户
            current_user_id = session.get("user_id")
            if current_user_id in user_ids:
                return jsonify({"success": False, "data": None, "message": "不能对自己执行批量操作", "code": 400}), 400

            if operation == "delete":
                if not self.is_super_admin():
                    return jsonify({"success": False, "data": None, "message": "只有超级管理员可以批量删除用户", "code": 403}), 403
                deleted_count = self.db.batch_delete_users(user_ids)
                return jsonify({"success": True, "data": {"affected_count": deleted_count, "operation": "delete"}, "message": "批量删除用户成功", "code": 200})

            elif operation == "activate":
                current_user_id = session.get('user_id')
                updated_count = self.db.batch_update_user_status(user_ids, True, current_user_id)
                return jsonify({"success": True, "data": {"affected_count": updated_count, "operation": "activate"}, "message": "批量激活用户成功", "code": 200})

            elif operation == "deactivate":
                current_user_id = session.get('user_id')
                updated_count = self.db.batch_update_user_status(user_ids, False, current_user_id)
                return jsonify({"success": True, "data": {"affected_count": updated_count, "operation": "deactivate"}, "message": "批量禁用用户成功", "code": 200})

            else:
                return jsonify({"success": False, "data": None, "message": "无效的操作", "code": 400}), 400

        @self.app.route("/admin/stats", methods=["GET"])
        def admin_get_stats():
            """获取系统统计信息（管理员）"""
            if not self.is_admin():
                return jsonify({"success": False, "data": None, "message": "权限不足", "code": 403}), 403

            stats = self.db.get_system_stats()
            return jsonify({"success": True, "data": stats, "message": "获取系统统计信息成功", "code": 200})

        @self.app.route("/admin/config", methods=["GET"])
        def admin_get_configs():
            """获取所有配置文件列表（超级管理员）"""
            if not self.is_super_admin():
                return jsonify({"success": False, "data": None, "message": "权限不足", "code": 403}), 403

            try:
                import os
                config_dir = os.path.join(os.path.dirname(__file__), "config")
                files = []
                
                if os.path.exists(config_dir):
                    for filename in os.listdir(config_dir):
                        if filename.endswith(('.toml', '.json')):
                            files.append(filename)
                
                return jsonify({"success": True, "data": {"files": sorted(files)}, "message": "获取配置文件列表成功", "code": 200})
            except Exception as e:
                return jsonify({"success": False, "data": None, "message": f"获取配置文件列表失败: {str(e)}", "code": 500}), 500

        @self.app.route("/admin/config/<filename>", methods=["GET"])
        def admin_get_config(filename):
            """获取配置文件内容（超级管理员）"""
            if not self.is_super_admin():
                return jsonify({"success": False, "data": None, "message": "权限不足", "code": 403}), 403

            try:
                import os
                config_dir = os.path.join(os.path.dirname(__file__), "config")
                config_file = os.path.join(config_dir, filename)

                # 安全检查：确保文件在配置目录内
                if not os.path.abspath(config_file).startswith(
                    os.path.abspath(config_dir)
                ):
                    return jsonify({"success": False, "data": None, "message": "无效的文件路径", "code": 400}), 400

                if not os.path.exists(config_file):
                    return jsonify({"success": False, "data": None, "message": "配置文件不存在", "code": 404}), 404

                with open(config_file, "r", encoding="utf-8") as f:
                    content = f.read()

                return jsonify({"success": True, "data": {"filename": filename, "content": content}, "message": "获取配置文件内容成功", "code": 200})
            except Exception as e:
                return jsonify({"success": False, "data": None, "message": f"读取配置文件失败: {str(e)}", "code": 500}), 500

        @self.app.route("/admin/config/<filename>", methods=["PUT"])
        def admin_update_config(filename):
            """更新配置文件（超级管理员）"""
            if not self.is_super_admin():
                return jsonify({"success": False, "data": None, "message": "权限不足", "code": 403}), 403

            try:
                import os
                config_dir = os.path.join(os.path.dirname(__file__), "config")
                config_file = os.path.join(config_dir, filename)

                # 安全检查：确保文件在配置目录内
                if not os.path.abspath(config_file).startswith(
                    os.path.abspath(config_dir)
                ):
                    return jsonify({"success": False, "data": None, "message": "无效的文件路径", "code": 400}), 400

                data = request.get_json()

                if filename.endswith(".toml"):
                    # 对于TOML文件，直接保存文本内容
                    content = data.get("content", "")
                    with open(config_file, "w", encoding="utf-8") as f:
                        f.write(content)
                elif filename.endswith(".json"):
                    # 对于JSON文件，保存JSON格式
                    content = data.get("content", {})
                    with open(config_file, "w", encoding="utf-8") as f:
                        json.dump(content, f, indent=2, ensure_ascii=False)
                else:
                    return jsonify({"success": False, "data": None, "message": "不支持的文件格式", "code": 400}), 400

                return jsonify({"success": True, "data": {"filename": filename}, "message": "配置文件更新成功", "code": 200})
            except Exception as e:
                return jsonify({"success": False, "data": None, "message": f"保存配置失败: {str(e)}", "code": 500}), 500

    def is_admin(self) -> bool:
        """检查当前用户是否为管理员或超级管理员"""
        user_role = session.get("role", "user")
        return user_role in ["admin", "super_admin"]

    def is_super_admin(self) -> bool:
        """检查当前用户是否为超级管理员"""
        user_role = session.get("role", "user")
        return user_role == "super_admin"

    async def process_with_agent(
        self, message: str, conversation_id: str = None
    ) -> str:
        """Process user message with OpenManus agent."""
        try:
            # Get or create agent instance for this conversation
            session_id = session.get("user_id", "guest")
            agent_key = conversation_id if conversation_id else f"session_{session_id}"
            
            if agent_key not in self.conversation_agents:
                self.conversation_agents[agent_key] = await Manus.create()

            agent = self.conversation_agents[agent_key]
            
            # Reset agent state to IDLE before processing
            agent.state = AgentState.IDLE
            agent.current_step = 0

            # Load conversation history only if conversation_id is provided
            if conversation_id:
                messages = self.db.get_conversation_messages(conversation_id)

                # Convert to OpenManus message format
                agent.memory.clear()
                for msg in messages[
                    :-1
                ]:  # Exclude the last message (current user input)
                    agent.memory.add_message(
                        Message(
                            role=msg["role"],
                            content=msg["content"],
                            tool_calls=msg.get("tool_calls"),
                            tool_call_id=msg.get("tool_call_id"),
                        )
                    )

            # Process the message
            await agent.run(message)

            # Get the last assistant message
            if agent.memory.messages:
                last_message = agent.memory.messages[-1]
                return last_message.content or "抱歉，我无法生成回复。"
            else:
                return "抱歉，我无法生成回复。"

        except Exception as e:
            logger.error(f"Agent processing error: {e}")
            return f"处理您的请求时遇到错误：{str(e)}"

    def process_with_agent_stream(self, message: str, conversation_id: str = None, session_id: str = None):
        """Process user message with OpenManus agent and yield streaming response."""
        try:
            # Use provided session_id or default to guest
            if session_id is None:
                session_id = "guest"
            
            # Use conversation_id as the key for agent instances to ensure each conversation has its own agent
            agent_key = conversation_id if conversation_id else f"session_{session_id}"
            
            # Get or create agent instance for this conversation
            if agent_key not in self.conversation_agents:
                # Create agent synchronously for streaming
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                self.conversation_agents[agent_key] = loop.run_until_complete(Manus.create())
                loop.close()

            agent = self.conversation_agents[agent_key]
            
            # Reset agent state to IDLE before processing
            agent.state = AgentState.IDLE
            agent.current_step = 0

            # Load conversation history only if conversation_id is provided
            if conversation_id:
                messages = self.db.get_conversation_messages(conversation_id)

                # Convert to OpenManus message format
                agent.memory.clear()
                for msg in messages[
                    :-1
                ]:  # Exclude the last message (current user input)
                    agent.memory.add_message(
                        Message(
                            role=msg["role"],
                            content=msg["content"],
                            tool_calls=msg.get("tool_calls"),
                            tool_call_id=msg.get("tool_call_id"),
                        )
                    )

            # Process the message with real-time streaming
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Start the agent processing
                if agent.state != AgentState.IDLE:
                    raise RuntimeError(f"Cannot run agent from state: {agent.state}")

                agent.state = AgentState.RUNNING
                
                # Yield initial thinking message
                yield "🤔 开始思考...\n\n"
                
                # Add user message to memory
                agent.update_memory("user", message)
                
                while (agent.current_step < agent.max_steps and agent.state != AgentState.FINISHED):
                    agent.current_step += 1
                    
                    # Yield step information
                    yield f"📝 **步骤 {agent.current_step}:**\n"
                    
                    # Execute the step and capture the result
                    step_result = loop.run_until_complete(agent.step())
                    
                    # Yield the step result
                    if step_result:
                        yield f"{step_result}\n\n"
                    
                    # Check if agent finished
                    if agent.state == AgentState.FINISHED:
                        break
                        
                    # Check for stuck state
                    if agent.is_stuck():
                        agent.handle_stuck_state()
                        yield "⚠️ 检测到重复响应，正在调整策略...\n\n"
                
                # Get the final response
                if agent.memory.messages:
                    last_message = agent.memory.messages[-1]
                    if last_message.role == 'assistant' and last_message.content:
                        yield "\n✅ **最终回复:**\n"
                        # Stream the final response in chunks for better UX
                        final_response = last_message.content
                        chunk_size = 20
                        for i in range(0, len(final_response), chunk_size):
                            chunk = final_response[i:i + chunk_size]
                            yield chunk
                            import time
                            time.sleep(0.03)
                
                if agent.current_step >= agent.max_steps:
                    yield f"\n⏰ 已达到最大步数限制 ({agent.max_steps})\n"
                    
            finally:
                agent.state = AgentState.IDLE
                agent.current_step = 0
                loop.close()

        except Exception as e:
            logger.error(f"Agent streaming error: {e}")
            yield f"处理您的请求时遇到错误：{str(e)}"

    def run(self, host="127.0.0.1", port=8080, debug=True):
        """Run the Flask application."""
        logger.info(f"Starting OpenManus Web UI on {host}:{port}")
        self.app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    webui = OpenManusWebUI()
    webui.run()
