# Copyright 2021 Canonical
# See LICENSE file for licensing details.
import logging

from kubernetes import kubernetes
from kubernetes import client, config, utils


logger = logging.getLogger(__name__)


class PortainerResources:
    """Class to handle the creation and deletion of those Kubernetes resources
    required by the Portainer UI, but not automatically handled by Juju"""

    def __init__(self, charm):
        self.model = charm.model
        self.app = charm.app
        self.config = charm.config
        self.namespace = charm.namespace
        # Setup some Kubernetes API clients we'll need
        kcl = kubernetes.client.ApiClient()
        self.apps_api = kubernetes.client.AppsV1Api(kcl)
        self.core_api = kubernetes.client.CoreV1Api(kcl)
        self.auth_api = kubernetes.client.RbacAuthorizationV1Api(kcl)

    def apply(self) -> None:
        logger.info("Creating additional Kubernetes resources")
        k8s_client=client.api_client.ApiClient(configuration=config.load_kube_config())
        utils.create_from_yaml(k8s_client, 'nginx.yaml')
        logger.info("Created additional Kubernetes resources")

    def delete(self) -> None:
        """Delete all of the Portainer resources created by the apply method"""
        # Delete service accounts
        for sa in self._service_accounts:
            self.core_api.delete_namespaced_service_account(
                namespace=sa["namespace"], name=sa["body"].metadata.name
            )
        # Delete Portainer services
        for service in self._services:
            self.core_api.delete_namespaced_service(
                namespace=service["namespace"], name=service["body"].metadata.name
            )
        # Delete Portainer cluster roles
        for cr in self._clusterroles:
            self.auth_api.delete_cluster_role(name=cr["body"].metadata.name)
        # Delete Portainer cluster role bindings
        for crb in self._clusterrolebindings:
            self.auth_api.delete_cluster_role_binding(name=crb["body"].metadata.name)

        logger.info("Deleted additional Portainer resources")

    @property
    def dashboard_volumes(self) -> dict:
        """Returns the additional volumes required by the Dashboard"""
        # Get the service account details so we can reference it's token
        service_account = self.core_api.read_namespaced_service_account(
            name="portainer", namespace=self.namespace
        )
        return [
            kubernetes.client.V1Volume(
                name="tmp-volume-dashboard",
                empty_dir=kubernetes.client.V1EmptyDirVolumeSource(),
            ),
        ]

    @property
    def dashboard_volume_mounts(self) -> dict:
        """Returns the additional volume mounts for the dashboard containers"""
        return [
            kubernetes.client.V1VolumeMount(mount_path="/tmp", name="tmp-volume-dashboard"),
            # kubernetes.client.V1VolumeMount(
            #     mount_path="/certs", name="portainer-certs"
            # ),
            kubernetes.client.V1VolumeMount(
                mount_path="/var/run/secrets/kubernetes.io/serviceaccount",
                name="portainer-service-account",
            ),
        ]

    @property
    def _service_accounts(self) -> list:
        """Return a dictionary containing parameters for the dashboard svc account"""
        return [
            {
                "namespace": self.namespace,
                "body": kubernetes.client.V1ServiceAccount(
                    api_version="v1",
                    metadata=kubernetes.client.V1ObjectMeta(
                        namespace=self.namespace,
                        name="portainer-sa-clusteradmin",
                        labels={"app.kubernetes.io/name": self.app.name,"app.kubernetes.io/instance": self.app.name,"app.kubernetes.io/version": "ce-latest-ee-2.4.0",
                        },
                    ),
                ),
            }
        ]


    @property
    def _services(self) -> list:
        """Return a list of Kubernetes services needed by the Kubernetes Dashboard"""
        # Note that this service is actually created by Juju, we are patching
        # it here to include the correct port mapping
        # TODO: Update when support improves in Juju

        return [
            {
                "namespace": self.namespace,
                "body": kubernetes.client.V1Service(
                    api_version="v1",
                    metadata=kubernetes.client.V1ObjectMeta(
                        namespace=self.namespace,
                        name=self.app.name,
                        labels={"io.portainer.kubernetes.application.stack": self.app.name,"app.kubernetes.io/name": self.app.name,"app.kubernetes.io/instance": self.app.name,"app.kubernetes.io/version": "ce-latest-ee-2.4.0"},
                    ),
                    spec=kubernetes.client.V1ServiceSpec(
                        type="NodePort",                     
                        ports=[
                            kubernetes.client.V1ServicePort(
                                name="http",
                                port=9000,
                                target_port=9000,
                                node_port=30777,
                            ),
                            kubernetes.client.V1ServicePort(
                                name="edge",
                                port=8000,
                                target_port=8000,
                                node_port=30776,
                            ),
                        ],
                        selector={"app.kubernetes.io/name": self.app.name,"app.kubernetes.io/instance": self.app.name},
                    ),
                ),
            },
            
        ]



    @property
    def _clusterroles(self) -> list:
        """Return a list of Cluster Roles required by the Portainer UI"""
        return [
            {
                "body": kubernetes.client.V1ClusterRole(
                    api_version="rbac.authorization.k8s.io/v1",
                    metadata=kubernetes.client.V1ObjectMeta(
                        name="portainer",
                        labels={"app.kubernetes.io/name": self.app.name},
                    ),
                    rules=[
                        # Allow portainer to access cluster
                        kubernetes.client.V1PolicyRule(
                            api_groups=[""],
                            resources=[""],
                            verbs=[""],
                        ),
                    ],
                )
            }
        ]

    @property
    def _clusterrolebindings(self) -> list:
        """Return a list of Cluster Role Bindings required by the Portainer UI"""
        return [
            {
                "body": kubernetes.client.V1ClusterRoleBinding(
                    api_version="rbac.authorization.k8s.io/v1",
                    metadata=kubernetes.client.V1ObjectMeta(
                        name="portainer",
                        labels={"app.kubernetes.io/name": self.app.name,"app.kubernetes.io/name": self.app.name,"app.kubernetes.io/version": "ce-latest-ee-2.4.0"},
                    ),
                    role_ref=kubernetes.client.V1RoleRef(
                        api_group="rbac.authorization.k8s.io",
                        kind="ClusterRole",
                        name="cluster-admin",
                    ),
                    subjects=[
                        kubernetes.client.V1Subject(
                            kind="ServiceAccount",
                            name="portainer-sa-clusteradmin",
                            namespace=self.namespace,
                        )
                    ],
                )
            }
        ]
