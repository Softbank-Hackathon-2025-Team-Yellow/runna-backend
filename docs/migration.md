# 데이터베이스 마이그레이션 가이드 (Alembic)

## 개요
이 프로젝트는 SQLAlchemy와 Alembic을 사용하여 데이터베이스 스키마 변경을 관리합니다.

## 설정

### 1. 초기 설정
Alembic은 이미 설정되어 있으며, 다음과 같은 구조로 되어 있습니다:

```
backend/
├── alembic.ini          # Alembic 설정 파일
├── migrations/          # 마이그레이션 디렉토리
│   ├── env.py          # Alembic 환경 설정
│   ├── script.py.mako  # 마이그레이션 템플릿
│   └── versions/       # 마이그레이션 파일들
```

### 2. 환경변수 설정
`.env` 파일에서 데이터베이스 URL을 설정합니다:
```bash
DATABASE_URL=postgresql://username:password@localhost:5432/runna_db
```

## 마이그레이션 명령어

### 1. 새 마이그레이션 생성 (자동 감지)
모델 변경사항을 자동으로 감지하여 마이그레이션 파일을 생성합니다:

```bash
uv run alembic revision --autogenerate -m "마이그레이션 설명"
```

예시:
```bash
uv run alembic revision --autogenerate -m "Add user table"
uv run alembic revision --autogenerate -m "Add index to function name"
```

### 2. 빈 마이그레이션 생성 (수동)
수동으로 작성할 마이그레이션 파일을 생성합니다:

```bash
uv run alembic revision -m "마이그레이션 설명"
```

### 3. 마이그레이션 적용
최신 버전까지 마이그레이션을 적용합니다:

```bash
uv run alembic upgrade head
```

특정 버전까지 적용:
```bash
uv run alembic upgrade <revision_id>
```

### 4. 마이그레이션 되돌리기
이전 버전으로 되돌립니다:

```bash
uv run alembic downgrade -1      # 1단계 되돌리기
uv run alembic downgrade <revision_id>  # 특정 버전으로 되돌리기
uv run alembic downgrade base    # 모든 마이그레이션 되돌리기
```

### 5. 마이그레이션 히스토리 확인
현재 마이그레이션 상태 확인:

```bash
uv run alembic current
```

마이그레이션 히스토리 확인:
```bash
uv run alembic history --verbose
```

## 모델 변경 워크플로우

### 1. 모델 수정
SQLAlchemy 모델 파일을 수정합니다:
- `app/models/function.py`
- `app/models/job.py`
- `app/models/execution.py`

### 2. 마이그레이션 생성
```bash
uv run alembic revision --autogenerate -m "변경사항 설명"
```

### 3. 마이그레이션 파일 검토
생성된 파일 (`migrations/versions/xxxxx_변경사항_설명.py`)을 검토하고 필요시 수정합니다.

### 4. 마이그레이션 적용
```bash
uv run alembic upgrade head
```

## 주의사항

### 1. 모델 Import
`migrations/env.py`에서 모든 모델을 import해야 합니다:

```python
# Import all models to ensure they are registered with Base.metadata
from app.models.function import Function
from app.models.execution import Execution  
from app.models.job import Job
```

### 2. 마이그레이션 파일 검토
자동 생성된 마이그레이션은 항상 검토해야 합니다:
- 데이터 손실 가능성
- 인덱스 추가/삭제
- 외래키 제약조건 변경

### 3. 백업
프로덕션 환경에서는 마이그레이션 전 반드시 데이터베이스를 백업합니다.

### 4. 테스트
새로운 마이그레이션은 개발/스테이징 환경에서 먼저 테스트합니다.

## 일반적인 시나리오

### 새 테이블 추가
1. 새 모델 클래스 작성
2. `migrations/env.py`에 import 추가
3. 마이그레이션 생성 및 적용

### 컬럼 추가/삭제
1. 모델에서 컬럼 추가/삭제
2. 마이그레이션 생성
3. 생성된 파일에서 기본값 설정 확인
4. 마이그레이션 적용

### 인덱스 추가
1. 모델에 `index=True` 추가 또는 `Index()` 정의
2. 마이그레이션 생성 및 적용

### 데이터 마이그레이션
```python
# 마이그레이션 파일에서
from alembic import op
import sqlalchemy as sa

def upgrade():
    # 스키마 변경
    op.add_column('users', sa.Column('email', sa.String(255)))
    
    # 데이터 마이그레이션
    connection = op.get_bind()
    connection.execute("UPDATE users SET email = 'default@example.com' WHERE email IS NULL")

def downgrade():
    op.drop_column('users', 'email')
```

## 트러블슈팅

### 마이그레이션 충돌
```bash
# 현재 상태 확인
uv run alembic current

# 수동으로 특정 버전으로 설정
uv run alembic stamp <revision_id>
```

### 스키마 불일치
```bash
# 현재 데이터베이스 상태와 동기화
uv run alembic stamp head
```

### 마이그레이션 파일 병합
여러 브랜치에서 마이그레이션이 생성된 경우:
```bash
uv run alembic merge -m "Merge migrations" <rev1> <rev2>
```