# -*- coding: utf-8 -*-

"""
Copyright (C) 2021 IBM Corporation
    Contributors:
        * Rafael Peria de Sene <rpsene@br.ibm.com>
"""

import os
import sys
import time
import subprocess
from urllib.parse import urlparse

import jenkins


def execute(command):
    ''' Execute a command with its parameters and return the exit code '''
    try:
        return subprocess.check_call([command], stderr=subprocess.STDOUT,shell=True)
    except subprocess.CalledProcessError as excp:
        return excp.returncode


def check_connectivity_ping(url):
    ''' Check if the script can access resources at IBM Cloud'''
    domain = urlparse(url).netloc
    server_ip = (domain.split(":")[0])
    print("INFO: Checking the Jenkins server availability...")
    tentative = 0
    for tentative in range(5):
        if execute("ping -c 1 " + server_ip) == 0:
            print("INFO: Jenkins is accessible...")
            return True
        elif tentative >= 5:
            print("ERROR: Jenkins is NOT accessible...")
            return False
        tentative += tentative


def download_tar_artifact(jenkins_user,jenkins_token,artifact_url):
    ''' Download artifacts from a Jenkins job '''
    artifact = artifact_url.split("/")[-1]

    wget="cd /tmp &&"
    wget=wget+" wget --progress=bar:force:noscroll --auth-no-challenge"
    wget=wget+" --user=" + jenkins_user + " --password=" + jenkins_token
    wget=wget+" " + str(artifact_url)

    if execute(wget) == 0:
        print("INFO: Cluster access artifact was downloaded.")
        if execute("mkdir -p /tmp/output; tar -xvf /tmp/" + artifact + " -C /tmp/output") == 0:
            print("INFO: Cluster access artifact was extracted.")
            # os.path.splitext removes the .tar from the file name
            move="mv /tmp/output/" + os.path.splitext(artifact)[0]
            move=move+"/*" + " /tmp/output"
            if execute(move) == 0:
                print("INFO: Cluster access artifact was moved.")
            else:
                sys.exit("ERROR: Could NOT move the artifact files to the target location.")
        else:
            sys.exit("ERROR: Could NOT extract the artifact files to the target location.")
    else:
        sys.exit("ERROR: Could NOT download the cluster access artifact.")


def connect_to_jenkins():
    '''Check if Jenkins is ready to be used'''

    jenkins_url = get_jenkins_server_parameters()["POWERVS_JENKINS_URL"]
    jenkins_user = get_jenkins_server_parameters()["POWERVS_JENKINS_USER"]
    jenkins_token = get_jenkins_server_parameters()["POWERVS_JENKINS_TOKEN"]

    is_jenkins_available = False

    if not check_connectivity_ping(jenkins_url):
        print("ERROR: Could not reach " + jenkins_url)
        is_jenkins_available = False
    else:
        # connecting to the jenkins instance
        print("INFO: Connecting to the Jenkins instance...")
        jenkins_server = jenkins.Jenkins(jenkins_url, username=jenkins_user,
                                     password=jenkins_token, timeout=45)

        # collects the Jenkins version to indicate it is available
        user = jenkins_server.get_whoami()
        version = jenkins_server.get_version()

        if version:
            print('Hello %s from Jenkins %s' % (user['fullName'], version))
            is_jenkins_available = True
    return [is_jenkins_available,jenkins_server]


def get_jenkins_job_parameters():
    ''' Parameters for executing a Jenkins job '''
    jenkins_job_parameters = {
        'REQUESTOR_EMAIL': os.getenv("REQUESTOR_EMAIL"),
        'OPENSHIFT_VERSION': os.getenv("OPENSHIFT_VERSION"),
        'CLUSTER_ID': os.getenv("CLUSTER_ID"),
        'OPENSHIFT_CLUSTER_FLAVOR': os.getenv("OPENSHIFT_CLUSTER_FLAVOR")
    }
    return jenkins_job_parameters


def get_jenkins_server_parameters():
    ''' Parameters to connect to a Jenkins server '''
    jenkins_server_parameters = {
        'POWERVS_JENKINS_URL': os.getenv("POWERVS_JENKINS_URL"),
        'POWERVS_JENKINS_USER': os.getenv("POWERVS_JENKINS_USER"),
        'POWERVS_JENKINS_TOKEN': os.getenv("POWERVS_JENKINS_TOKEN")
    }
    return jenkins_server_parameters


def get_jenkins_jobs_names():
    ''' Jenkins jobs names '''
    jenkins_server_parameters = {
        'POOL': "ibmcloud-powervs-pool-of-clusters/get-cluster-from-pool",
        'CREATE': "ibmcloud-powervs-pool-of-clusters/populate-pool",
        'DESTROY': "ibmcloud-powervs-pool-of-clusters/destroy-cluster",
        'TAKEN': "ibmcloud-powervs-pool-of-clusters/set-cluster-from-pool-as-allocated",
    }
    return jenkins_server_parameters


def action(jenkins_action="none"):
    ''' Execute the proper Jenkins action'''

    is_jenkins_available = connect_to_jenkins()
    if is_jenkins_available[0]:
        # Reads the action value from env if not
        # set by user when calling jenkins_actions
        if jenkins_action != "none":
            jk_action = jenkins_action
        else:
            jk_action = os.getenv("ACTION")

        if jk_action == "create":
            create_cluster(is_jenkins_available[1])
        elif jk_action == "destroy":
            destroy_cluster(is_jenkins_available[1])
        else:
            sys.exit("ERROR: option " + jk_action + " is not supported.")
    else:
        sys.exit("ERROR: Jenkins failed to respond, cancelling.")


def set_cluster_as_taken(cluster_id,jenkins_server):
    ''' Update the DB enty setting a given cluster as taken '''
    jenkins_url = get_jenkins_server_parameters()["POWERVS_JENKINS_URL"]
    jenkins_job_name = get_jenkins_jobs_names()["TAKEN"]

    parameters = {
        'CLUSTER_ID': cluster_id
    }

    next_build_number = jenkins_server.get_job_info(jenkins_job_name)[
        'nextBuildNumber']
    jenkins_server.build_job(jenkins_job_name, parameters, jenkins_url)
    print("INFO: Setting cluster from pool as taken...")

    # Give Jenkins sometime to process the request and queue the job
    time.sleep(25)

    # Monitor the build
    result = "none"
    counter = 0
    while result != 'SUCCESS':
        build_info = jenkins_server.get_build_info(
            jenkins_job_name, next_build_number)
        result = build_info['result']
        url = jenkins_server.get_job_info(jenkins_job_name)['url']

        counter = (counter + 1)
        print("*", end="", flush=True)

        # avoid too many calls
        time.sleep(30)
        if result == 'SUCCESS':
            print("\nINFO: Jenkins job to set cluster from pool as taken was completed!")
        elif result == 'FAILURE':
            print ("ERROR: " + url)
            print(jenkins_server.get_build_console_output(jenkins_job_name, next_build_number))
            sys.exit("ERROR: Could not set cluster from pool as taken.")


def get_cluster_from_pool(jenkins_server):
    ''' Look for an available cluster in the pool of clusters '''
    jenkins_url = get_jenkins_server_parameters()["POWERVS_JENKINS_URL"]
    jenkins_user = get_jenkins_server_parameters()["POWERVS_JENKINS_USER"]
    jenkins_token = get_jenkins_server_parameters()["POWERVS_JENKINS_TOKEN"]
    jenkins_job_name = get_jenkins_jobs_names()["POOL"]

    next_build_number = jenkins_server.get_job_info(jenkins_job_name)[
            'nextBuildNumber']
    jenkins_server.build_job(jenkins_job_name, get_jenkins_job_parameters(), jenkins_url)
    print("INFO: Trying to get a cluster from the pool...")

    # Give Jenkins sometime to process the request and queue the job
    time.sleep(25)
    cluster_available_in_pool = False

    # Monitor the build
    result = "none"
    counter = 0
    while result != 'SUCCESS':
        build_info = jenkins_server.get_build_info(jenkins_job_name, next_build_number)
        result = build_info['result']
        url = jenkins_server.get_job_info(jenkins_job_name)['url']

        counter = (counter + 1)
        print("*", end="", flush=True)

        # Avoid too many calls to the Jenkins server
        time.sleep(30)

        if result == 'SUCCESS':
            print("\nINFO: Jenkins job to collect available clusters in the pool was completed!")
            for atf in build_info['artifacts']:
                file_url = str(atf['relativePath'])
                file_name = str(atf['fileName'])
                if file_name.endswith('.info'):
                    full_url = (url + str(next_build_number) +
                                "/artifact/" + file_url)
                    execute("cd /tmp && wget --auth-no-challenge --user=" +
                            jenkins_user + " --password=" + jenkins_token + " " + str(full_url))
                    # Check if the .info contains none, which is the indication
                    # that the pool of cluster is empty and we need to create a
                    # new cluster
                    with open("/tmp/"+file_name) as file_to_read:
                        first_line = file_to_read.readline()
                        if "none" in first_line:
                            print("WARNING: The pool is empty, creating a new cluster!")
                            cluster_available_in_pool = False
                        else:
                            cluster_id = first_line.split(",")[0].rstrip()
                            artifact_url = first_line.split(",")[1].rstrip()
                            download_tar_artifact(jenkins_user,jenkins_token,artifact_url)
                            set_cluster_as_taken(cluster_id,jenkins_server)
                            cluster_available_in_pool = True
                else:
                    print("ERROR: Could not locate information about the pool of clusters.")
                    cluster_available_in_pool = False
        elif result == 'FAILURE':
            print("ERROR: We failed trying to talk with the queue manager.")
            print("ERROR: " + url)
            print("WARNING: A new OCP cluster will be created.")
            print(jenkins_server.get_build_console_output(jenkins_job_name, next_build_number))
            cluster_available_in_pool = False
    return cluster_available_in_pool


def create_cluster(jenkins_server):
    ''' Creates a new cluster if none available '''
    if not get_cluster_from_pool(jenkins_server):
        jenkins_url = get_jenkins_server_parameters()["POWERVS_JENKINS_URL"]
        jenkins_user = get_jenkins_server_parameters()["POWERVS_JENKINS_USER"]
        jenkins_token = get_jenkins_server_parameters()["POWERVS_JENKINS_TOKEN"]
        jenkins_job_name = get_jenkins_jobs_names()["CREATE"]

        next_build_number = jenkins_server.get_job_info(jenkins_job_name)['nextBuildNumber']
        jenkins_server.build_job(jenkins_job_name, get_jenkins_job_parameters(),jenkins_url)
        print("INFO: Creating a new cluster...")

        # Give Jenkins some time to process the request and queue the job
        time.sleep(45)

        # Monitor the build
        result = "none"
        counter = 0
        while result != 'SUCCESS':
            build_info = jenkins_server.get_build_info(jenkins_job_name, next_build_number)
            result = build_info['result']
            url = jenkins_server.get_job_info(jenkins_job_name)['url']

            counter = (counter + 1)
            print("*", end="", flush=True)

            # Avoid too many calls to the Jenkins server
            time.sleep(30)

            if result == 'SUCCESS':
                print("\nINFO: Jenkins job to create a new cluster was completed!")
                for atf in build_info['artifacts']:
                    file_url = str(atf['relativePath'])
                    file_name = str(atf['fileName'])
                    if file_name.endswith('.tar'):
                        full_url = (url + str(next_build_number) +
                                    "/artifact/" + file_url)
                        download_tar_artifact(jenkins_user,jenkins_token,full_url)
                        cluster_id = file_name.replace("-access-details.tar","")
                        set_cluster_as_taken(cluster_id,jenkins_server)
                    else:
                        print("ERROR: Could not download the cluster access credentials.")
                        print("WARNING: Deleting allocated resources.")
                        destroy_cluster(jenkins_server,cluster_id)
                        sys.exit("ERROR: New cluster build failed.")
            elif result == 'FAILURE':
                print("ERROR: We could not create a new cluster.")
                print("ERROR: " + url)
                print(jenkins_server.get_build_console_output(jenkins_job_name, next_build_number))
                sys.exit("ERROR: New cluster build failed.")


def destroy_cluster(jenkins_server,cluster_id="none"):
    ''' Destroy a cluster '''
    jenkins_url = get_jenkins_server_parameters()["POWERVS_JENKINS_URL"]
    jenkins_job_name = get_jenkins_jobs_names()["DESTROY"]

    next_build_number = jenkins_server.get_job_info(jenkins_job_name)[
        'nextBuildNumber']

    if cluster_id != "none":
        jenkins_job_parameters = {
            'CLUSTER_ID': cluster_id,
        }
        print("INFO: Destroying the cluster " + cluster_id)
        jenkins_server.build_job(jenkins_job_name, jenkins_job_parameters, jenkins_url)
    else:
        # Get the values for cluster_id from the environment variables.
        jenkins_server.build_job(jenkins_job_name, get_jenkins_job_parameters(), jenkins_url)
        print("INFO: Destroying the cluster " +  get_jenkins_job_parameters()["CLUSTER_ID"])

    # Give Jenkins some time to process the request and queue the job
    time.sleep(25)

    # Monitor the build
    result = "none"
    counter = 0
    while result != 'SUCCESS':
        build_info = jenkins_server.get_build_info(jenkins_job_name, next_build_number)
        result = build_info['result']
        url = jenkins_server.get_job_info(jenkins_job_name)['url']

        counter = (counter + 1)
        print("*", end="", flush=True)

        # Avoid too many calls to the Jenkins server
        time.sleep(30)
        if result == 'SUCCESS':
            print("\nINFO: Jenkins job to delete a cluster was completed!")
        elif result == 'FAILURE':
            print("\nINFO: Jenkins job to delete a cluster FAILED!")
            print("ERROR: Cluster was NOT deleted.")
            print("WARNING: Garbage collector will destroy it within 12-24 hours.")
            print("ERROR: " + url)
            print(jenkins_server.get_build_console_output(jenkins_job_name, next_build_number))


def main():
    '''Calls the main execution function.'''
    action()


if __name__ == "__main__":
    sys.exit(main())
