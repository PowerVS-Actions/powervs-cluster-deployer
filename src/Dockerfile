FROM python:3.9

LABEL maintaner="Rafael Peria de Sene - rpsene@br.ibm.com "

RUN apt-get update && apt-get upgrade -y && \
apt-get install -y python3-pip wget && \
pip3 install python-jenkins urllib3

WORKDIR /cluster

ENV ACTION=""
ENV POWERVS_JENKINS_URL=""
ENV POWERVS_JENKINS_USER=""
ENV POWERVS_JENKINS_TOKEN=""
ENV REQUESTOR_EMAIL=""
ENV OPENSHIFT_VERSION=""
ENV OPENSHIFT_CLUSTER_FLAVOR=""

# CLUSTER_ID is used to delete a given cluster.
ENV CLUSTER_ID=""

ADD ./powervs.py ./

CMD ["powervs.py"]

ENTRYPOINT ["/usr/local/bin/python3.9"]
