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
import requests
import jenkins
from urllib.parse import urlparse


def execute(command):
    ''' Execute a command with its parameters and return the exit code '''
    try:
        return subprocess.check_call([command], stderr=subprocess.STDOUT,
                                     shell=True)
    except subprocess.CalledProcessError as excp:
        return excp.returncode


def check_connectivity_ping(url):
    ''' Check if the script can access resources at IBM Cloud'''
    domain = urlparse(url).netloc
    ip = (domain.split(":")[0])
    print("INFO: checking the Jenkins server availability...")
    tentative = 0
    for tentative in range(5):
        if execute("ping -c 1 " + ip) == 0:
            print("INFO: Jenkins is accessible...")
            return True
        elif tentative >= 5:
            print("ERROR: Jenkins is NOT accessible...")
            return False
        else:
            tentative += tentative


def check_connectivity(url):
    ''' Check if the script can access Jenkins'''
    return requests.head(url).status_code == 200


def jenkins_action(jenkins_action="none"):
    ''' Execute the proper Jenkins action'''

    if jenkins_action is not "none":
        action = jenkins_action
    else:
        action = os.getenv("ACTION")

    jenkins_job_parameters = {
        'REQUESTOR_EMAIL': os.getenv("REQUESTOR_EMAIL"),
        'OPENSHIFT_VERSION': os.getenv("OPENSHIFT_VERSION"),
        'CLUSTER_ID': os.getenv("CLUSTER_ID"),
        'OPENSHIFT_CLUSTER_FLAVOR': os.getenv("OPENSHIFT_CLUSTER_FLAVOR")
    }

    if action == "create":
        jenkins_job_name = "ibmcloud-powervs-ocp-actions/ibmcloud-powervs-redhat-cluster-deploy"
        run_jenkins(jenkins_job_name, jenkins_job_parameters)
    elif action == "destroy":
        jenkins_job_name = "ibmcloud-powervs-ocp-actions/ibmcloud-powervs-redhat-cluster-destroy"
        run_jenkins(jenkins_job_name, jenkins_job_parameters)
    else:
        sys.exit("ERROR: option " + action + " is not supported.")


def run_jenkins(job_name, parameters):
    ''' Run Jenkins job and waits for its completition'''

    jenkins_url = os.getenv("POWERVS_JENKINS_URL")
    jenkins_user = os.getenv("POWERVS_JENKINS_USER")
    jenkins_token = os.getenv("POWERVS_JENKINS_TOKEN")

    if not check_connectivity_ping(jenkins_url):
        sys.exit("ERROR: could not reach " + jenkins_url)

    # connect to the jenkins instance
    print("INFO: connecting to the Jenkins instance...")
    jenkins_server = jenkins.Jenkins(jenkins_url, username=jenkins_user,
                                     password=jenkins_token, timeout=45)

    # collects the Jenkins version to indicate it is available
    user = jenkins_server.get_whoami()
    version = jenkins_server.get_version()

    # wait for at least 30 seconds for Jenkins to be ready
    if version:
        print('Hello %s from Jenkins %s' % (user['fullName'], version))

        # get the next build number, which will be the one we want to monitor
        next_build_number = jenkins_server.get_job_info(job_name)[
            'nextBuildNumber']
        jenkins_server.build_job(job_name, parameters, jenkins_url)
        print("INFO: Jenkins job started...")

        # give Jenkins sometime to process the request and queue the job
        time.sleep(45)

        # monitor the build
        result = "none"
        counter = 0
        while result != 'SUCCESS':
            build_info = jenkins_server.get_build_info(
                job_name, next_build_number)
            result = build_info['result']
            url = jenkins_server.get_job_info(job_name)['url']

            counter = (counter + 1)
            print("*", end="", flush=True)

            # avoid too many calls
            time.sleep(45)

            if result == 'SUCCESS':
                print("\nINFO: success, job completed!")
                for atf in build_info['artifacts']:
                    file_url = str(atf['relativePath'])
                    file_name = str(atf['fileName'])
                    if file_name.endswith('.tar'):
                        print(url + str(next_build_number) +
                              "/artifact/" + file_url)
                        full_url = (url + str(next_build_number) +
                                    "/artifact/" + file_url)
                        execute("cd /tmp && wget --auth-no-challenge --user=" +
                                jenkins_user + " --password=" + jenkins_token + " " + str(full_url))
                        execute("mkdir -p /tmp/output; tar -xvf /tmp/" +
                                file_name + " -C /tmp/output")
                        execute("mv /tmp/output/" + os.path.splitext(file_name)
                                [0] + "/*" + " /tmp/output")
                    else:
                        sys.exit(
                            "ERROR: could not locate the cluster build artifact.")
            elif result == 'FAILURE':
                print ("CLUSTER BUILD FAILED: " + url)
                print(jenkins_server.get_build_console_output(
                    job_name, next_build_number))
                jenkins_action("destroy")
                sys.exit("ERROR: build failed.")
    else:
        sys.exit("ERROR: Jenkins failed to be respond, cancelling.")


def main():
    '''Calls the main execution function.'''
    jenkins_action()


if __name__ == "__main__":
    sys.exit(main())
