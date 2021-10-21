#!/usr/bin/env python3
# Copyright 2021 Portainer.io
# See LICENSE file for licensing details.

"""Pebble service for Portainer."""

import logging

from ops import model

from config import PortainerConfig

logger = logging.getLogger(__name__)


class PebbleService:
    """Pebble service for Portainer."""

    CONTAINER_NAME = "portainer"
    PEBBLE_SERVICE = CONTAINER_NAME

    @classmethod
    def start_service(cls, unit: model.Unit, config: PortainerConfig) -> bool:
        """Start Portainer Pebble service.

        Returns: whether the service is started successfully or not.
        """
        # get a reference to the portainer workload container
        container = unit.get_container(cls.CONTAINER_NAME)
        if container.can_connect():
            svc = container.get_services().get(cls.PEBBLE_SERVICE, None)
            # Check if the service is already running
            if not svc:
                # Add a new layer
                container.add_layer(
                    cls.PEBBLE_SERVICE, cls._build_layer_by_config(config), combine=True
                )
                container.start(cls.PEBBLE_SERVICE)
            return True
        else:
            return False

    @classmethod
    def update_service(cls, unit: model.Unit, config: PortainerConfig) -> bool:
        """Update Portainer Pebble service.

        Returns: whether the service is updated successfully or not.
        """
        # get a reference to the portainer workload container
        container = unit.get_container(cls.CONTAINER_NAME)
        if container.can_connect():
            # override existing layer
            container.add_layer(
                cls.PEBBLE_SERVICE, cls._build_layer_by_config(config), combine=True
            )
            container.restart(cls.PEBBLE_SERVICE)
            return True
        else:
            return False

    @classmethod
    def _build_layer_by_config(cls, config: PortainerConfig) -> dict:
        """Construct pebble layer from the input config.

        Returns: a pebble layer dictionary by config.
        """
        cmd = "/portainer"
        if config.is_edge_node_port_configured():
            cmd = f"{cmd} --tunnel-port {config.service_edge_node_port}"
        return {
            "services": {
                cls.PEBBLE_SERVICE: {
                    "override": "replace",
                    "command": cmd,
                    "startup": "enabled",
                }
            },
        }
