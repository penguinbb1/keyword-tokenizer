#!/usr/bin/env python3
"""
GitHub 开源前安全检查脚本

检查项目中是否包含敏感信息，确保可以安全开源

使用方法:
    python scripts/security_check.py
"""
import os
import re
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

# 敏感信息模式
SENSITIVE_PATTERNS = [
    # API Keys
    (r'sk-ant-[a-zA-Z0-9-_]{20,}', 'Anthropic API Key'),
    (r'sk-[a-zA-Z0-9]{48,}', 'OpenAI API Key'),
    (r'AIza[a-zA-Z0-9_-]{35}', 'Google API Key'),
    
    # 密码/密钥
    (r'password\s*[=:]\s*["\'][^"\']{8,}["\']', '硬编码密码'),
    (r'secret\s*[=:]\s*["\'][^"\']{8,}["\']', '硬编码密钥'),
    (r'token\s*[=:]\s*["\'][^"\']{20,}["\']', '硬编码 Token'),
    
    # 私钥
    (r'-----BEGIN.*PRIVATE KEY-----', '私钥文件'),
    
    # AWS
    (r'AKIA[0-9A-Z]{16}', 'AWS Access Key'),
]

# 敏感文件
SENSITIVE_FILES = [
    '.env',
    '.env.local',
    '*.pem',
    '*.key',
    'credentials.json',
    'secrets.json',
]

# 应该检查的文件扩展名
CHECK_EXTENSIONS = {'.py', '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.md', '.txt'}

# 排除的目录
EXCLUDE_DIRS = {'venv', 'env', '.venv', '__pycache__', '.git', 'node_modules', '.idea'}


def check_file_content(filepath: Path) -> list:
    """检查文件内容是否包含敏感信息"""
    issues = []
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        for pattern, description in SENSITIVE_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                # 隐藏实际值
                masked_matches = [m[:10] + '...' if len(m) > 10 else m for m in matches]
                issues.append({
                    'file': str(filepath.relative_to(PROJECT_ROOT)),
                    'type': description,
                    'matches': masked_matches
                })
                
    except Exception as e:
        pass
    
    return issues


def check_sensitive_files() -> list:
    """检查是否存在敏感文件"""
    issues = []
    
    for pattern in SENSITIVE_FILES:
        if '*' in pattern:
            # 通配符匹配
            ext = pattern.replace('*', '')
            for filepath in PROJECT_ROOT.rglob(f'*{ext}'):
                if not any(exc in filepath.parts for exc in EXCLUDE_DIRS):
                    issues.append({
                        'file': str(filepath.relative_to(PROJECT_ROOT)),
                        'type': f'敏感文件类型: {pattern}',
                        'action': '建议添加到 .gitignore'
                    })
        else:
            filepath = PROJECT_ROOT / pattern
            if filepath.exists():
                issues.append({
                    'file': pattern,
                    'type': '敏感配置文件',
                    'action': '确保已添加到 .gitignore'
                })
    
    return issues


def check_gitignore() -> list:
    """检查 .gitignore 是否完整"""
    issues = []
    gitignore_path = PROJECT_ROOT / '.gitignore'
    
    if not gitignore_path.exists():
        issues.append({
            'file': '.gitignore',
            'type': '缺少 .gitignore 文件',
            'action': '创建 .gitignore 文件'
        })
        return issues
    
    with open(gitignore_path, 'r') as f:
        gitignore_content = f.read()
    
    required_entries = ['.env', '__pycache__', 'venv/', '*.pyc']
    
    for entry in required_entries:
        if entry not in gitignore_content:
            issues.append({
                'file': '.gitignore',
                'type': f'缺少忽略项: {entry}',
                'action': f'添加 {entry} 到 .gitignore'
            })
    
    return issues


def check_env_example() -> list:
    """检查 .env.example 是否存在"""
    issues = []
    
    env_example = PROJECT_ROOT / '.env.example'
    if not env_example.exists():
        issues.append({
            'file': '.env.example',
            'type': '缺少环境变量示例文件',
            'action': '创建 .env.example 供其他开发者参考'
        })
    
    return issues


def main():
    print("=" * 60)
    print("🔒 GitHub 开源安全检查")
    print("=" * 60)
    print()
    
    all_issues = []
    
    # 1. 检查 .gitignore
    print("📋 检查 .gitignore...")
    issues = check_gitignore()
    all_issues.extend(issues)
    if issues:
        for issue in issues:
            print(f"  ⚠️ {issue['type']}")
    else:
        print("  ✅ .gitignore 配置完整")
    print()
    
    # 2. 检查敏感文件
    print("📁 检查敏感文件...")
    issues = check_sensitive_files()
    all_issues.extend(issues)
    if issues:
        for issue in issues:
            print(f"  ⚠️ {issue['file']}: {issue['type']}")
    else:
        print("  ✅ 未发现敏感文件")
    print()
    
    # 3. 检查 .env.example
    print("📝 检查环境变量示例...")
    issues = check_env_example()
    all_issues.extend(issues)
    if issues:
        for issue in issues:
            print(f"  ⚠️ {issue['type']}")
    else:
        print("  ✅ .env.example 存在")
    print()
    
    # 4. 扫描文件内容
    print("🔍 扫描代码中的敏感信息...")
    file_count = 0
    for filepath in PROJECT_ROOT.rglob('*'):
        if filepath.is_file() and filepath.suffix in CHECK_EXTENSIONS:
            if not any(exc in filepath.parts for exc in EXCLUDE_DIRS):
                file_count += 1
                issues = check_file_content(filepath)
                all_issues.extend(issues)
                if issues:
                    for issue in issues:
                        print(f"  ⚠️ {issue['file']}: {issue['type']}")
    
    if not any(i.get('matches') for i in all_issues):
        print(f"  ✅ 已扫描 {file_count} 个文件，未发现敏感信息")
    print()
    
    # 总结
    print("=" * 60)
    if all_issues:
        print(f"⚠️ 发现 {len(all_issues)} 个潜在问题，请在开源前修复")
        print()
        print("📋 建议操作:")
        print("  1. 确保 .env 文件已添加到 .gitignore")
        print("  2. 移除代码中的硬编码密钥")
        print("  3. 使用环境变量管理敏感配置")
        print("  4. 提供 .env.example 作为配置示例")
    else:
        print("✅ 安全检查通过，可以开源！")
    print("=" * 60)
    
    return len(all_issues) == 0


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
