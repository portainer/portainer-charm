# Copyright 2021 Portainer.io
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing


import unittest
from unittest.mock import Mock, patch

from config import PortainerConfig
from pebble_service import PebbleService


class TestPebbleService(unittest.TestCase):
    # When start_service cannot connect to the container
    # Then it doesn't add the layer nor starts the service, and returns False
    def test_start_service_can_not_connect(self):
        _container = Mock()
        _unit = Mock()
        _unit.get_container.return_value = _container
        _container.can_connect.return_value = False
        _config = PortainerConfig.default()

        result = PebbleService.start_service(_unit, _config)

        _container.can_connect.assert_called_once()
        _container.add_layer.assert_not_called()
        _container.start.assert_not_called()
        self.assertFalse(result)

    # When start_service can connect to the container and has a service running
    # Then it adds the layer, starts the service, returns True
    @patch("pebble_service.PebbleService._build_layer_by_config")
    def test_start_service_can_connect_no_service(self, mock_config_build):
        _container = Mock()
        _unit = Mock()
        _service = Mock()
        _unit.get_container.return_value = _container
        _container.can_connect.return_value = True
        _container.get_services.return_value = _service
        _service.get.return_value = False
        _config = PortainerConfig.default()
        mock_config_build.return_value = {}

        result = PebbleService.start_service(_unit, _config)

        _container.can_connect.assert_called_once()
        _service.get.assert_called_with(PebbleService.PEBBLE_SERVICE, None)
        mock_config_build.assert_called_with(_config)
        _container.add_layer.assert_called_with(PebbleService.PEBBLE_SERVICE, {}, combine=True)
        _container.start.assert_called_with(PebbleService.PEBBLE_SERVICE)
        self.assertTrue(result)

    # When start_service can connect to the container and doesn't have a service running
    # Then it doesn't add the layer nor starts the service, but returns True
    def test_start_service_can_connect_service_exists(self):
        _container = Mock()
        _unit = Mock()
        _service = Mock()
        _unit.get_container.return_value = _container
        _container.can_connect.return_value = True
        _container.get_services.return_value = _service
        _service.get.return_value = True
        _config = PortainerConfig.default()

        result = PebbleService.start_service(_unit, _config)

        _container.can_connect.assert_called_once()
        _service.get.assert_called_with(PebbleService.PEBBLE_SERVICE, None)
        _container.add_layer.assert_not_called()
        _container.start.assert_not_called()
        self.assertTrue(result)

    # When update_service cannot connect to the container
    # Then it doesn't add the layer nor restarts the service, and returns False
    def test_update_service_can_not_connect(self):
        _container = Mock()
        _unit = Mock()
        _unit.get_container.return_value = _container
        _container.can_connect.return_value = False
        _config = PortainerConfig.default()

        result = PebbleService.update_service(_unit, _config)

        _container.can_connect.assert_called_once()
        _container.add_layer.assert_not_called()
        _container.restart.assert_not_called()
        self.assertFalse(result)

    # When update_service can connect to the container
    # Then it adds the layer, restarts the service, returns True
    @patch("pebble_service.PebbleService._build_layer_by_config")
    def test_update_service_can_connect(self, mock_config_build):
        _container = Mock()
        _unit = Mock()
        _unit.get_container.return_value = _container
        _container.can_connect.return_value = True
        _config = PortainerConfig.default()
        mock_config_build.return_value = {}

        result = PebbleService.update_service(_unit, _config)

        _container.can_connect.assert_called_once()
        mock_config_build.assert_called_with(_config)
        _container.add_layer.assert_called_with(PebbleService.PEBBLE_SERVICE, {}, combine=True)
        _container.restart.assert_called_with(PebbleService.PEBBLE_SERVICE)
        self.assertTrue(result)

    # When building config with edge node not set
    # Then it returns just portainer cmd
    def test_build_layer_non_edge(self):
        _config = Mock()
        _config.is_edge_node_port_configured.return_value = False

        result = PebbleService._build_layer_by_config(_config)

        self.assertDictEqual(
            result,
            {
                "services": {
                    PebbleService.PEBBLE_SERVICE: {
                        "override": "replace",
                        "command": "/portainer",
                        "startup": "enabled",
                    }
                },
            },
        )

    # When building config with edge node set
    # Then it returns just portainer cmd with edge parameters
    def test_build_layer_edge(self):
        _config = Mock()
        _config.is_edge_node_port_configured.return_value = True
        _config.service_edge_node_port = 9999

        result = PebbleService._build_layer_by_config(_config)

        self.assertDictEqual(
            result,
            {
                "services": {
                    PebbleService.PEBBLE_SERVICE: {
                        "override": "replace",
                        "command": f"/portainer --tunnel-port {_config.service_edge_node_port}",
                        "startup": "enabled",
                    }
                },
            },
        )
