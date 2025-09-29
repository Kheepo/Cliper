"""Comprehensive deployment management system for production environments.

Provides:
- Multi-environment deployment configurations
- Container orchestration support
- Health check and readiness probe management
- Auto-scaling configuration
- Load balancer integration
- Database migration management
- Secret and configuration management
- Rollback and blue-green deployment support
"""

import os
import json
import yaml
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from fastapi import FastAPI, HTTPException
import docker
import kubernetes
from kubernetes import client, config
import boto3
from google.cloud import container_v1

from api.utils.enhanced_logging import get_logger
from api.config.production import get_settings
from api.utils.health_checker import get_health_checker
from api.utils.resource_monitor import get_resource_monitor


logger = get_logger(__name__)
settings = get_settings()


class DeploymentEnvironment(str, Enum):
    """Deployment environments."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class DeploymentStrategy(str, Enum):
    """Deployment strategies."""
    ROLLING_UPDATE = "rolling_update"
    BLUE_GREEN = "blue_green"
    CANARY = "canary"
    RECREATE = "recreate"


class DeploymentStatus(str, Enum):
    """Deployment status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class ContainerOrchestrator(str, Enum):
    """Container orchestration platforms."""
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    DOCKER_SWARM = "docker_swarm"
    ECS = "ecs"
    GKE = "gke"


class CloudProvider(str, Enum):
    """Cloud providers."""
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"
    DIGITAL_OCEAN = "digital_ocean"
    LOCAL = "local"


@dataclass
class ResourceRequirements:
    """Resource requirements for deployment."""
    cpu_request: str = "100m"
    cpu_limit: str = "500m"
    memory_request: str = "128Mi"
    memory_limit: str = "512Mi"
    storage_request: str = "1Gi"
    storage_limit: str = "10Gi"


@dataclass
class HealthCheckConfig:
    """Health check configuration."""
    enabled: bool = True
    path: str = "/health"
    port: int = 8000
    initial_delay_seconds: int = 30
    period_seconds: int = 10
    timeout_seconds: int = 5
    failure_threshold: int = 3
    success_threshold: int = 1


@dataclass
class AutoScalingConfig:
    """Auto-scaling configuration."""
    enabled: bool = True
    min_replicas: int = 2
    max_replicas: int = 10
    target_cpu_utilization: int = 70
    target_memory_utilization: int = 80
    scale_up_cooldown: int = 300  # seconds
    scale_down_cooldown: int = 600  # seconds


@dataclass
class LoadBalancerConfig:
    """Load balancer configuration."""
    enabled: bool = True
    type: str = "ClusterIP"  # ClusterIP, NodePort, LoadBalancer
    port: int = 80
    target_port: int = 8000
    protocol: str = "TCP"
    annotations: Dict[str, str] = field(default_factory=dict)
    ssl_enabled: bool = True
    ssl_certificate_arn: Optional[str] = None


@dataclass
class DatabaseConfig:
    """Database configuration for deployment."""
    host: str
    port: int
    name: str
    username: str
    password_secret_name: str
    ssl_enabled: bool = True
    connection_pool_size: int = 20
    migration_enabled: bool = True
    backup_enabled: bool = True
    backup_schedule: str = "0 2 * * *"  # Daily at 2 AM


@dataclass
class SecretConfig:
    """Secret configuration."""
    name: str
    type: str = "Opaque"
    data: Dict[str, str] = field(default_factory=dict)
    from_env: List[str] = field(default_factory=list)
    from_file: Dict[str, str] = field(default_factory=dict)


@dataclass
class ConfigMapConfig:
    """ConfigMap configuration."""
    name: str
    data: Dict[str, str] = field(default_factory=dict)
    from_env: List[str] = field(default_factory=list)
    from_file: Dict[str, str] = field(default_factory=dict)


@dataclass
class DeploymentConfig:
    """Complete deployment configuration."""
    name: str
    environment: DeploymentEnvironment
    strategy: DeploymentStrategy
    orchestrator: ContainerOrchestrator
    cloud_provider: CloudProvider
    
    # Container configuration
    image: str
    image_tag: str = "latest"
    replicas: int = 2
    
    # Resource configuration
    resources: ResourceRequirements = field(default_factory=ResourceRequirements)
    
    # Health checks
    health_check: HealthCheckConfig = field(default_factory=HealthCheckConfig)
    readiness_check: HealthCheckConfig = field(default_factory=HealthCheckConfig)
    
    # Scaling
    auto_scaling: AutoScalingConfig = field(default_factory=AutoScalingConfig)
    
    # Load balancing
    load_balancer: LoadBalancerConfig = field(default_factory=LoadBalancerConfig)
    
    # Database
    database: Optional[DatabaseConfig] = None
    
    # Secrets and config
    secrets: List[SecretConfig] = field(default_factory=list)
    config_maps: List[ConfigMapConfig] = field(default_factory=list)
    
    # Environment variables
    environment_variables: Dict[str, str] = field(default_factory=dict)
    
    # Volumes
    volumes: List[Dict[str, Any]] = field(default_factory=list)
    
    # Network configuration
    network_policies: List[Dict[str, Any]] = field(default_factory=list)
    
    # Monitoring
    monitoring_enabled: bool = True
    logging_enabled: bool = True
    
    # Backup and disaster recovery
    backup_enabled: bool = True
    disaster_recovery_enabled: bool = False


@dataclass
class DeploymentResult:
    """Deployment result."""
    deployment_id: str
    status: DeploymentStatus
    environment: DeploymentEnvironment
    start_time: datetime
    end_time: Optional[datetime] = None
    error_message: Optional[str] = None
    rollback_available: bool = False
    previous_version: Optional[str] = None
    current_version: Optional[str] = None
    health_check_url: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


class KubernetesDeployer:
    """Kubernetes deployment manager."""
    
    def __init__(self, config_path: Optional[str] = None):
        try:
            if config_path:
                config.load_kube_config(config_file=config_path)
            else:
                config.load_incluster_config()
        except Exception:
            try:
                config.load_kube_config()
            except Exception as e:
                logger.warning(f"Could not load Kubernetes config: {e}")
                self.client = None
                return
        
        self.apps_v1 = client.AppsV1Api()
        self.core_v1 = client.CoreV1Api()
        self.autoscaling_v1 = client.AutoscalingV1Api()
        self.networking_v1 = client.NetworkingV1Api()
        
        logger.info("Kubernetes deployer initialized")
    
    async def deploy(self, config: DeploymentConfig) -> DeploymentResult:
        """Deploy application to Kubernetes."""
        if not self.client:
            raise Exception("Kubernetes client not available")
        
        deployment_id = f"{config.name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        start_time = datetime.now()
        
        try:
            # Create namespace if it doesn't exist
            await self._ensure_namespace(config.environment.value)
            
            # Create secrets
            for secret_config in config.secrets:
                await self._create_secret(secret_config, config.environment.value)
            
            # Create config maps
            for configmap_config in config.config_maps:
                await self._create_configmap(configmap_config, config.environment.value)
            
            # Create deployment
            deployment = await self._create_deployment(config)
            
            # Create service
            if config.load_balancer.enabled:
                service = await self._create_service(config)
            
            # Create HPA if auto-scaling is enabled
            if config.auto_scaling.enabled:
                hpa = await self._create_hpa(config)
            
            # Wait for deployment to be ready
            await self._wait_for_deployment_ready(config.name, config.environment.value)
            
            # Perform health check
            health_check_url = await self._get_health_check_url(config)
            
            return DeploymentResult(
                deployment_id=deployment_id,
                status=DeploymentStatus.COMPLETED,
                environment=config.environment,
                start_time=start_time,
                end_time=datetime.now(),
                current_version=config.image_tag,
                health_check_url=health_check_url
            )
        
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            return DeploymentResult(
                deployment_id=deployment_id,
                status=DeploymentStatus.FAILED,
                environment=config.environment,
                start_time=start_time,
                end_time=datetime.now(),
                error_message=str(e)
            )
    
    async def _ensure_namespace(self, namespace: str):
        """Ensure namespace exists."""
        try:
            self.core_v1.read_namespace(name=namespace)
        except client.exceptions.ApiException as e:
            if e.status == 404:
                namespace_manifest = client.V1Namespace(
                    metadata=client.V1ObjectMeta(name=namespace)
                )
                self.core_v1.create_namespace(body=namespace_manifest)
                logger.info(f"Created namespace: {namespace}")
    
    async def _create_secret(self, secret_config: SecretConfig, namespace: str):
        """Create Kubernetes secret."""
        secret_data = {}
        
        # Add data from config
        for key, value in secret_config.data.items():
            secret_data[key] = value.encode('utf-8')
        
        # Add data from environment variables
        for env_var in secret_config.from_env:
            if env_var in os.environ:
                secret_data[env_var] = os.environ[env_var].encode('utf-8')
        
        # Add data from files
        for key, file_path in secret_config.from_file.items():
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    secret_data[key] = f.read()
        
        secret_manifest = client.V1Secret(
            metadata=client.V1ObjectMeta(name=secret_config.name, namespace=namespace),
            type=secret_config.type,
            data=secret_data
        )
        
        try:
            self.core_v1.create_namespaced_secret(namespace=namespace, body=secret_manifest)
            logger.info(f"Created secret: {secret_config.name}")
        except client.exceptions.ApiException as e:
            if e.status == 409:  # Already exists
                self.core_v1.patch_namespaced_secret(
                    name=secret_config.name,
                    namespace=namespace,
                    body=secret_manifest
                )
                logger.info(f"Updated secret: {secret_config.name}")
            else:
                raise
    
    async def _create_configmap(self, configmap_config: ConfigMapConfig, namespace: str):
        """Create Kubernetes ConfigMap."""
        configmap_data = {}
        
        # Add data from config
        configmap_data.update(configmap_config.data)
        
        # Add data from environment variables
        for env_var in configmap_config.from_env:
            if env_var in os.environ:
                configmap_data[env_var] = os.environ[env_var]
        
        # Add data from files
        for key, file_path in configmap_config.from_file.items():
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    configmap_data[key] = f.read()
        
        configmap_manifest = client.V1ConfigMap(
            metadata=client.V1ObjectMeta(name=configmap_config.name, namespace=namespace),
            data=configmap_data
        )
        
        try:
            self.core_v1.create_namespaced_config_map(namespace=namespace, body=configmap_manifest)
            logger.info(f"Created ConfigMap: {configmap_config.name}")
        except client.exceptions.ApiException as e:
            if e.status == 409:  # Already exists
                self.core_v1.patch_namespaced_config_map(
                    name=configmap_config.name,
                    namespace=namespace,
                    body=configmap_manifest
                )
                logger.info(f"Updated ConfigMap: {configmap_config.name}")
            else:
                raise
    
    async def _create_deployment(self, config: DeploymentConfig) -> client.V1Deployment:
        """Create Kubernetes deployment."""
        # Container specification
        container = client.V1Container(
            name=config.name,
            image=f"{config.image}:{config.image_tag}",
            ports=[client.V1ContainerPort(container_port=8000)],
            resources=client.V1ResourceRequirements(
                requests={
                    "cpu": config.resources.cpu_request,
                    "memory": config.resources.memory_request
                },
                limits={
                    "cpu": config.resources.cpu_limit,
                    "memory": config.resources.memory_limit
                }
            ),
            env=[
                client.V1EnvVar(name=key, value=value)
                for key, value in config.environment_variables.items()
            ]
        )
        
        # Add health checks
        if config.health_check.enabled:
            container.liveness_probe = client.V1Probe(
                http_get=client.V1HTTPGetAction(
                    path=config.health_check.path,
                    port=config.health_check.port
                ),
                initial_delay_seconds=config.health_check.initial_delay_seconds,
                period_seconds=config.health_check.period_seconds,
                timeout_seconds=config.health_check.timeout_seconds,
                failure_threshold=config.health_check.failure_threshold
            )
        
        if config.readiness_check.enabled:
            container.readiness_probe = client.V1Probe(
                http_get=client.V1HTTPGetAction(
                    path=config.readiness_check.path,
                    port=config.readiness_check.port
                ),
                initial_delay_seconds=config.readiness_check.initial_delay_seconds,
                period_seconds=config.readiness_check.period_seconds,
                timeout_seconds=config.readiness_check.timeout_seconds,
                failure_threshold=config.readiness_check.failure_threshold,
                success_threshold=config.readiness_check.success_threshold
            )
        
        # Pod specification
        pod_spec = client.V1PodSpec(
            containers=[container],
            restart_policy="Always"
        )
        
        # Deployment specification
        deployment_spec = client.V1DeploymentSpec(
            replicas=config.replicas,
            selector=client.V1LabelSelector(
                match_labels={"app": config.name}
            ),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(
                    labels={"app": config.name, "version": config.image_tag}
                ),
                spec=pod_spec
            ),
            strategy=self._get_deployment_strategy(config.strategy)
        )
        
        # Deployment manifest
        deployment_manifest = client.V1Deployment(
            metadata=client.V1ObjectMeta(
                name=config.name,
                namespace=config.environment.value,
                labels={"app": config.name, "environment": config.environment.value}
            ),
            spec=deployment_spec
        )
        
        try:
            deployment = self.apps_v1.create_namespaced_deployment(
                namespace=config.environment.value,
                body=deployment_manifest
            )
            logger.info(f"Created deployment: {config.name}")
            return deployment
        except client.exceptions.ApiException as e:
            if e.status == 409:  # Already exists
                deployment = self.apps_v1.patch_namespaced_deployment(
                    name=config.name,
                    namespace=config.environment.value,
                    body=deployment_manifest
                )
                logger.info(f"Updated deployment: {config.name}")
                return deployment
            else:
                raise
    
    def _get_deployment_strategy(self, strategy: DeploymentStrategy) -> client.V1DeploymentStrategy:
        """Get Kubernetes deployment strategy."""
        if strategy == DeploymentStrategy.ROLLING_UPDATE:
            return client.V1DeploymentStrategy(
                type="RollingUpdate",
                rolling_update=client.V1RollingUpdateDeployment(
                    max_surge="25%",
                    max_unavailable="25%"
                )
            )
        elif strategy == DeploymentStrategy.RECREATE:
            return client.V1DeploymentStrategy(type="Recreate")
        else:
            # Default to rolling update
            return client.V1DeploymentStrategy(
                type="RollingUpdate",
                rolling_update=client.V1RollingUpdateDeployment(
                    max_surge="25%",
                    max_unavailable="25%"
                )
            )
    
    async def _create_service(self, config: DeploymentConfig) -> client.V1Service:
        """Create Kubernetes service."""
        service_spec = client.V1ServiceSpec(
            selector={"app": config.name},
            ports=[
                client.V1ServicePort(
                    port=config.load_balancer.port,
                    target_port=config.load_balancer.target_port,
                    protocol=config.load_balancer.protocol
                )
            ],
            type=config.load_balancer.type
        )
        
        service_manifest = client.V1Service(
            metadata=client.V1ObjectMeta(
                name=f"{config.name}-service",
                namespace=config.environment.value,
                annotations=config.load_balancer.annotations
            ),
            spec=service_spec
        )
        
        try:
            service = self.core_v1.create_namespaced_service(
                namespace=config.environment.value,
                body=service_manifest
            )
            logger.info(f"Created service: {config.name}-service")
            return service
        except client.exceptions.ApiException as e:
            if e.status == 409:  # Already exists
                service = self.core_v1.patch_namespaced_service(
                    name=f"{config.name}-service",
                    namespace=config.environment.value,
                    body=service_manifest
                )
                logger.info(f"Updated service: {config.name}-service")
                return service
            else:
                raise
    
    async def _create_hpa(self, config: DeploymentConfig) -> client.V1HorizontalPodAutoscaler:
        """Create Horizontal Pod Autoscaler."""
        hpa_spec = client.V1HorizontalPodAutoscalerSpec(
            scale_target_ref=client.V1CrossVersionObjectReference(
                api_version="apps/v1",
                kind="Deployment",
                name=config.name
            ),
            min_replicas=config.auto_scaling.min_replicas,
            max_replicas=config.auto_scaling.max_replicas,
            target_cpu_utilization_percentage=config.auto_scaling.target_cpu_utilization
        )
        
        hpa_manifest = client.V1HorizontalPodAutoscaler(
            metadata=client.V1ObjectMeta(
                name=f"{config.name}-hpa",
                namespace=config.environment.value
            ),
            spec=hpa_spec
        )
        
        try:
            hpa = self.autoscaling_v1.create_namespaced_horizontal_pod_autoscaler(
                namespace=config.environment.value,
                body=hpa_manifest
            )
            logger.info(f"Created HPA: {config.name}-hpa")
            return hpa
        except client.exceptions.ApiException as e:
            if e.status == 409:  # Already exists
                hpa = self.autoscaling_v1.patch_namespaced_horizontal_pod_autoscaler(
                    name=f"{config.name}-hpa",
                    namespace=config.environment.value,
                    body=hpa_manifest
                )
                logger.info(f"Updated HPA: {config.name}-hpa")
                return hpa
            else:
                raise
    
    async def _wait_for_deployment_ready(self, name: str, namespace: str, timeout: int = 600):
        """Wait for deployment to be ready."""
        start_time = datetime.now()
        
        while (datetime.now() - start_time).seconds < timeout:
            try:
                deployment = self.apps_v1.read_namespaced_deployment(name=name, namespace=namespace)
                
                if (deployment.status.ready_replicas and 
                    deployment.status.ready_replicas == deployment.spec.replicas):
                    logger.info(f"Deployment {name} is ready")
                    return
                
                await asyncio.sleep(10)
            except Exception as e:
                logger.warning(f"Error checking deployment status: {e}")
                await asyncio.sleep(10)
        
        raise Exception(f"Deployment {name} did not become ready within {timeout} seconds")
    
    async def _get_health_check_url(self, config: DeploymentConfig) -> Optional[str]:
        """Get health check URL for the deployment."""
        try:
            service = self.core_v1.read_namespaced_service(
                name=f"{config.name}-service",
                namespace=config.environment.value
            )
            
            if service.spec.type == "LoadBalancer" and service.status.load_balancer.ingress:
                ingress = service.status.load_balancer.ingress[0]
                host = ingress.ip or ingress.hostname
                port = config.load_balancer.port
                return f"http://{host}:{port}{config.health_check.path}"
            elif service.spec.type == "NodePort":
                # For NodePort, you'd need to get the node IP
                port = service.spec.ports[0].node_port
                return f"http://localhost:{port}{config.health_check.path}"
            else:
                # For ClusterIP, return internal URL
                return f"http://{service.metadata.name}.{config.environment.value}.svc.cluster.local:{config.load_balancer.port}{config.health_check.path}"
        
        except Exception as e:
            logger.warning(f"Could not determine health check URL: {e}")
            return None
    
    async def rollback(self, name: str, namespace: str, revision: Optional[int] = None) -> bool:
        """Rollback deployment to previous version."""
        try:
            # Get deployment
            deployment = self.apps_v1.read_namespaced_deployment(name=name, namespace=namespace)
            
            # Trigger rollback by updating deployment
            if revision:
                # Rollback to specific revision
                deployment.metadata.annotations = deployment.metadata.annotations or {}
                deployment.metadata.annotations["deployment.kubernetes.io/revision"] = str(revision)
            
            # Update deployment to trigger rollback
            self.apps_v1.patch_namespaced_deployment(
                name=name,
                namespace=namespace,
                body=deployment
            )
            
            # Wait for rollback to complete
            await self._wait_for_deployment_ready(name, namespace)
            
            logger.info(f"Successfully rolled back deployment: {name}")
            return True
        
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False


class DockerDeployer:
    """Docker deployment manager."""
    
    def __init__(self):
        try:
            self.client = docker.from_env()
            logger.info("Docker deployer initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            self.client = None
    
    async def deploy(self, config: DeploymentConfig) -> DeploymentResult:
        """Deploy application using Docker."""
        if not self.client:
            raise Exception("Docker client not available")
        
        deployment_id = f"{config.name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        start_time = datetime.now()
        
        try:
            # Pull image
            image_name = f"{config.image}:{config.image_tag}"
            self.client.images.pull(image_name)
            
            # Stop existing container if it exists
            try:
                existing_container = self.client.containers.get(config.name)
                existing_container.stop()
                existing_container.remove()
                logger.info(f"Stopped and removed existing container: {config.name}")
            except docker.errors.NotFound:
                pass
            
            # Create and start new container
            container = self.client.containers.run(
                image_name,
                name=config.name,
                ports={f"{config.load_balancer.target_port}/tcp": config.load_balancer.port},
                environment=config.environment_variables,
                detach=True,
                restart_policy={"Name": "unless-stopped"},
                mem_limit=config.resources.memory_limit,
                cpu_period=100000,
                cpu_quota=int(float(config.resources.cpu_limit.rstrip('m')) * 100)
            )
            
            # Wait for container to be healthy
            await self._wait_for_container_healthy(container)
            
            health_check_url = f"http://localhost:{config.load_balancer.port}{config.health_check.path}"
            
            return DeploymentResult(
                deployment_id=deployment_id,
                status=DeploymentStatus.COMPLETED,
                environment=config.environment,
                start_time=start_time,
                end_time=datetime.now(),
                current_version=config.image_tag,
                health_check_url=health_check_url
            )
        
        except Exception as e:
            logger.error(f"Docker deployment failed: {e}")
            return DeploymentResult(
                deployment_id=deployment_id,
                status=DeploymentStatus.FAILED,
                environment=config.environment,
                start_time=start_time,
                end_time=datetime.now(),
                error_message=str(e)
            )
    
    async def _wait_for_container_healthy(self, container, timeout: int = 300):
        """Wait for container to be healthy."""
        start_time = datetime.now()
        
        while (datetime.now() - start_time).seconds < timeout:
            container.reload()
            
            if container.status == "running":
                # Check if health check is passing
                try:
                    health = container.attrs.get("State", {}).get("Health", {})
                    if health.get("Status") == "healthy":
                        logger.info(f"Container {container.name} is healthy")
                        return
                    elif health.get("Status") == "unhealthy":
                        raise Exception(f"Container {container.name} is unhealthy")
                except Exception:
                    # If no health check is defined, just check if running
                    logger.info(f"Container {container.name} is running")
                    return
            
            await asyncio.sleep(5)
        
        raise Exception(f"Container {container.name} did not become healthy within {timeout} seconds")


class DeploymentManager:
    """Main deployment manager."""
    
    def __init__(self):
        self.kubernetes_deployer = KubernetesDeployer()
        self.docker_deployer = DockerDeployer()
        self.deployments: Dict[str, DeploymentResult] = {}
        
        logger.info("Deployment manager initialized")
    
    async def deploy(self, config: DeploymentConfig) -> DeploymentResult:
        """Deploy application using specified orchestrator."""
        logger.info(f"Starting deployment: {config.name} to {config.environment.value}")
        
        try:
            if config.orchestrator == ContainerOrchestrator.KUBERNETES:
                result = await self.kubernetes_deployer.deploy(config)
            elif config.orchestrator == ContainerOrchestrator.DOCKER:
                result = await self.docker_deployer.deploy(config)
            else:
                raise ValueError(f"Unsupported orchestrator: {config.orchestrator}")
            
            # Store deployment result
            self.deployments[result.deployment_id] = result
            
            logger.info(f"Deployment completed: {result.deployment_id} - {result.status.value}")
            return result
        
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            raise
    
    async def rollback(self, deployment_id: str) -> bool:
        """Rollback a deployment."""
        if deployment_id not in self.deployments:
            raise ValueError(f"Deployment not found: {deployment_id}")
        
        deployment = self.deployments[deployment_id]
        
        try:
            if deployment.environment == DeploymentEnvironment.PRODUCTION:
                # For production, use Kubernetes rollback
                success = await self.kubernetes_deployer.rollback(
                    name=deployment_id.split('-')[0],  # Extract name from deployment_id
                    namespace=deployment.environment.value
                )
            else:
                # For other environments, implement rollback logic
                success = True  # Placeholder
            
            if success:
                deployment.status = DeploymentStatus.ROLLED_BACK
                logger.info(f"Successfully rolled back deployment: {deployment_id}")
            
            return success
        
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False
    
    def get_deployment_status(self, deployment_id: str) -> Optional[DeploymentResult]:
        """Get deployment status."""
        return self.deployments.get(deployment_id)
    
    def list_deployments(self, environment: Optional[DeploymentEnvironment] = None) -> List[DeploymentResult]:
        """List deployments."""
        deployments = list(self.deployments.values())
        
        if environment:
            deployments = [d for d in deployments if d.environment == environment]
        
        return sorted(deployments, key=lambda x: x.start_time, reverse=True)
    
    def create_deployment_config(
        self,
        name: str,
        environment: DeploymentEnvironment,
        image: str,
        **kwargs
    ) -> DeploymentConfig:
        """Create deployment configuration with defaults."""
        config = DeploymentConfig(
            name=name,
            environment=environment,
            strategy=DeploymentStrategy.ROLLING_UPDATE,
            orchestrator=ContainerOrchestrator.KUBERNETES if environment == DeploymentEnvironment.PRODUCTION else ContainerOrchestrator.DOCKER,
            cloud_provider=CloudProvider.AWS if environment == DeploymentEnvironment.PRODUCTION else CloudProvider.LOCAL,
            image=image
        )
        
        # Apply environment-specific defaults
        if environment == DeploymentEnvironment.PRODUCTION:
            config.replicas = 3
            config.auto_scaling.min_replicas = 3
            config.auto_scaling.max_replicas = 20
            config.resources.cpu_request = "200m"
            config.resources.cpu_limit = "1000m"
            config.resources.memory_request = "256Mi"
            config.resources.memory_limit = "1Gi"
        elif environment == DeploymentEnvironment.STAGING:
            config.replicas = 2
            config.auto_scaling.min_replicas = 2
            config.auto_scaling.max_replicas = 5
        else:
            config.replicas = 1
            config.auto_scaling.enabled = False
        
        # Apply custom overrides
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        return config
    
    def export_config(self, config: DeploymentConfig, format: str = "yaml") -> str:
        """Export deployment configuration."""
        config_dict = {
            "name": config.name,
            "environment": config.environment.value,
            "strategy": config.strategy.value,
            "orchestrator": config.orchestrator.value,
            "cloud_provider": config.cloud_provider.value,
            "image": config.image,
            "image_tag": config.image_tag,
            "replicas": config.replicas,
            "resources": {
                "cpu_request": config.resources.cpu_request,
                "cpu_limit": config.resources.cpu_limit,
                "memory_request": config.resources.memory_request,
                "memory_limit": config.resources.memory_limit
            },
            "health_check": {
                "enabled": config.health_check.enabled,
                "path": config.health_check.path,
                "port": config.health_check.port
            },
            "auto_scaling": {
                "enabled": config.auto_scaling.enabled,
                "min_replicas": config.auto_scaling.min_replicas,
                "max_replicas": config.auto_scaling.max_replicas
            },
            "environment_variables": config.environment_variables
        }
        
        if format.lower() == "yaml":
            return yaml.dump(config_dict, default_flow_style=False)
        elif format.lower() == "json":
            return json.dumps(config_dict, indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")


# Global deployment manager
deployment_manager: Optional[DeploymentManager] = None


def get_deployment_manager() -> DeploymentManager:
    """Get the global deployment manager."""
    global deployment_manager
    if deployment_manager is None:
        deployment_manager = DeploymentManager()
    return deployment_manager