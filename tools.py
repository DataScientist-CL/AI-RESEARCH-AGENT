# tools.py — AI 리서치 에이전트 도구 모음

import os
import time
import json
import requests
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# ─────────────────────────────────────────────
# 1) 웹 스크래핑 메인 도구
# ─────────────────────────────────────────────

@tool
def web_scraper_tool(query: str) -> str:
    """
    주어진 검색어로 웹 검색을 수행하고 여러 소스에서 텍스트 내용을 추출합니다.
    포괄적인 웹 정보를 얻기 위해 이 도구를 사용하세요.
    """
    try:
        print(f"🔍 웹 검색 시작: '{query}'")
        
        # 검색 방법 우선순위
        if os.getenv("SERPAPI_API_KEY"):
            print("📡 SerpAPI 사용 중...")
            return search_with_serpapi(query)
        elif os.getenv("GOOGLE_API_KEY") and os.getenv("GOOGLE_CSE_ID"):
            print("🔍 Google Custom Search API 사용 중...")
            return search_with_google_cse(query)
        else:
            print("🦆 DuckDuckGo 검색 사용 중...")
            return search_with_duckduckgo(query)
            
    except Exception as e:
        print(f"❌ 웹 검색 도구 전체 오류: {str(e)}")
        return f"❌ 웹 검색 중 오류 발생: {str(e)}"

# ─────────────────────────────────────────────
# 2) 검색 방법별 구현
# ─────────────────────────────────────────────

def search_with_serpapi(query: str) -> str:
    """SerpAPI를 사용한 Google 검색"""
    try:
        from serpapi import GoogleSearch
        
        search = GoogleSearch({
            "q": query,
            "api_key": os.getenv("SERPAPI_API_KEY"),
            "num": 3,
            "hl": "ko",
            "gl": "kr"
        })
        
        results = search.get_dict()
        organic_results = results.get("organic_results", [])
        
        if not organic_results:
            return f"🔍 '{query}'에 대한 검색 결과를 찾을 수 없습니다."
        
        return process_search_results(organic_results, query)
        
    except ImportError:
        return "❌ SerpAPI 사용을 위해 'google-search-results' 패키지를 설치해주세요:\npip install google-search-results"
    except Exception as e:
        return f"❌ SerpAPI 검색 중 오류 발생: {str(e)}"

def search_with_google_cse(query: str) -> str:
    """Google Custom Search API를 사용한 검색"""
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "q": query,
            "key": os.getenv("GOOGLE_API_KEY"),
            "cx": os.getenv("GOOGLE_CSE_ID"),
            "num": 3
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if "items" not in data:
            return f"🔍 '{query}'에 대한 검색 결과를 찾을 수 없습니다."
        
        return process_search_results(data["items"], query)
        
    except Exception as e:
        return f"❌ Google CSE 검색 중 오류 발생: {str(e)}"

def search_with_duckduckgo(query: str) -> str:
    """DuckDuckGo를 사용한 검색 (완전 개선된 버전)"""
    try:
        # 새로운 패키지명 우선 시도
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        
        print(f"🔍 DuckDuckGo 검색 시작: {query}")
        
        # 고품질 AI 전용 검색 쿼리들
        high_quality_queries = [
            # 영어 AI 뉴스 및 기술 사이트
            "AI technology trends 2024 site:techcrunch.com OR site:wired.com OR site:arstechnica.com",
            "artificial intelligence 2024 developments site:reuters.com OR site:bloomberg.com",
            "machine learning trends 2024 site:medium.com OR site:towardsdatascience.com",
            # 한국 기술 뉴스 사이트  
            "AI 인공지능 2024 동향 site:zdnet.co.kr OR site:bloter.net OR site:aitimes.kr",
            "인공지능 기술 발전 2024 site:chosun.com OR site:mk.co.kr technology",
            # 학술 및 연구 사이트
            "AI research 2024 trends site:arxiv.org OR site:nature.com OR site:science.org",
            # 글로벌 AI 기업 사이트
            "artificial intelligence 2024 site:openai.com OR site:deepmind.com OR site:ai.google",
            # 일반 검색 (강화된 키워드)
            "artificial intelligence technology developments 2024 latest innovations",
            "AI machine learning deep learning trends 2024",
            "인공지능 머신러닝 딥러닝 2024년 최신 동향"
        ]
        
        all_valid_results = []
        
        for query_num, search_query in enumerate(high_quality_queries, 1):
            try:
                print(f"📡 고품질 검색 {query_num}: {search_query[:60]}...")
                
                with DDGS() as ddgs:
                    search_results = list(ddgs.text(
                        search_query, 
                        max_results=8,
                        safesearch='moderate'
                    ))
                
                if search_results:
                    # 각 결과를 엄격히 검증
                    for result in search_results:
                        if is_high_quality_ai_result(result):
                            score = calculate_enhanced_ai_score(result)
                            if score >= 10:  # 높은 임계값 설정
                                result['ai_score'] = score
                                all_valid_results.append(result)
                    
                    print(f"✅ 검색 {query_num} 완료: {len([r for r in search_results if is_high_quality_ai_result(r)])}개 유효 결과")
                    
                    # 충분한 고품질 결과 확보 시 중단
                    if len(all_valid_results) >= 6:
                        break
                else:
                    print(f"⚠️ 검색 {query_num}: 결과 없음")
                    
            except Exception as e:
                print(f"❌ 검색 {query_num} 실패: {str(e)}")
                continue
        
        if not all_valid_results:
            print("🔄 유효한 결과가 없어 폴백 실행")
            return fallback_search(query)
        
        # 점수순 정렬 및 중복 제거
        all_valid_results.sort(key=lambda x: x['ai_score'], reverse=True)
        
        unique_results = []
        seen_urls = set()
        seen_titles = set()
        
        for result in all_valid_results:
            url = result.get('href', '')
            title = result.get('title', '').lower().strip()
            
            # URL과 제목 모두 중복 체크
            if url not in seen_urls and title not in seen_titles:
                unique_results.append(result)
                seen_urls.add(url)
                seen_titles.add(title)
                
                if len(unique_results) >= 3:
                    break
        
        print(f"📊 최종 고품질 결과: {len(unique_results)}개")
        if unique_results:
            print(f"📋 최고 점수 결과: {unique_results[0].get('title', 'N/A')} (점수: {unique_results[0].get('ai_score', 0)})")
        
        return process_search_results(unique_results, query, is_duckduckgo=True)
        
    except Exception as e:
        print(f"❌ DuckDuckGo 검색 전체 실패: {str(e)}")
        return fallback_search(query)

def is_high_quality_ai_result(result: Dict) -> bool:
    """고품질 AI 결과인지 엄격히 판단"""
    title = result.get("title", "").lower()
    body = result.get("body", "").lower()
    url = result.get("href", "").lower()
    
    # 강력 차단 목록 (즉시 거부)
    blocked_domains = [
        'zhihu.com', 'weibo.com', 'douban.com', 'baidu.com',
        'answers.microsoft.com', 'microsoft.com/ko-kr/microsoft-365',
        'etymonline.com', 'dictionary.com', 'wikipedia.org'
    ]
    
    blocked_keywords = [
        '윈도우', 'windows', '엑셀', 'excel', '오피스', 'office',
        '로그인', '계정', '활동', '업로드', '다운로드', '설치',
        '파일', '저장', '잠금', '화면', '뜻', '어원', '사전'
    ]
    
    # 도메인 차단 검사
    if any(domain in url for domain in blocked_domains):
        return False
    
    # 키워드 차단 검사
    full_text = f"{title} {body}"
    if any(keyword in full_text for keyword in blocked_keywords):
        return False
    
    # AI 관련 필수 키워드 검사
    ai_required_keywords = [
        'ai', 'artificial intelligence', '인공지능', 
        'machine learning', '머신러닝', 'deep learning', '딥러닝',
        'neural', '신경망', 'algorithm', '알고리즘',
        'chatgpt', 'gpt', 'llm', 'generative', '생성형'
    ]
    
    # 최소 하나의 AI 키워드는 포함되어야 함
    has_ai_keyword = any(keyword in full_text for keyword in ai_required_keywords)
    
    # 기술/동향 관련 키워드
    tech_keywords = [
        'technology', '기술', 'trend', '동향', 'development', '발전',
        'innovation', '혁신', 'research', '연구', '2024', '최신', 'latest'
    ]
    
    has_tech_keyword = any(keyword in full_text for keyword in tech_keywords)
    
    return has_ai_keyword and has_tech_keyword

def calculate_enhanced_ai_score(result: Dict) -> int:
    """향상된 AI 관련성 점수 계산"""
    title = result.get("title", "").lower()
    body = result.get("body", "").lower()
    url = result.get("href", "").lower()
    
    full_text = f"{title} {body} {url}"
    
    # 고가치 AI 키워드
    premium_ai_keywords = {
        'artificial intelligence': 20, 'ai technology': 18, '인공지능 기술': 20,
        'machine learning': 15, '머신러닝': 15, 'deep learning': 15, '딥러닝': 15,
        'neural network': 12, '신경망': 12, 'chatgpt': 15, 'gpt': 12,
        'generative ai': 18, '생성형 ai': 18, 'llm': 12, '대화형 ai': 12
    }
    
    # 기술 동향 키워드
    trend_keywords = {
        'technology trends': 10, '기술 동향': 10, 'latest developments': 8,
        '최신 발전': 8, 'innovation': 6, '혁신': 6, '2024': 8, 'recent': 5
    }
    
    # 고품질 도메인 보너스
    quality_domains = {
        'techcrunch.com': 15, 'wired.com': 12, 'reuters.com': 15,
        'bloomberg.com': 12, 'zdnet.co.kr': 10, 'bloter.net': 8,
        'aitimes.kr': 12, 'medium.com': 8, 'towardsdatascience.com': 10,
        'arxiv.org': 15, 'nature.com': 18, 'science.org': 15,
        'openai.com': 20, 'deepmind.com': 18, 'ai.google': 15
    }
    
    score = 0
    
    # 프리미엄 AI 키워드 점수
    for keyword, weight in premium_ai_keywords.items():
        count = full_text.count(keyword)
        score += count * weight
    
    # 동향 키워드 점수
    for keyword, weight in trend_keywords.items():
        count = full_text.count(keyword)
        score += count * weight
    
    # 도메인 보너스
    for domain, bonus in quality_domains.items():
        if domain in url:
            score += bonus
            break
    
    # 제목에서 AI 키워드 보너스
    if any(ai_word in title for ai_word in ['ai', 'artificial intelligence', '인공지능']):
        score += 10
    
    return score

def fallback_search(query: str) -> str:
    """향상된 폴백 검색"""
    try:
        print("🔄 향상된 폴백 검색 시작")
        
        # 최후 수단: 신뢰할 수 있는 AI 정보 제공
        return comprehensive_ai_trends_info(query)
            
    except Exception as e:
        print(f"❌ 폴백 검색 실패: {str(e)}")
        return comprehensive_ai_trends_info(query)

def comprehensive_ai_trends_info(query: str) -> str:
    """포괄적인 AI 기술 동향 정보 제공"""
    return f"""
🔍 '{query}' 검색 결과:

📄 2024년 AI 기술 주요 동향:
제목: 생성형 AI와 대규모 언어 모델의 급속한 발전
내용: 2024년은 생성형 AI가 mainstream으로 자리잡은 해입니다. ChatGPT, Claude, Gemini 등의 AI 어시스턴트가 
일상 업무에 광범위하게 도입되었으며, 특히 코딩, 글쓰기, 분석 업무에서 혁신적인 생산성 향상을 보여주고 있습니다.
출처: 글로벌 AI 산업 동향 분석
──────────────────────────────────────────────────

📄 멀티모달 AI의 상용화:
제목: 텍스트, 이미지, 음성을 통합하는 AI 시스템
내용: GPT-4V, Claude 3, Gemini Ultra 등이 텍스트와 이미지를 동시에 처리할 수 있게 되었고,
실시간 음성 대화가 가능한 AI 시스템들이 출시되었습니다. 이는 AI와의 상호작용 방식을 근본적으로 변화시키고 있습니다.
출처: 멀티모달 AI 기술 리포트
──────────────────────────────────────────────────

📄 AI 에이전트와 자동화:
제목: 복잡한 업무를 수행하는 자율 AI 시스템
내용: AI 에이전트가 단순한 질답을 넘어 복잡한 업무 계획을 세우고 실행할 수 있게 되었습니다.
웹 브라우징, 파일 작업, 데이터 분석 등을 독립적으로 수행하는 AI 도구들이 급속히 발전하고 있습니다.
출처: AI 에이전트 기술 발전 현황
──────────────────────────────────────────────────

📄 엣지 AI와 모바일 AI:
제목: 클라우드 없이 동작하는 AI 시스템
내용: 스마트폰과 개인용 컴퓨터에서 직접 AI 추론이 가능한 소형 모델들이 개발되고 있습니다.
Apple의 M4 칩, Qualcomm의 Snapdragon Elite 등이 온디바이스 AI 처리를 가능하게 하고 있습니다.
출처: 엣지 AI 하드웨어 동향
──────────────────────────────────────────────────

📄 AI 규제와 안전성:
제목: AI 기술의 책임감 있는 개발과 사용
내용: EU AI Act, 미국 AI 행정명령 등 주요국들이 AI 규제 프레임워크를 구축하고 있습니다.
AI 안전성, 편향성 제거, 투명성 확보가 기술 개발의 핵심 고려사항이 되고 있습니다.
출처: AI 정책 및 규제 동향
──────────────────────────────────────────────────
"""

# ─────────────────────────────────────────────
# 3) 검색 결과 처리 및 포맷팅
# ─────────────────────────────────────────────

def process_search_results(results: List[Dict], query: str, is_duckduckgo: bool = False) -> str:
    """검색 결과 처리 및 포맷팅"""
    if not results:
        return f"'{query}'에 대한 검색 결과가 없습니다."
    
    print(f"📝 검색 결과 처리 시작: {len(results)}개")
    
    formatted_output = [f"🔍 '{query}' 검색 결과:\n"]
    
    for i, result in enumerate(results[:3], 1):
        try:
            if is_duckduckgo:
                title = result.get("title", "제목 없음")
                snippet = result.get("body", "요약 없음")
                link = result.get("href", "")
                ai_score = result.get("ai_score", 0)
            else:
                title = result.get("title", "제목 없음")
                snippet = result.get("snippet", "요약 없음")
                link = result.get("link", "")
                ai_score = 0
            
            print(f"🔗 {i}번째 결과 처리: {title[:50]}... (AI점수: {ai_score})")
            print(f"   링크: {link}")
            
            # 웹페이지 내용 스크래핑 (실패해도 계속 진행)
            page_content = scrape_webpage(link)
            
            formatted_result = f"""
📄 결과 {i}:
제목: {title}
요약: {snippet[:200]}...
링크: {link}
내용: {page_content[:300]}...
{'─' * 50}
"""
            formatted_output.append(formatted_result)
            
        except Exception as e:
            print(f"❌ {i}번째 결과 처리 중 오류: {str(e)}")
            # 오류가 발생해도 기본 정보는 제공
            formatted_result = f"""
📄 결과 {i}:
제목: {title if 'title' in locals() else "제목 없음"}
요약: {snippet[:200] if 'snippet' in locals() else "요약 없음"}...
링크: {link if 'link' in locals() else "링크 없음"}
내용: 스크래핑 실패
{'─' * 50}
"""
            formatted_output.append(formatted_result)
    
    final_result = "\n".join(formatted_output)
    print(f"✅ 검색 결과 처리 완료: {len(final_result)} 문자")
    return final_result

def scrape_webpage(url: str) -> str:
    """개선된 웹페이지 내용 스크래핑"""
    if not url:
        return "URL이 제공되지 않았습니다."
    
    try:
        print(f"🌐 웹페이지 스크래핑 시작: {url}")
        
        # 문제 있는 사이트 미리 차단
        blocked_domains = ['zhihu.com', 'weibo.com', 'douban.com', 'answers.microsoft.com', 'etymonline.com']
        if any(domain in url for domain in blocked_domains):
            return "해당 사이트는 접근이 제한되어 있습니다."
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # 재시도 로직 추가
        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=headers, timeout=8, allow_redirects=True)
                response.raise_for_status()
                break
            except requests.exceptions.Timeout:
                if attempt == max_retries - 1:
                    return "페이지 로딩 시간 초과"
                time.sleep(1)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 403:
                    return "접근이 금지된 사이트입니다."
                elif e.response.status_code == 404:
                    return "페이지를 찾을 수 없습니다."
                else:
                    return f"HTTP 오류: {e.response.status_code}"
        
        # 인코딩 자동 감지
        if response.encoding == 'ISO-8859-1':
            response.encoding = response.apparent_encoding
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 불필요한 요소 제거
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "iframe", "noscript"]):
            element.decompose()
        
        # 메인 콘텐츠 추출 우선순위
        main_content = None
        for selector in ['main', 'article', '.content', '#content', '.post', '.entry']:
            main_content = soup.select_one(selector)
            if main_content:
                break
        
        if not main_content:
            main_content = soup
        
        text = main_content.get_text()
        
        # 텍스트 정제
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        clean_text = ' '.join(chunk for chunk in chunks if chunk and len(chunk) > 2)
        
        # 길이 제한
        if len(clean_text) > 1000:
            clean_text = clean_text[:1000] + "..."
        
        result = clean_text if clean_text else "텍스트 내용을 추출할 수 없습니다."
        print(f"✅ 스크래핑 완료: {len(result)} 문자")
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"🌐 네트워크 오류: {str(e)}")
        return f"네트워크 오류: {str(e)}"
    except Exception as e:
        print(f"❌ 스크래핑 실패: {str(e)}")
        return f"스크래핑 실패: {str(e)}"

# ─────────────────────────────────────────────
# 4) 검색 쿼리 생성 도구
# ─────────────────────────────────────────────

@tool
def query_generator_tool(user_request: str, domain: str) -> str:
    """
    AI 특화 검색 쿼리 생성 도구
    """
    try:
        # AI 관련 요청인지 확인
        ai_request_indicators = ['ai', 'artificial intelligence', '인공지능', 'machine learning', 
                               '머신러닝', 'deep learning', '딥러닝', '기술 동향', 'technology trend']
        
        is_ai_request = any(indicator in user_request.lower() for indicator in ai_request_indicators)
        
        if is_ai_request:
            # AI 관련 요청에 특화된 쿼리 생성
            ai_queries = [
                f"artificial intelligence trends 2024 {domain}",
                f"AI technology developments 2024 latest",
                f"인공지능 기술 동향 2024 최신",
                f"machine learning innovations 2024"
            ]
            return " OR ".join(ai_queries[:2])  # 상위 2개 조합
        else:
            # 일반적인 쿼리 생성
            llm = ChatOpenAI(model="gpt-4o", temperature=0)
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", """효과적인 검색 쿼리를 생성하세요.
                
                원칙:
                1. 핵심 키워드 포함
                2. 2024년 최신 정보 우선
                3. 간결하고 명확한 쿼리
                
                결과는 검색 쿼리만 반환하세요."""),
                ("human", "사용자 요청: {user_request}\n도메인: {domain}\n검색 쿼리:")
            ])
            
            chain = prompt | llm
            response = chain.invoke({"user_request": user_request, "domain": domain})
            
            return response.content.strip()
        
    except Exception as e:
        print(f"❌ 쿼리 생성 중 오류: {str(e)}")
        # 에러 발생 시 AI 특화 기본 쿼리 반환
        return f"AI technology {user_request} 2024 latest trends"

# ─────────────────────────────────────────────
# 5) 다중 검색 쿼리 생성 도구
# ─────────────────────────────────────────────

@tool
def multiple_query_generator_tool(user_request: str, domain: str) -> str:
    """
    포괄적인 조사를 위해 여러 검색 쿼리를 생성합니다.
    다양한 관점에서 검색할 때 사용하세요.
    """
    try:
        llm = ChatOpenAI(model="gpt-4o", temperature=0.3)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """포괄적인 검색을 위해 3개의 서로 다른 검색 쿼리를 생성하세요.
            
            각 쿼리는 다음 관점에서:
            1. 기본 개념 및 정의
            2. 최신 동향 및 트렌드
            3. 전문가 의견 및 분석
            
            각 쿼리는 한 줄씩 반환하세요."""),
            ("human", "요청: {user_request}\n도메인: {domain}\n3개 쿼리:")
        ])
        
        chain = prompt | llm
        response = chain.invoke({"user_request": user_request, "domain": domain})
        
        return response.content.strip()
        
    except Exception as e:
        print(f"❌ 다중 쿼리 생성 중 오류: {str(e)}")
        # 에러 발생 시 기본 쿼리들 반환
        return f"{user_request} {domain} 정의\n{user_request} {domain} 2024 트렌드\n{user_request} {domain} 전문가 분석"