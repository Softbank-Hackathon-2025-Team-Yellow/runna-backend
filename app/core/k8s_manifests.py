import uuid
from typing import Dict, List, Optional

from app.config import settings
from app.models.function import Function


class ManifestBuilder:
    """
    Kubernetes manifest 생성 전담 클래스
    
    모든 K8s 리소스의 manifest 생성 로직을 중앙화하여
    테스트와 수정을 용이하게 함
    """

    @staticmethod
    def build_knative_service_manifest(
        function: Function,
        namespace: str,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> Dict:
        """
        KNative Service 매니페스트 생성
        
        Args:
            function: 배포할 함수 객체
            namespace: 배포할 네임스페이스
            env_vars: 추가 환경변수 (선택사항)
            
        Returns:
            KNative Service 매니페스트
            
        Raises:
            ValueError: 지원하지 않는 runtime인 경우
        """
        revision_name = f"{function.name}-{uuid.uuid4().hex[:8]}"

        # Runtime별 Docker 이미지 선택
        if function.runtime == "PYTHON":
            docker_image = settings.k8s_python_image
        elif function.runtime == "NODEJS":
            docker_image = settings.k8s_nodejs_image
        else:
            raise ValueError(f"Unsupported runtime: {function.runtime}")

        # 환경변수 설정
        env_list = [
            {"name": "CODE_CONTENT", "value": function.code},
            {"name": "RUNTIME", "value": function.runtime},
        ]
        if env_vars:
            env_list.extend([{"name": k, "value": v} for k, v in env_vars.items()])

        return {
            "apiVersion": "serving.knative.dev/v1",
            "kind": "Service",
            "metadata": {
                "name": function.name,
                "namespace": namespace,
                "labels": {
                    "app": "runna",
                    "workspace": function.workspace.alias,
                    "function": function.name,
                },
            },
            "spec": {
                "template": {
                    "metadata": {
                        "name": revision_name,
                        "annotations": {
                            "autoscaling.knative.dev/minScale": settings.knative_min_scale,
                            "autoscaling.knative.dev/maxScale": settings.knative_max_scale,
                        },
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": "user-container",
                                "image": docker_image,
                                "resources": {
                                    "requests": {
                                        "cpu": settings.k8s_cpu_request,
                                        "memory": settings.k8s_memory_request,
                                    },
                                    "limits": {
                                        "cpu": settings.k8s_cpu_limit,
                                        "memory": settings.k8s_memory_limit,
                                    },
                                },
                                "env": env_list,
                            }
                        ],
                    },
                },
            },
        }

    @staticmethod
    def build_cluster_domain_claim_manifest(domain: str, namespace: str) -> Dict:
        """
        ClusterDomainClaim 매니페스트 생성
        
        Args:
            domain: 클레임할 도메인 (예: workspace-alias.runna.haifu.cloud)
            namespace: 도메인을 사용할 네임스페이스
            
        Returns:
            ClusterDomainClaim 매니페스트
        """
        return {
            "apiVersion": "networking.internal.knative.dev/v1alpha1",
            "kind": "ClusterDomainClaim",
            "metadata": {"name": domain, "namespace": namespace},
            "spec": {"namespace": namespace},
        }

    @staticmethod
    def build_domain_mapping_manifest(
        domain: str, namespace: str, service_name: str
    ) -> Dict:
        """
        DomainMapping 매니페스트 생성
        
        Args:
            domain: 매핑할 도메인
            namespace: DomainMapping이 생성될 네임스페이스  
            service_name: 연결할 KNative Service 이름
            
        Returns:
            DomainMapping 매니페스트
        """
        return {
            "apiVersion": "serving.knative.dev/v1beta1",
            "kind": "DomainMapping",
            "metadata": {"name": domain, "namespace": namespace},
            "spec": {
                "ref": {
                    "name": service_name,
                    "kind": "Service",
                    "apiVersion": "serving.knative.dev/v1",
                }
            },
        }

    @staticmethod
    def build_http_route_manifest(
        namespace: str,
        hostname: str,
        path: str,
        service_name: str,
        gateway_name: str = "3scale-kourier-gateway",
    ) -> Dict:
        """
        HTTPRoute 매니페스트 생성
        
        Args:
            namespace: HTTPRoute가 생성될 네임스페이스
            hostname: 라우팅할 호스트명 (예: workspace-alias.runna.haifu.cloud)
            path: 라우팅할 경로 (예: /my-function)
            service_name: 백엔드 KNative Service 이름
            gateway_name: Gateway 이름
            
        Returns:
            HTTPRoute 매니페스트
        """
        route_name = f"{service_name}-route"

        return {
            "apiVersion": "gateway.networking.k8s.io/v1beta1",
            "kind": "HTTPRoute",
            "metadata": {"name": route_name, "namespace": namespace},
            "spec": {
                "parentRefs": [{"name": gateway_name}],
                "hostnames": [hostname],
                "rules": [
                    {
                        "matches": [{"path": {"type": "PathPrefix", "value": path}}],
                        "backendRefs": [
                            {
                                "name": service_name,
                                "port": 80,
                            }
                        ],
                    }
                ],
            },
        }

    @staticmethod
    def generate_route_name(service_name: str) -> str:
        """HTTPRoute 이름 생성 헬퍼"""
        return f"{service_name}-route"