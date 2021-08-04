#!/usr/bin/env python3
# Copyright 2021 Canonical
# See LICENSE file for licensing details.

import datetime
import logging
import os
from ipaddress import IPv4Address
from pathlib import Path
from subprocess import check_output
from typing import Optional

#from cryptography import x509
from kubernetes import kubernetes
from ops.charm import CharmBase, InstallEvent, RemoveEvent
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus
from ops.pebble import ConnectionError

#import cert
import resources

logger = logging.getLogger(__name__)

# Reduce the log output from the Kubernetes library
#logging.getLogger("kubernetes").setLevel(logging.INFO)


class PortainerCharm(CharmBase):
    """Charm the service."""

    _authed = False
    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.install, self._on_install)
 #       self.framework.observe(self.on.config_changed, self._on_config_changed)
 #       self.framework.observe(self.on.remove, self._on_remove)
 #      self.framework.observe(self.on.delete_resources_action, self._on_delete_resources_action)
        self._stored.set_default(things=[])
 #       self._stored.set_default(dashboard_cmd="")

    def _on_install(self, event: InstallEvent) -> None:
        """Handle the install event, create Kubernetes resources"""
        if not self._k8s_auth():
            event.defer()
        return
        self.unit.status = MaintenanceStatus("creating k8s resources")
        # Create the Kubernetes resources needed for the Dashboard
        logging.debug("found a new thing")
        r = resources.PortainerResources(self)
        r.apply()

    @property
    def _k8s_auth(self) -> bool:
        """Authenticate to kubernetes."""
        if self._authed:
            return True
        # Remove os.environ.update when lp:1892255 is FIX_RELEASED.
        os.environ.update(
            dict(
                e.split("=")
                for e in Path("/proc/1/environ").read_text().split("\x00")
                if "KUBERNETES_SERVICE" in e
            )
        )
        # Authenticate against the Kubernetes API using a mounted ServiceAccount token
        kubernetes.config.load_incluster_config()
        # Test the service account we've got for sufficient perms
        auth_api = kubernetes.client.RbacAuthorizationV1Api(kubernetes.client.ApiClient())

        try:
            auth_api.list_cluster_role()
        except kubernetes.client.exceptions.ApiException as e:
            if e.status == 403:
                # If we can't read a cluster role, we don't have enough permissions
                self.unit.status = BlockedStatus("Run juju trust on this application to continue")
                return False
            else:
                raise e

        self._authed = True
        return True
    
    @property
    def namespace(self) -> str:
        with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace", "r") as f:
            return f.read().strip()

    @property
    def pod_ip(self) -> Optional[IPv4Address]:
        return IPv4Address(check_output(["unit-get", "private-address"]).decode().strip())


if __name__ == "__main__":
    main(PortainerCharm)
