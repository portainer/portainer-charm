# Copyright 2021 Portainer.io
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing


import unittest
from unittest.mock import Mock, PropertyMock, mock_open, patch

from kubernetes import kubernetes

from config import PortainerConfig
from k8s_service import K8sService


class TestK8sService(unittest.TestCase):
    @patch("k8s_service.K8sService.build_k8s_spec_by_config")
    @patch("k8s_service.K8sService.get_namespace")
    @patch("k8s_service.kubernetes.client.CoreV1Api.create_namespaced_service")
    @patch("k8s_service.kubernetes.client.CoreV1Api.delete_namespaced_service")
    def test_create_k8s_service_success(self, dns, cns, ns, build_spec):
        namespace = "lma"
        app_name = "app"
        config = PortainerConfig({})
        spec: dict[str, str] = {}
        ns.return_value = namespace
        build_spec.return_value = spec

        K8sService.create_k8s_service_by_config(app_name, config)

        dns.assert_called_with(name=app_name, namespace=namespace)
        build_spec.assert_called_with(app_name, config)
        cns.assert_called_with(
            namespace=namespace,
            body=kubernetes.client.V1Service(
                api_version="v1",
                metadata=kubernetes.client.V1ObjectMeta(
                    namespace=namespace,
                    name=app_name,
                    labels={
                        "io.portainer.kubernetes.application.stack": app_name,
                        "app.kubernetes.io/name": app_name,
                        "app.kubernetes.io/instance": app_name,
                        "app.kubernetes.io/version": K8sService.SERVICE_VERSION,
                    },
                ),
                spec=spec,
            ),
        )

    @patch("k8s_service.K8sService.build_k8s_spec_by_config")
    @patch("k8s_service.K8sService.get_namespace")
    @patch("k8s_service.kubernetes.client.CoreV1Api.create_namespaced_service")
    @patch("k8s_service.kubernetes.client.CoreV1Api.delete_namespaced_service")
    def test_create_k8s_service_delete_404(self, dns, cns, ns, build_spec):
        namespace = "lma"
        app_name = "app"
        config = PortainerConfig({})
        spec: dict[str, str] = {}
        ns.return_value = namespace
        build_spec.return_value = spec
        dns.side_effect = kubernetes.client.exceptions.ApiException(status=404)

        K8sService.create_k8s_service_by_config(app_name, config)

        dns.assert_called_with(name=app_name, namespace=namespace)
        build_spec.assert_called_with(app_name, config)
        cns.assert_called_with(
            namespace=namespace,
            body=kubernetes.client.V1Service(
                api_version="v1",
                metadata=kubernetes.client.V1ObjectMeta(
                    namespace=namespace,
                    name=app_name,
                    labels={
                        "io.portainer.kubernetes.application.stack": app_name,
                        "app.kubernetes.io/name": app_name,
                        "app.kubernetes.io/instance": app_name,
                        "app.kubernetes.io/version": K8sService.SERVICE_VERSION,
                    },
                ),
                spec=spec,
            ),
        )

    def test_build_k8s_spec(self):
        app_name = "app"
        c1 = Mock()
        m_st = PropertyMock(return_value="ServiceType")
        m_hp = PropertyMock(return_value=1111)
        m_ep = PropertyMock(return_value=2222)
        m_hnp = PropertyMock(return_value=3333)
        m_enp = PropertyMock(return_value=4444)
        c1.is_http_node_port_configured.return_value = False
        c1.is_edge_node_port_configured.return_value = False
        type(c1).service_type = m_st
        type(c1).service_http_port = m_hp
        type(c1).service_edge_port = m_ep
        type(c1).service_http_node_port = m_hnp
        type(c1).service_edge_node_port = m_enp

        r1 = K8sService.build_k8s_spec_by_config(app_name, c1)

        self.assertEqual(
            r1,
            kubernetes.client.V1ServiceSpec(
                type="ServiceType",
                ports=[
                    kubernetes.client.V1ServicePort(
                        name="http",
                        port=1111,
                        target_port=9000,
                    ),
                    kubernetes.client.V1ServicePort(
                        name="edge",
                        port=2222,
                        target_port=8000,
                    ),
                ],
                selector={
                    "app.kubernetes.io/name": app_name,
                },
            ),
        )

    def test_build_k8s_spec_node_port(self):
        app_name = "app"
        c1 = Mock()
        m_st = PropertyMock(return_value="ServiceType")
        m_hp = PropertyMock(return_value=1111)
        m_ep = PropertyMock(return_value=2222)
        m_hnp = PropertyMock(return_value=3333)
        m_enp = PropertyMock(return_value=4444)
        c1.is_http_node_port_configured.return_value = True
        c1.is_edge_node_port_configured.return_value = True
        type(c1).service_type = m_st
        type(c1).service_http_port = m_hp
        type(c1).service_edge_port = m_ep
        type(c1).service_http_node_port = m_hnp
        type(c1).service_edge_node_port = m_enp

        r1 = K8sService.build_k8s_spec_by_config(app_name, c1)

        self.assertEqual(
            r1,
            kubernetes.client.V1ServiceSpec(
                type="ServiceType",
                ports=[
                    kubernetes.client.V1ServicePort(
                        name="http",
                        port=1111,
                        target_port=9000,
                        node_port=3333,
                    ),
                    kubernetes.client.V1ServicePort(
                        name="edge",
                        port=2222,
                        target_port=8000,
                        node_port=4444,
                    ),
                ],
                selector={
                    "app.kubernetes.io/name": app_name,
                },
            ),
        )

    @patch("k8s_service.kubernetes.client.CoreV1Api.list_namespaced_service")
    @patch("k8s_service.K8sService.get_namespace")
    @patch("k8s_service.kubernetes.config.load_incluster_config")
    def test_k8s_auth_success(self, load_config, ns, list_svc):
        ns.return_value = "lma"
        load_config.return_value = True

        r = K8sService.k8s_auth()

        list_svc.assert_called_with(namespace="lma")
        self.assertTrue(r)

    @patch("k8s_service.kubernetes.client.CoreV1Api.list_namespaced_service")
    @patch("k8s_service.K8sService.get_namespace")
    @patch("k8s_service.kubernetes.config.load_incluster_config")
    def test_k8s_auth_403(self, load_config, ns, list_svc):
        ns.return_value = "lma"
        load_config.return_value = True
        list_svc.side_effect = kubernetes.client.exceptions.ApiException(status=403)

        r1 = K8sService.k8s_auth()

        list_svc.assert_called_with(namespace="lma")
        self.assertFalse(r1)

    @patch("k8s_service.kubernetes.client.CoreV1Api.list_namespaced_service")
    @patch("k8s_service.K8sService.get_namespace")
    @patch("k8s_service.kubernetes.config.load_incluster_config")
    def test_k8s_auth_exception(self, load_config, ns, list_svc):
        ns.return_value = "lma"
        load_config.return_value = True
        list_svc.side_effect = kubernetes.client.exceptions.ApiException(status=100)

        self.assertRaises(kubernetes.client.exceptions.ApiException, K8sService.k8s_auth)

    @patch("k8s_service.kubernetes.client.CoreV1Api.patch_namespaced_service")
    @patch("k8s_service.K8sService.get_namespace")
    @patch("k8s_service.K8sService.build_k8s_spec_by_config")
    def test_patch_k8s_service(self, build_spec, ns, pns):
        namespace = "lma"
        app_name = "app"
        config = PortainerConfig({})
        spec = kubernetes.client.V1ServiceSpec(
            type="ServiceType",
            ports=[
                kubernetes.client.V1ServicePort(
                    name="http",
                    port=1111,
                    target_port=9000,
                    node_port=3333,
                ),
                kubernetes.client.V1ServicePort(
                    name="edge",
                    port=2222,
                    target_port=8000,
                    node_port=4444,
                ),
            ],
            selector={
                "app.kubernetes.io/name": app_name,
            },
        )
        ns.return_value = namespace
        build_spec.return_value = spec

        K8sService.patch_k8s_service_by_config(app_name, config)

        build_spec.assert_called_with(app_name, config)
        pns.assert_called_with(
            name=app_name,
            namespace=namespace,
            body=[
                {
                    "op": "replace",
                    "path": "/spec/ports",
                    "value": [
                        {"name": "http", "nodePort": 3333, "port": 1111, "targetPort": 9000},
                        {"name": "edge", "nodePort": 4444, "port": 2222, "targetPort": 8000},
                    ],
                },
                {
                    "op": "replace",
                    "path": "/spec/selector",
                    "value": {"app.kubernetes.io/name": "app"},
                },
                {"op": "replace", "path": "/spec/type", "value": "ServiceType"},
            ],
        )

    @patch("k8s_service.kubernetes.client.CoreV1Api.patch_namespaced_service")
    @patch("k8s_service.utils.clean_nones")
    @patch("k8s_service.K8sService.build_k8s_spec_by_config")
    def test_patch_k8s_empty(self, build_spec, clean, pns):
        app_name = "app"
        config = PortainerConfig({})
        clean.return_value = {}
        build_spec.return_value = kubernetes.client.V1ServiceSpec()

        K8sService.patch_k8s_service_by_config(app_name, config)

        build_spec.assert_called_with(app_name, config)
        pns.assert_not_called()

    @patch("k8s_service.K8sService.get_namespace")
    @patch("k8s_service.kubernetes.client.RbacAuthorizationV1Api.create_cluster_role_binding")
    @patch("k8s_service.kubernetes.client.RbacAuthorizationV1Api.delete_cluster_role_binding")
    @patch("k8s_service.kubernetes.client.RbacAuthorizationV1Api.read_cluster_role")
    @patch("k8s_service.kubernetes.client.CoreV1Api.create_namespaced_service_account")
    @patch("k8s_service.kubernetes.client.CoreV1Api.delete_namespaced_service_account")
    def test_create_k8s_service_account(self, dns, cns, rcr, dcr, ccr, ns):
        namespace = "lma"
        app_name = "app"
        ns.return_value = namespace

        r = K8sService.create_k8s_service_account(app_name)

        rcr.assert_called_with(name="cluster-admin")
        dns.assert_called_with(name="portainer-sa-clusteradmin", namespace=namespace)
        cns.assert_called_with(
            namespace=namespace,
            body=kubernetes.client.V1ServiceAccount(
                api_version="v1",
                metadata=kubernetes.client.V1ObjectMeta(
                    namespace=namespace,
                    name="portainer-sa-clusteradmin",
                    labels={
                        "app.kubernetes.io/name": app_name,
                        "app.kubernetes.io/instance": app_name,
                        "app.kubernetes.io/version": K8sService.SERVICE_VERSION,
                    },
                ),
            ),
        )
        dcr.assert_called_with(name="portainer")
        ccr.assert_called_with(
            body=kubernetes.client.V1ClusterRoleBinding(
                api_version="rbac.authorization.k8s.io/v1",
                metadata=kubernetes.client.V1ObjectMeta(
                    namespace=namespace,
                    name=app_name,
                    labels={
                        "app.kubernetes.io/name": app_name,
                        "app.kubernetes.io/instance": app_name,
                        "app.kubernetes.io/version": K8sService.SERVICE_VERSION,
                    },
                ),
                role_ref=kubernetes.client.V1RoleRef(
                    api_group="rbac.authorization.k8s.io",
                    kind="ClusterRole",
                    name="cluster-admin",
                ),
                subjects=[
                    kubernetes.client.V1Subject(
                        kind="ServiceAccount",
                        namespace=namespace,
                        name="portainer-sa-clusteradmin",
                    ),
                ],
            )
        )
        self.assertTrue(r)

    @patch("k8s_service.K8sService.get_namespace")
    @patch("k8s_service.kubernetes.client.RbacAuthorizationV1Api.create_cluster_role_binding")
    @patch("k8s_service.kubernetes.client.RbacAuthorizationV1Api.delete_cluster_role_binding")
    @patch("k8s_service.kubernetes.client.RbacAuthorizationV1Api.read_cluster_role")
    @patch("k8s_service.kubernetes.client.CoreV1Api.create_namespaced_service_account")
    @patch("k8s_service.kubernetes.client.CoreV1Api.delete_namespaced_service_account")
    def test_create_k8s_service_account_rbac_missing(self, dns, cns, rcr, dcr, ccr, ns):
        namespace = "lma"
        app_name = "app"
        ns.return_value = namespace
        rcr.side_effect = kubernetes.client.exceptions.ApiException(status=404)

        r = K8sService.create_k8s_service_account(app_name)

        self.assertFalse(r)
        rcr.assert_called_with(name="cluster-admin")
        dns.assert_not_called()
        cns.assert_not_called()
        dcr.assert_not_called()
        ccr.assert_not_called()

    @patch("k8s_service.K8sService.get_namespace")
    @patch("k8s_service.kubernetes.client.RbacAuthorizationV1Api.create_cluster_role_binding")
    @patch("k8s_service.kubernetes.client.RbacAuthorizationV1Api.delete_cluster_role_binding")
    @patch("k8s_service.kubernetes.client.RbacAuthorizationV1Api.read_cluster_role")
    @patch("k8s_service.kubernetes.client.CoreV1Api.create_namespaced_service_account")
    @patch("k8s_service.kubernetes.client.CoreV1Api.delete_namespaced_service_account")
    def test_create_k8s_service_account_404(self, dns, cns, rcr, dcr, ccr, ns):
        namespace = "lma"
        app_name = "app"
        ns.return_value = namespace
        dns.side_effect = kubernetes.client.exceptions.ApiException(status=404)
        dcr.side_effect = kubernetes.client.exceptions.ApiException(status=404)

        r = K8sService.create_k8s_service_account(app_name)

        rcr.assert_called_with(name="cluster-admin")
        dns.assert_called_with(name="portainer-sa-clusteradmin", namespace=namespace)
        cns.assert_called_with(
            namespace=namespace,
            body=kubernetes.client.V1ServiceAccount(
                api_version="v1",
                metadata=kubernetes.client.V1ObjectMeta(
                    namespace=namespace,
                    name="portainer-sa-clusteradmin",
                    labels={
                        "app.kubernetes.io/name": app_name,
                        "app.kubernetes.io/instance": app_name,
                        "app.kubernetes.io/version": K8sService.SERVICE_VERSION,
                    },
                ),
            ),
        )
        dcr.assert_called_with(name="portainer")
        ccr.assert_called_with(
            body=kubernetes.client.V1ClusterRoleBinding(
                api_version="rbac.authorization.k8s.io/v1",
                metadata=kubernetes.client.V1ObjectMeta(
                    namespace=namespace,
                    name=app_name,
                    labels={
                        "app.kubernetes.io/name": app_name,
                        "app.kubernetes.io/instance": app_name,
                        "app.kubernetes.io/version": K8sService.SERVICE_VERSION,
                    },
                ),
                role_ref=kubernetes.client.V1RoleRef(
                    api_group="rbac.authorization.k8s.io",
                    kind="ClusterRole",
                    name="cluster-admin",
                ),
                subjects=[
                    kubernetes.client.V1Subject(
                        kind="ServiceAccount",
                        namespace=namespace,
                        name="portainer-sa-clusteradmin",
                    ),
                ],
            )
        )
        self.assertTrue(r)

    @patch("builtins.open", new_callable=mock_open, read_data="namespace")
    def test_get_namespace(self, mock_file):
        K8sService.get_namespace()

        mock_file.assert_called_with(
            "/var/run/secrets/kubernetes.io/serviceaccount/namespace", "r"
        )
