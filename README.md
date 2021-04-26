# powervs-jenkins
A simple combination of Python, Jenkins and Docker to easily deploy anything in PowerVS

## Build the container image

```
docker build -t pvs-jenkins .
```

## Set the variables

```
vi ./src/variables

The parameters can be set according the Jenkins job you plan to use.
```

## Run

```
docker run --rm -v ${PWD}/artifacts:/tmp --env-file ./variables pvs-jenkins:latest
```
