"""
模型选择器
根据任务复杂度选择合适的LLM模型
"""
from enum import Enum
from typing import Optional, Dict, List

from core.config import settings


class ModelTier(str, Enum):
    """模型层级"""
    FAST = "fast"           # 快速响应，成本低
    BALANCED = "balanced"   # 平衡性能和成本
    POWERFUL = "powerful"   # 最强能力，成本高


class TaskComplexity(str, Enum):
    """任务复杂度"""
    SIMPLE = "simple"           # 简单任务
    NORMAL = "normal"           # 普通任务
    COMPLEX = "complex"         # 复杂任务
    DEEP_REASONING = "deep_reasoning"  # 深度推理


class ModelResolver:
    """
    模型选择器
    
    根据任务复杂度选择合适的模型:
    - FAST: 简单问答、格式化
    - BALANCED: 普通对话、分析
    - POWERFUL: 复杂推理、代码生成
    """
    
    # 模型配置
    MODELS: Dict[ModelTier, List[str]] = {
        ModelTier.FAST: [
            "gpt-4o-mini",
            "claude-3-haiku",
            "deepseek-chat",
        ],
        ModelTier.BALANCED: [
            "gpt-4o",
            "claude-3-sonnet",
            "deepseek-reasoner",
        ],
        ModelTier.POWERFUL: [
            "gpt-4-turbo",
            "claude-3-opus",
            "deepseek-r1",
        ]
    }
    
    # 复杂度到层级的映射
    COMPLEXITY_TIER_MAP = {
        TaskComplexity.SIMPLE: ModelTier.FAST,
        TaskComplexity.NORMAL: ModelTier.BALANCED,
        TaskComplexity.COMPLEX: ModelTier.POWERFUL,
        TaskComplexity.DEEP_REASONING: ModelTier.POWERFUL,
    }
    
    def __init__(self, default_tier: ModelTier = ModelTier.BALANCED):
        self.default_tier = default_tier
        self.user_preferences: Dict[str, str] = {}
    
    def resolve(
        self,
        task_complexity: TaskComplexity = TaskComplexity.NORMAL,
        user_preference: Optional[str] = None,
        tenant_config: Optional[Dict] = None
    ) -> str:
        """
        根据任务复杂度选择模型
        
        Args:
            task_complexity: 任务复杂度
            user_preference: 用户指定的模型
            tenant_config: 租户配置
            
        Returns:
            模型名称
        """
        # 1. 用户偏好优先
        if user_preference:
            return user_preference
        
        # 2. 租户配置
        if tenant_config and tenant_config.get("default_model"):
            return tenant_config["default_model"]
        
        # 3. 根据复杂度选择层级
        tier = self.COMPLEXITY_TIER_MAP.get(task_complexity, self.default_tier)
        
        # 4. 返回该层级的第一个可用模型
        models = self.MODELS.get(tier, [])
        
        if models:
            return models[0]
        
        # 5. 使用默认配置
        return settings.DEFAULT_LLM_MODEL
    
    def get_fallback_model(self, failed_model: str) -> Optional[str]:
        """
        获取备用模型
        
        Args:
            failed_model: 失败的模型
            
        Returns:
            备用模型名称
        """
        # 找到失败模型所在的层级
        for tier, models in self.MODELS.items():
            if failed_model in models:
                # 尝试同层级其他模型
                for model in models:
                    if model != failed_model:
                        return model
        
        # 尝试更低层级
        fallback_order = [ModelTier.BALANCED, ModelTier.FAST]
        for tier in fallback_order:
            models = self.MODELS.get(tier, [])
            if models:
                return models[0]
        
        return None
    
    def estimate_task_complexity(self, message: str) -> TaskComplexity:
        """
        估算任务复杂度
        
        Args:
            message: 用户消息
            
        Returns:
            任务复杂度
        """
        message_lower = message.lower()
        
        # 深度推理关键词
        deep_keywords = [
            "analyze", "explain why", "reasoning", "prove",
            "深度分析", "原因", "论证", "推导"
        ]
        if any(kw in message_lower for kw in deep_keywords):
            return TaskComplexity.DEEP_REASONING
        
        # 复杂任务关键词
        complex_keywords = [
            "code", "implement", "design", "architect",
            "代码", "实现", "设计", "架构"
        ]
        if any(kw in message_lower for kw in complex_keywords):
            return TaskComplexity.COMPLEX
        
        # 简单任务关键词
        simple_keywords = [
            "what is", "define", "translate", "format",
            "是什么", "定义", "翻译", "格式"
        ]
        if any(kw in message_lower for kw in simple_keywords):
            return TaskComplexity.SIMPLE
        
        return TaskComplexity.NORMAL
    
    def get_model_tier(self, model: str) -> Optional[ModelTier]:
        """获取模型所属层级"""
        for tier, models in self.MODELS.items():
            if model in models:
                return tier
        return None
    
    def list_available_models(self) -> Dict[str, List[str]]:
        """列出所有可用模型"""
        return {
            tier.value: models
            for tier, models in self.MODELS.items()
        }


# 全局模型选择器
model_resolver: Optional[ModelResolver] = None


def init_model_resolver(default_tier: ModelTier = ModelTier.BALANCED):
    """初始化模型选择器"""
    global model_resolver
    model_resolver = ModelResolver(default_tier)


def get_model_resolver() -> Optional[ModelResolver]:
    return model_resolver