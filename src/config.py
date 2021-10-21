#!/usr/bin/env python3
# Copyright 2021 Portainer.io
# See LICENSE file for licensing details.

"""Portainer Config Wrapper."""

# from default_enum import DefaultEnumMeta
from __future__ import annotations

from enum import Enum


class ChangeType(str, Enum):
    """Types of Config Change."""

    CHANGE_SERVICE = "K8sServiceChange"
    CHANGE_CLI = "CliParameterChange"


class ServiceType(str, Enum):
    """K8s Service Types."""

    SERVICETYPE_LB = "LoadBalancer"
    SERVICETYPE_CIP = "ClusterIP"
    SERVICETYPE_NP = "NodePort"


class PortainerConfig(object):
    """Portainer Config Wrapper."""

    CONFIG_SERVICETYPE = "service_type"
    CONFIG_SERVICEHTTPPORT = "service_http_port"
    CONFIG_SERVICEHTTPNODEPORT = "service_http_node_port"
    CONFIG_SERVICEEDGEPORT = "service_edge_port"
    CONFIG_SERVICEEDGENODEPORT = "service_edge_node_port"
    DEFAULT_SERVICETYPE = ServiceType.SERVICETYPE_LB
    DEFAULT_SERVICEHTTPPORT = 9000
    DEFAULT_SERVICEEDGEPORT = 8000

    def __init__(self, config: dict) -> None:
        self._config = config
        super().__init__()

    @property
    def service_type(self) -> ServiceType | None:
        """Returns config ServiceType, None if invalid."""
        try:
            return ServiceType(self._config.get(self.CONFIG_SERVICETYPE))
        except Exception:
            return None

    @property
    def service_http_port(self) -> int | None:
        """Returns config http port, None if not set."""
        return self._config.get(self.CONFIG_SERVICEHTTPPORT)

    @property
    def service_http_node_port(self) -> int | None:
        """Returns config http node port, None if not set."""
        return self._config.get(self.CONFIG_SERVICEHTTPNODEPORT)

    @property
    def service_edge_port(self) -> int | None:
        """Returns config edge port, None if not set."""
        return self._config.get(self.CONFIG_SERVICEEDGEPORT)

    @property
    def service_edge_node_port(self) -> int | None:
        """Returns config edge node port, None if not set."""
        return self._config.get(self.CONFIG_SERVICEEDGENODEPORT)

    # @service_type.setter
    # def service_type(self, st: ServiceType):
    #     """Sets service type to target without validation."""
    #     self._config[self.CONFIG_SERVICETYPE] = str(st)

    def compare(self, target: PortainerConfig) -> set[ChangeType]:
        """Compare with another config.

        Returns the set of changes between two, or an empty set.
        """
        changes = set()
        if (
            self.service_type != target.service_type
            or self.service_http_port != target.service_http_port
            or self.service_edge_port != target.service_edge_port
            or self.service_http_node_port != target.service_http_node_port
            or self.service_edge_node_port != target.service_edge_node_port
        ):
            changes.add(ChangeType.CHANGE_SERVICE)
        # cli parameter needs update if service type is changed to or from nodeport
        if self.service_type != target.service_type and (
            self.service_type == ServiceType.SERVICETYPE_NP
            or target.service_type == ServiceType.SERVICETYPE_NP
        ):
            changes.add(ChangeType.CHANGE_CLI)
        return changes

    def merge(self, target: PortainerConfig):
        """Merge the target config into the current one."""
        self._config = {**self._config, **target._config}

    def validate(self) -> list[str]:
        """Validates the contained config.

        Returns: a list of errors or an empty list if none.
        """
        errors = []
        if self.service_type is None:
            errors.append(
                f"config - service type {self._config.get(self.CONFIG_SERVICETYPE)} is not recognized"
            )
        if self.service_http_port is None or self.service_edge_port is None:
            errors.append("config - service http or edge port cannot be None")
        elif self.service_http_port == self.service_edge_port:
            errors.append("config - service http and edge port cannot be the same")
        if (
            self.service_http_node_port == self.service_edge_node_port
            and self.service_http_node_port is not None
        ):
            errors.append("config - service http and edge node port cannot be the same")
        return errors

    def is_http_node_port_configured(self) -> bool:
        """Returns: whether the http node port is configured."""
        return (
            self.service_type == ServiceType.SERVICETYPE_NP
            and self.service_http_node_port is not None
        )

    def is_edge_node_port_configured(self) -> bool:
        """Returns: whether the edge node port is configured."""
        return (
            self.service_type == ServiceType.SERVICETYPE_NP
            and self.service_edge_node_port is not None
        )

    def to_dict(self) -> dict:
        """Returns: a shallow copy of the wrapped dictionary."""
        return self._config.copy()

    def __str__(self):
        """Returns: the string form of the wrapped config."""
        return str(self._config)

    @classmethod
    def default(cls) -> PortainerConfig:
        """Returns: default config."""
        return PortainerConfig(
            {
                cls.CONFIG_SERVICETYPE: cls.DEFAULT_SERVICETYPE,
                cls.CONFIG_SERVICEHTTPPORT: cls.DEFAULT_SERVICEHTTPPORT,
                cls.CONFIG_SERVICEEDGEPORT: cls.DEFAULT_SERVICEEDGEPORT,
            }
        )
