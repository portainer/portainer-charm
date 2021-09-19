# Portainer

## Description

Portainer is a lightweight ‘universal’ management GUI that can be used to easily manage Docker, Swarm, Kubernetes and ACI environments. It is designed to be as simple to deploy as it is to use.

Portainer consists of a single container that can run on any cluster. It can be deployed as a Linux container or a Windows native container.

Portainer allows you to manage all your orchestrator resources (containers, images, volumes, networks and more) through a super-simple graphical interface.

This fully supported version of Portainer is available for business use. Visit http://www.portainer.io to learn more.


## Usage

Create a Juju model for Portainer:

```
juju add-model portainer
```

Deploy Portainer:

```
juju deploy portainer --trust
```

Give Portainer cluster access:

```
juju trust portainer --scope=cluster
```

This will deploy Portainer and expose it over an external load balancer.

To access Portainer inside a browser:

1. Run `juju status` to check the IP of the of the running Portainer application 
2. Navigate to http://IP_ADDRESS:9000

## Configuration

You can deploy Portainer and expose it over ClusterIP if you prefer:

```
juju config portainer service_type=ClusterIP service_http_port=9000 service_edge_port=8000
```

You can also use Node port:

```
juju config portainer service_type=NodePort service_http_port=9000 service_edge_port=8000 service_http_node_port=30777 service_edge_node_port=30776
```

It is also possible to expose Portainer over Ingress:

```
juju config portainer service_type=ClusterIP service_http_port=9000 service_edge_port=8000
juju deploy nginx-ingress-integrator ingress
juju config ingress service-name=portainer service-port=9000
```

## Developing

Create and activate a virtualenv with the development requirements:

```
virtualenv -p python3 venv
source venv/bin/activate
pip install -r requirements-dev.txt
```

Pack with Charmcraft:

```
charmcraft pack
```

## Testing

The Python operator framework includes a very nice harness for testing
operator behaviour without full deployment. Just `run_tests`:

    ./run_tests
