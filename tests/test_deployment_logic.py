import uuid
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from app.api.functions import deploy_function
from app.models.function import Function, Runtime, DeploymentStatus
from app.models.job import Job
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.function import FunctionDeployRequest


# ============================================
# Test Fixtures
# ============================================

def create_mock_function(function_id, workspace_id, code="print('hello')", 
                         runtime=Runtime.PYTHON, deployment_status=DeploymentStatus.NOT_DEPLOYED):
    """테스트용 Function Mock 생성"""
    return Function(
        id=function_id,
        name="test-function",
        code=code,
        runtime=runtime,
        workspace_id=workspace_id,
        endpoint="/test",
        deployment_status=deployment_status
    )


def create_mock_workspace(workspace_id, user_id):
    """테스트용 Workspace Mock 생성"""
    return Workspace(
        id=workspace_id,
        name="test-workspace",
        user_id=user_id
    )


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
    workspace_id = uuid.uuid4()
    
    mock_function = create_mock_function(function_id, workspace_id)
    mock_workspace = create_mock_workspace(workspace_id, mock_current_user.id)
    
    with patch("app.api.functions._validate_function_access") as mock_validate:
        mock_validate.return_value = (True, mock_function, None)
        
        with patch("app.api.functions.WorkspaceService") as MockWorkspaceService:
            MockWorkspaceService.return_value.get_workspace_by_id.return_value = mock_workspace
            
            with patch("app.core.static_analysis.analyzer") as mock_analyzer:
                mock_analyzer.analyze_python_code.return_value = {"is_safe": True}
                
                with patch("app.services.function_service.FunctionService") as MockFunctionService:
                    expected_result = {
                        "ingress_url": "http://test.url",
                        "service_name": "test-service"
                    }
                    MockFunctionService.return_value.deploy_function_to_k8s.return_value = expected_result

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
                    
                    # Function 상태 업데이트 검증
                    assert mock_function.deployment_status == DeploymentStatus.DEPLOYED
                    assert mock_function.knative_url == "http://test.url"
                    assert mock_function.last_deployed_at is not None
                    
                    # Job이 생성되지 않음 검증
                    for call in mock_db.add.call_args_list:
                        args, _ = call
                        assert not isinstance(args[0], Job)
                    
                    # db.commit 호출 검증
                    assert mock_db.commit.called


# ============================================
# Failure Case Tests
# ============================================

@pytest.mark.asyncio
async def test_deploy_function_k8s_failure():
    """K8s 배포 실패 시 FAILED 상태로 변경되는지 테스트"""
    mock_db = MagicMock(spec=Session)
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    
    function_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    
    mock_function = create_mock_function(function_id, workspace_id)
    mock_workspace = create_mock_workspace(workspace_id, mock_current_user.id)
    
    with patch("app.api.functions._validate_function_access") as mock_validate:
        mock_validate.return_value = (True, mock_function, None)
        
        with patch("app.api.functions.WorkspaceService") as MockWorkspaceService:
            MockWorkspaceService.return_value.get_workspace_by_id.return_value = mock_workspace
            
            with patch("app.core.static_analysis.analyzer") as mock_analyzer:
                mock_analyzer.analyze_python_code.return_value = {"is_safe": True}
                
                with patch("app.services.function_service.FunctionService") as MockFunctionService:
                    # K8s 배포 실패 시뮬레이션
                    MockFunctionService.return_value.deploy_function_to_k8s.side_effect = Exception("K8s connection failed")

                    response = await deploy_function(
                        function_id=function_id,
                        deploy_request=FunctionDeployRequest(),
                        db=mock_db,
                        current_user=mock_current_user
                    )
                    
                    # 실패 응답 검증
                    assert response["success"] is False
                    assert response["error"]["code"] == "DEPLOYMENT_FAILED"
                    assert "K8s connection failed" in response["error"]["message"]
                    
                    # Function 상태 FAILED로 변경 검증
                    assert mock_function.deployment_status == DeploymentStatus.FAILED
                    assert mock_function.deployment_error is not None


@pytest.mark.asyncio
async def test_deploy_function_empty_code():
    """빈 코드일 때 VALIDATION_ERROR 반환 테스트"""
    mock_db = MagicMock(spec=Session)
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    
    function_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    
    # 빈 코드로 Function 생성
    mock_function = create_mock_function(function_id, workspace_id, code="")
    mock_workspace = create_mock_workspace(workspace_id, mock_current_user.id)
    
    with patch("app.api.functions._validate_function_access") as mock_validate:
        mock_validate.return_value = (True, mock_function, None)
        
        with patch("app.api.functions.WorkspaceService") as MockWorkspaceService:
            MockWorkspaceService.return_value.get_workspace_by_id.return_value = mock_workspace

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
async def test_deploy_function_static_analysis_failure():
    """정적 분석 실패 시 VALIDATION_ERROR 반환 테스트"""
    mock_db = MagicMock(spec=Session)
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    
    function_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    
    # 위험한 코드 (os.system 사용)
    dangerous_code = "import os; os.system('rm -rf /')"
    mock_function = create_mock_function(function_id, workspace_id, code=dangerous_code)
    mock_workspace = create_mock_workspace(workspace_id, mock_current_user.id)
    
    with patch("app.api.functions._validate_function_access") as mock_validate:
        mock_validate.return_value = (True, mock_function, None)
        
        with patch("app.api.functions.WorkspaceService") as MockWorkspaceService:
            MockWorkspaceService.return_value.get_workspace_by_id.return_value = mock_workspace
            
            with patch("app.core.static_analysis.analyzer") as mock_analyzer:
                # 정적 분석 실패 시뮬레이션
                mock_analyzer.analyze_python_code.return_value = {
                    "is_safe": False, 
                    "violations": ["Dangerous system call detected"]
                }

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


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_deploy_function_success())
    asyncio.run(test_deploy_function_k8s_failure())
    asyncio.run(test_deploy_function_empty_code())
    asyncio.run(test_deploy_function_static_analysis_failure())
    asyncio.run(test_deploy_function_access_denied())
    print("All tests passed!")

