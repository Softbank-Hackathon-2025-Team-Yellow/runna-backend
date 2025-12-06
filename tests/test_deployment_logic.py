import json
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.orm import Session

from app.api.functions import deploy_function
from app.models.function import Function, Runtime, DeploymentStatus
from app.models.job import Job, JobStatus
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.function import FunctionDeployRequest

@pytest.mark.asyncio
async def test_deploy_function_sync_logic():
    # Mock dependencies
    mock_db = MagicMock(spec=Session)
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    
    # Mock Function and Workspace
    function_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    
    mock_function = Function(
        id=function_id,
        name="test-function",
        code="print('hello')",
        runtime=Runtime.PYTHON,
        workspace_id=workspace_id,
        endpoint="/test",
        deployment_status=DeploymentStatus.NOT_DEPLOYED
    )
    
    mock_workspace = Workspace(
        id=workspace_id,
        name="test-workspace",
        user_id=mock_current_user.id
    )
    
    # Patch dependencies
    with patch("app.api.functions._validate_function_access") as mock_validate:
        mock_validate.return_value = (True, mock_function, None)
        
        with patch("app.api.functions.WorkspaceService") as MockWorkspaceService:
            mock_ws_service = MockWorkspaceService.return_value
            mock_ws_service.get_workspace_by_id.return_value = mock_workspace
            
            with patch("app.core.static_analysis.analyzer") as mock_analyzer:
                mock_analyzer.analyze_python_code.return_value = {"is_safe": True}
                
                # Mock FunctionService
                with patch("app.services.function_service.FunctionService") as MockFunctionService:
                    mock_func_service = MockFunctionService.return_value
                    
                    expected_result = {
                        "ingress_url": "http://test.url",
                        "service_name": "test-service"
                    }
                    
                    # Mock deploy_function_to_k8s (it's called via asyncio.to_thread)
                    # When patching where it's used might be tricky with to_thread if not careful,
                    # but patching the class method usually works fine.
                    mock_func_service.deploy_function_to_k8s.return_value = expected_result

                    # Call the endpoint
                    deploy_request = FunctionDeployRequest(env_vars={"KEY": "VALUE"})
                    
                    # deploy_function is async
                    response = await deploy_function(
                        function_id=function_id,
                        deploy_request=deploy_request,
                        db=mock_db,
                        current_user=mock_current_user
                    )
                    
                    
                    # Assertions
                    data = response
                    assert data["success"] is True
                    assert data["data"]["status"] == "SUCCESS"
                    assert data["data"]["knative_url"] == "http://test.url"
                    
                    # Verify Job was NOT created
                    # db.add is called for Function metrics or something else? 
                    # Actually we don't expect db.add to be called for Job anymore.
                    # Let's inspect calls to db.add
                    
                    for call in mock_db.add.call_args_list:
                        args, _ = call
                        obj = args[0]
                        # Ensure no Job object is added
                        assert not isinstance(obj, Job)

                    # Check Function updates
                    assert mock_function.deployment_status == DeploymentStatus.DEPLOYED
                    assert mock_function.knative_url == "http://test.url"
                    
                    print("Sync deployment test passed successfully!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_deploy_function_sync_logic())
