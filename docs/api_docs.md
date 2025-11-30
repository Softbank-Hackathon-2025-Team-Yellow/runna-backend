# API Response Format

모든 API는 일관된 응답 형식을 사용합니다. 자세한 내용은 [Common API Response Types](common_api_docs.md)를 참조하세요.

## 기본 응답 구조

```typescript
interface CommonApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
    details?: any;
  };
}
```

- **성공 응답**: `{ success: true, data: T }`
- **실패 응답**: `{ success: false, error: {...} }`

아래 문서의 응답 예시들은 `data` 필드 내용만 표시하며, 실제 응답은 위 구조로 래핑됩니다.

---

# Types

## Enum Types

### `Runtime`

함수의 런타임 타입. python과 node.js 지원

| Value    | Description |
| -------- | ----------- |
| `python` |             |
| `nodejs` |             |

### `ExecutionType`

함수의 실행 타입. sync(동기) 또는 async(비동기) 지원

| Value       | Description |
| ----------- | ----------- |
| **`sync`**  | 동기        |
| **`async`** | 비동기      |

### `JobStatus`

함수 실행 작업의 상태

| Value     | Description                                            |
| --------- | ------------------------------------------------------ |
| `pending` | 실행 대기 중 (async 함수의 최초 요청 시에만 임시 반환) |
| `running` | 함수 실행 중                                           |
| `success` | 실행 성공                                              |
| `failed`  | 실행 실패                                              |

## Data Types

### `Function`

함수 정의 타입

| Field            | Type                              | Nullable | Description                       |
| ---------------- | --------------------------------- | -------- | --------------------------------- |
| `id`             | number                            | No       | 함수 고유 ID                      |
| `name`           | string                            | No       | 함수 이름 (고유값)                |
| `runtime`        | [`Runtime`](#Runtime)             | No       | 실행 환경 (`python`, `nodejs` 등) |
| `code`           | string                            | No       | 함수 코드                         |
| `execution_type` | [`ExecutionType`](#ExecutionType) | No       | 실행 타입 (`sync` 또는 `async`)   |
| `created_at`     | string(Datetime)                  | No       | 함수 생성 시간                    |
| `updated_at`     | string(Datetime)                  | No       | 함수 수정 시간                    |

### `Job`

함수 실행 작업 타입. 함수 실행 요청 시 생성되며 실행 결과가 기록됨

| Field         | Type                      | Nullable | Description         |
| ------------- | ------------------------- | -------- | ------------------- |
| `id`          | number                    | No       | 작업 ID             |
| `function_id` | number                    | No       | 실행된 함수의 ID    |
| `status`      | [`JobStatus`](#JobStatus) | No       | 작업 실행 상태      |
| `result`      | Object                    | Yes      | 함수 실행 결과      |
| `timestamp`   | string(Datetime)          | No       | 함수 실행 요청 시간 |
| `duration`    | number                    | Yes      | 함수 실행 시간(ms)  |

# 1. **Function Management API**

## **1.1. GET `/functions`**

함수 목록 조회

### **Request**

**Request Type**

| Field | Type | Nullable | Description |
| ----- | ---- | -------- | ----------- |
| -     | -    | -        |             |

### **Response**

**Response Type**

| Field       | Type                            | Nullable | Description |
| ----------- | ------------------------------- | -------- | ----------- |
| `functions` | Array<[`Function`](#Function) > | No       | 함수 목록   |

**Example**

```json
{
  "functions": [
    {
      "id": 1,
      "name": "myFunction",
      "runtime": "python",
      "code": "def handler(event): return event",
      "execution_type": "sync",
      "created_at": "2023-10-30T10:00:00Z",
      "updated_at": "2023-10-30T10:00:00Z"
    }
  ]
}
```

---

## **1.2. POST `/functions`**

함수 등록 (function_id 반환)

### **Request**

**Request Type**

| Field            | Type                              | Nullable | Description                       |
| ---------------- | --------------------------------- | -------- | --------------------------------- |
| `name`           | string                            | No       | 함수 이름                         |
| `runtime`        | [`Runtime`](#Runtime)             | No       | 실행 환경 (`python`, `nodejs` 등) |
| `code`           | string                            | No       | 함수 코드                         |
| `execution_type` | [`ExecutionType`](#ExecutionType) | No       | 실행 타입 (`sync` 또는 `async`)   |

**Example**

```json
{
  "name": "myFunction",
  "runtime": "python",
  "code": "def handler(event): return event",
  "execution_type": "sync"
}
```

### **Response**

**Response Type**

| Field         | Type   | Nullable | Description  |
| ------------- | ------ | -------- | ------------ |
| `function_id` | number | No       | 함수 고유 ID |

**Example**

```json
{
  "function_id": 12345
}
```

---

## **1.3. PUT `/functions/{function_id}`**

함수 수정

### **Request**

**Request Type**

| Field            | Type                              | Nullable | Description                       |
| ---------------- | --------------------------------- | -------- | --------------------------------- |
| `name`           | string                            | Yes      | 함수 이름                         |
| `runtime`        | [`Runtime`](#Runtime)             | Yes      | 실행 환경 (`python`, `nodejs` 등) |
| `code`           | string                            | Yes      | 함수 코드                         |
| `execution_type` | [`ExecutionType`](#ExecutionType) | Yes      | 실행 타입 (`sync` 또는 `async`)   |

**Example**

```json
{
  "name": "myUpdatedFunction",
  "runtime": "nodejs",
  "code": "function handler(event) { return event }",
  "execution_type": "async"
}
```

### **Response**

**Response Type**

| Field         | Type   | Nullable | Description  |
| ------------- | ------ | -------- | ------------ |
| `function_id` | number | No       | 함수 고유 ID |

**Example**

```json
{
  "function_id": 12345
}
```

---

## **1.4. GET `/functions/{function_id}`**

함수 정보 조회

### **Request**

**Request Type**

| Field         | Type   | Nullable | Description  |
| ------------- | ------ | -------- | ------------ |
| `function_id` | number | No       | 함수 고유 ID |

**Example**

```json
{
  "function_id": 12345
}
```

### **Response**

**Response Type**

[`Function`](#Function)

**Example**

```json
{
  "id": 12345,
  "name": "myFunction",
  "runtime": "python",
  "code": "def handler(event): return event",
  "execution_type": "sync",
  "created_at": "2023-10-30T10:00:00Z",
  "updated_at": "2023-10-30T10:00:00Z"
}
```

---

## **1.5. DELETE `/functions/{function_id}`**

함수 삭제

### **Request**

**Request Type**

| Field         | Type   | Nullable | Description  |
| ------------- | ------ | -------- | ------------ |
| `function_id` | number | No       | 함수 고유 ID |

**Example**

```json
{
  "function_id": 12345
}
```

### **Response**

No response

---

## **1.6. GET `/functions/{function_id}/metrics`**

함수 메트릭 조회

### **Request**

**Request Type**

| Field         | Type   | Nullable | Description  |
| ------------- | ------ | -------- | ------------ |
| `function_id` | number | No       | 함수 고유 ID |

**Example**

```json
{
  "function_id": 12345
}
```

### **Response**

**Response Type**

| Field                | Type   | Nullable | Description                        |
| -------------------- | ------ | -------- | ---------------------------------- |
| `invocations`        | object | No       | 호출 관련 메트릭 (총 호출 횟수 등) |
| `success_rate`       | number | No       | 함수 성공률                        |
| `avg_execution_time` | string | No       | 평균 실행 시간                     |
| `cpu_usage`          | string | No       | 함수의 CPU 사용량                  |
| `memory_usage`       | string | No       | 함수의 메모리 사용량               |

**Example**

```json
{
  "invocations": {
    "total": 1000,
    "successful": 950,
    "failed": 50
  },
  "success_rate": 95,
  "avg_execution_time": "120ms",
  "cpu_usage": "70%",
  "memory_usage": "256MB"
}
```

---

# 2. **Function Execution API**

## **2.1. POST `/functions/{function_id}/invoke`**

함수 실행 (id 반환)

### **Request**

**Request Type**

| Field    | Type   | Nullable | Description                    |
| -------- | ------ | -------- | ------------------------------ |
| `param1` | string | Yes      | 함수에 전달할 첫 번째 파라미터 |
| `param2` | string | Yes      | 함수에 전달할 두 번째 파라미터 |

**Example**

```json
{
  "param1": "value1",
  "param2": "value2"
}
```

### **Response**

**Response Type**

[`Job`](#Job) 

**Example**

```json
{
  "id": 12345,
  "function_id": 67890,
  "status": "pending",
  "result": null,
  "timestamp": "2023-10-30T10:00:00Z",
  "duration": 452
}
```

---

# 3. **Jobs (Executions) API**

## **3.1. GET `/jobs/{id}`**

실행 결과 조회

### **Request**

**Request Type**

| Field | Type   | Nullable | Description    |
| ----- | ------ | -------- | -------------- |
| `id`  | number | No       | 비동기 작업 ID |

**Example**

```json
{
  "id": 12345
}
```

### **Response**

**Response Type**

[`Job`](#Job) 

**Example**

```json
{
  "id": 12345,
  "function_id": 67890,
  "status": "success",
  "result": {
    "data": "function result"
  },
  "timestamp": "2023-10-30T10:00:00Z",
  "duration": 421
}
```

## **3.2. GET `/functions/{function_id}/jobs`**

실행 기록 조회

### **Request**

**Request Type**

| Field         | Type   | Nullable | Description  |
| ------------- | ------ | -------- | ------------ |
| `function_id` | number | No       | 함수 고유 ID |

**Example**

```json
{
  "function_id": 12345
}
```

### **Response**

**Response Type**

| Field  | Type                  | Nullable | Description |
| ------ | --------------------- | -------- | ----------- |
| `jobs` | Array<[`Job`](#Job) > | No       | 작업 리스트 |

**Example**

```json
{
  "jobs": [
    {
      "id": 12345,
      "function_id": 1,
      "status": "success",
      "timestamp": "2023-10-30T10:00:00Z",
      "result": {
        "data": "function result"
      },
      "duration": 452
    },
    {
      "id": 67890,
      "function_id": 1,
      "status": "failed",
      "timestamp": "2023-10-30T11:00:00Z",
      "result": null,
      "duration": 452
    }
  ]
}
```