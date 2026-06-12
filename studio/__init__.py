# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""design-studio 内核: 设计卡片精修 agent.

子包地图:
- core:    配置 / 卡片协议 / 机器门禁 / 抽象接口
- llm:     OpenAI 兼容客户端 + 缓存 + 预算
- roles:   产出 schema + 角色运行时 + 工厂
- skills:  技能模型 / 注册表 / 装载裁决
- context: 上下文组装(角色隔离视图) / 压缩 / 裁剪
- memory:  工作区 + topic 级记忆 + agent 级记忆
- loop:    轮次循环编排
"""

__version__ = "0.2.0"
