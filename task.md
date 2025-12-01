# Redis 기반 서버리스 함수 실행 시스템 구현 태스크

## 1. Redis Stream & Pub/Sub 시스템 구현

### 1.1 RedisService 확장
- [x] RedisService에 Redis Stream 메서드 추가
  - `xadd()`: 스트림에 메시지 추가
  - `xgroup_create()`: Consumer Group 생성
  - `xreadgroup()`: Consumer Group으로 메시지 읽기
  - `xack()`: 메시지 처리 완료 확인
- [x] RedisService에 Pub/Sub 메서드 추가
  - `publish()`: 채널에 메시지 발행
  - `subscribe()`: 채널 구독
  - `get_pubsub()`: pubsub 객체 반환

### 1.2 ExecutionClient 리팩토링
- [x] 현재 리스트 기반 큐를 Redis Stream으로 변경
- [x] exec_queue → exec_stream으로 변경
- [x] Consumer Group 기반 메시지 처리 지원

## 2. Sync 요청 처리를 위한 waiters 시스템

### 2.1 Waiters 맵 구현
- [ ] In-memory waiters 맵 구현 (`Dict[str, asyncio.Future]`)
- [ ] Job ID 기반 Future 생성 및 관리
- [ ] Future 완료 및 정리 로직

### 2.2 Redis pub/sub 리스너
- [ ] 백그라운드 pub/sub 리스너 구현
- [ ] callback_channel에서 메시지 수신
- [ ] 해당 Job의 Future 완료 처리
- [ ] FastAPI lifespan에서 리스너 시작

## 3. Job 모델 및 API 개선

### 3.1 API 엔드포인트 개선
- [ ] sync 요청 처리 로직 구현 (Future 대기)
- [ ] async 요청 처리 로직 구현 (즉시 응답)

## 4. Worker 프로세스 구현

### 4.1 Worker 기본 구조
- [x] `worker.py` 메인 엔트리포인트 생성
- [x] Worker 클래스 구현 (Consumer Group 기반)
- [x] Redis Stream 소비 루프 구현

### 4.2 함수 실행 추상화
- [x] `execute_function` 추상화 인터페이스 구현
- [x] 더미 구현 (현재 단계용)
- [ ] KNative/서버리스 런타임 연동 준비

### 4.3 결과 처리
- [x] Worker에서 Job 상태 업데이트 로직
- [x] 성공/실패에 따른 DB 업데이트
- [X] Pub/Sub으로 결과 알림 발송
- [x] Stream 메시지 ACK 처리

## 5. 에러 처리 & 설정

### 5.1 설정 및 상수
- [ ] Redis 스트림/채널 이름 상수화
- [ ] Consumer Group 이름 설정

### 5.2 에러 처리
- [ ] Worker 에러 처리 및 FAILED 상태 처리
- [ ] Redis 연결 실패 대응 로직
- [ ] 예외 상황별 적절한 에러 응답

## 6. 테스트 및 검증

### 6.1 단위 테스트
- [ ] RedisService Stream/PubSub 메서드 테스트
- [ ] Waiters 시스템 테스트
- [ ] Worker 로직 테스트

### 6.2 통합 테스트  
- [ ] Sync/Async 함수 실행 플로우 테스트
- [ ] 타임아웃 시나리오 테스트
- [ ] 에러 처리 시나리오 테스트

## 구현 우선순위

1. **Phase 1**: RedisService 확장 (Stream, PubSub)
2. **Phase 2**: Job 모델 확장 및 API 기본 구조
3. **Phase 3**: Waiters 시스템 및 Pub/Sub 리스너
4. **Phase 4**: Worker 프로세스 구현
5. **Phase 5**: 에러 처리 및 테스트