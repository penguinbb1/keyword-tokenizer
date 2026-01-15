#!/usr/bin/env python
"""
测试哪个模型名称可用
"""
import httpx
import os
import sys
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv()

api_key = os.environ.get('ANTHROPIC_API_KEY', '')
if not api_key:
    print("❌ 未找到 ANTHROPIC_API_KEY")
    exit(1)

print(f"API Key: {api_key[:20]}...")

# 尝试多个模型名称
models = [
    "claude-3-5-sonnet-latest",
    "claude-3-5-sonnet-20241022",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
    "claude-3-5-haiku-latest",
    "claude-3-5-haiku-20241022",
    "claude-3-opus-20240229",
]

print("\n测试可用模型...")
working_model = None

for model in models:
    try:
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": model,
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "Hi"}]
            },
            timeout=30
        )
        
        if response.status_code == 200:
            print(f"  ✅ {model} - 可用!")
            working_model = model
            break
        else:
            error = response.json().get('error', {}).get('message', response.text[:100])
            print(f"  ❌ {model} - {response.status_code}: {error[:50]}")
    except Exception as e:
        print(f"  ❌ {model} - 异常: {e}")

if working_model:
    print(f"\n🎉 找到可用模型: {working_model}")
    print(f"\n请将此模型名更新到 services/ai_enhancer_v2.py 中")
else:
    print("\n⚠️ 没有找到可用模型，请检查 API Key 权限")
