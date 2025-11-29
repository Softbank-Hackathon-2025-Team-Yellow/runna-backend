# Common API Response Types

모든 API 응답은 일관된 구조를 가지며, 성공과 실패를 명확히 구분할 수 있도록 설계되었습니다.

## 기본 구조

### `CommonApiResponse<T>`

모든 API 응답의 기본 구조입니다.

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

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | 요청 성공 여부 |
| `data` | T | 성공 시 반환되는 데이터 (optional) |
| `message` | string | 추가 메시지 (optional) |
| `error` | object | 실패 시 오류 정보 (optional) |

### `SuccessResponse<T>`

성공 응답의 구조입니다.

```typescript
type SuccessResponse<T = any> = CommonApiResponse<T> & {
  success: true;
  data: T;
}
```

### `ErrorResponse`

실패 응답의 구조입니다.

```typescript
type ErrorResponse = CommonApiResponse<never> & {
  success: false;
  error: {
    code: string;
    message: string;
    details?: any;
  };
}
```

## 응답 예시

### 성공 응답

```json
{
  "success": true,
  "data": {
    "function_id": 12345
  }
}
```

```json
{
  "success": true,
  "data": {
    "functions": [
      {
        "name": "myFunction",
        "runtime": "python",
        "code": "def handler(event): return event",
        "execution_type": "sync"
      }
    ]
  }
}
```


### 실패 응답

```json
{
  "success": false,
  "error": {
    "code": "FUNCTION_NOT_FOUND",
    "message": "Function with id 12345 not found"
  }
}
```

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid function parameters",
    "details": {
      "field": "runtime",
      "reason": "Must be one of: python, nodejs"
    }
  }
}
```

## 에러 코드

### 일반적인 에러 코드

| Code | Description |
|------|-------------|
| `VALIDATION_ERROR` | 요청 데이터 유효성 검사 실패 |
| `NOT_FOUND` | 요청한 리소스를 찾을 수 없음 |
| `FUNCTION_NOT_FOUND` | 함수를 찾을 수 없음 |
| `JOB_NOT_FOUND` | 작업을 찾을 수 없음 |
| `EXECUTION_ERROR` | 함수 실행 중 오류 발생 |
| `INTERNAL_ERROR` | 서버 내부 오류 |
| `RATE_LIMIT_EXCEEDED` | 요청 빈도 제한 초과 |

### HTTP 상태 코드

- `200 OK`: 성공
- `400 Bad Request`: 잘못된 요청 (VALIDATION_ERROR)
- `404 Not Found`: 리소스를 찾을 수 없음 (NOT_FOUND, FUNCTION_NOT_FOUND, JOB_NOT_FOUND)
- `429 Too Many Requests`: 요청 빈도 제한 초과 (RATE_LIMIT_EXCEEDED)
- `500 Internal Server Error`: 서버 내부 오류 (INTERNAL_ERROR, EXECUTION_ERROR)