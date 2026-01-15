"""
AI增强服务
使用Claude API处理未知词，并将结果写入词典
"""
import json
from typing import List, Dict, Optional
import httpx
from config import settings
from services.dictionary_manager import DictionaryManager


class AIEnhancer:
    """AI增强服务"""
    
    def __init__(self):
        self.api_key = settings.anthropic_api_key
        self.timeout = settings.ai_timeout_seconds
        self.dict_manager = DictionaryManager()
        
        # 标签类型说明（用于prompt）
        self.tag_descriptions = {
            "品牌词": "商品品牌名称，如 Apple, Nike, 华为",
            "商品词": "商品品类名称，如 跑步鞋, 手机, 笔记本电脑",
            "人群词": "目标用户群体，如 男士, 女士, 儿童, 学生",
            "场景词": "使用场景，如 办公, 运动, 户外, 旅行",
            "颜色词": "颜色描述，如 黑色, 红色, 星空灰",
            "尺寸词": "尺寸规格，如 10.5码, 14寸, 256GB",
            "卖点词": "产品卖点特性，如 防水, 耐磨, 高速",
            "属性词": "产品属性特征，如 内存, 屏幕, 电池, 材质",
        }
    
    async def process_single(self, token: str, context: str = "") -> Optional[Dict]:
        """
        处理单个未知词
        
        Args:
            token: 未知词
            context: 上下文（原始关键词）
            
        Returns:
            标签结果
        """
        if not self.api_key:
            return None
        
        prompt = self._build_prompt([token], context)
        
        try:
            result = await self._call_api(prompt)
            if result and token in result:
                # 写入词典
                self._save_to_dict(token, result[token])
                return result[token]
        except Exception as e:
            print(f"AI处理失败: {e}")
        
        return None
    
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
            {token: {tag, confidence}}
        """
        if not self.api_key or not tokens:
            return {}
        
        prompt = self._build_prompt(tokens, context)
        
        try:
            result = await self._call_api(prompt)
            if result:
                # 批量写入词典
                for token, tag_info in result.items():
                    self._save_to_dict(token, tag_info)
                return result
        except Exception as e:
            print(f"AI批量处理失败: {e}")
        
        return {}
    
    def _build_prompt(self, tokens: List[str], context: str = "") -> str:
        """构建prompt"""
        tag_desc = "\n".join([f"- {k}: {v}" for k, v in self.tag_descriptions.items()])
        
        prompt = f"""你是一个电商关键词分析专家。请分析以下词语，判断每个词属于哪种标签类型。

标签类型说明：
{tag_desc}

待分析的词语：
{json.dumps(tokens, ensure_ascii=False)}

{f'上下文（原始关键词）: {context}' if context else ''}

请返回JSON格式，示例：
{{
  "词语1": {{"tag": "品牌词", "confidence": 0.9}},
  "词语2": {{"tag": "商品词", "confidence": 0.85}}
}}

注意：
1. 每个词只返回最可能的一个标签
2. confidence 表示置信度，范围 0-1
3. 如果无法判断，confidence 设为 0.5 以下
4. 只返回JSON，不要其他说明
"""
        return prompt
    
    async def _call_api(self, prompt: str) -> Optional[Dict]:
        """调用Claude API"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 1024,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ]
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data["content"][0]["text"]
                
                # 解析JSON
                # 处理可能的markdown代码块
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                
                return json.loads(content.strip())
            else:
                print(f"API调用失败: {response.status_code} - {response.text}")
                return None
    
    def _save_to_dict(self, token: str, tag_info: Dict):
        """保存结果到词典"""
        self.dict_manager.add_entry(
            word=token,
            tag=tag_info.get("tag", "未知"),
            confidence=tag_info.get("confidence", 0.7),
            source="ai_generated"
        )
