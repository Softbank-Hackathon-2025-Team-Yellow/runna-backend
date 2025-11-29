# Runna Backend API

## 설명
서버리스 서비스인 Runna의 백엔드 API입니다.

## 환경 설정

### 1. 환경변수 설정
먼저 `.env.example` 파일을 복사하여 `.env` 파일을 생성하고 실제 값으로 수정하세요:

```bash
cp .env.example .env
```

`.env` 파일을 열어 다음 값들을 실제 환경에 맞게 수정:

```bash
# Database Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/your_db_name

# KNative Configuration  
KNATIVE_URL=http://your-knative-url:8080
KNATIVE_TIMEOUT=30

# Security Configuration
SECRET_KEY=your-super-secret-key-for-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Environment
ENVIRONMENT=development  # development | production
DEBUG=true
```

### 2. 보안 주의사항
- 🔐 **SECRET_KEY**: 프로덕션에서는 반드시 안전한 키로 설정
- 🗄️ **DATABASE_URL**: 실제 데이터베이스 연결 정보로 변경
- 🚫 **절대 `.env` 파일을 Git에 커밋하지 마세요**

## 설치

### 1. Python 의존성 설치
```bash
# uv 사용 (권장)
uv sync

# 또는 pip 사용
pip install -r requirements.txt
```

### 2. 데이터베이스 설정
PostgreSQL 데이터베이스가 실행 중이어야 합니다:

```bash
# PostgreSQL 설치 (Ubuntu/Debian)
sudo apt-get install postgresql postgresql-contrib

# 데이터베이스 및 사용자 생성
sudo -u postgres createdb runna_db
sudo -u postgres createuser runna_user
sudo -u postgres psql -c "ALTER USER runna_user WITH PASSWORD 'your_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE runna_db TO runna_user;"
```

### 3. 애플리케이션 실행
```bash
# 개발 모드로 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 또는 프로덕션 모드
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## API 문서
서버 실행 후 다음 URL에서 API 문서를 확인할 수 있습니다:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 주요 기능
- 함수 관리 (CRUD 작업)
- 함수 실행 (동기/비동기)
- 작업 관리 및 추적
- 보안을 위한 정적 코드 분석
- KNative 통합

## 개발 가이드

### 환경변수 추가하기
새로운 환경변수를 추가할 때:

1. `app/config.py`의 `Settings` 클래스에 필드 추가
2. `.env.example` 파일에 예시 값 추가
3. README.md 업데이트

### 테스트 실행
```bash
# 테스트 실행 (구현 예정)
pytest

# 커버리지 확인 (구현 예정)
pytest --cov=app
```

## 프로젝트 구조
```
backend/
├── app/
│   ├── api/          # API 엔드포인트
│   ├── core/         # 핵심 기능
│   ├── models/       # 데이터베이스 모델
│   ├── schemas/      # Pydantic 스키마
│   └── services/     # 비즈니스 로직
├── tests/            # 테스트 파일
├── .env.example      # 환경변수 템플릿
└── README.md         # 이 파일
```

## API 명세
자세한 API 명세는 다음 문서를 참조하세요:
- [API 문서](docs/api_docs.md)
- [공통 API 응답 형식](docs/common_api_docs.md)