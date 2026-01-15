"""
AI 候选池机制

解决问题：AI 标注结果直接写入词典会导致"错误自我强化"

实现：
1. AI 标注结果先进入"候选池"
2. 候选池中的词条需要满足晋升条件才能进入正式词典
3. 晋升条件：
   - ai_confidence >= 阈值
   - 出现次数 >= N
   - 与现有词典无冲突

词条生命周期：
AI 标注 → 候选池 → [审核/自动晋升] → 正式词典
                  ↓
              [过期淘汰]
"""
import json
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
import threading


@dataclass
class CandidateEntry:
    """候选词条"""
    word: str
    tag: str
    confidence: float
    source: str = "ai"
    first_seen: str = ""  # ISO 格式时间戳
    last_seen: str = ""
    seen_count: int = 1
    contexts: List[str] = field(default_factory=list)  # 出现的上下文样本
    promoted: bool = False
    rejected: bool = False
    reject_reason: str = ""
    
    def __post_init__(self):
        if not self.first_seen:
            self.first_seen = datetime.now().isoformat()
        if not self.last_seen:
            self.last_seen = self.first_seen


class CandidatePool:
    """候选池管理器"""
    
    def __init__(
        self, 
        pool_path: Path,
        min_confidence: float = 0.75,
        min_seen_count: int = 5,
        max_contexts: int = 10,
        expire_days: int = 30
    ):
        """
        Args:
            pool_path: 候选池存储路径
            min_confidence: 最低置信度要求
            min_seen_count: 最少出现次数
            max_contexts: 最多保存的上下文样本数
            expire_days: 过期天数
        """
        self.pool_path = Path(pool_path)
        self.min_confidence = min_confidence
        self.min_seen_count = min_seen_count
        self.max_contexts = max_contexts
        self.expire_days = expire_days
        
        self.pool: Dict[str, CandidateEntry] = {}  # key: word_lower
        self._lock = threading.RLock()
        
        self._load()
    
    def _load(self):
        """加载候选池"""
        if self.pool_path.exists():
            try:
                with open(self.pool_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for key, entry_data in data.items():
                    self.pool[key] = CandidateEntry(**entry_data)
            except Exception as e:
                print(f"⚠️ 加载候选池失败: {e}")
    
    def _save(self):
        """保存候选池"""
        try:
            self.pool_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                key: asdict(entry) 
                for key, entry in self.pool.items()
            }
            
            with open(self.pool_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 保存候选池失败: {e}")
    
    def add(
        self, 
        word: str, 
        tag: str, 
        confidence: float, 
        context: Optional[str] = None,
        source: str = "ai"
    ) -> CandidateEntry:
        """
        添加候选词条
        
        如果词条已存在，更新出现次数和置信度
        """
        with self._lock:
            key = word.lower()
            now = datetime.now().isoformat()
            
            if key in self.pool:
                entry = self.pool[key]
                entry.seen_count += 1
                entry.last_seen = now
                
                # 更新置信度（取平均）
                entry.confidence = (entry.confidence + confidence) / 2
                
                # 添加上下文样本
                if context and context not in entry.contexts:
                    entry.contexts.append(context)
                    if len(entry.contexts) > self.max_contexts:
                        entry.contexts = entry.contexts[-self.max_contexts:]
            else:
                entry = CandidateEntry(
                    word=word,
                    tag=tag,
                    confidence=confidence,
                    source=source,
                    first_seen=now,
                    last_seen=now,
                    contexts=[context] if context else []
                )
                self.pool[key] = entry
            
            self._save()
            return entry
    
    def add_batch(
        self, 
        entries: List[Dict],
        context: Optional[str] = None
    ):
        """批量添加"""
        for entry in entries:
            self.add(
                word=entry.get("word", ""),
                tag=entry.get("tag", "属性词"),
                confidence=entry.get("confidence", 0.5),
                context=context,
                source=entry.get("source", "ai")
            )
    
    def get_promotable(self, dictionary_manager=None) -> List[CandidateEntry]:
        """
        获取可晋升的词条
        
        条件：
        1. confidence >= min_confidence
        2. seen_count >= min_seen_count
        3. 未被拒绝
        4. 与现有词典无冲突（如果提供了 dictionary_manager）
        """
        promotable = []
        
        with self._lock:
            for entry in self.pool.values():
                if entry.promoted or entry.rejected:
                    continue
                
                if entry.confidence < self.min_confidence:
                    continue
                
                if entry.seen_count < self.min_seen_count:
                    continue
                
                # 检查与现有词典的冲突
                if dictionary_manager:
                    if self._has_conflict(entry, dictionary_manager):
                        continue
                
                promotable.append(entry)
        
        return promotable
    
    def _has_conflict(self, entry: CandidateEntry, dictionary_manager) -> bool:
        """检查是否与现有词典冲突"""
        word_lower = entry.word.lower()
        
        # 获取现有标签
        existing_tags = []
        for dict_name in ["brands", "products", "audiences", "scenarios", 
                          "colors", "features", "attributes"]:
            if dictionary_manager.contains(dict_name, word_lower):
                existing_entry = dictionary_manager.get_entry(dict_name, word_lower)
                if existing_entry:
                    existing_tags.append(existing_entry.get("tag", dict_name))
        
        # 如果现有标签与候选标签不同，存在冲突
        if existing_tags and entry.tag not in existing_tags:
            return True
        
        return False
    
    def promote(self, word: str, dictionary_manager) -> bool:
        """
        将词条晋升到正式词典
        
        Returns:
            是否成功晋升
        """
        with self._lock:
            key = word.lower()
            
            if key not in self.pool:
                return False
            
            entry = self.pool[key]
            
            if entry.promoted:
                return True
            
            if entry.rejected:
                return False
            
            # 写入词典
            try:
                dictionary_manager.add_entry(
                    word=entry.word,
                    tag=entry.tag,
                    confidence=entry.confidence,
                    source=f"ai_promoted:{entry.seen_count}times"
                )
                
                entry.promoted = True
                self._save()
                return True
                
            except Exception as e:
                print(f"⚠️ 晋升失败: {e}")
                return False
    
    def reject(self, word: str, reason: str = ""):
        """拒绝词条"""
        with self._lock:
            key = word.lower()
            
            if key in self.pool:
                self.pool[key].rejected = True
                self.pool[key].reject_reason = reason
                self._save()
    
    def cleanup_expired(self):
        """清理过期词条"""
        with self._lock:
            now = datetime.now()
            expire_threshold = now - timedelta(days=self.expire_days)
            
            expired_keys = []
            
            for key, entry in self.pool.items():
                if entry.promoted or entry.rejected:
                    continue
                
                last_seen = datetime.fromisoformat(entry.last_seen)
                if last_seen < expire_threshold:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.pool[key]
            
            if expired_keys:
                self._save()
                print(f"🧹 清理了 {len(expired_keys)} 个过期候选词条")
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        total = len(self.pool)
        promoted = sum(1 for e in self.pool.values() if e.promoted)
        rejected = sum(1 for e in self.pool.values() if e.rejected)
        pending = total - promoted - rejected
        
        # 按标签统计
        tag_counts = {}
        for entry in self.pool.values():
            if not entry.promoted and not entry.rejected:
                tag_counts[entry.tag] = tag_counts.get(entry.tag, 0) + 1
        
        return {
            "total": total,
            "promoted": promoted,
            "rejected": rejected,
            "pending": pending,
            "by_tag": tag_counts
        }
    
    def get_pending_review(self, limit: int = 50) -> List[CandidateEntry]:
        """获取待审核的词条（按出现次数排序）"""
        pending = [
            entry for entry in self.pool.values()
            if not entry.promoted and not entry.rejected
        ]
        
        pending.sort(key=lambda e: e.seen_count, reverse=True)
        return pending[:limit]


# 工厂函数
def create_candidate_pool(
    pool_path: str = "data/candidate_pool.json",
    **kwargs
) -> CandidatePool:
    """创建候选池"""
    return CandidatePool(Path(pool_path), **kwargs)


# 测试代码
if __name__ == "__main__":
    pool = CandidatePool(Path("test_pool.json"))
    
    # 模拟添加
    for i in range(10):
        pool.add("testword", "商品词", 0.85, f"context_{i}")
    
    print(f"统计: {pool.get_stats()}")
    print(f"待审核: {len(pool.get_pending_review())}")
    
    # 检查可晋升
    promotable = pool.get_promotable()
    print(f"可晋升: {len(promotable)}")
    for entry in promotable:
        print(f"  - {entry.word}: {entry.tag} (conf={entry.confidence}, count={entry.seen_count})")
