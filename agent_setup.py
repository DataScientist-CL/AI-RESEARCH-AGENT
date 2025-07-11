# agent_setup.py — AI 리서치 에이전트 설정 (수정 버전)

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import AgentExecutor, create_openai_tools_agent
from tools import web_scraper_tool, query_generator_tool

# ─────────────────────────────────────────────
# 1) 환경 변수 로드 및 초기 설정
# ─────────────────────────────────────────────

# .env 파일 로드 (API 키를 불러오기 위함)
load_dotenv()

# API 키 확인 함수
def verify_api_key():
    """OpenAI API 키 확인"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI API 키가 설정되지 않았습니다. .env 파일을 확인해주세요.")
    
    if not api_key.startswith("sk-"):
        raise ValueError("올바르지 않은 OpenAI API 키 형식입니다.")
    
    print(f"✅ OpenAI API 키 확인 완료: {api_key[:7]}...")
    return api_key

# API 키 확인
verify_api_key()

# ─────────────────────────────────────────────
# 2) LLM 모델 초기화
# ─────────────────────────────────────────────

# OpenAI ChatGPT 모델 초기화
# temperature=0: 일관된 답변을 위해 창의성을 최소화
# model="gpt-4o": 최신 GPT-4 모델 사용
llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0,
    max_tokens=4000,  # 응답 길이 제한
    timeout=60,       # 타임아웃 설정
    max_retries=2     # 재시도 횟수
)

# ─────────────────────────────────────────────
# 3) 에이전트 도구 설정
# ─────────────────────────────────────────────

# 에이전트가 사용할 도구들 정의
tools = [
    web_scraper_tool,      # 웹 검색 및 스크래핑 도구
    query_generator_tool   # 검색 쿼리 생성 도구
]

print(f"🔧 에이전트 도구 로드 완료: {len(tools)}개")
for tool in tools:
    print(f"   - {tool.name}: {tool.description}")

# ─────────────────────────────────────────────
# 4) 프롬프트 템플릿 정의
# ─────────────────────────────────────────────

# **중요**: OpenAI Tools Agent에 맞는 프롬프트 구조 사용
# 기존 ReAct 방식과 다른 구조를 사용해야 함
prompt = ChatPromptTemplate.from_messages([
    ("system", """
    당신은 전문적인 AI 리서치 에이전트입니다. 사용자가 요청한 주제에 대해 철저한 조사를 수행하고 전문적인 보고서를 작성합니다.

    ## 🎯 당신의 역할:
    1. 사용자의 요청을 정확히 이해하고 분석
    2. 효과적인 검색 전략 수립
    3. 신뢰할 수 있는 정보 수집 및 검증
    4. 수집된 정보를 체계적으로 분석
    5. 전문적이고 이해하기 쉬운 보고서 작성

    ## 📋 작업 절차:
    1. **검색 쿼리 생성**: query_generator_tool을 사용하여 최적의 검색 쿼리 생성
    2. **정보 수집**: web_scraper_tool을 사용하여 관련 정보 검색 및 수집
    3. **추가 검색**: 필요 시 다른 관점에서 추가 검색 수행
    4. **정보 분석**: 수집된 정보를 종합하여 핵심 내용 추출
    5. **보고서 작성**: 아래 형식에 맞춰 최종 보고서 작성

    ## 📄 보고서 형식:
    ```
    # [주제명] 리서치 보고서

    ## 🔍 개요
    [주제에 대한 간략한 소개와 보고서의 목적]

    ## 📊 주요 발견사항
    ### 1. [첫 번째 주요 발견]
    - [구체적인 내용과 데이터]
    - [출처 및 신뢰성]

    ### 2. [두 번째 주요 발견]
    - [구체적인 내용과 데이터]
    - [출처 및 신뢰성]

    ### 3. [세 번째 주요 발견]
    - [구체적인 내용과 데이터]
    - [출처 및 신뢰성]

    ## 🎯 핵심 인사이트
    [수집된 정보에서 도출된 핵심 통찰]

    ## 🔮 향후 전망
    [해당 분야의 미래 전망 및 예측]

    ## 💡 결론
    [보고서의 핵심 요약 및 최종 결론]
    ```

    ## ⚠️ 주의사항:
    - 정확하고 신뢰할 수 있는 정보만 포함
    - 출처가 불분명한 내용은 반드시 언급
    - 객관적이고 균형 잡힌 시각 유지
    - 전문 용어 사용 시 간단한 설명 추가
    """),
    
    ("user", """
    🔍 리서치 요청 내용:
    - 주제: {topic}
    - 전문 도메인: {domain}
    
    위 내용에 대해 철저한 조사를 수행하고 전문적인 보고서를 작성해주세요.
    """),
    
    # 중요: agent_scratchpad는 OpenAI Tools Agent에서 필수
    MessagesPlaceholder("agent_scratchpad")
])

# ─────────────────────────────────────────────
# 5) 에이전트 생성 및 설정
# ─────────────────────────────────────────────

print("🤖 AI 리서치 에이전트 생성 중...")

# **핵심 수정사항**: create_react_agent 대신 create_openai_tools_agent 사용
# 이 방식이 현재 LangChain 버전에서 더 안정적
agent = create_openai_tools_agent(
    llm=llm,
    tools=tools,
    prompt=prompt
)

# AgentExecutor 설정
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,                    # 디버깅을 위한 상세 로그
    handle_parsing_errors=True,      # 파싱 오류 자동 처리
    max_iterations=10,               # 최대 반복 횟수 제한
    max_execution_time=300,          # 최대 실행 시간 (5분)
    early_stopping_method="generate", # 조기 종료 방법
    return_intermediate_steps=False   # 중간 단계 반환 안 함 (성능 개선)
)

print("✅ AI 리서치 에이전트 생성 완료!")
print(f"🔧 설정된 도구 수: {len(tools)}")
print(f"🎛️ 최대 반복 횟수: {agent_executor.max_iterations}")
print(f"⏱️ 최대 실행 시간: {agent_executor.max_execution_time}초")

# ─────────────────────────────────────────────
# 6) 에이전트 테스트 함수 (선택사항)
# ─────────────────────────────────────────────

async def test_agent_setup():
    """에이전트 설정 테스트"""
    try:
        print("🧪 에이전트 기본 테스트 시작...")
        
        # 간단한 테스트 실행
        test_result = await agent_executor.ainvoke({
            "topic": "AI 기술 테스트",
            "domain": "기술"
        })
        
        print("✅ 에이전트 테스트 성공!")
        return True
        
    except Exception as e:
        print(f"❌ 에이전트 테스트 실패: {e}")
        return False

# 모듈 임포트 시 기본 정보 출력
if __name__ == "__main__":
    print("📋 agent_setup.py 실행됨")
    print("🤖 에이전트 준비 완료")
    
    # 테스트 실행 (선택사항)
    import asyncio
    asyncio.run(test_agent_setup())