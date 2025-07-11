# task_manager.py — AI 리서치 에이전트 작업 관리자 (개선 버전)

import asyncio
import uuid
import json
import traceback
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
from pathlib import Path

# ─────────────────────────────────────────────
# 1) 작업 상태 및 데이터 클래스
# ─────────────────────────────────────────────

class TaskStatus(Enum):
    """작업 상태 정의"""
    PENDING = "pending"         # 대기 중
    RUNNING = "running"         # 실행 중
    COMPLETED = "completed"     # 완료
    FAILED = "failed"          # 실패
    CANCELLED = "cancelled"     # 취소됨

@dataclass
class TaskInfo:
    """작업 정보를 저장하는 데이터 클래스"""
    task_id: str
    topic: str
    domain: str
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: int = 0
    current_step: str = ""
    result: Optional[str] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (JSON 직렬화용)"""
        return {
            **asdict(self),
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }

# ─────────────────────────────────────────────
# 2) 작업 관리자 클래스
# ─────────────────────────────────────────────

class TaskManager:
    """AI 리서치 에이전트를 위한 작업 관리자"""
    
    def __init__(self, max_concurrent_tasks: int = 5):
        """
        작업 관리자 초기화
        
        Args:
            max_concurrent_tasks: 최대 동시 실행 작업 수
        """
        self.tasks: Dict[str, TaskInfo] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.max_concurrent_tasks = max_concurrent_tasks
        
        # 작업 저장 디렉토리 생성
        self.storage_dir = Path("task_storage")
        self.storage_dir.mkdir(exist_ok=True)
        
        print(f"📋 작업 관리자 초기화 완료 - 최대 동시 작업: {max_concurrent_tasks}개")
    
    def create_task(self, topic: str, domain: str) -> str:
        """
        새로운 작업 생성
        
        Args:
            topic: 리서치 주제
            domain: 리서치 도메인
            
        Returns:
            생성된 작업 ID
        """
        task_id = str(uuid.uuid4())
        task_info = TaskInfo(
            task_id=task_id,
            topic=topic,
            domain=domain,
            status=TaskStatus.PENDING,
            created_at=datetime.now()
        )
        
        self.tasks[task_id] = task_info
        self._save_task(task_info)
        
        print(f"📝 새 작업 생성: {task_id[:8]}... (주제: {topic})")
        return task_id
    
    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        """
        작업 정보 조회
        
        Args:
            task_id: 작업 ID
            
        Returns:
            작업 정보 또는 None
        """
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> Dict[str, TaskInfo]:
        """모든 작업 조회"""
        return self.tasks.copy()
    
    def get_running_tasks(self) -> Dict[str, TaskInfo]:
        """실행 중인 작업 조회"""
        return {
            task_id: task_info 
            for task_id, task_info in self.tasks.items() 
            if task_info.status == TaskStatus.RUNNING
        }
    
    def update_task_progress(self, task_id: str, progress: int, current_step: str):
        """
        작업 진행 상황 업데이트
        
        Args:
            task_id: 작업 ID
            progress: 진행률 (0-100)
            current_step: 현재 단계 설명
        """
        if task_id in self.tasks:
            self.tasks[task_id].progress = min(100, max(0, progress))
            self.tasks[task_id].current_step = current_step
            self._save_task(self.tasks[task_id])
            print(f"📊 작업 진행: {task_id[:8]}... {progress}% - {current_step}")
    
    async def start_task(self, task_id: str, agent_executor) -> asyncio.Task:
        """
        작업 시작
        
        Args:
            task_id: 작업 ID
            agent_executor: 에이전트 실행기
            
        Returns:
            비동기 작업 객체
            
        Raises:
            ValueError: 작업이 존재하지 않거나 실행할 수 없는 상태
        """
        if task_id not in self.tasks:
            raise ValueError(f"작업 {task_id}을(를) 찾을 수 없습니다.")
        
        if len(self.running_tasks) >= self.max_concurrent_tasks:
            raise ValueError(f"최대 동시 실행 작업 수({self.max_concurrent_tasks})에 도달했습니다.")
        
        task_info = self.tasks[task_id]
        if task_info.status != TaskStatus.PENDING:
            raise ValueError(f"작업 {task_id}은(는) 대기 상태가 아닙니다. 현재 상태: {task_info.status.value}")
        
        # 작업 시작
        task_info.status = TaskStatus.RUNNING
        task_info.started_at = datetime.now()
        self._save_task(task_info)
        
        # 비동기 작업 실행
        async_task = asyncio.create_task(
            self._run_research_task(task_id, agent_executor)
        )
        self.running_tasks[task_id] = async_task
        
        print(f"🚀 작업 시작: {task_id[:8]}... (주제: {task_info.topic})")
        return async_task
    
    async def _run_research_task(self, task_id: str, agent_executor):
        """
        실제 연구 작업 실행
        
        Args:
            task_id: 작업 ID
            agent_executor: 에이전트 실행기
        """
        task_info = self.tasks[task_id]
        start_time = datetime.now()
        
        try:
            # 단계별 진행 상황 업데이트
            self.update_task_progress(task_id, 10, "검색 쿼리 생성 중...")
            await asyncio.sleep(0.1)  # 상태 업데이트 시간
            
            self.update_task_progress(task_id, 20, "웹 검색 수행 중...")
            await asyncio.sleep(0.1)
            
            self.update_task_progress(task_id, 40, "정보 수집 및 분석 중...")
            
            # 에이전트 실행
            result = await agent_executor.ainvoke({
                "topic": task_info.topic,
                "domain": task_info.domain
            })
            
            self.update_task_progress(task_id, 80, "보고서 작성 중...")
            await asyncio.sleep(0.1)
            
            self.update_task_progress(task_id, 90, "최종 검토 중...")
            await asyncio.sleep(0.1)
            
            # 작업 완료
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            task_info.status = TaskStatus.COMPLETED
            task_info.completed_at = end_time
            task_info.progress = 100
            task_info.current_step = "완료"
            task_info.result = result.get("output", "결과를 찾을 수 없습니다.")
            task_info.execution_time = execution_time
            
            self._save_task(task_info)
            
            print(f"✅ 작업 완료: {task_id[:8]}... (실행 시간: {execution_time:.2f}초)")
            
        except asyncio.CancelledError:
            # 작업 취소됨
            task_info.status = TaskStatus.CANCELLED
            task_info.completed_at = datetime.now()
            task_info.current_step = "취소됨"
            task_info.execution_time = (datetime.now() - start_time).total_seconds()
            
            self._save_task(task_info)
            print(f"🚫 작업 취소: {task_id[:8]}...")
            
        except Exception as e:
            # 작업 실패
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            task_info.status = TaskStatus.FAILED
            task_info.completed_at = end_time
            task_info.error = str(e)
            task_info.current_step = "실패"
            task_info.execution_time = execution_time
            
            self._save_task(task_info)
            
            # 상세한 오류 로그
            error_trace = traceback.format_exc()
            print(f"❌ 작업 실패: {task_id[:8]}... - {str(e)}")
            print(f"📋 오류 상세:\n{error_trace}")
            
        finally:
            # 실행 중인 작업 목록에서 제거
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
    
    def cancel_task(self, task_id: str) -> bool:
        """
        작업 취소
        
        Args:
            task_id: 작업 ID
            
        Returns:
            취소 성공 여부
        """
        if task_id in self.running_tasks:
            self.running_tasks[task_id].cancel()
            print(f"🚫 작업 취소 요청: {task_id[:8]}...")
            return True
        
        if task_id in self.tasks and self.tasks[task_id].status == TaskStatus.PENDING:
            self.tasks[task_id].status = TaskStatus.CANCELLED
            self.tasks[task_id].completed_at = datetime.now()
            self._save_task(self.tasks[task_id])
            print(f"🚫 대기 중인 작업 취소: {task_id[:8]}...")
            return True
        
        return False
    
    def _save_task(self, task_info: TaskInfo):
        """작업 정보를 파일에 저장"""
        try:
            file_path = self.storage_dir / f"{task_info.task_id}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(task_info.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ 작업 저장 오류: {e}")
    
    def _load_task(self, task_id: str) -> Optional[TaskInfo]:
        """파일에서 작업 정보 로드"""
        try:
            file_path = self.storage_dir / f"{task_id}.json"
            if not file_path.exists():
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 날짜 문자열을 datetime으로 변환
            data['created_at'] = datetime.fromisoformat(data['created_at'])
            if data['started_at']:
                data['started_at'] = datetime.fromisoformat(data['started_at'])
            if data['completed_at']:
                data['completed_at'] = datetime.fromisoformat(data['completed_at'])
            data['status'] = TaskStatus(data['status'])
            
            return TaskInfo(**data)
            
        except Exception as e:
            print(f"❌ 작업 로드 오류 ({task_id}): {e}")
            return None
    
    def load_all_tasks(self):
        """모든 저장된 작업 로드"""
        loaded_count = 0
        for json_file in self.storage_dir.glob("*.json"):
            task_id = json_file.stem
            task_info = self._load_task(task_id)
            if task_info:
                self.tasks[task_id] = task_info
                loaded_count += 1
        
        print(f"📂 저장된 작업 {loaded_count}개 로드 완료")
    
    def cleanup_old_tasks(self, days: int = 7):
        """
        오래된 작업 정리
        
        Args:
            days: 보관 기간 (일)
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        tasks_to_remove = []
        
        for task_id, task_info in self.tasks.items():
            if task_info.created_at < cutoff_date:
                tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            # 파일 삭제
            file_path = self.storage_dir / f"{task_id}.json"
            if file_path.exists():
                file_path.unlink()
            
            # 메모리에서 제거
            del self.tasks[task_id]
        
        print(f"🗑️ 오래된 작업 {len(tasks_to_remove)}개 정리 완료")
    
    def get_task_statistics(self) -> Dict[str, Any]:
        """작업 통계 조회"""
        total_tasks = len(self.tasks)
        status_counts = {}
        
        for status in TaskStatus:
            status_counts[status.value] = sum(
                1 for task in self.tasks.values() 
                if task.status == status
            )
        
        running_tasks = len(self.running_tasks)
        
        # 평균 실행 시간 계산
        completed_tasks = [
            task for task in self.tasks.values() 
            if task.status == TaskStatus.COMPLETED and task.execution_time
        ]
        avg_execution_time = (
            sum(task.execution_time for task in completed_tasks) / len(completed_tasks)
            if completed_tasks else 0
        )
        
        return {
            "total_tasks": total_tasks,
            "running_tasks": running_tasks,
            "status_counts": status_counts,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "avg_execution_time": avg_execution_time,
            "completed_tasks": len(completed_tasks)
        }
    
    def get_recent_tasks(self, limit: int = 10) -> List[TaskInfo]:
        """최근 작업 조회"""
        sorted_tasks = sorted(
            self.tasks.values(),
            key=lambda x: x.created_at,
            reverse=True
        )
        return sorted_tasks[:limit]

# ─────────────────────────────────────────────
# 3) 전역 작업 관리자 인스턴스
# ─────────────────────────────────────────────

# 전역 작업 관리자 인스턴스 생성
task_manager = TaskManager()

# 시스템 시작 시 기존 작업 로드
task_manager.load_all_tasks()

# 모듈 임포트 시 정보 출력
if __name__ == "__main__":
    print("📋 task_manager.py 실행됨")
    print("📊 작업 관리자 준비 완료")
    
    # 통계 출력
    stats = task_manager.get_task_statistics()
    print(f"📊 작업 통계: {stats}")
    
    # 오래된 작업 정리
    task_manager.cleanup_old_tasks()