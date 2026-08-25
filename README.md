# Book Search

`books.csv`의 도서 데이터를 SQLite에 적재하고, 도서명 검색과 페이지네이션을 제공하는 최소 FastAPI 프로젝트입니다. 별도 빌드 도구 없이 HTML/CSS/JavaScript 화면도 함께 제공합니다.

## 실행 방법

Python 3.13 환경에서 확인했습니다.

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
```

### macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
```

실행 후 아래 주소를 사용합니다.

- 검색 화면: <http://127.0.0.1:8000/>
- Swagger API 문서: <http://127.0.0.1:8000/docs>
- 상태 확인: <http://127.0.0.1:8000/health>

## SQLite DB 생성 및 사용 방법

프로젝트 루트에 `books.csv`가 있어야 합니다. 서버 최초 실행 시 CSV를 읽어 같은 프로젝트 안에 `books.db`와 `books` 테이블을 자동 생성합니다.

- CSV 기본 경로: `./books.csv`
- DB 기본 경로: `./books.db`
- 기본키: CSV의 `id`를 `INTEGER PRIMARY KEY`로 사용
- `title`, `author`, `publisher`, `category`, `published_date`, `isbn`: `TEXT`
- `price`, `stock`: `INTEGER`
- 기존 테이블에 데이터가 있으면 다시 적재하지 않습니다.
- 동시 실행 시에도 `id` 기준 `INSERT OR IGNORE`로 중복 적재를 방지합니다.

DB 파일명을 변경하려면 `.env.example`을 `.env`로 복사한 뒤 프로젝트 내부 상대경로를 지정합니다. 절대경로나 프로젝트 밖의 경로는 허용하지 않습니다.

```powershell
Copy-Item .env.example .env
```

```dotenv
DATABASE_PATH=data/books.db
```

DB를 원본 CSV로 다시 만들려면 서버를 종료하고 `books.db`를 삭제한 뒤 서버를 다시 실행합니다. `.env`와 `books.db`는 Git 제외 대상입니다.

## API 사용 방법

```http
GET /api/books?query=검색어&page=1&size=20
```

- `query`: 도서명 부분 일치 검색. 생략하거나 공백이면 전체 목록을 조회합니다.
- `page`: 1부터 시작합니다.
- `size`: 기본값 20, 허용 범위 1~100입니다.
- 결과는 `id` 오름차순으로 반환합니다.
- 검색 결과가 없거나 전체 페이지를 넘어가면 `200 OK`와 빈 `items`를 반환합니다.
- 잘못된 `page` 또는 `size`는 `422`를 반환합니다.

응답 형태:

```json
{
  "items": [],
  "page": 1,
  "total": 0,
  "total_pages": 0
}
```

## 사용 기술

- Python 3.13
- FastAPI, Uvicorn, Pydantic
- Python 표준 라이브러리 `sqlite3`, `csv`
- python-dotenv
- HTML, CSS, Vanilla JavaScript
- pytest, FastAPI TestClient, httpx2

SQLAlchemy는 사용하지 않았습니다. 제한 시간과 현재 규모를 고려해 `sqlite3`로 직접 쿼리합니다.

## 구현한 기능

- UTF-8 CSV 검증 및 SQLite 자동 적재
- 앱 반복·동시 실행 시 중복 적재 방지
- 도서명 부분 일치 검색
- SQL 파라미터 바인딩과 LIKE 특수문자 escape
- 서버 측 `LIMIT/OFFSET` 페이지네이션
- 페이지·페이지 크기 validation
- 빈 검색 결과 처리
- DB 연결의 명시적 commit/rollback 및 close
- 검색 입력, 검색 버튼, Enter 검색
- 도서 제목·저자·출판사·카테고리·출간일·가격·재고 표시
- 이전/다음 및 현재/전체 페이지 표시
- Loading, empty, API 오류 화면
- 빠른 연속 검색 시 이전 요청 취소 및 마지막 검색 결과 표시
- Swagger 문서와 health endpoint

## 테스트

```powershell
python -m pytest
```

현재 테스트는 CSV 적재, 중복 방지, DB 연결 종료, 검색, 페이지네이션, 빈 결과, 입력 validation, SQL Injection 방어, 정적 페이지 제공을 확인합니다.

## 구현하지 못했거나 생략한 부분

- 브라우저 사용자 흐름을 반복 실행하는 E2E 자동화 테스트는 저장소에 포함하지 못했습니다. 개발 중 실제 Chrome으로 흐름을 확인했지만, 현재 저장소에는 pytest 기반 백엔드·정적 파일 테스트만 남아 있습니다.
- 프런트엔드 JavaScript 상태 변화에 대한 독립적인 단위 테스트는 없습니다.
- 도서 등록·수정·삭제 API는 구현하지 않았습니다.
- 인증, 사용자, 권한 기능은 구현하지 않았습니다.
- DB migration 도구와 스키마 버전 관리는 생략했습니다.
- Docker 및 배포 환경 구성은 포함하지 않았습니다.
- 정렬, 카테고리 필터, 검색어 자동완성은 구현하지 않았습니다.

## 시간이 더 있다면 개선할 부분

- 프런트 UI 개선: 모바일 목록 표현, 접근성 점검, 상세 화면, 정렬·필터, 디자인 완성도 개선
- 검색 성능 개선: 현재 `%검색어%` LIKE 검색은 일반 B-tree `title` 인덱스를 효과적으로 사용하기 어렵습니다. SQLite FTS5 도입 또는 검색 요구사항에 맞는 인덱스·검색 방식 검토
- 대용량 데이터 대응: CSV 스트리밍·분할 적재, cursor pagination, 쿼리 실행 계획 측정, 필요 시 PostgreSQL 같은 서버형 DB로 전환
- 코드 세분화: 현재 `main.py`에 설정, CSV 적재, DB 처리, API가 함께 있습니다. 규모가 커지면 책임 단위로 분리하고 SOLID 원칙과 의존성 방향을 재검토
- 테스트 개선: 브라우저 E2E 테스트를 정식 테스트 스위트에 추가하고 오류·동시 요청·접근성 시나리오를 자동화
