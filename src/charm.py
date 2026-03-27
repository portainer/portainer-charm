#!/usr/bin/env python3
# Copyright 2021 Portainer.io
# See LICENSE file for licensing details.

"""A Juju charm for Portainer."""

import logging
import sys

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, MaintenanceStatus, WaitingStatus

from config import ChangeType, PortainerConfig
from k8s_service import K8sService
from pebble_service import PebbleService

# disable bytecode caching according to: https://discourse.charmhub.io/t/upgrading-a-charm/1131
sys.dont_write_bytecode = True
logger = logging.getLogger(__name__)
# Reduce the log output from the Kubernetes library
# logging.getLogger("kubernetes").setLevel(logging.INFO)
CHARM_VERSION = 1.0


class PortainerCharm(CharmBase):
    """A Juju charm for Portainer."""

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        logger.info(
            f"initialising charm, version: {CHARM_VERSION}",
        )
        # setup default config value, only create if not exist
        self._stored.set_default(
            charm_version=CHARM_VERSION,
            config=PortainerConfig.default().to_dict(),
        )
        logger.debug(f"start with config: {self._config}")
        # hooks up events
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.start, self._start_portainer)
        self.framework.observe(self.on.upgrade_charm, self._upgrade_charm)
        self.framework.observe(self.on.portainer_pebble_ready, self._start_portainer)

    def _on_install(self, event):
        """Handle the install event, create Kubernetes resources."""
        # scaling isn't currently supported so the running instance
        # requires to be a leader.
        if not self.unit.is_leader():
            logger.warn("portainer must work as a leader, waiting for leadership")
            self.unit.status = WaitingStatus("waiting for leadership")
            event.defer()
            return
        if not K8sService.k8s_auth():
            self.unit.status = WaitingStatus("waiting for k8s auth")
            logger.info("waiting for k8s auth, installation deferred")
            event.defer()
            return
        self.unit.status = MaintenanceStatus("creating kubernetes service for portainer")
        K8sService.create_k8s_service_by_config(self._app_name, self._config)
        if not K8sService.create_k8s_service_account(self._app_name):
            self.unit.status = WaitingStatus("waiting for service account perconditions")
            logger.info("waiting for service account perconditions, installation deferred")
            event.defer()
            return

    def _on_config_changed(self, event):
        """Handles the configuration changes."""
        # self.model.config is the aggregated config in the current runtime
        logger.debug(f"current config: {self._config} vs future config: {self.model.config}")
        _new_config = PortainerConfig(self.model.config)
        # validate new config
        _config_errors = _new_config.validate()
        if _config_errors:
            self.unit.status = WaitingStatus("waiting for a valid config")
            logger.info(f"waiting for a valid config, current errors: {', '.join(_config_errors)}")
            event.defer()
            return
        # get config changes
        _changes = self._config.compare(_new_config)
        # patch k8s service when service config changes
        if ChangeType.CHANGE_SERVICE in _changes:
            if not K8sService.k8s_auth():
                self.unit.status = WaitingStatus("waiting for k8s auth")
                logger.info("waiting for k8s auth, configuration deferred")
                event.defer()
                return
            K8sService.patch_k8s_service_by_config(self._app_name, _new_config)
        # update pebble when cli related config changes
        if ChangeType.CHANGE_CLI in _changes:
            if PebbleService.update_service(self.unit, _new_config):
                logger.info("pebble service updated")
            else:
                self.unit.status = WaitingStatus("waiting for container to start")
                logger.info("waiting for container to start, configuration deferred")
                event.defer()
                return
        # set the config
        self._config = _new_config
        logger.debug(f"merged config: {self._config}")

    def _start_portainer(self, _):
        """Function to handle starting Portainer using Pebble."""
        if PebbleService.start_service(self.unit, self._config):
            self.unit.status = ActiveStatus()

    def _upgrade_charm(self, _):
        """Handle charm upgrade."""
        logger.info(f"upgrading from {self._stored.charm_version} to {CHARM_VERSION}")
        if CHARM_VERSION < self._stored.charm_version:
            logger.error("downgrade is not supported")
        elif CHARM_VERSION == self._stored.charm_version:
            logger.info("nothing to upgrade")
        else:
            # upgrade logic here
            logger.info("nothing to upgrade")

    @property
    def _app_name(self) -> str:
        """Returns: the current app name."""
        return self.app.name

    @property
    def _config(self) -> PortainerConfig:
        """Returns: the stored config."""
        return PortainerConfig(self._stored.config)

    @_config.setter
    def _config(self, config: PortainerConfig):
        """Sets the stored config to input."""
        self._stored.config = config.to_dict()


if __name__ == "__main__":
    main(PortainerCharm, use_juju_for_storage=True)
