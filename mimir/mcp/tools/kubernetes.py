from typing import Any

import kr8s.asyncio
from kr8s.objects import Pod

from mimir.logger import logger
from mimir.mcp.app import mcp
from mimir.mcp.decorators import require_approval


@mcp.tool()
async def list_pods(namespace: str = "default") -> list[dict[str, Any]]:
    """List all pods in a namespace."""
    logger.info("list_pods", namespace=namespace)
    return [
        {
            "name": pod.name,
            "namespace": pod.namespace,
            "status": pod.status.phase,
            "ready": all(cs.ready for cs in (pod.status.containerStatuses or [])),
            "restarts": sum(
                cs.restartCount for cs in (pod.status.containerStatuses or [])
            ),
            "node": pod.spec.nodeName,
        }
        async for pod in kr8s.asyncio.get("pods", namespace=namespace)
    ]


@mcp.tool()
async def list_deployments(namespace: str = "default") -> list[dict[str, Any]]:
    """List all deployments in a namespace."""
    logger.info("list_deployments", namespace=namespace)
    return [
        {
            "name": d.name,
            "namespace": d.namespace,
            "replicas": d.spec.replicas,
            "ready_replicas": d.status.readyReplicas or 0,
            "available_replicas": d.status.availableReplicas or 0,
        }
        async for d in kr8s.asyncio.get("deployments", namespace=namespace)
    ]


@mcp.tool()
async def list_services(namespace: str = "default") -> list[dict[str, Any]]:
    """List all services in a namespace."""
    logger.info("list_services", namespace=namespace)
    return [
        {
            "name": svc.name,
            "namespace": svc.namespace,
            "type": svc.spec.type,
            "cluster_ip": svc.spec.clusterIP,
            "ports": [
                {
                    "port": p.port,
                    "protocol": p.protocol,
                    "target_port": str(p.targetPort),
                }
                for p in (svc.spec.ports or [])
            ],
        }
        async for svc in kr8s.asyncio.get("services", namespace=namespace)
    ]


@mcp.tool()
async def list_namespaces() -> list[dict[str, Any]]:
    """List all namespaces in the cluster."""
    logger.info("list_namespaces")
    return [
        {
            "name": ns.name,
            "status": ns.status.phase,
        }
        async for ns in kr8s.asyncio.get("namespaces")
    ]


@mcp.tool()
async def get_pod_logs(
    name: str,
    namespace: str = "default",
    container: str | None = None,
    tail_lines: int = 100,
) -> str:
    """Get logs from a pod. Returns the last tail_lines lines."""
    logger.info(
        "get_pod_logs",
        name=name,
        namespace=namespace,
        container=container,
        tail_lines=tail_lines,
    )
    pods = [pod async for pod in kr8s.asyncio.get("pods", name, namespace=namespace)]
    if len(pods) == 0:
        raise ValueError(f"Pod {name} not found in namespace {namespace}")

    pod = pods[0]
    kwargs: dict[str, Any] = {"tail_lines": tail_lines}
    if container:
        kwargs["container"] = container
    lines = []
    async for line in pod.logs(**kwargs):
        lines.append(line)
    return "\n".join(lines)


_RESOURCE_KIND_MAP = {
    "pod": "pods",
    "pods": "pods",
    "deployment": "deployments",
    "deployments": "deployments",
    "service": "services",
    "services": "services",
    "node": "nodes",
    "nodes": "nodes",
    "namespace": "namespaces",
    "namespaces": "namespaces",
    "configmap": "configmaps",
    "configmaps": "configmaps",
    "replicaset": "replicasets",
    "replicasets": "replicasets",
    "statefulset": "statefulsets",
    "statefulsets": "statefulsets",
    "daemonset": "daemonsets",
    "daemonsets": "daemonsets",
}


@mcp.tool()
async def describe_resource(
    kind: str,
    name: str,
    namespace: str = "default",
) -> dict[str, Any]:
    """Describe a Kubernetes resource and return its full spec and status."""
    logger.info("describe_resource", kind=kind, name=name, namespace=namespace)
    normalized = _RESOURCE_KIND_MAP.get(kind.lower(), kind.lower())
    resources = [
        r async for r in kr8s.asyncio.get(normalized, name, namespace=namespace)
    ]
    if len(resources) == 0:
        raise ValueError(
            f"{kind} {name} not found in namespace {namespace} (tried resource type '{normalized}')"
        )

    resource = resources[0]
    return resource.raw


@mcp.tool()
@require_approval
async def deploy_pod(
    name: str,
    image: str,
    namespace: str = "default",
    labels: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Deploy a pod with the given name and image. Returns the created pod's metadata."""
    logger.info("deploy_pod", name=name, image=image, namespace=namespace)
    pod = Pod.gen(name=name, image=image, namespace=namespace, labels=labels or {})
    pod.create()
    return {
        "name": pod.name,
        "namespace": pod.namespace,
        "uid": pod.metadata.uid,
        "image": image,
    }


@mcp.tool()
async def list_nodes() -> list[dict[str, Any]]:
    """List all nodes in the cluster."""
    logger.info("list_nodes")
    return [
        {
            "name": node.name,
            "ready": next(
                (c.status for c in (node.status.conditions or []) if c.type == "Ready"),
                "Unknown",
            ),
            "roles": [
                label.split("/")[1]
                for label in (node.metadata.labels or {})
                if label.startswith("node-role.kubernetes.io/")
            ],
            "version": node.status.nodeInfo.kubeletVersion,
        }
        async for node in kr8s.asyncio.get("nodes")
    ]
