"""Content classifier for cache policy decisions."""

import re
from enum import Enum


class CachePolicy(Enum):
    """Cache policy decision."""
    CACHE = "cache"           # Can be cached
    NO_CACHE = "no_cache"     # Should not be cached


class ContentClassifier:
    """内容分类器，决定请求是否可以全局缓存。
    
    全局共享缓存原则：
    - 概念性问题答案应该被所有学生共享
    - 隐私问题通过内容过滤解决，而非隔离
    """
    
    # 代码相关模式（不缓存）
    CODE_PATTERNS = [
        r"```[\s\S]*?```",                    # 代码块
        r"`[^`]+`",                           # 行内代码
        r"def\s+\w+\s*\(",                   # 函数定义
        r"class\s+\w+",                       # 类定义
        r"import\s+\w+",                     # 导入语句
        r"from\s+\w+\s+import",               # from import
        r"for\s+\w+\s+in",                    # for 循环
        r"while\s+",                          # while 循环
        r"if\s+.*:",                          # if 语句
        r"else:",                             # else
        r"elif\s+.*:",                        # elif
        r"try:",                              # try
        r"except",                            # except
        r"return\s+",                         # return
        r"print\s*\(",                        # print
    ]
    
    # 个人信息模式（不缓存）
    PERSONAL_PATTERNS = [
        r"学号[\s:是]*\d{6,}",                   # 学号
        r"姓名[:\s]*[\u4e00-\u9fa5]{2,4}",    # 中文姓名
        r"电话[:\s]*\d{11}",                   # 手机号
        r"身份证[:\s]*\d{18}",                 # 身份证
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",  # 邮箱
    ]
    
    # 项目/作业相关（不缓存）
    PROJECT_PATTERNS = [
        r"我的项目",
        r"我的作业",
        r"我们组",
        r"报错|错误|error|exception|traceback",
        r"bug|fix|修复",
        r"debug|调试",
    ]
    
    # 概念性问题模式（可缓存，较长 TTL）
    CONCEPT_PATTERNS = [
        r"什么是|explain|what is",
        r"定义|definition",
        r"概念|concept",
        r"区别|difference|compare|vs|versus",
        r"为什么|why|reason",
        r"如何|how to|how do",
        r"优缺点|pros and cons|advantages|disadvantages",
        r"原理|principle|mechanism",
        r"介绍|introduce",
    ]
    
    @classmethod
    def classify(cls, prompt: str) -> CachePolicy:
        """判断内容是否可以全局缓存。
        
        Rules:
        1. 包含代码 → 不缓存
        2. 包含个人信息 → 不缓存
        3. 项目/作业具体问题 → 不缓存
        4. 其他 → 可以缓存
        """
        # 检查代码
        for pattern in cls.CODE_PATTERNS:
            if re.search(pattern, prompt, re.IGNORECASE):
                return CachePolicy.NO_CACHE
        
        # 检查个人信息
        for pattern in cls.PERSONAL_PATTERNS:
            if re.search(pattern, prompt):
                return CachePolicy.NO_CACHE
        
        # 检查项目/作业相关内容
        for pattern in cls.PROJECT_PATTERNS:
            if re.search(pattern, prompt, re.IGNORECASE):
                return CachePolicy.NO_CACHE
        
        return CachePolicy.CACHE
    
    @classmethod
    def is_concept_question(cls, prompt: str) -> bool:
        """判断是否是概念性问题（可缓存更久）"""
        for pattern in cls.CONCEPT_PATTERNS:
            if re.search(pattern, prompt, re.IGNORECASE):
                return True
        return False
