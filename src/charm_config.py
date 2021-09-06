class CharmConfig:
    """Class that wraps charm configuration"""
    
    SERVICETYPE_LB = "LoadBalancer"
    SERVICETYPE_CIP = "ClusterIP"
    SERVICETYPE_NP = "NodePort"
    CONFIG_SERVICETYPE = "service_type"
    CONFIG_SERVICEHTTPPORT = "service_http_port"
    CONFIG_SERVICEHTTPNODEPORT = "service_http_node_port"
    CONFIG_SERVICEEDGEPORT = "service_edge_port"
    CONFIG_SERVICEEDGENODEPORT = "service_edge_node_port"

    def __init__(self, config: dict):
        self._config = config

    @property
    def service_type(self):
