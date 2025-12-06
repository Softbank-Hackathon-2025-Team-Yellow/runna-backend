import uuid
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from app.api.functions import deploy_function
from app.models.function import DeploymentStatus
from app.models.user import User
from app.schemas.function import FunctionDeployRequest
from app.services.k8s_service import K8sServiceError


# ============================================
# Success Case Tests
# ============================================

@pytest.mark.asyncio
async def test_deploy_function_success():
    """배포 성공 시 SUCCESS 상태와 knative_url 반환 테스트"""
    mock_db = MagicMock(spec=Session)
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    
    function_id = uuid.uuid4()
    mock_function = MagicMock()
    
    with patch("app.api.functions._validate_function_access") as mock_validate:
        mock_validate.return_value = (True, mock_function, None)
        
        with patch("app.api.functions.FunctionService") as MockFunctionService:
            # FunctionService.deploy() mock
            expected_result = {
                "status": "SUCCESS",
                "knative_url": "http://test.url",
                "message": "Deployment successful"
            }
            MockFunctionService.return_value.deploy.return_value = expected_result

            response = await deploy_function(
                function_id=function_id,
                deploy_request=FunctionDeployRequest(env_vars={"KEY": "VALUE"}),
                db=mock_db,
                current_user=mock_current_user
            )
            
            # 성공 응답 검증
            assert response["success"] is True
            assert response["data"]["status"] == "SUCCESS"
            assert response["data"]["knative_url"] == "http://test.url"
            
            # deploy() 호출 검증
            MockFunctionService.return_value.deploy.assert_called_once_with(
                function_id=function_id,
                env_vars={"KEY": "VALUE"}
            )


# ============================================
# Failure Case Tests
# ============================================

@pytest.mark.asyncio
async def test_deploy_function_k8s_failure():
    """K8s 배포 실패 시 DEPLOYMENT_FAILED 반환 테스트"""
    mock_db = MagicMock(spec=Session)
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    
    function_id = uuid.uuid4()
    mock_function = MagicMock()
    
    with patch("app.api.functions._validate_function_access") as mock_validate:
        mock_validate.return_value = (True, mock_function, None)
        
        with patch("app.api.functions.FunctionService") as MockFunctionService:
            # K8s 배포 실패 시뮬레이션
            MockFunctionService.return_value.deploy.side_effect = K8sServiceError("K8s connection failed")

            response = await deploy_function(
                function_id=function_id,
                deploy_request=FunctionDeployRequest(),
                db=mock_db,
                current_user=mock_current_user
            )
            
            # 실패 응답 검증
            assert response["success"] is False
            assert response["error"]["code"] == "DEPLOYMENT_FAILED"


@pytest.mark.asyncio
async def test_deploy_function_validation_error():
    """유효성 검증 실패 시 VALIDATION_ERROR 반환 테스트"""
    mock_db = MagicMock(spec=Session)
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    
    function_id = uuid.uuid4()
    mock_function = MagicMock()
    
    with patch("app.api.functions._validate_function_access") as mock_validate:
        mock_validate.return_value = (True, mock_function, None)
        
        with patch("app.api.functions.FunctionService") as MockFunctionService:
            # 코드 비어있음 에러
            MockFunctionService.return_value.deploy.side_effect = ValueError("Function code is empty")

            response = await deploy_function(
                function_id=function_id,
                deploy_request=FunctionDeployRequest(),
                db=mock_db,
                current_user=mock_current_user
            )
            
            # 유효성 검증 실패 응답 검증
            assert response["success"] is False
            assert response["error"]["code"] == "VALIDATION_ERROR"
            assert "empty" in response["error"]["message"].lower()


@pytest.mark.asyncio
async def test_deploy_function_access_denied():
    """권한 없는 사용자의 배포 요청 시 ACCESS_DENIED 반환 테스트"""
    mock_db = MagicMock(spec=Session)
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    
    function_id = uuid.uuid4()
    
    with patch("app.api.functions._validate_function_access") as mock_validate:
        # 권한 없음 시뮬레이션
        mock_validate.return_value = (False, None, "You don't have permission")

        response = await deploy_function(
            function_id=function_id,
            deploy_request=FunctionDeployRequest(),
            db=mock_db,
            current_user=mock_current_user
        )
        
        # 권한 거부 응답 검증
        assert response["success"] is False
        assert response["error"]["code"] == "ACCESS_DENIED"


@pytest.mark.asyncio
async def test_deploy_function_static_analysis_failure():
    """정적 분석 실패 시 VALIDATION_ERROR 반환 테스트"""
    mock_db = MagicMock(spec=Session)
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    
    function_id = uuid.uuid4()
    mock_function = MagicMock()
    
    with patch("app.api.functions._validate_function_access") as mock_validate:
        mock_validate.return_value = (True, mock_function, None)
        
        with patch("app.api.functions.FunctionService") as MockFunctionService:
            # 정적 분석 실패
            MockFunctionService.return_value.deploy.side_effect = ValueError(
                "Code validation failed: Dangerous system call detected"
            )

            response = await deploy_function(
                function_id=function_id,
                deploy_request=FunctionDeployRequest(),
                db=mock_db,
                current_user=mock_current_user
            )
            
            # 유효성 검증 실패 응답 검증
            assert response["success"] is False
            assert response["error"]["code"] == "VALIDATION_ERROR"
            assert "validation failed" in response["error"]["message"].lower()


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_deploy_function_success())
    asyncio.run(test_deploy_function_k8s_failure())
    asyncio.run(test_deploy_function_validation_error())
    asyncio.run(test_deploy_function_access_denied())
    asyncio.run(test_deploy_function_static_analysis_failure())
    print("All tests passed!")


