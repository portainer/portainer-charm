# portainer

## TODO

- [x] Service account creation
- [x] Fixed image to ee 2.7.0 (needs to be done when publishing)
- [x] Simple upgrade
- [x] Fill up readme
- [x] Validate config
- [ ] Tests
- [ ] Code cleanups

## Description

Portainer EE is a lightweight ‘universal’ management GUI that can be used to easily manage Docker, Swarm, Kubernetes and ACI environments. It is designed to be as simple to deploy as it is to use.

Portainer consists of a single container that can run on any cluster. It can be deployed as a Linux container or a Windows native container.

Portainer allows you to manage all your orchestrator resources (containers, images, volumes, networks and more) through a super-simple graphical interface.

This fully supported version of Portainer is available for business use. Visit http://www.portainer.io to learn more.

## Usage

### Create a Model for Portainer
juju add-model portainer

### Deploy with Storage (Existing PV)
juju deploy portainer --trust --storage data={your storage-pool},100M,1

### Trust Portainer to have Cluster Access
juju trust portainer --scope=cluster

### Config with Load Balancer (Default)
juju config portainer service_type=LoadBalancer service_http_port=9000 service_edge_port=8000

### Config with ClusterIP
juju config portainer service_type=ClusterIP service_http_port=9000 service_edge_port=8000

### Config with Node Port
juju config portainer service_type=NodePort service_http_port=9000 service_edge_port=8000 service_http_node_port=30777 service_edge_node_port=30776

### Relate with Ingress
juju config portainer service_type=ClusterIP service_http_port=9000 service_edge_port=8000
juju deploy nginx-ingress-integrator ingress
juju config ingress service-name=portainer service-port=9000

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
