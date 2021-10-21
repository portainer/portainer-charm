# Copyright 2021 Portainer.io
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing


import unittest

from config import ChangeType, PortainerConfig


class TestConfig(unittest.TestCase):
    def test_service_type(self):
        r1 = PortainerConfig({"service_type": "LoadBalancer"}).service_type
        r2 = PortainerConfig({"service_type": "NotExist"}).service_type
        r3 = PortainerConfig({"service_type": None}).service_type
        r4 = PortainerConfig({}).service_type

        self.assertEqual(r1, "LoadBalancer")
        self.assertFalse(r2, None)
        self.assertFalse(r3, None)
        self.assertFalse(r4, None)

    def test_service_http_port(self):
        r1 = PortainerConfig({"service_http_port": 8888}).service_http_port
        r2 = PortainerConfig({"service_http_port": None}).service_http_port
        r3 = PortainerConfig({}).service_http_port

        self.assertEqual(r1, 8888)
        self.assertFalse(r2, None)
        self.assertFalse(r3, None)

    def test_service_http_node_port(self):
        r1 = PortainerConfig({"service_http_node_port": 7777}).service_http_node_port
        r2 = PortainerConfig({"service_http_node_port": None}).service_http_node_port
        r3 = PortainerConfig({}).service_http_node_port

        self.assertEqual(r1, 7777)
        self.assertFalse(r2, None)
        self.assertFalse(r3, None)

    def test_service_edge_port(self):
        r1 = PortainerConfig({"service_edge_port": 6666}).service_edge_port
        r2 = PortainerConfig({"service_edge_port": None}).service_edge_port
        r3 = PortainerConfig({}).service_edge_port

        self.assertEqual(r1, 6666)
        self.assertFalse(r2, None)
        self.assertFalse(r3, None)

    def test_service_edge_node_port(self):
        r1 = PortainerConfig({"service_edge_node_port": 5555}).service_edge_node_port
        r2 = PortainerConfig({"service_edge_node_port": None}).service_edge_node_port
        r3 = PortainerConfig({}).service_edge_node_port

        self.assertEqual(r1, 5555)
        self.assertFalse(r2, None)
        self.assertFalse(r3, None)

    def test_compare_service_change(self):
        c11 = PortainerConfig({"service_type": "LoadBalancer"})
        c12 = PortainerConfig({"service_type": "ClusterIP"})
        c21 = PortainerConfig({"service_http_port": 1111})
        c22 = PortainerConfig({"service_http_port": 2222})
        c31 = PortainerConfig({"service_http_node_port": 1111})
        c32 = PortainerConfig({"service_http_node_port": 2222})
        c41 = PortainerConfig({"service_edge_port": 1111})
        c42 = PortainerConfig({"service_edge_port": 2222})
        c51 = PortainerConfig({"service_edge_node_port": 1111})
        c52 = PortainerConfig({"service_edge_node_port": 2222})

        self.assertSetEqual(c11.compare(c12), {ChangeType.CHANGE_SERVICE})
        self.assertSetEqual(c21.compare(c22), {ChangeType.CHANGE_SERVICE})
        self.assertSetEqual(c31.compare(c32), {ChangeType.CHANGE_SERVICE})
        self.assertSetEqual(c41.compare(c42), {ChangeType.CHANGE_SERVICE})
        self.assertSetEqual(c51.compare(c52), {ChangeType.CHANGE_SERVICE})

    def test_compare_cli_change(self):
        c11 = PortainerConfig({"service_type": "LoadBalancer"})
        c12 = PortainerConfig({"service_type": "NodePort"})
        c21 = PortainerConfig({"service_type": "NodePort"})
        c22 = PortainerConfig({"service_type": "ClusterIP"})

        self.assertTrue(ChangeType.CHANGE_CLI in c11.compare(c12))
        self.assertTrue(ChangeType.CHANGE_CLI in c21.compare(c22))

    def test_compare_mix(self):
        c11 = PortainerConfig(
            {
                "service_type": "LoadBalancer",
                "service_http_node_port": 1111,
                "service_edge_node_port": 3333,
                "service_edge_port": 5555,
            }
        )
        c12 = PortainerConfig(
            {
                "service_type": "NodePort",
                "service_http_node_port": 2222,
                "service_edge_node_port": 4444,
                "service_edge_port": 5555,
            }
        )
        c21 = PortainerConfig(
            {
                "service_type": "LoadBalancer",
                "service_edge_node_port": 3333,
            }
        )
        c22 = PortainerConfig(
            {
                "service_type": "LoadBalancer",
                "service_http_node_port": 2222,
            }
        )
        c31 = PortainerConfig(
            {
                "service_type": "LoadBalancer",
                "service_http_node_port": 1111,
                "service_edge_node_port": 3333,
                "service_edge_port": 5555,
            }
        )
        c32 = PortainerConfig(
            {
                "service_type": "LoadBalancer",
                "service_http_node_port": 1111,
                "service_edge_node_port": 3333,
                "service_edge_port": 5555,
            }
        )

        self.assertSetEqual(c11.compare(c12), {ChangeType.CHANGE_SERVICE, ChangeType.CHANGE_CLI})
        self.assertSetEqual(c21.compare(c22), {ChangeType.CHANGE_SERVICE})
        self.assertEqual(len(c31.compare(c32)), 0)

    def test_merge(self):
        c1 = PortainerConfig(
            {
                "service_type": "LoadBalancer",
                "service_http_node_port": 1111,
                "service_edge_node_port": 2222,
                "service_http_port": 3333,
            }
        )
        c2 = PortainerConfig(
            {
                "service_type": "NodePort",
                "service_http_node_port": 1111,
                "service_edge_node_port": 3333,
                "service_edge_port": 4444,
            }
        )

        r = PortainerConfig(
            {
                "service_type": "NodePort",
                "service_http_node_port": 1111,
                "service_edge_node_port": 3333,
                "service_http_port": 3333,
                "service_edge_port": 4444,
            }
        )

        c1.merge(c2)

        self.assertDictEqual(c1.to_dict(), r.to_dict())

    def test_validate_service_types(self):
        c1 = PortainerConfig(
            {
                "service_type": "LoadBalancer",
                "service_http_port": 3333,
                "service_edge_port": 4444,
            }
        )
        c2 = PortainerConfig(
            {
                "service_type": "NotExist",
                "service_http_port": 3333,
                "service_edge_port": 4444,
            }
        )
        c3 = PortainerConfig(
            {
                "service_type": None,
                "service_http_port": 3333,
                "service_edge_port": 4444,
            }
        )
        c4 = PortainerConfig(
            {
                "service_http_port": 3333,
                "service_edge_port": 4444,
            }
        )

        self.assertEqual(len(c1.validate()), 0)
        self.assertEqual(len(c2.validate()), 1)
        self.assertEqual(len(c3.validate()), 1)
        self.assertEqual(len(c4.validate()), 1)

    def test_validate_ports(self):
        c1 = PortainerConfig(
            {
                "service_type": "LoadBalancer",
                "service_http_port": 3333,
                "service_edge_port": 4444,
            }
        )
        c2 = PortainerConfig(
            {
                "service_type": "LoadBalancer",
                "service_http_port": 3333,
            }
        )
        c3 = PortainerConfig(
            {
                "service_type": "LoadBalancer",
                "service_edge_port": 4444,
            }
        )
        c4 = PortainerConfig(
            {
                "service_type": "LoadBalancer",
                "service_http_port": 3333,
                "service_edge_port": 3333,
            }
        )

        self.assertEqual(len(c1.validate()), 0)
        self.assertEqual(len(c2.validate()), 1)
        self.assertEqual(len(c3.validate()), 1)
        self.assertEqual(len(c4.validate()), 1)

    def test_validate_node_ports(self):
        c1 = PortainerConfig(
            {
                "service_type": "LoadBalancer",
                "service_http_port": 3333,
                "service_edge_port": 4444,
            }
        )
        c2 = PortainerConfig(
            {
                "service_type": "LoadBalancer",
                "service_http_port": 3333,
                "service_edge_port": 4444,
                "service_http_node_port": 5555,
            }
        )
        c3 = PortainerConfig(
            {
                "service_type": "LoadBalancer",
                "service_http_port": 3333,
                "service_edge_port": 4444,
                "service_edge_node_port": 5555,
            }
        )
        c4 = PortainerConfig(
            {
                "service_type": "LoadBalancer",
                "service_http_port": 3333,
                "service_edge_port": 4444,
                "service_http_node_port": 5555,
                "service_edge_node_port": 5555,
            }
        )

        self.assertEqual(len(c1.validate()), 0)
        self.assertEqual(len(c2.validate()), 0)
        self.assertEqual(len(c3.validate()), 0)
        self.assertEqual(len(c4.validate()), 1)

    def test_validate_mixed(self):
        c1 = PortainerConfig({})
        c2 = PortainerConfig(
            {
                "service_type": "something",
                "service_edge_port": 4444,
                "service_http_node_port": 4444,
            }
        )
        c3 = PortainerConfig(
            {
                "service_type": "something",
                "service_http_port": 3333,
                "service_edge_port": 4444,
                "service_edge_node_port": 5555,
                "service_http_node_port": 5555,
            }
        )

        self.assertEqual(len(c1.validate()), 2)
        self.assertEqual(len(c2.validate()), 2)
        self.assertEqual(len(c3.validate()), 2)

    def test_http_node_port_configured(self):
        c1 = PortainerConfig(
            {
                "service_type": "NodePort",
                "service_http_node_port": 4444,
            }
        )
        c2 = PortainerConfig(
            {
                "service_type": "NodePort",
            }
        )
        c3 = PortainerConfig(
            {
                "service_http_node_port": 4444,
            }
        )
        c4 = PortainerConfig(
            {
                "service_type": "something",
                "service_http_node_port": 4444,
            }
        )

        self.assertTrue(c1.is_http_node_port_configured())
        self.assertFalse(c2.is_http_node_port_configured())
        self.assertFalse(c3.is_http_node_port_configured())
        self.assertFalse(c4.is_http_node_port_configured())

    def test_edge_node_port_configured(self):
        c1 = PortainerConfig(
            {
                "service_type": "NodePort",
                "service_edge_node_port": 4444,
            }
        )
        c2 = PortainerConfig(
            {
                "service_type": "NodePort",
            }
        )
        c3 = PortainerConfig(
            {
                "service_edge_node_port": 4444,
            }
        )
        c4 = PortainerConfig(
            {
                "service_type": "something",
                "service_edge_node_port": 4444,
            }
        )

        self.assertTrue(c1.is_edge_node_port_configured())
        self.assertFalse(c2.is_edge_node_port_configured())
        self.assertFalse(c3.is_edge_node_port_configured())
        self.assertFalse(c4.is_edge_node_port_configured())
