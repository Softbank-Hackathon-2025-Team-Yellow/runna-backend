"""
Workspace 및 namespace 이름에 대한 Sanitization 및 검증 유틸리티

Injection 공격에 대한 다층 방어를 제공하고 Kubernetes namespace 호환성을 보장합니다.
"""

import re
from typing import Optional

from sqlalchemy.orm import Session


class SanitizationError(ValueError):
    """Sanitization 또는 검증 실패 시 발생하는 예외"""

    pass


def sanitize_workspace_name(name: str, strict: bool = True) -> str:
    """
    Kubernetes namespace에서 안전하게 사용하기 위해 workspace 이름을 sanitize합니다.

    이 함수는 다음을 통해 심층 방어를 제공합니다:
    1. 잠재적으로 위험한 문자 제거
    2. Kubernetes 네이밍 제약사항 강제
    3. Injection 공격 방지

    Args:
        name: 사용자 입력으로부터 받은 원본 workspace 이름
        strict: True면 유효하지 않은 입력에 대해 오류 발생, False면 수정 시도

    Returns:
        Sanitize된 workspace 이름

    Raises:
        SanitizationError: 이름이 유효하지 않고 strict=True인 경우

    보안 고려사항:
        - Shell metacharacter를 통한 command injection 방지
        - Path traversal 시도 차단 (../)
        - 잠재적 XSS 벡터 제거
        - Kubernetes DNS-1123 label 표준 강제
    """
    if not name:
        raise SanitizationError("Workspace 이름은 비어있을 수 없습니다")

    # 앞뒤 공백 제거
    name = name.strip()

    if not name:
        raise SanitizationError(
            "Workspace 이름은 비어있거나 공백만으로 구성될 수 없습니다"
        )

    # Path traversal 시도 확인
    if ".." in name or "/" in name or "\\" in name:
        raise SanitizationError(
            "Workspace 이름은 경로 탐색 문자(., /, \\)를 포함할 수 없습니다"
        )

    # Null byte 확인 (일반적인 injection 기술)
    if "\0" in name or "\x00" in name:
        raise SanitizationError("Workspace 이름은 null 바이트를 포함할 수 없습니다")

    # 제어 문자 제거 (ASCII 0-31, 127)
    if any(ord(c) < 32 or ord(c) == 127 for c in name):
        if strict:
            raise SanitizationError("Workspace 이름은 제어 문자를 포함할 수 없습니다")
        else:
            name = "".join(c for c in name if ord(c) >= 32 and ord(c) != 127)

    # 하이픈으로 시작하거나 끝나면 안됨
    if name.startswith("-") or name.endswith("-"):
        if strict:
            raise SanitizationError(
                "Workspace 이름은 하이픈으로 시작하거나 끝날 수 없습니다"
            )
        else:
            name = name.strip("-")

    # 길이 제약 (workspace 최대 20자 + UUID 36자 + 하이픈 1자 = 57 < 63)
    if len(name) > 20:
        raise SanitizationError(
            f"Workspace 이름은 20자 이하여야 합니다 (현재 {len(name)}자). "
            "이는 전체 Kubernetes namespace 이름이 63자 제한 내에 유지되도록 보장합니다."
        )

    if len(name) < 1:
        raise SanitizationError(
            "Sanitization 후 workspace 이름은 최소 1자 이상이어야 합니다"
        )

    # Kubernetes 예약 namespace 차단
    reserved_names = {"default", "kube-system", "kube-public", "kube-node-lease"}
    if name in reserved_names:
        raise SanitizationError(
            f"Workspace 이름 '{name}'은(는) Kubernetes에 예약되어 있어 사용할 수 없습니다"
        )

    return name


def validate_namespace_name(namespace: str) -> None:
    """
    Kubernetes namespace 생성 전 최종 검증을 수행합니다.

    이것은 Kubernetes API를 호출하기 전 마지막 방어선입니다.
    NamespaceManager에서 namespace 생성 직전에 호출되어야 합니다.

    Args:
        namespace: 전체 namespace 이름 (workspace-name + function-id)

    Raises:
        SanitizationError: namespace 이름이 유효하지 않은 경우

    보안 고려사항:
        - 전체 namespace 이름 검증 (workspace + function-id)
        - Kubernetes 63자 제한을 초과하지 않도록 보장
        - function_id 조작을 통한 namespace injection 방지
    """
    if not namespace:
        raise SanitizationError("Namespace 이름은 비어있을 수 없습니다")

    # Kubernetes namespace 길이 제한
    if len(namespace) > 63:
        raise SanitizationError(
            f"Namespace 이름이 63자 제한을 초과합니다: '{namespace}' ({len(namespace)}자)"
        )

    # Kubernetes DNS-1123 label 형식과 일치해야 함
    if not re.match(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", namespace):
        raise SanitizationError(
            f"Namespace 이름 '{namespace}'이(가) Kubernetes DNS-1123 label 형식과 일치하지 않습니다. "
            "영숫자로 시작하고 끝나야 하며, 소문자, 숫자, 하이픈만 포함해야 합니다."
        )

    # 추가 보안: 의심스러운 패턴 확인
    # 연속된 하이픈은 injection 시도를 나타낼 수 있음
    if "--" in namespace:
        raise SanitizationError(
            f"Namespace 이름 '{namespace}'에 연속된 하이픈이 포함되어 있어 의심스럽습니다"
        )


def sanitize_function_id(function_id: str) -> str:
    """
    Function UUID를 검증하고 sanitize합니다.

    UUID는 내부적으로 생성되어 안전해야 하지만,
    이 함수는 심층 방어를 위한 추가 검증 계층을 제공합니다.

    Args:
        function_id: Function UUID 문자열

    Returns:
        검증된 UUID 문자열

    Raises:
        SanitizationError: UUID 형식이 유효하지 않은 경우
    """
    if not function_id:
        raise SanitizationError("Function ID는 비어있을 수 없습니다")

    # UUID 형식: 8-4-4-4-12 16진수 문자
    uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"

    function_id = function_id.lower().strip()

    if not re.match(uuid_pattern, function_id):
        raise SanitizationError(
            f"Function ID '{function_id}'은(는) 유효한 UUID 형식이 아닙니다"
        )

    return function_id


def create_workspace_namespace_name(workspace_alias: str, prefix: str = "runna") -> str:
    """
    Workspace alias로부터 안전한 namespace 이름을 생성합니다.

    Args:
        workspace_alias: Workspace 별칭 (이미 sanitize됨)
        prefix: Namespace prefix (기본값: "runna")

    Returns:
        Kubernetes에 사용할 준비가 된 안전한 namespace 이름

    Raises:
        SanitizationError: 입력이 유효하지 않은 경우
    """
    if not workspace_alias:
        raise SanitizationError("Workspace alias는 비어있을 수 없습니다")
    
    if not prefix:
        raise SanitizationError("Prefix는 비어있을 수 없습니다")

    # Namespace 이름 생성
    namespace = f"{prefix}-{workspace_alias}"

    # 최종 검증
    validate_namespace_name(namespace)

    return namespace


def create_safe_namespace_name(workspace_name: str, function_id: str) -> str:
    """
    Workspace와 function ID로부터 안전한 namespace 이름을 생성합니다.
    
    (Deprecated: 이전 아키텍처용. 새로운 아키텍처에서는 create_workspace_namespace_name 사용)

    모든 sanitization 단계를 적용하고 최종 namespace 이름을 생성하는
    편의 함수입니다.

    Args:
        workspace_name: Workspace 이름 (sanitize됨)
        function_id: Function UUID (검증됨)

    Returns:
        Kubernetes에 사용할 준비가 된 안전한 namespace 이름

    Raises:
        SanitizationError: 입력이 유효하지 않은 경우
    """
    # Workspace 이름 sanitize (대소문자 정규화 포함)
    safe_workspace = sanitize_workspace_name(workspace_name.lower(), strict=True)

    # Function ID 검증
    safe_function_id = sanitize_function_id(function_id)

    # Namespace 이름 생성
    namespace = f"{safe_workspace}-{safe_function_id}"

    # 최종 검증
    validate_namespace_name(namespace)

    return namespace


def sanitize_workspace_alias(
    name: str, db: Optional[Session] = None, max_attempts: int = 10
) -> str:
    """
    Workspace name을 기반으로 안전한 alias를 생성합니다.

    alias는 workspace의 불변 식별자로 사용되며, subdomain/namespace 연결에 활용됩니다.
    중복 발생 시 자동으로 suffix를 추가합니다 (예: my-workspace, my-workspace-2, my-workspace-3).

    Args:
        name: 원본 workspace 이름
        db: 중복 검사를 위한 데이터베이스 세션 (선택적)
        max_attempts: 중복 해결을 위한 최대 시도 횟수

    Returns:
        안전한 alias 문자열

    Raises:
        SanitizationError: alias 생성 실패 시
    """
    if not name:
        raise SanitizationError("Workspace 이름은 비어있을 수 없습니다")

    # 1. 기본 정규화
    alias = name.strip().lower()

    # 2. 특수문자를 하이픈으로 변환
    alias = re.sub(r"[^a-z0-9-]", "-", alias)

    # 3. 연속된 하이픈 제거
    alias = re.sub(r"-+", "-", alias)

    # 4. 앞뒤 하이픈 제거
    alias = alias.strip("-")

    # 5. 최대 20자 제한
    if len(alias) > 20:
        alias = alias[:20].rstrip("-")

    # 6. 최소 1자 검증
    if len(alias) < 1:
        raise SanitizationError("Sanitization 후 alias가 비어있습니다")

    # 7. 예약어 검증
    reserved_names = {"default", "kube-system", "kube-public", "kube-node-lease"}
    if alias in reserved_names:
        alias = f"{alias}-ws"  # workspace suffix 추가

    # 8. 중복 검사 및 해결 (db가 제공된 경우)
    if db:
        from app.models.workspace import Workspace

        base_alias = alias
        for attempt in range(1, max_attempts + 1):
            existing = db.query(Workspace).filter(Workspace.alias == alias).first()
            if not existing:
                break

            # 중복 발생 시 suffix 추가
            suffix = f"-{attempt + 1}"
            max_base_length = 20 - len(suffix)
            alias = f"{base_alias[:max_base_length]}{suffix}"
        else:
            raise SanitizationError(
                f"'{base_alias}' 기반으로 unique한 alias를 생성할 수 없습니다 "
                f"({max_attempts}번 시도)"
            )

    return alias


def sanitize_function_endpoint(
    name: str, workspace_id=None, db: Optional[Session] = None, max_attempts: int = 10
) -> str:
    """
    Function name을 기반으로 안전한 endpoint를 생성합니다.

    endpoint는 Function 호출을 위한 URL 경로입니다 (예: /my-function).
    중복 발생 시 자동으로 suffix를 추가합니다.

    Args:
        name: 원본 function 이름
        workspace_id: Workspace ID (workspace 내 중복 검사용, 선택적)
        db: 중복 검사를 위한 데이터베이스 세션 (선택적)
        max_attempts: 중복 해결을 위한 최대 시도 횟수

    Returns:
        안전한 endpoint 문자열 (/ 포함)

    Raises:
        SanitizationError: endpoint 생성 실패 시
    """
    if not name:
        raise SanitizationError("Function 이름은 비어있을 수 없습니다")

    # 1. 기본 정규화
    endpoint = name.strip().lower()

    # 2. 특수문자를 하이픈으로 변환
    endpoint = re.sub(r"[^a-z0-9-/]", "-", endpoint)

    # 3. 연속된 하이픈/슬래시 제거
    endpoint = re.sub(r"-+", "-", endpoint)
    endpoint = re.sub(r"/+", "/", endpoint)

    # 4. 앞뒤 하이픈/슬래시 제거
    endpoint = endpoint.strip("-").strip("/")

    # 5. 최대 99자 제한 (/ prefix를 위해 1자 남김)
    if len(endpoint) > 99:
        endpoint = endpoint[:99].rstrip("-")

    # 6. 최소 1자 검증
    if len(endpoint) < 1:
        raise SanitizationError("Sanitization 후 endpoint가 비어있습니다")

    # 7. / prefix 추가
    endpoint = f"/{endpoint}"

    # 8. 중복 검사 및 해결 (db가 제공된 경우)
    if db:
        from app.models.function import Function

        base_endpoint = endpoint
        for attempt in range(1, max_attempts + 1):
            # Workspace 내 중복 검사
            if workspace_id:
                existing = (
                    db.query(Function)
                    .filter(
                        Function.workspace_id == workspace_id,
                        Function.endpoint == endpoint,
                    )
                    .first()
                )
            else:
                # workspace_id가 없으면 전역 검사 (하위 호환성)
                existing = (
                    db.query(Function).filter(Function.endpoint == endpoint).first()
                )

            if not existing:
                break

            # 중복 발생 시 suffix 추가
            suffix = f"-{attempt + 1}"
            max_base_length = 99 - len(suffix)
            # / 제거 후 base 추출
            base_without_slash = base_endpoint[1:]
            endpoint = f"/{base_without_slash[:max_base_length]}{suffix}"
        else:
            raise SanitizationError(
                f"'{base_endpoint}' 기반으로 unique한 endpoint를 생성할 수 없습니다 "
                f"({max_attempts}번 시도)"
            )

    return endpoint


def validate_custom_endpoint(endpoint: str) -> str:
    """
    사용자가 직접 입력한 custom endpoint를 검증합니다.

    Args:
        endpoint: 사용자 입력 endpoint

    Returns:
        검증된 endpoint

    Raises:
        SanitizationError: endpoint가 유효하지 않은 경우
    """
    if not endpoint:
        raise SanitizationError("Endpoint는 비어있을 수 없습니다")

    endpoint = endpoint.strip()

    if not endpoint:
        raise SanitizationError("Endpoint는 비어있을 수 없습니다")

    if not endpoint.startswith("/"):
        raise SanitizationError("Endpoint는 /로 시작해야 합니다")

    if len(endpoint) > 100:
        raise SanitizationError(
            f"Endpoint는 100자 이하여야 합니다 (현재 {len(endpoint)}자)"
        )

    # URL-safe 문자만 허용
    if not re.match(r"^/[a-z0-9/-]+$", endpoint):
        raise SanitizationError(
            "Endpoint는 소문자, 숫자, 하이픈, 슬래시만 포함해야 합니다"
        )

    # 연속된 하이픈 불가
    if "--" in endpoint:
        raise SanitizationError("Endpoint는 연속된 하이픈을 포함할 수 없습니다")

    # 연속된 슬래시 불가
    if "//" in endpoint:
        raise SanitizationError("Endpoint는 연속된 슬래시를 포함할 수 없습니다")

    # 하이픈으로 끝나면 안됨
    if endpoint.endswith("-"):
        raise SanitizationError("Endpoint는 하이픈으로 끝날 수 없습니다")

    # 슬래시로만 구성되면 안됨
    if endpoint == "/":
        raise SanitizationError("Endpoint는 /만으로 구성될 수 없습니다")

    return endpoint
