# main.py — AI 리서치 에이전트 FastAPI 서버 (HTML 파일 연동)

# ─────────────────────────────────────────────
# 1) 환경 변수 로드 및 초기 설정, 필수 라이브러리 임포트
# ─────────────────────────────────────────────

import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import Optional
import asyncio
import traceback
import time

# 프로젝트 내부 모듈 임포트
from agent_setup import agent_executor 

# .env 파일 로드: 환경 변수 (API 키 등) 불러옴
load_dotenv() 

# API 키 확인 함수
# ─────────────────────────────────────────────
# 2) API 키 확인 및 FastAPI 애플리케이션 초기화
# ─────────────────────────────────────────────

def check_api_key():
    """API 키 확인 함수"""
    _debug_api_key = os.getenv("OPENAI_API_KEY")
    if _debug_api_key:
        print(f"✅ OpenAI API 키 확인 완료: {_debug_api_key[:7]}...")
        return True
    else:
        print(f"❌ OpenAI API Key가 환경 변수에서 로드되지 않았습니다.")
        return False

# 시작 시 API 키 확인
check_api_key()

# ─────────────────────────────────────────────
# 3) FastAPI 애플리케이션 설정 및 CORS 미들웨어
# ─────────────────────────────────────────────

# FastAPI 애플리케이션 초기화
app = FastAPI(
    title="AI Research Agent API",
    description="전문 분야별 정보를 리서치하고 요약 보고서를 생성하는 API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 미들웨어 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# 4) HTML 파일 로드 함수
# ─────────────────────────────────────────────

# HTML 파일 읽기 함수
def load_html_file():
    """HTML 파일을 읽어서 반환"""
    try:
        # 현재 디렉토리에서 HTML 파일 찾기
        possible_files = ['main.html', 'index.html', 'ai-research-agent.html']
        
        for filename in possible_files:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as file:
                    content = file.read()
                print(f"✅ HTML 파일 로드 성공: {filename}")
                return content
        
        # HTML 파일이 없으면 기본 메시지 반환
        return """
        <html>
        <body>
            <h1>🤖 AI 리서치 에이전트</h1>
            <p>HTML 파일을 찾을 수 없습니다.</p>
            <p>main.html, index.html, 또는 ai-research-agent.html 파일을 현재 디렉토리에 추가해주세요.</p>
            <p><a href="/docs">API 문서 보기</a></p>
        </body>
        </html>
        """
    except Exception as e:
        print(f"❌ HTML 파일 읽기 실패: {e}")
        return f"<html><body><h1>오류</h1><p>HTML 파일을 읽을 수 없습니다: {e}</p></body></html>"

# ─────────────────────────────────────────────
# 5) Pydantic 모델 정의 (API 요청 및 응답 데이터 구조)
# ─────────────────────────────────────────────

# Pydantic 모델 정의
class ResearchRequest(BaseModel):
    """리서치 요청 모델"""
    topic: str = Field(..., description="리서치할 주제", example="최근 AI 기술 동향")
    domain: str = Field(..., description="리서치할 전문 도메인", example="기술")

class ResearchResponse(BaseModel):
    """리서치 응답 모델"""
    status: str = Field(..., example="success", description="API 호출 결과 상태")
    report: str = Field(..., description="AI 에이전트가 생성한 리서치 보고서 내용")
    execution_time: Optional[float] = Field(None, description="실행 시간 (초)")

# ─────────────────────────────────────────────
# 6) API 엔드포인트 정의
# ─────────────────────────────────────────────

# API 엔드포인트 정의
@app.get("/", response_class=HTMLResponse)
async def main_page():
    """메인 HTML 인터페이스 페이지 - 외부 HTML 파일 사용"""
    html_content = load_html_file()
    return HTMLResponse(content=html_content)

@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "openai_api_key": "configured" if os.getenv("OPENAI_API_KEY") else "missing",
        "html_file_found": any(os.path.exists(f) for f in ['main.html', 'index.html', 'ai-research-agent.html'])
    }

@app.post("/research", response_model=ResearchResponse)
async def conduct_research(request: ResearchRequest):
    """AI 에이전트가 리서치를 수행하고 보고서를 반환"""
    # API 키 확인
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=500, 
            detail="OpenAI API 키가 설정되지 않았습니다."
        )

    # 입력 값 검증
    if not request.topic.strip():
        raise HTTPException(status_code=400, detail="주제를 입력해주세요.")
    
    if not request.domain.strip():
        raise HTTPException(status_code=400, detail="도메인을 입력해주세요.")

    # 실행 시간 측정 시작
    start_time = time.time()
    
    try:
        print(f"🔄 리서치 에이전트 실행 시작 - 주제: '{request.topic}', 도메인: '{request.domain}'")
        
        # LangChain 에이전트 실행
        result = await agent_executor.ainvoke({
            "topic": request.topic, 
            "domain": request.domain
        })
        
        # 실행 시간 계산
        execution_time = time.time() - start_time
        
        # 결과 추출
        report_content = result.get("output", "리서치 결과물을 찾을 수 없습니다.")
        
        print(f"✅ 리서치 에이전트 실행 완료 - 보고서 길이: {len(report_content)} 문자, 실행 시간: {execution_time:.2f}초")
        
        return ResearchResponse(
            status="success",
            report=report_content,
            execution_time=round(execution_time, 2)
        )
        
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"❌ 리서치 에이전트 실행 중 오류 발생: {e}")
        print(f"📋 상세 오류 내용:\n{error_trace}")
        
        raise HTTPException(
            status_code=500, 
            detail=f"리서치 에이전트 실행 중 오류가 발생했습니다: {str(e)}"
        )

# ─────────────────────────────────────────────
# 7) 서버 시작/종료 이벤트 핸들러
# ─────────────────────────────────────────────

# 서버 시작 이벤트 핸들러
@app.on_event("startup")
async def startup_event():
    """서버 시작 시 실행되는 이벤트"""
    print("🚀 AI 리서치 에이전트 API 서버가 시작되었습니다!")
    print("📋 API 문서: http://127.0.0.1:8000/docs")
    print("🔍 헬스 체크: http://127.0.0.1:8000/health")
    
    # HTML 파일 확인
    html_files = ['main.html', 'index.html', 'ai-research-agent.html']
    found_files = [f for f in html_files if os.path.exists(f)]
    
    if found_files:
        print(f"✅ HTML 파일 발견: {found_files}")
    else:
        print(f"⚠️ HTML 파일을 찾을 수 없습니다. 다음 중 하나를 추가하세요: {html_files}")
    
    # 에이전트 초기화 확인
    try:
        from agent_setup import agent_executor
        print("✅ 에이전트 초기화 완료")
    except Exception as e:
        print(f"❌ 에이전트 초기화 실패: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """서버 종료 시 실행되는 이벤트"""
    print("🛑 AI 리서치 에이전트 API 서버가 종료됩니다.")

# ─────────────────────────────────────────────
# 8) 서버 실행
# ─────────────────────────────────────────────

# 서버 실행
if __name__ == "__main__":
    import uvicorn
    
    if not check_api_key():
        print("❌ API 키가 설정되지 않았습니다. 서버를 시작할 수 없습니다.")
        exit(1)
    
    print("🚀 AI 리서치 에이전트 API 서버를 시작합니다...")
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_level="info"
    )