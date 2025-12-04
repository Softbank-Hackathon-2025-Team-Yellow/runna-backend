try:
    config.load_kube_config()
    print("✅ Loaded Kube Config")
except:
    config.load_incluster_config()
    print("✅ Loaded In-Cluster Config")

k8s_custom = client.CustomObjectsApi()

knative_manifest = {
    "apiVersion": "serving.knative.dev/v1",
    "kind": "Service",
    "metadata": {
        "name": func_name,
        "namespace": namespace,
        # [1] 메타데이터 라벨링
        "labels": {},
    },
    "spec": {
        "template": {
            "metadata": {
                "name": rev_name,
                "annotations": {
                    # [2] 오토스케일링 설정
                    "autoscaling.knative.dev/minScale": "1",
                    "autoscaling.knative.dev/maxScale": "10",
                },
            },
            "spec": {
                "containers": [
                    {
                        "name": "user-container",
                        "image": f"docker.io/{docker_id}/python-runner:v1",
                        "resources": {
                            "requests": {"cpu": "100m", "memory": "128Mi"},
                            "limits": {"cpu": "500m", "memory": "256Mi"},
                        },
                        # [5] 환경변수 (Inline Code)
                        "env": [
                            # 인자로 받은 코드를 여기에 넣습니다.
                            {"name": "CODE_CONTENT", "value": code_content},
                            # (필요시) API Key 등 추가
                            {"name": "SERVICE_API_KEY", "value": "secret-123"},
                        ],
                    }
                ],
            },
        },
    },
}

# --- 3. K8s API 호출 ---
group = "serving.knative.dev"
version = "v1"
plural = "services"

response = k8s_custom.create_namespaced_custom_object(
    group=group,
    version=version,
    namespace=namespace,
    plural=plural,
    body=knative_manifest,
)
