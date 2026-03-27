#!/usr/bin/env python3
# Copyright 2021 Portainer.io
# See LICENSE file for licensing details.

"""Class that provides K8s services."""

import logging

from kubernetes import kubernetes

import utils
from config import PortainerConfig

logger = logging.getLogger(__name__)


class K8sService:
    """Class that provides K8s services."""

    SERVICE_VERSION = "portainer-ee"

    @classmethod
    def create_k8s_service_by_config(cls, app_name: str, config: PortainerConfig):
        """Delete then create k8s service by stored config."""
        api = kubernetes.client.CoreV1Api(kubernetes.client.ApiClient())
        _namespace = cls.get_namespace()
        try:
            api.delete_namespaced_service(name=app_name, namespace=_namespace)
        except kubernetes.client.exceptions.ApiException as e:
            if e.status == 404:
                logger.info(f"{app_name} service doesn't exist, skip deletion")
            else:
                raise e
        api.create_namespaced_service(
            namespace=_namespace,
            body=kubernetes.client.V1Service(
                api_version="v1",
                metadata=kubernetes.client.V1ObjectMeta(
                    namespace=_namespace,
                    name=app_name,
                    labels={
                        "io.portainer.kubernetes.application.stack": app_name,
                        "app.kubernetes.io/name": app_name,
                        "app.kubernetes.io/instance": app_name,
                        "app.kubernetes.io/version": cls.SERVICE_VERSION,
                    },
                ),
                spec=cls.build_k8s_spec_by_config(app_name, config),
            ),
        )

    @classmethod
    def build_k8s_spec_by_config(
        cls, app_name: str, config: PortainerConfig
    ) -> kubernetes.client.V1ServiceSpec:
        """Constructs k8s service spec by input config.

        Returns: a k8s V1ServiceSpec object built from config.
        """
        service_type = config.service_type
        http_port = kubernetes.client.V1ServicePort(
            name="http",
            port=config.service_http_port,
            target_port=9000,
        )
        if config.is_http_node_port_configured():
            http_port.node_port = config.service_http_node_port

        edge_port = kubernetes.client.V1ServicePort(
            name="edge",
            port=config.service_edge_port,
            target_port=8000,
        )
        if config.is_edge_node_port_configured():
            edge_port.node_port = config.service_edge_node_port

        result = kubernetes.client.V1ServiceSpec(
            type=service_type,
            ports=[
                http_port,
                edge_port,
            ],
            selector={
                "app.kubernetes.io/name": app_name,
            },
        )
        logger.debug(f"generating spec: {result}")
        return result

    @classmethod
    def k8s_auth(cls) -> bool:
        """Authenticate to kubernetes.

        Returns: whether it is currently authenticated or not.
        """
        # Authenticate against the Kubernetes API using a mounted ServiceAccount token
        kubernetes.config.load_incluster_config()
        # Test the service account we've got for sufficient perms
        api = kubernetes.client.CoreV1Api(kubernetes.client.ApiClient())

        try:
            api.list_namespaced_service(namespace=cls.get_namespace())
        except kubernetes.client.exceptions.ApiException as e:
            if e.status == 403:
                return False
            else:
                raise e
        return True

    # Issue with this method:
    # _build_k8s_spec_by_config generates the object that leaves 'None'
    # when stringified, e.g. {'cluster_ip': None,'external_i_ps': None,'external_name': None},
    # causing k8s complaining: Invalid value: []core.IPFamily(nil):
    # primary ipFamily can not be unset.
    @classmethod
    def patch_k8s_service_by_config(cls, app_name: str, config: PortainerConfig):
        """Patch k8s service by stored config."""
        logger.info("updating k8s service by config")
        client = kubernetes.client.ApiClient()
        api = kubernetes.client.CoreV1Api(client)

        # a direct replacement of /spec won't work,
        # since it misses things like cluster_ip;
        # need to serialize the object to dictionay
        # then clean none entries to replace bits by bits.
        spec = utils.clean_nones(
            client.sanitize_for_serialization(cls.build_k8s_spec_by_config(app_name, config))
        )
        body = []
        for k, v in spec.items():
            body.append(
                {
                    "op": "replace",
                    "path": f"/spec/{k}",
                    "value": v,
                }
            )
        logger.debug(f"patching with body: {body}")
        if body:
            api.patch_namespaced_service(
                name=app_name,
                namespace=cls.get_namespace(),
                body=body,
            )
        else:
            logger.info("nothing to patch, skip patching")
            return

    @classmethod
    def create_k8s_service_account(cls, app_name: str) -> bool:
        """Delete then create the service accounts needed by Portainer.

        Returns: whether the execution is successful or not.
        """
        logger.info("creating k8s service account")
        _serviceaccount_name = "portainer-sa-clusteradmin"
        _clusterrb_name = "portainer"
        _clusterrole_name = "cluster-admin"
        _namespace = cls.get_namespace()
        client = kubernetes.client.ApiClient()
        api = kubernetes.client.CoreV1Api(client)
        rbac = kubernetes.client.RbacAuthorizationV1Api(client)
        # check cluster role, make sure it exists
        try:
            rbac.read_cluster_role(name=_clusterrole_name)
        except kubernetes.client.exceptions.ApiException as e:
            if e.status == 404:
                logger.error(
                    f"{_clusterrole_name} cluster role doesn't exist, please make sure RBAC is enabled in k8s cluster."
                )
                return False
            else:
                raise e
        # creates service account
        try:
            api.delete_namespaced_service_account(name=_serviceaccount_name, namespace=_namespace)
        except kubernetes.client.exceptions.ApiException as e:
            if e.status == 404:
                logger.info(f"{_serviceaccount_name} service account doesn't exist, skip deletion")
            else:
                raise e
        api.create_namespaced_service_account(
            namespace=_namespace,
            body=kubernetes.client.V1ServiceAccount(
                api_version="v1",
                metadata=kubernetes.client.V1ObjectMeta(
                    namespace=_namespace,
                    name=_serviceaccount_name,
                    labels={
                        "app.kubernetes.io/name": app_name,
                        "app.kubernetes.io/instance": app_name,
                        "app.kubernetes.io/version": cls.SERVICE_VERSION,
                    },
                ),
            ),
        )
        # create cluster role binding with the service account
        logger.info("creating k8s cluster role binding")
        try:
            rbac.delete_cluster_role_binding(name=_clusterrb_name)
        except kubernetes.client.exceptions.ApiException as e:
            if e.status == 404:
                logger.info(f"{_clusterrb_name} cluster role binding doesn't exist, skip deletion")
            else:
                raise e
        rbac.create_cluster_role_binding(
            body=kubernetes.client.V1ClusterRoleBinding(
                api_version="rbac.authorization.k8s.io/v1",
                metadata=kubernetes.client.V1ObjectMeta(
                    namespace=_namespace,
                    name=app_name,
                    labels={
                        "app.kubernetes.io/name": app_name,
                        "app.kubernetes.io/instance": app_name,
                        "app.kubernetes.io/version": cls.SERVICE_VERSION,
                    },
                ),
                role_ref=kubernetes.client.V1RoleRef(
                    api_group="rbac.authorization.k8s.io",
                    kind="ClusterRole",
                    name=_clusterrole_name,
                ),
                subjects=[
                    kubernetes.client.V1Subject(
                        kind="ServiceAccount",
                        namespace=_namespace,
                        name=_serviceaccount_name,
                    ),
                ],
            )
        )
        return True

    @staticmethod
    def get_namespace() -> str:
        """Fetch the current Kubernetes namespace by reading it from the service account.

        Returns: current k8s namespace in str.
        """
        with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace", "r") as f:
            return f.read().strip()
