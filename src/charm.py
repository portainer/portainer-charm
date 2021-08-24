#!/usr/bin/env python3
# Copyright 2021 Portainer
# See LICENSE file for licensing details.

import logging

from kubernetes import kubernetes
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus

logger = logging.getLogger(__name__)
# Reduce the log output from the Kubernetes library
# logging.getLogger("kubernetes").setLevel(logging.INFO)


class PortainerCharm(CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.start, self._start_portainer)
        self.framework.observe(self.on.portainer_pebble_ready, self._start_portainer)

    def _on_install(self, event):
        """Handle the install event, create Kubernetes resources"""
        if not self._k8s_auth():
            event.defer()
            return
        self.unit.status = MaintenanceStatus("patching kubernetes service for portainer")

        api = kubernetes.client.CoreV1Api(kubernetes.client.ApiClient())
        api.delete_namespaced_service(name="portainer", namespace=self.namespace)
        api.create_namespaced_service(**self._service)

    def _start_portainer(self, _):
        """Function to handle starting Portainer using Pebble"""
        # Get a reference to the portainer workload container
        container = self.unit.get_container("portainer")
        with container.is_ready():
            svc = container.get_services().get("portainer", None)
            # Check if the service is already running
            if not svc:
                # Add a new layer
                container.add_layer("portainer", self._layer, combine=True)
                container.start("portainer")

            self.unit.status = ActiveStatus()

    def _k8s_auth(self) -> bool:
        """Authenticate to kubernetes."""
        # Authenticate against the Kubernetes API using a mounted ServiceAccount token
        kubernetes.config.load_incluster_config()
        # Test the service account we've got for sufficient perms
        api = kubernetes.client.CoreV1Api(kubernetes.client.ApiClient())

        try:
            api.list_namespaced_service(namespace=self.namespace)
        except kubernetes.client.exceptions.ApiException as e:
            if e.status == 403:
                # If we can't read a cluster role, we don't have enough permissions
                self.unit.status = BlockedStatus("Run juju trust on this application to continue")
                return False
            else:
                raise e
        return True

    @property
    def _layer(self) -> dict:
        """Returns a pebble layer for Portainer"""
        return {
            "services": {
                "portainer": {
                    "override": "replace",
                    "command": "/portainer --tunnel-port 30776",
                }
            },
        }

    @property
    def _service(self) -> dict:
        """Return a Kubernetes service setup for Portainer"""
        return {
            "namespace": self.namespace,
            "body": kubernetes.client.V1Service(
                api_version="v1",
                metadata=kubernetes.client.V1ObjectMeta(
                    namespace=self.namespace,
                    name=self.app.name,
                    labels={
                            "io.portainer.kubernetes.application.stack": self.app.name,
                            "app.kubernetes.io/name": self.app.name,
                            "app.kubernetes.io/instance": self.app.name,
                            "app.kubernetes.io/version": "ce-latest-ee-2.4.0",
                    },
                ),
                spec=kubernetes.client.V1ServiceSpec(
                    type="NodePort",
                    ports=[
                        kubernetes.client.V1ServicePort(
                            name="http",
                            port=9000,
                            target_port=9000,
                            node_port=30776,
                        ),
                        kubernetes.client.V1ServicePort(
                            name="edge",
                            port=8000,
                            target_port=8000,
                            node_port=30777,
                        ),
                    ],
                    selector={
                        "app.kubernetes.io/name": self.app.name,
                    },
                ),
            ),
        }

    @property
    def namespace(self) -> str:
        """Fetch the current Kubernetes namespace by reading it from the service account"""
        with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace", "r") as f:
            return f.read().strip()


if __name__ == "__main__":
    main(PortainerCharm, use_juju_for_storage=True)
