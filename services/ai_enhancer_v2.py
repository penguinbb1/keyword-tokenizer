"""
AI 增强服务 (V2)

功能：
1. 使用 Claude API 为未知词标注标签
2. 结果先进入候选池，不直接写入词典（防止污染）
3. 支持批量处理，减少 API 调用次数
4. 可配置触发阈值

使用方法：
1. 在 .env 文件中配置 ANTHROPIC_API_KEY
2. 在 pipeline 中启用 AI 增强
"""
import json
import asyncio
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
import httpx

from config import settings


@dataclass
class AITagResult:
    """AI 标注结果"""
    word: str
    tag: str
    confidence: float
    context: str = ""


class AIEnhancer:
    """AI 增强服务"""
    
    def __init__(self, candidate_pool=None):
        self.api_key = settings.anthropic_api_key
        self.timeout = settings.ai_timeout_seconds
        self.confidence_threshold = settings.ai_confidence_threshold
        self.candidate_pool = candidate_pool
        
        # 已处理过的词（避免重复调用 API）
        self._processed_cache: Set[str] = set()
        self._cache_max_size = 10000
        
        # 批量处理缓冲区
        self._batch_buffer: List[Dict] = []
        self._batch_size = 20  # 每批处理的词数
        
        # 标签类型说明
        self.tag_descriptions = {
            "品牌词": "商品品牌名称，如 Apple, Nike, 华为, New Balance",
            "商品词": "商品品类名称，如 跑步鞋, 手机, 笔记本电脑, leggings, casque",
            "人群词": "目标用户群体，如 男士, 女士, 儿童, damen, femme, mens",
            "场景词": "使用场景，如 办公, 运动, 户外, running, yoga, camping",
            "颜色词": "颜色描述，如 黑色, 红色, schwarz, noir, negro",
            "尺寸词": "尺寸规格，如 10.5码, 14寸, 256GB, S/M/L/XL",
            "卖点词": "产品卖点特性，如 防水, 耐磨, waterproof, breathable, wireless",
            "属性词": "产品属性特征，如 long sleeve, high waist, cotton, 棉质",
        }
    
    @property
    def is_enabled(self) -> bool:
        """检查 AI 服务是否可用"""
        return bool(self.api_key)
    
    async def enhance_tokens(
        self, 
        tokens: List[Dict],
        context: str = ""
    ) -> List[Dict]:
        """
        增强 token 标注结果
        
        对于低置信度的 token，调用 AI 进行标注
        
        Args:
            tokens: 标注结果列表 [{"token": "...", "tags": [...], "confidence": 0.5}, ...]
            context: 原始关键词（上下文）
            
        Returns:
            增强后的 token 列表
        """
        if not self.is_enabled:
            return tokens
        
        # 筛选需要 AI 处理的 token
        low_conf_tokens = []
        for t in tokens:
            word = t.get("token", "")
            conf = t.get("confidence", 0)
            
            # 跳过已处理的词
            if word.lower() in self._processed_cache:
                continue
            
            # 跳过太短的词
            if len(word) <= 1:
                continue
            
            # 低置信度的词需要 AI 处理
            if conf <= self.confidence_threshold:
                low_conf_tokens.append(word)
        
        if not low_conf_tokens:
            return tokens
        
        # 调用 AI 标注
        ai_results = await self.process_batch(low_conf_tokens, context)
        
        # 合并结果
        enhanced_tokens = []
        for t in tokens:
            word = t.get("token", "")
            if word in ai_results:
                ai_result = ai_results[word]
                enhanced_tokens.append({
                    "token": word,
                    "tags": [ai_result["tag"]],
                    "confidence": ai_result["confidence"],
                    "method": "ai"
                })
            else:
                enhanced_tokens.append(t)
        
        return enhanced_tokens
    
    async def process_batch(
        self,
        tokens: List[str],
        context: str = ""
    ) -> Dict[str, Dict]:
        """
        批量处理未知词
        
        Args:
            tokens: 未知词列表
            context: 上下文
            
        Returns:
            {token: {"tag": "...", "confidence": 0.9}}
        """
        if not self.is_enabled or not tokens:
            return {}
        
        # 去重
        unique_tokens = list(set(tokens))
        
        # 分批处理（每批最多 20 个词）
        all_results = {}
        
        for i in range(0, len(unique_tokens), self._batch_size):
            batch = unique_tokens[i:i + self._batch_size]
            
            try:
                result = await self._call_api(batch, context)
                if result:
                    all_results.update(result)
                    
                    # 添加到缓存
                    for word in result:
                        self._add_to_cache(word)
                    
                    # 添加到候选池
                    if self.candidate_pool:
                        for word, tag_info in result.items():
                            self.candidate_pool.add(
                                word=word,
                                tag=tag_info.get("tag", "属性词"),
                                confidence=tag_info.get("confidence", 0.7),
                                context=context,
                                source="ai"
                            )
            except Exception as e:
                print(f"⚠️ AI 批量处理失败: {e}")
        
        return all_results
    
    async def process_single(self, token: str, context: str = "") -> Optional[Dict]:
        """处理单个未知词"""
        results = await self.process_batch([token], context)
        return results.get(token)
    
    async def _call_api(self, tokens: List[str], context: str = "") -> Optional[Dict]:
        """调用 Claude API"""
        prompt = self._build_prompt(tokens, context)
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json={
                        # 使用稳定的模型版本
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": 2048,
                        "messages": [
                            {"role": "user", "content": prompt}
                        ]
                    },
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    content = data["content"][0]["text"]
                    return self._parse_response(content)
                else:
                    # 打印详细错误信息
                    error_detail = response.text[:300] if response.text else "无详情"
                    print(f"⚠️ API 调用失败: {response.status_code} - {error_detail}")
                    return None
                    
            except httpx.TimeoutException:
                print("⚠️ API 调用超时")
                return None
            except Exception as e:
                print(f"⚠️ API 调用异常: {e}")
                return None
    
    def _build_prompt(self, tokens: List[str], context: str = "") -> str:
        """构建 prompt"""
        tag_desc = "\n".join([f"- {k}: {v}" for k, v in self.tag_descriptions.items()])
        
        prompt = f"""你是一个电商关键词分析专家，精通中文、英语、日语、德语、法语、西班牙语。
请分析以下词语，判断每个词属于哪种标签类型。

标签类型说明：
{tag_desc}

待分析的词语：
{json.dumps(tokens, ensure_ascii=False)}

{f'上下文（原始关键词）: {context}' if context else ''}

请返回 JSON 格式，示例：
{{
  "词语1": {{"tag": "品牌词", "confidence": 0.9}},
  "词语2": {{"tag": "商品词", "confidence": 0.85}}
}}

注意：
1. 每个词只返回最可能的一个标签
2. confidence 表示置信度，范围 0.6-0.95（AI 标注通常不应超过 0.95）
3. 如果无法判断或是虚词（如 for, with, de, para），返回 {{"tag": "属性词", "confidence": 0.7}}
4. 只返回纯 JSON，不要 markdown 代码块或其他说明
5. 确保 JSON 格式正确，可以被直接解析
"""
        return prompt
    
    def _parse_response(self, content: str) -> Optional[Dict]:
        """解析 API 响应"""
        try:
            # 清理可能的 markdown 代码块
            content = content.strip()
            if content.startswith("```"):
                # 移除 ```json 或 ```
                lines = content.split("\n")
                content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            
            return json.loads(content)
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON 解析失败: {e}")
            print(f"   响应内容: {content[:200]}...")
            return None
    
    def _add_to_cache(self, word: str):
        """添加到缓存"""
        # 防止缓存过大
        if len(self._processed_cache) >= self._cache_max_size:
            # 清空一半
            items = list(self._processed_cache)
            self._processed_cache = set(items[self._cache_max_size // 2:])
        
        self._processed_cache.add(word.lower())
    
    def clear_cache(self):
        """清空缓存"""
        self._processed_cache.clear()
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "enabled": self.is_enabled,
            "cache_size": len(self._processed_cache),
            "confidence_threshold": self.confidence_threshold,
            "candidate_pool_connected": self.candidate_pool is not None
        }


# 工厂函数
def create_ai_enhancer(candidate_pool=None) -> AIEnhancer:
    """创建 AI 增强服务实例"""
    return AIEnhancer(candidate_pool)


# 测试代码
if __name__ == "__main__":
    async def test():
        enhancer = AIEnhancer()
        
        print(f"AI 服务状态: {'启用' if enhancer.is_enabled else '未启用'}")
        
        if enhancer.is_enabled:
            result = await enhancer.process_batch(
                ["thermique", "chauffante", "cycling"],
                context="法语/英语电商关键词"
            )
            print(f"标注结果: {result}")
    
    asyncio.run(test())
