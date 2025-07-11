# cache_manager.py — AI 리서치 에이전트 캐시 관리자 (개선 버전)

import hashlib
import json
import os
import sqlite3
import threading
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from contextlib import contextmanager

# ─────────────────────────────────────────────
# 1) 캐시 엔트리 데이터 클래스
# ─────────────────────────────────────────────

@dataclass
class CacheEntry:
    """캐시 항목 정보를 저장하는 데이터 클래스"""
    key: str
    value: Any
    created_at: datetime
    expires_at: Optional[datetime]
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    size_bytes: int = 0

# ─────────────────────────────────────────────
# 2) 캐시 매니저 클래스
# ─────────────────────────────────────────────

class CacheManager:
    """AI 리서치 에이전트를 위한 캐시 관리자"""
    
    def __init__(self, cache_dir: str = "cache", max_size_mb: int = 100):
        """
        캐시 매니저 초기화
        
        Args:
            cache_dir: 캐시 파일 저장 디렉토리
            max_size_mb: 최대 캐시 크기 (MB)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        self.db_path = self.cache_dir / "cache.db"
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.lock = threading.RLock()
        
        # 초기화 작업
        self._init_database()
        self._cleanup_expired()
        
        print(f"📦 캐시 매니저 초기화 완료 - 디렉토리: {self.cache_dir}, 최대 크기: {max_size_mb}MB")
    
    def _init_database(self):
        """SQLite 데이터베이스 초기화"""
        with self._get_db_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key TEXT PRIMARY KEY,
                    created_at TIMESTAMP,
                    expires_at TIMESTAMP,
                    access_count INTEGER DEFAULT 0,
                    last_accessed TIMESTAMP,
                    size_bytes INTEGER,
                    file_path TEXT
                )
            """)
            conn.commit()
    
    @contextmanager
    def _get_db_connection(self):
        """데이터베이스 연결 관리"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _generate_cache_key(self, topic: str, domain: str, query_params: Dict = None) -> str:
        """캐시 키 생성"""
        cache_data = {
            "topic": topic.lower().strip(),
            "domain": domain.lower().strip(),
            "params": query_params or {}
        }
        cache_string = json.dumps(cache_data, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(cache_string.encode('utf-8')).hexdigest()
    
    def _get_file_path(self, key: str) -> Path:
        """캐시 파일 경로 생성"""
        return self.cache_dir / f"{key}.pkl"
    
    def get(self, topic: str, domain: str, query_params: Dict = None) -> Optional[str]:
        """
        캐시에서 데이터 조회
        
        Args:
            topic: 검색 주제
            domain: 검색 도메인
            query_params: 추가 쿼리 파라미터
            
        Returns:
            캐시된 결과 또는 None
        """
        key = self._generate_cache_key(topic, domain, query_params)
        
        with self.lock:
            try:
                with self._get_db_connection() as conn:
                    row = conn.execute(
                        "SELECT * FROM cache_entries WHERE key = ?", (key,)
                    ).fetchone()
                
                if not row:
                    return None
                
                # 만료 확인
                if row['expires_at']:
                    expires_at = datetime.fromisoformat(row['expires_at'])
                    if datetime.now() > expires_at:
                        print(f"🗑️ 만료된 캐시 삭제: {key[:8]}...")
                        self._delete_entry(key)
                        return None
                
                # 파일에서 데이터 로드
                file_path = Path(row['file_path'])
                if not file_path.exists():
                    print(f"🗑️ 파일 없는 캐시 삭제: {key[:8]}...")
                    self._delete_entry(key)
                    return None
                
                with open(file_path, 'rb') as f:
                    data = pickle.load(f)
                
                # 접근 통계 업데이트
                self._update_access_stats(key)
                
                print(f"📦 캐시 히트: {key[:8]}... (주제: {topic})")
                return data
                
            except Exception as e:
                print(f"❌ 캐시 조회 오류: {e}")
                return None
    
    def set(self, topic: str, domain: str, value: str, 
            expire_hours: int = 24, query_params: Dict = None) -> bool:
        """
        캐시에 데이터 저장
        
        Args:
            topic: 검색 주제
            domain: 검색 도메인
            value: 저장할 값
            expire_hours: 만료 시간 (시간)
            query_params: 추가 쿼리 파라미터
            
        Returns:
            저장 성공 여부
        """
        key = self._generate_cache_key(topic, domain, query_params)
        
        with self.lock:
            try:
                # 파일에 데이터 저장
                file_path = self._get_file_path(key)
                with open(file_path, 'wb') as f:
                    pickle.dump(value, f)
                
                # 파일 크기 확인
                size_bytes = file_path.stat().st_size
                
                # 데이터베이스에 메타데이터 저장
                now = datetime.now()
                expires_at = now + timedelta(hours=expire_hours)
                
                with self._get_db_connection() as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO cache_entries 
                        (key, created_at, expires_at, access_count, last_accessed, size_bytes, file_path)
                        VALUES (?, ?, ?, 0, ?, ?, ?)
                    """, (key, now.isoformat(), expires_at.isoformat(), 
                          now.isoformat(), size_bytes, str(file_path)))
                    conn.commit()
                
                print(f"💾 캐시 저장: {key[:8]}... (주제: {topic}, 크기: {size_bytes} bytes)")
                
                # 캐시 크기 관리
                self._manage_cache_size()
                
                return True
                
            except Exception as e:
                print(f"❌ 캐시 저장 오류: {e}")
                return False
    
    def _update_access_stats(self, key: str):
        """접근 통계 업데이트"""
        try:
            with self._get_db_connection() as conn:
                conn.execute("""
                    UPDATE cache_entries 
                    SET access_count = access_count + 1, last_accessed = ?
                    WHERE key = ?
                """, (datetime.now().isoformat(), key))
                conn.commit()
        except Exception as e:
            print(f"❌ 접근 통계 업데이트 오류: {e}")
    
    def _delete_entry(self, key: str):
        """캐시 항목 삭제"""
        try:
            with self._get_db_connection() as conn:
                row = conn.execute(
                    "SELECT file_path FROM cache_entries WHERE key = ?", (key,)
                ).fetchone()
                
                if row:
                    file_path = Path(row['file_path'])
                    if file_path.exists():
                        file_path.unlink()
                    
                    conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                    conn.commit()
                    
        except Exception as e:
            print(f"❌ 캐시 항목 삭제 오류: {e}")
    
    def _cleanup_expired(self):
        """만료된 캐시 항목 정리"""
        try:
            now = datetime.now()
            with self._get_db_connection() as conn:
                expired_entries = conn.execute("""
                    SELECT key, file_path FROM cache_entries 
                    WHERE expires_at < ?
                """, (now.isoformat(),)).fetchall()
                
                for entry in expired_entries:
                    file_path = Path(entry['file_path'])
                    if file_path.exists():
                        file_path.unlink()
                
                # 데이터베이스에서 삭제
                deleted_count = conn.execute(
                    "DELETE FROM cache_entries WHERE expires_at < ?", 
                    (now.isoformat(),)
                ).rowcount
                conn.commit()
                
                if deleted_count > 0:
                    print(f"🗑️ 만료된 캐시 {deleted_count}개 정리 완료")
                    
        except Exception as e:
            print(f"❌ 만료된 캐시 정리 오류: {e}")
    
    def _manage_cache_size(self):
        """캐시 크기 관리 (LRU 방식)"""
        try:
            with self._get_db_connection() as conn:
                # 현재 캐시 크기 확인
                total_size = conn.execute(
                    "SELECT SUM(size_bytes) FROM cache_entries"
                ).fetchone()[0] or 0
                
                if total_size <= self.max_size_bytes:
                    return
                
                print(f"🗑️ 캐시 크기 초과 ({total_size / 1024 / 1024:.1f}MB), 정리 중...")
                
                # 가장 오래된 항목부터 삭제 (LRU)
                old_entries = conn.execute("""
                    SELECT key, file_path FROM cache_entries 
                    ORDER BY last_accessed ASC
                """).fetchall()
                
                for entry in old_entries:
                    file_path = Path(entry['file_path'])
                    if file_path.exists():
                        file_path.unlink()
                    
                    conn.execute("DELETE FROM cache_entries WHERE key = ?", (entry['key'],))
                    conn.commit()
                    
                    # 크기 재확인
                    current_size = conn.execute(
                        "SELECT SUM(size_bytes) FROM cache_entries"
                    ).fetchone()[0] or 0
                    
                    if current_size <= self.max_size_bytes * 0.8:  # 80%까지 줄이기
                        break
                
                print(f"✅ 캐시 크기 정리 완료")
                
        except Exception as e:
            print(f"❌ 캐시 크기 관리 오류: {e}")
    
    def clear_all(self):
        """모든 캐시 삭제"""
        try:
            with self.lock:
                with self._get_db_connection() as conn:
                    entries = conn.execute("SELECT file_path FROM cache_entries").fetchall()
                    
                    for entry in entries:
                        file_path = Path(entry['file_path'])
                        if file_path.exists():
                            file_path.unlink()
                    
                    conn.execute("DELETE FROM cache_entries")
                    conn.commit()
                    
                print("🗑️ 모든 캐시 삭제 완료")
                
        except Exception as e:
            print(f"❌ 캐시 전체 삭제 오류: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계 조회"""
        try:
            with self._get_db_connection() as conn:
                stats = conn.execute("""
                    SELECT 
                        COUNT(*) as total_entries,
                        SUM(size_bytes) as total_size,
                        AVG(access_count) as avg_access_count,
                        MAX(access_count) as max_access_count
                    FROM cache_entries
                """).fetchone()
                
                return {
                    "total_entries": stats['total_entries'] or 0,
                    "total_size_mb": (stats['total_size'] or 0) / 1024 / 1024,
                    "avg_access_count": stats['avg_access_count'] or 0,
                    "max_access_count": stats['max_access_count'] or 0,
                    "max_size_mb": self.max_size_bytes / 1024 / 1024
                }
                
        except Exception as e:
            print(f"❌ 캐시 통계 조회 오류: {e}")
            return {}

# ─────────────────────────────────────────────
# 3) 전역 캐시 매니저 인스턴스
# ─────────────────────────────────────────────

# 전역 캐시 매니저 인스턴스 생성
cache_manager = CacheManager()

# 모듈 임포트 시 정보 출력
if __name__ == "__main__":
    print("📋 cache_manager.py 실행됨")
    print("📦 캐시 매니저 준비 완료")
    
    # 통계 출력
    stats = cache_manager.get_stats()
    print(f"📊 캐시 통계: {stats}")
    
    # 테스트 (선택사항)
    test_key = "test_topic"
    test_domain = "test_domain"
    test_value = "테스트 캐시 데이터"
    
    # 저장 테스트
    cache_manager.set(test_key, test_domain, test_value)
    
    # 조회 테스트
    result = cache_manager.get(test_key, test_domain)
    print(f"🧪 테스트 결과: {result == test_value}")
    
    # 정리
    cache_manager.clear_all()