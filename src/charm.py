#!/usr/bin/env python3
# Copyright 2021 Portainer
# See LICENSE file for licensing details.

import logging
import utils
import sys

from kubernetes import kubernetes
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, WaitingStatus

# disable bytecode caching according to: https://discourse.charmhub.io/t/upgrading-a-charm/1131
sys.dont_write_bytecode = True
logger = logging.getLogger(__name__)
# Reduce the log output from the Kubernetes library
# logging.getLogger("kubernetes").setLevel(logging.INFO)
CHARM_VERSION = 1.0
SERVICE_VERSION = "portainer-ee"
SERVICETYPE_LB = "LoadBalancer"
SERVICETYPE_CIP = "ClusterIP"
SERVICETYPE_NP = "NodePort"
CONFIG_SERVICETYPE = "service_type"
CONFIG_SERVICEHTTPPORT = "service_http_port"
CONFIG_SERVICEHTTPNODEPORT = "service_http_node_port"
CONFIG_SERVICEEDGEPORT = "service_edge_port"
CONFIG_SERVICEEDGENODEPORT = "service_edge_node_port"

class PortainerCharm(CharmBase):
    """Charm the service."""
    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        logger.info(f"initialising charm, version: {CHARM_VERSION}", )
        # setup default config value, only create if not exist
        self._stored.set_default(
            charm_version = CHARM_VERSION,
            config = self._default_config,
        )
        logger.debug(f"start with config: {self._config}")
        # hooks up events
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.start, self._start_portainer)
        self.framework.observe(self.on.upgrade_charm, self._upgrade_charm)
        self.framework.observe(self.on.portainer_pebble_ready, self._start_portainer)

    def _on_install(self, event):
        """Handle the install event, create Kubernetes resources"""
        logger.info("installing charm")
        if not self.unit.is_leader():
            logger.warn("portainer must work as a leader, waiting for leadership")
            self.unit.status = WaitingStatus('waiting for leadership')
            event.defer()
            return
        if not self._k8s_auth():
            self.unit.status = WaitingStatus('waiting for k8s auth')
            logger.info("waiting for k8s auth, installation deferred")
            event.defer()
            return
        self.unit.status = MaintenanceStatus("creating kubernetes service for portainer")
        self._create_k8s_service_by_config()
        if not self._create_k8s_service_account():
            self.unit.status = WaitingStatus('waiting for service account perconditions')
            logger.info("waiting for service account perconditions, installation deferred")
            event.defer()
            return

    def _update_pebble(self, event, config: dict):
        """Update pebble by config"""
        logger.info("updating pebble")
        # get a reference to the portainer workload container
        container = self.unit.get_container("portainer")
        if container.is_ready():
            svc = container.get_services().get("portainer", None)
            # check if the pebble service is already running
            if svc:
                logger.info("stopping pebble service")
                container.stop("portainer")
            # override existing layer
            container.add_layer("portainer", self._build_layer_by_config(config), combine=True)
            logger.info("starting pebble service")
            container.start("portainer")
        else:
            self.unit.status = WaitingStatus('waiting for container to start')
            logger.info("waiting for container to start, update pebble deferred")
            event.defer()

    def _on_config_changed(self, event):
        """Handles the configuration changes"""
        logger.info("configuring charm")
        # self.model.config is the aggregated config in the current runtime
        logger.debug(f"current config: {self._config} vs future config: {self.model.config}")
        if not self._validate_config(self.model.config):
            self.unit.status = WaitingStatus('waiting for a valid config')
            logger.info("waiting for a valid config, configuration deferred")
            event.defer()
            return
        # merge the runtime config with stored one
        new_config = { **self._config, **self.model.config }
        if new_config != self._config:
            if not self._k8s_auth():
                self.unit.status = WaitingStatus('waiting for k8s auth')
                logger.info("waiting for k8s auth, configuration deferred")
                event.defer()
                return
            self._patch_k8s_service_by_config(new_config)
        # update pebble if service type is changed to or from nodeport
        if (new_config[CONFIG_SERVICETYPE] != self._config[CONFIG_SERVICETYPE]
            and (new_config[CONFIG_SERVICETYPE] == SERVICETYPE_NP 
                or self._config[CONFIG_SERVICETYPE] == SERVICETYPE_NP)):
            self._update_pebble(event, new_config)
        # set the config
        self._config = new_config
        logger.debug(f"merged config: {self._config}")

    def _start_portainer(self, _):
        """Function to handle starting Portainer using Pebble"""
        # Get a reference to the portainer workload container
        container = self.unit.get_container("portainer")
        with container.is_ready():
            svc = container.get_services().get("portainer", None)
            # Check if the service is already running
            if not svc:
                # Add a new layer
                container.add_layer("portainer", self._build_layer_by_config(self._config), combine=True)
                container.start("portainer")

            self.unit.status = ActiveStatus()

    def _upgrade_charm(self, _):
        """Handle charm upgrade"""
        logger.info(f"upgrading from {self._stored.charm_version} to {CHARM_VERSION}")
        if CHARM_VERSION < self._stored.charm_version:
            logger.error("downgrade is not supported")
        elif CHARM_VERSION == self._stored.charm_version:
            logger.info("nothing to upgrade")
        else:
            # upgrade logic here
            logger.info("nothing to upgrade")

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

    def _replace_k8s_service_by_config(self, new_config: dict):
        """Replace k8s service by stored config."""
        logger.info("replacing k8s service by config")
        logger.debug(f"replacing by config: {new_config}")
        api = kubernetes.client.CoreV1Api(kubernetes.client.ApiClient())
        # a direct replacement of /spec won't work, since it misses things like cluster_ip;
        # need to get the existing config, replace the key parts inside then submit.
        existing = None
        try:
            existing = api.read_namespaced_service(
                name="portainer",
                namespace=self.namespace,
            )
        except kubernetes.client.exceptions.ApiException as e:
            if e.status == 404:
                logger.info("portainer service doesn't exist, skip patching")
                return
            else:
                raise e
        if not existing:
            logger.info("portainer service doesn't exist, skip patching")
            return
        replace = self._build_k8s_spec_by_config(new_config)
        existing.spec.type = replace.spec.type
        existing.spec.ports = replace.spec.ports
        api.replace_namespaced_service(
            name="portainer", 
            namespace=self.namespace, 
            body=existing,
        )

    # Issue with this method:
    # _build_k8s_spec_by_config generates the object that leaves 'None'
    # when stringified, e.g. {'cluster_ip': None,'external_i_ps': None,'external_name': None},
    # causing k8s complaining: Invalid value: []core.IPFamily(nil): primary ipFamily can not be unset
    def _patch_k8s_service_by_config(self, new_config: dict):
        """Patch k8s service by stored config."""
        logger.info("updating k8s service by config")
        client = kubernetes.client.ApiClient()
        api = kubernetes.client.CoreV1Api(client)
        
        # a direct replacement of /spec won't work, since it misses things like cluster_ip;
        # need to serialize the object to dictionay then clean none entries to replace bits by bits.
        spec = utils.clean_nones(
            client.sanitize_for_serialization(
                self._build_k8s_spec_by_config(new_config)))
        body = []
        for k, v in spec.items():
            body.append({
                "op": "replace",
                "path": f"/spec/{k}",
                "value": v,
            })
        logger.debug(f"patching with body: {body}")
        if body:
            api.patch_namespaced_service(
                name="portainer",
                namespace=self.namespace,
                body=body,
            )
        else:
            logger.info("nothing to patch, skip patching")
            return
    
    def _create_k8s_service_by_config(self):
        """Delete then create k8s service by stored config."""
        logger.info("creating k8s service")
        api = kubernetes.client.CoreV1Api(kubernetes.client.ApiClient())
        try:
            api.delete_namespaced_service(name="portainer", namespace=self.namespace)
        except kubernetes.client.exceptions.ApiException as e:
            if e.status == 404:
                logger.info("portainer service doesn't exist, skip deletion")
            else:
                raise e
        api.create_namespaced_service(
            namespace=self.namespace,
            body=self._build_k8s_service_by_config(self._config),
        )

    def _create_k8s_service_account(self) -> bool:
        """Delete then create the service accounts needed by Portainer"""
        logger.info("creating k8s service account")
        SERVICEACCOUNT_NAME = "portainer-sa-clusteradmin"
        CLUSTERRB_NAME = "portainer"
        CLUSTERROLE_NAME = "cluster-admin"
        client = kubernetes.client.ApiClient()
        api = kubernetes.client.CoreV1Api(client)
        rbac = kubernetes.client.RbacAuthorizationV1Api(client)
        # check cluster role, make sure it exists
        try:
            rbac.read_cluster_role(name=CLUSTERROLE_NAME)
        except kubernetes.client.exceptions.ApiException as e:
            if e.status == 404:
                logger.error(f"{CLUSTERROLE_NAME} cluster role doesn't exist, please make sure RBAC is enabled in k8s cluster.")
                return False
            else:
                raise e
        # creates service account
        try:
            api.delete_namespaced_service_account(name=SERVICEACCOUNT_NAME, namespace=self.namespace)
        except kubernetes.client.exceptions.ApiException as e:
            if e.status == 404:
                logger.info(f"{SERVICEACCOUNT_NAME} service account doesn't exist, skip deletion")
            else:
                raise e
        api.create_namespaced_service_account(
            namespace=self.namespace,
            body=kubernetes.client.V1ServiceAccount(
                api_version="v1",
                metadata=kubernetes.client.V1ObjectMeta(
                    namespace=self.namespace,
                    name=SERVICEACCOUNT_NAME,
                    labels={
                        "app.kubernetes.io/name": self.app.name,
                        "app.kubernetes.io/instance": self.app.name,
                        "app.kubernetes.io/version": SERVICE_VERSION,
                    },
                ),
            ),
        )
        # create cluster role binding with the service account
        logger.info("creating k8s cluster role binding")
        try:
            rbac.delete_cluster_role_binding(name=CLUSTERRB_NAME)
        except kubernetes.client.exceptions.ApiException as e:
            if e.status == 404:
                logger.info(f"{CLUSTERRB_NAME} cluster role binding doesn't exist, skip deletion")
            else:
                raise e
        rbac.create_cluster_role_binding(
            body = kubernetes.client.V1ClusterRoleBinding(
                api_version="rbac.authorization.k8s.io/v1",
                metadata=kubernetes.client.V1ObjectMeta(
                    namespace=self.namespace,
                    name=self.app.name,
                    labels={
                        "app.kubernetes.io/name": self.app.name,
                        "app.kubernetes.io/instance": self.app.name,
                        "app.kubernetes.io/version": SERVICE_VERSION,
                    },
                ),
                role_ref=kubernetes.client.V1RoleRef(
                    api_group="rbac.authorization.k8s.io",
                    kind="ClusterRole",
                    name=CLUSTERROLE_NAME,
                ),
                subjects=[
                    kubernetes.client.V1Subject(
                        kind="ServiceAccount",
                        namespace=self.namespace,
                        name=SERVICEACCOUNT_NAME,
                    ),
                ],
            )
        )
        return True

    def _validate_config(self, config: dict) -> bool:
        """Validates the input config"""
        if config.get(CONFIG_SERVICETYPE) not in (SERVICETYPE_CIP, SERVICETYPE_LB, SERVICETYPE_NP):
            logger.error(f"config - service type {config.get(CONFIG_SERVICETYPE)} is not recognized")
            return False
        if config.get(CONFIG_SERVICEHTTPPORT) is None or config.get(CONFIG_SERVICEEDGEPORT) is None:
            logger.error(f"config - service http or edge port cannot be None")
            return False
        if config.get(CONFIG_SERVICEHTTPPORT) == config.get(CONFIG_SERVICEEDGEPORT):
            logger.error(f"config - service http and edge port cannot be the same")
            return False
        if (config.get(CONFIG_SERVICEHTTPNODEPORT) == config.get(CONFIG_SERVICEEDGENODEPORT)
            and config.get(CONFIG_SERVICEHTTPNODEPORT) is not None):
            logger.error(f"config - service http and edge node port cannot be the same")
            return False
        return True

    def _build_k8s_service_by_config(self, config: dict) -> kubernetes.client.V1Service:
        """Constructs k8s service spec by input config"""
        return kubernetes.client.V1Service(
            api_version="v1",
            metadata=kubernetes.client.V1ObjectMeta(
                namespace=self.namespace,
                name=self.app.name,
                labels={
                    "io.portainer.kubernetes.application.stack": self.app.name,
                    "app.kubernetes.io/name": self.app.name,
                    "app.kubernetes.io/instance": self.app.name,
                    "app.kubernetes.io/version": SERVICE_VERSION,
                },
            ),
            spec=self._build_k8s_spec_by_config(config),
        )

    def _build_k8s_spec_by_config(self, config: dict) -> kubernetes.client.V1ServiceSpec:
        """Constructs k8s service spec by input config"""
        service_type = config[CONFIG_SERVICETYPE]
        http_port = kubernetes.client.V1ServicePort(
            name="http",
            port=config[CONFIG_SERVICEHTTPPORT],
            target_port=9000,
        )
        if (service_type == SERVICETYPE_NP 
            and CONFIG_SERVICEHTTPNODEPORT in config):
            http_port.node_port = config[CONFIG_SERVICEHTTPNODEPORT]

        edge_port = kubernetes.client.V1ServicePort(
            name="edge",
            port=config[CONFIG_SERVICEEDGEPORT],
            target_port=8000,
        )
        if (service_type == SERVICETYPE_NP 
            and CONFIG_SERVICEEDGENODEPORT in config):
            edge_port.node_port = config[CONFIG_SERVICEEDGENODEPORT]
        
        result = kubernetes.client.V1ServiceSpec(
            type=service_type,
            ports=[
                http_port,
                edge_port,
            ],
            selector={
                "app.kubernetes.io/name": self.app.name,
            },
        )
        logger.debug(f"generating spec: {result}")
        return result

    def _build_layer_by_config(self, config: dict) -> dict:
        """Returns a pebble layer by config"""
        cmd = "/portainer"
        if (config[CONFIG_SERVICETYPE] == SERVICETYPE_NP 
            and CONFIG_SERVICEEDGENODEPORT in config):
            cmd = f"{cmd} --tunnel-port {config[CONFIG_SERVICEEDGENODEPORT]}"
        return {
            "services": {
                "portainer": {
                    "override": "replace",
                    "command": cmd,
                    "startup": "enabled",
                }
            },
        }

    @property
    def _config(self) -> dict:
        """Returns the stored config"""
        return self._stored.config

    @_config.setter
    def _config(self, config: dict):
        """Sets the stored config to input"""
        self._stored.config = config

    @property
    def _default_config(self) -> dict:
      """Returns the default config of this charm, which sets:

      - service.type to LoadBalancer
      - service.httpPort to 9000
      - service.edgePort to 8000
      """
      return {
          CONFIG_SERVICETYPE: SERVICETYPE_LB,
          CONFIG_SERVICEHTTPPORT: 9000,
          CONFIG_SERVICEEDGEPORT: 8000,
      }

    @property
    def namespace(self) -> str:
        """Fetch the current Kubernetes namespace by reading it from the service account"""
        with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace", "r") as f:
            return f.read().strip()


if __name__ == "__main__":
    main(PortainerCharm, use_juju_for_storage=True)
