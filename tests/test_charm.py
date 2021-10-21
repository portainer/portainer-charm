# Copyright 2021 Portainer.io
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import unittest
from unittest.mock import Mock, PropertyMock, patch

from ops.model import ActiveStatus, WaitingStatus

# from ops.model import WaitingStatus
from ops.testing import Harness

from charm import CHARM_VERSION, PortainerCharm
from config import ChangeType, PortainerConfig

# Given charm is inited as a none leader with init hooks
# class TestNonLeaderInitHooks(unittest.TestCase):
#     def setUp(self):
#         self.harness = Harness(PortainerCharm)
#         self.addCleanup(self.harness.cleanup)
#         self.harness.set_leader(False)
#         self.harness.begin_with_initial_hooks()

#     # When init complete
#     def test_wait_status(self):
#         # Then charm is in waiting status for leadership
#         self.assertIsInstance(self.harness.charm.unit.status, WaitingStatus)

# Given charm is inited as a leader with init hooks
# class TestInitHooks(unittest.TestCase):
#     def setUp(self):
#         self.harness = Harness(PortainerCharm)
#         self.addCleanup(self.harness.cleanup)
#         self.harness.set_leader(True)
#         self.harness.begin_with_initial_hooks()

# Given charm is inited as a leader without init hooks


def assert_not_any_call(self, *args, **kwargs):
    try:
        self.assert_any_call(*args, **kwargs)
    except AssertionError:
        return
    raise AssertionError(
        "Expected %s to not have been called." % self._format_mock_call_signature(args, kwargs)
    )


Mock.assert_not_any_call = assert_not_any_call


class TestWithoutInitHooks(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(PortainerCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.set_leader(True)
        self.harness.begin()

    # When init complete
    def test_store_init(self):
        # Then charm's store should have charm version and config set
        self.assertEqual(self.harness.charm._stored.charm_version, CHARM_VERSION)
        self.assertDictEqual(
            self.harness.charm._stored.config._under, PortainerConfig.default().to_dict()
        )

    # When install is called
    @patch("charm.K8sService.create_k8s_service_account")
    @patch("charm.K8sService.create_k8s_service_by_config")
    @patch("charm.K8sService.k8s_auth")
    def test_installation(self, auth, create_service, create_account):
        config = PortainerConfig({})
        m_config = PropertyMock(return_value=config)
        type(self.harness.charm)._config = m_config

        self.harness.charm.on.install.emit()

        # Then k8s is authenticated
        auth.assert_called_once()
        create_service.assert_called_with(self.harness.charm._app_name, config)
        create_account.assert_called_with(self.harness.charm._app_name)

    # When install is called but current unit is not leader
    @patch("charm.logger")
    @patch("charm.K8sService.create_k8s_service_account")
    @patch("charm.K8sService.create_k8s_service_by_config")
    @patch("charm.K8sService.k8s_auth")
    def test_installation_not_leader(self, auth, create_service, create_account, logger):
        self.harness.set_leader(False)

        self.harness.charm.on.install.emit()

        # Then charm is in waiting status
        self.assertIsInstance(self.harness.charm.unit.status, WaitingStatus)
        logger.warn.assert_called_once()
        auth.assert_not_called()
        create_service.assert_not_called()
        create_account.assert_not_called()

    # When install is called but k8s auth failed
    @patch("charm.K8sService.create_k8s_service_account")
    @patch("charm.K8sService.create_k8s_service_by_config")
    @patch("charm.K8sService.k8s_auth")
    def test_installation_auth_failed(self, auth, create_service, create_account):
        auth.return_value = False

        self.harness.charm.on.install.emit()

        # Then charm is in waiting status
        self.assertIsInstance(self.harness.charm.unit.status, WaitingStatus)
        auth.assert_called_once()
        create_service.assert_not_called()
        create_account.assert_not_called()

    # When install is called but create service account failed
    @patch("charm.K8sService.create_k8s_service_account")
    @patch("charm.K8sService.create_k8s_service_by_config")
    @patch("charm.K8sService.k8s_auth")
    def test_installation_account_failed(self, auth, create_service, create_account):
        config = PortainerConfig({})
        m_config = PropertyMock(return_value=config)
        type(self.harness.charm)._config = m_config
        create_account.return_value = False

        self.harness.charm.on.install.emit()

        # Then charm is in waiting status
        self.assertIsInstance(self.harness.charm.unit.status, WaitingStatus)
        auth.assert_called_once()
        create_service.assert_called_with(self.harness.charm._app_name, config)
        create_account.assert_called_with(self.harness.charm._app_name)

    # When start event is emitted and pebble starts successfully
    @patch("charm.PebbleService.start_service")
    def test_start(self, start_pebble):
        config = PortainerConfig({})
        m_config = PropertyMock(return_value=config)
        type(self.harness.charm)._config = m_config
        start_pebble.return_value = True

        self.harness.charm.on.start.emit()

        # Then charm is in waiting status
        self.assertIsInstance(self.harness.charm.unit.status, ActiveStatus)
        start_pebble.assert_called_with(self.harness.charm.unit, config)

    # When config_change event is emitted but no change compared to existing one
    @patch("charm.PebbleService.update_service")
    @patch("charm.K8sService.patch_k8s_service_by_config")
    @patch("charm.K8sService.k8s_auth")
    @patch("charm.PortainerConfig")
    def test_config_valid_no_change(self, pc, auth, patch_service, update_pebble):
        old_config = Mock()
        p_config = PropertyMock(return_value=old_config)
        type(self.harness.charm)._config = p_config
        old_config.compare.return_value = []
        # valid config
        new_config = pc.return_value
        new_config.validate.return_value = []

        self.harness.update_config({})

        # config is set to the new one, but services are not called
        new_config.validate.assert_called_once()
        old_config.compare.assert_called_once()
        p_config.assert_any_call(new_config)
        auth.assert_not_called()
        patch_service.assert_not_called()
        update_pebble.assert_not_called()

    # When config_change event is emitted but target config is invalid
    @patch("charm.PebbleService.update_service")
    @patch("charm.K8sService.patch_k8s_service_by_config")
    @patch("charm.K8sService.k8s_auth")
    @patch("charm.PortainerConfig")
    def test_config_invalid(self, pc, auth, patch_service, update_pebble):
        old_config = Mock()
        p_config = PropertyMock(return_value=old_config)
        type(self.harness.charm)._config = p_config
        old_config.compare.return_value = []
        # invalid config
        new_config = pc.return_value
        new_config.validate.return_value = ["error"]

        self.harness.update_config({})

        # config is not set and services are not called
        self.assertIsInstance(self.harness.charm.unit.status, WaitingStatus)
        new_config.validate.assert_called_once()
        old_config.compare.assert_not_called()
        p_config.assert_not_any_call(new_config)
        auth.assert_not_called()
        patch_service.assert_not_called()
        update_pebble.assert_not_called()

    # When config_change event is emitted with valid changes
    @patch("charm.PebbleService.update_service")
    @patch("charm.K8sService.patch_k8s_service_by_config")
    @patch("charm.K8sService.k8s_auth")
    @patch("charm.PortainerConfig")
    def test_config_valid_change(self, pc, auth, patch_service, update_pebble):
        old_config = Mock()
        p_config = PropertyMock(return_value=old_config)
        type(self.harness.charm)._config = p_config
        old_config.compare.return_value = [ChangeType.CHANGE_SERVICE, ChangeType.CHANGE_CLI]
        # valid config
        new_config = pc.return_value
        new_config.validate.return_value = []

        self.harness.update_config({})

        # config is set to the new one and services are called
        new_config.validate.assert_called_once()
        old_config.compare.assert_called_once()
        p_config.assert_any_call(new_config)
        auth.assert_called_once()
        patch_service.assert_called_with(self.harness.charm._app_name, new_config)
        update_pebble.assert_called_with(self.harness.charm.unit, new_config)

    # When config_change event is emitted with valid changes but k8s auth failed
    @patch("charm.PebbleService.update_service")
    @patch("charm.K8sService.patch_k8s_service_by_config")
    @patch("charm.K8sService.k8s_auth")
    @patch("charm.PortainerConfig")
    def test_config_auth_failed(self, pc, auth, patch_service, update_pebble):
        old_config = Mock()
        p_config = PropertyMock(return_value=old_config)
        type(self.harness.charm)._config = p_config
        old_config.compare.return_value = [ChangeType.CHANGE_SERVICE, ChangeType.CHANGE_CLI]
        # valid config
        new_config = pc.return_value
        new_config.validate.return_value = []
        auth.return_value = False

        self.harness.update_config({})

        # config is not set and service in wait
        self.assertIsInstance(self.harness.charm.unit.status, WaitingStatus)
        new_config.validate.assert_called_once()
        old_config.compare.assert_called_once()
        p_config.assert_not_any_call(new_config)
        auth.assert_called_once()
        patch_service.assert_not_called()
        update_pebble.assert_not_called()

    # When config_change event is emitted with valid changes but pebble update failed
    @patch("charm.PebbleService.update_service")
    @patch("charm.K8sService.patch_k8s_service_by_config")
    @patch("charm.K8sService.k8s_auth")
    @patch("charm.PortainerConfig")
    def test_config_pebble_failed(self, pc, auth, patch_service, update_pebble):
        old_config = Mock()
        p_config = PropertyMock(return_value=old_config)
        type(self.harness.charm)._config = p_config
        old_config.compare.return_value = [ChangeType.CHANGE_CLI]
        # valid config
        new_config = pc.return_value
        new_config.validate.return_value = []
        update_pebble.return_value = False

        self.harness.update_config({})

        # config is not set and service in wait
        self.assertIsInstance(self.harness.charm.unit.status, WaitingStatus)
        new_config.validate.assert_called_once()
        old_config.compare.assert_called_once()
        p_config.assert_not_any_call(new_config)
        auth.assert_not_called()
        patch_service.assert_not_called()
        update_pebble.assert_called_with(self.harness.charm.unit, new_config)

    # when upgrade to a lower version
    @patch("charm.logger")
    def test_upgrade(self, logger):
        self.harness.charm._stored.charm_version = 999

        self.harness.charm.on.upgrade_charm.emit()

        # then it should log error
        logger.error.assert_called_once()

    # def test_config_changed(self):
    #     self.assertEqual(list(self.harness.charm._stored.things), [])
    #     self.harness.update_config({"thing": "foo"})
    #     self.assertEqual(list(self.harness.charm._stored.things), ["foo"])

    # def test_action(self):
    #     # the harness doesn't (yet!) help much with actions themselves
    #     action_event = Mock(params={"fail": ""})
    #     self.harness.charm._on_fortune_action(action_event)

    #     self.assertTrue(action_event.set_results.called)

    # def test_action_fail(self):
    #     action_event = Mock(params={"fail": "fail this"})
    #     self.harness.charm._on_fortune_action(action_event)

    #     self.assertEqual(action_event.fail.call_args, [("fail this",)])

    # def test_httpbin_pebble_ready(self):
    #     # Check the initial Pebble plan is empty
    #     initial_plan = self.harness.get_container_pebble_plan("httpbin")
    #     self.assertEqual(initial_plan.to_yaml(), "{}\n")
    #     # Expected plan after Pebble ready with default config
    #     expected_plan = {
    #         "services": {
    #             "httpbin": {
    #                 "override": "replace",
    #                 "summary": "httpbin",
    #                 "command": "gunicorn -b 0.0.0.0:80 httpbin:app -k gevent",
    #                 "startup": "enabled",
    #                 "environment": {"thing": "🎁"},
    #             }
    #         },
    #     }
    #     # Get the httpbin container from the model
    #     container = self.harness.model.unit.get_container("httpbin")
    #     # Emit the PebbleReadyEvent carrying the httpbin container
    #     self.harness.charm.on.httpbin_pebble_ready.emit(container)
    #     # Get the plan now we've run PebbleReady
    #     updated_plan = self.harness.get_container_pebble_plan("httpbin").to_dict()
    #     # Check we've got the plan we expected
    #     self.assertEqual(expected_plan, updated_plan)
    #     # Check the service was started
    #     service = self.harness.model.unit.get_container("httpbin").get_service("httpbin")
    #     self.assertTrue(service.is_running())
    #     # Ensure we set an ActiveStatus with no message
    #     self.assertEqual(self.harness.model.unit.status, ActiveStatus())
