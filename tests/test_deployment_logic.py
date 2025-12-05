import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.api.functions import deploy_function
from app.models.function import Function, Runtime, DeploymentStatus
from app.models.job import Job, JobStatus, JobType
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.function import FunctionDeployRequest

def test_deploy_function_async_logic():
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
    
    # Setup DB queries
    # 1. Validate function access (User -> Workspace -> Function)
    # We need to mock _validate_function_access or the query chain
    # Let's mock _validate_function_access directly if possible, or setup the query chain
    
    # Mocking the query chain for _validate_function_access and workspace check
    # This is complex, so let's patch _validate_function_access instead
    
    with patch("app.api.functions._validate_function_access") as mock_validate:
        mock_validate.return_value = (True, mock_function, None)
        
        with patch("app.api.functions.WorkspaceService") as MockWorkspaceService:
            mock_ws_service = MockWorkspaceService.return_value
            mock_ws_service.get_workspace_by_id.return_value = mock_workspace
            
            with patch("app.core.static_analysis.analyzer") as mock_analyzer:
                mock_analyzer.analyze_python_code.return_value = {"is_safe": True}
                
                # DeploymentClient is imported in app.api.functions, so we can patch it there
                # OR patch where it is defined
                with patch("app.api.functions.DeploymentClient") as MockDeploymentClient:
                    mock_client_instance = MockDeploymentClient.return_value
                    mock_client_instance.deployment_futures = {}
                    # Mock deploy_async as an async function
                    mock_client_instance.deploy_async = AsyncMock()
                    
                    # Call the endpoint
                    deploy_request = FunctionDeployRequest(env_vars={"KEY": "VALUE"})
                    
                    # We need to await if it's async, but deploy_function is defined as async def now
                    # So we need to run this test as async
                    import asyncio
                    
                    response = asyncio.run(deploy_function(
                        function_id=function_id,
                        deploy_request=deploy_request,
                        db=mock_db,
                        current_user=mock_current_user
                    ))
                    
                    # Assertions
                    # deploy_function returns a dict (create_success_response), not a Response object
                    # FastAPI handles the conversion to JSONResponse
                    data = response
                    assert data["success"] is True
                    assert data["data"]["status"] == "PENDING"
                    assert "job_id" in data["data"]
                    
                    # Verify Job creation
                    # mock_db.add.assert_called() # Job is added
                    # We can check the arguments passed to db.add
                    added_job = mock_db.add.call_args[0][0]
                    assert isinstance(added_job, Job)
                    assert added_job.function_id == function_id
                    assert added_job.job_type == JobType.DEPLOYMENT
                    assert added_job.status == JobStatus.PENDING
                    
                    # Verify asyncio.create_task was called (indirectly via DeploymentClient)
                    # Since we can't easily mock asyncio.create_task, we just verify the job was created
                    # The actual task execution will be tested in integration tests
                    
                    print("Test passed successfully!")

def test_deployment_client_async_logic():
    # Mock dependencies
    mock_db = MagicMock(spec=Session)
    
    # Mock Job and Function
    job_id = 123
    function_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    
    mock_job = Job(
        id=job_id,
        function_id=function_id,
        job_type=JobType.DEPLOYMENT,
        status=JobStatus.PENDING
    )
    
    mock_function = Function(
        id=function_id,
        name="test-function",
        workspace_id=workspace_id,
        deployment_status=DeploymentStatus.NOT_DEPLOYED
    )
    
    mock_workspace = Workspace(
        id=workspace_id,
        name="test-workspace"
    )
    
    # Setup DB queries
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        mock_job,       # 0. Job query
        mock_function,  # 1. Function query
    ]
    
    # Mock DeploymentClient
    # We need to import it inside the test or patch it
    from app.infra.deployment_client import DeploymentClient
    
    # Reset singleton for testing
    DeploymentClient._instance = None
    DeploymentClient._initialized = False
    client = DeploymentClient()
    
    # Create a Future for tracking
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    future = loop.create_future()
    client.deployment_futures[job_id] = future
    
    # Mock FunctionService
    with patch("app.services.function_service.FunctionService") as MockFunctionService:
        mock_service = MockFunctionService.return_value
        expected_result = {
            "namespace": "test-ns",
            "service_name": "test-svc",
            "ingress_url": "http://test.url"
        }
        mock_service.deploy_function_to_k8s.return_value = expected_result
        
        # Mock SessionLocal in deployment_client
        with patch("app.database.SessionLocal") as MockSessionLocal:
            MockSessionLocal.return_value = mock_db
            
            # Run deploy_async
            asyncio.run(client.deploy_async(
                job_id=job_id,
                function_id=function_id,
                custom_path="/test",
                env_vars={}
            ))
        
        # Assertions
        # 1. Job status updated to SUCCESS
        assert mock_job.status == JobStatus.SUCCESS
        assert json.loads(mock_job.result) == expected_result
        
        # 2. Function status updated
        assert mock_function.deployment_status == DeploymentStatus.DEPLOYED
        assert mock_function.knative_url == "http://test.url"
        assert mock_function.last_deployed_at is not None
        
        # 3. Future result set
        assert future.done()
        assert future.result()["status"] == "success"
        assert future.result()["result"] == expected_result
        
        # 4. FunctionService called
        mock_service.deploy_function_to_k8s.assert_called_once()
        
        # 5. DB closed
        mock_db.close.assert_called_once()
        
        print("DeploymentClient logic test passed successfully!")

if __name__ == "__main__":
    test_deploy_function_async_logic()
    test_deployment_client_async_logic()
