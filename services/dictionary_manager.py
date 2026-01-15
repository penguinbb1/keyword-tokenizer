"""
词典管理器
负责加载、查询、更新各类词典
"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Set
from collections import defaultdict
import threading


class DictionaryManager:
    """词典管理器"""
    
    def __init__(self, dictionary_path: Path):
        self.dictionary_path = Path(dictionary_path)
        self._dictionaries: Dict[str, Dict] = {}
        self._word_index: Dict[str, Set[str]] = defaultdict(set)  # word -> dict_names
        self._loaded = False
        self._lock = threading.Lock()
    
    def load_all(self):
        """加载所有词典"""
        with self._lock:
            self._dictionaries = {}
            self._word_index = defaultdict(set)
            
            # 加载各类词典
            dict_files = {
                "brands": "brands/global.json",
                "brands_zh": "brands/zh.json",
                "brands_ja": "brands/ja.json",
                "products": "products.json",
                "audiences": "audiences.json",
                "scenarios": "scenarios.json",
                "colors": "colors.json",
                "features": "features.json",
                "attributes": "attributes.json",
            }
            
            for dict_name, file_path in dict_files.items():
                full_path = self.dictionary_path / file_path
                if full_path.exists():
                    self._load_dictionary(dict_name, full_path)
                else:
                    # 创建空词典
                    self._dictionaries[dict_name] = {"entries": []}
            
            self._loaded = True
    
    def _load_dictionary(self, dict_name: str, file_path: Path):
        """加载单个词典文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self._dictionaries[dict_name] = data
            
            # 建立索引
            for entry in data.get("entries", []):
                word = entry.get("word", "").lower()
                if word:
                    self._word_index[word].add(dict_name)
            
            print(f"  ✓ 加载词典 {dict_name}: {len(data.get('entries', []))} 条")
        except Exception as e:
            print(f"  ✗ 加载词典 {dict_name} 失败: {e}")
            self._dictionaries[dict_name] = {"entries": []}
    
    def reload_all(self):
        """重新加载所有词典"""
        self.load_all()
    
    def is_loaded(self) -> bool:
        """检查词典是否已加载"""
        return self._loaded
    
    def get_stats(self) -> Dict:
        """获取词典统计信息"""
        stats = {}
        for dict_name, data in self._dictionaries.items():
            stats[dict_name] = len(data.get("entries", []))
        return stats
    
    def get_entries(self, dict_name: str) -> List[Dict]:
        """获取词典的所有条目"""
        if dict_name in self._dictionaries:
            return self._dictionaries[dict_name].get("entries", [])
        
        # 支持获取合并的品牌词典
        if dict_name == "brands":
            entries = []
            for name in ["brands", "brands_zh", "brands_ja"]:
                if name in self._dictionaries:
                    entries.extend(self._dictionaries[name].get("entries", []))
            return entries
        
        return []
    
    def get_all_words(self, dict_name: str) -> List[str]:
        """获取词典中的所有词（仅词，不含其他信息）"""
        entries = self.get_entries(dict_name)
        return [entry.get("word", "") for entry in entries if entry.get("word")]
    
    def get_entry(self, dict_name: str, word: str) -> Optional[Dict]:
        """获取单个词条"""
        word_lower = word.lower()
        entries = self.get_entries(dict_name)
        
        for entry in entries:
            if entry.get("word", "").lower() == word_lower:
                return entry
        
        return None
    
    def contains(self, dict_name: str, word: str) -> bool:
        """检查词典是否包含某个词"""
        word_lower = word.lower()
        
        # 先查索引
        if word_lower in self._word_index:
            if dict_name in self._word_index[word_lower]:
                return True
            # 对于 brands，检查所有品牌词典
            if dict_name == "brands":
                return any(
                    d in self._word_index[word_lower] 
                    for d in ["brands", "brands_zh", "brands_ja"]
                )
        
        return False
    
    def search(
        self, 
        word: str, 
        tag: Optional[str] = None,
        language: Optional[str] = None
    ) -> Dict:
        """搜索词典"""
        results = []
        word_lower = word.lower()
        
        for dict_name, data in self._dictionaries.items():
            # 语言过滤
            if language:
                if language == "zh" and not dict_name.endswith("_zh"):
                    continue
                if language == "ja" and not dict_name.endswith("_ja"):
                    continue
            
            for entry in data.get("entries", []):
                entry_word = entry.get("word", "").lower()
                if word_lower in entry_word or entry_word in word_lower:
                    results.append({
                        "word": entry.get("word"),
                        "dictionary": dict_name,
                        "confidence": entry.get("confidence", 1.0)
                    })
        
        return {"results": results, "count": len(results)}
    
    def add_entry(
        self, 
        word: str, 
        tag: str, 
        language: str = "global",
        confidence: float = 1.0,
        source: str = "manual"
    ):
        """添加词典条目"""
        # 确定目标词典
        dict_name = self._get_dict_name_for_tag(tag, language)
        
        if dict_name not in self._dictionaries:
            self._dictionaries[dict_name] = {"entries": []}
        
        # 检查是否已存在
        word_lower = word.lower()
        for entry in self._dictionaries[dict_name].get("entries", []):
            if entry.get("word", "").lower() == word_lower:
                # 更新现有条目
                entry["confidence"] = confidence
                entry["source"] = source
                return
        
        # 添加新条目
        new_entry = {
            "word": word,
            "confidence": confidence,
            "source": source
        }
        self._dictionaries[dict_name]["entries"].append(new_entry)
        
        # 更新索引
        self._word_index[word_lower].add(dict_name)
        
        # 保存到文件
        self._save_dictionary(dict_name)
    
    def remove_entry(self, word: str, tag: str):
        """删除词典条目"""
        dict_name = self._get_dict_name_for_tag(tag, "global")
        
        if dict_name not in self._dictionaries:
            return
        
        word_lower = word.lower()
        entries = self._dictionaries[dict_name].get("entries", [])
        self._dictionaries[dict_name]["entries"] = [
            e for e in entries if e.get("word", "").lower() != word_lower
        ]
        
        # 更新索引
        if word_lower in self._word_index:
            self._word_index[word_lower].discard(dict_name)
        
        # 保存到文件
        self._save_dictionary(dict_name)
    
    def _get_dict_name_for_tag(self, tag: str, language: str) -> str:
        """根据标签类型获取词典名"""
        tag_dict_mapping = {
            "品牌词": "brands",
            "商品词": "products",
            "人群词": "audiences",
            "场景词": "scenarios",
            "颜色词": "colors",
            "卖点词": "features",
            "属性词": "attributes",
            "尺寸词": "attributes",  # 尺寸词用正则，但也可以存词典
        }
        
        base_name = tag_dict_mapping.get(tag, "attributes")
        
        # 品牌词按语言区分
        if base_name == "brands" and language != "global":
            return f"brands_{language}"
        
        return base_name
    
    def _save_dictionary(self, dict_name: str):
        """保存词典到文件"""
        # 确定文件路径
        file_mapping = {
            "brands": "brands/global.json",
            "brands_zh": "brands/zh.json",
            "brands_ja": "brands/ja.json",
            "products": "products.json",
            "audiences": "audiences.json",
            "scenarios": "scenarios.json",
            "colors": "colors.json",
            "features": "features.json",
            "attributes": "attributes.json",
        }
        
        if dict_name not in file_mapping:
            return
        
        file_path = self.dictionary_path / file_mapping[dict_name]
        
        # 确保目录存在
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(
                    self._dictionaries[dict_name], 
                    f, 
                    ensure_ascii=False, 
                    indent=2
                )
        except Exception as e:
            print(f"保存词典 {dict_name} 失败: {e}")
    
    def get_all_words_for_tokenizer(self, language: str = "zh") -> List[str]:
        """获取所有词（用于添加到分词器自定义词典）"""
        words = []
        
        for dict_name, data in self._dictionaries.items():
            # 根据语言过滤
            if language == "zh" and dict_name.endswith("_ja"):
                continue
            if language == "ja" and dict_name.endswith("_zh"):
                continue
            
            for entry in data.get("entries", []):
                word = entry.get("word", "")
                if word:
                    words.append(word)
        
        return words
