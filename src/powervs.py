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


def check_connectivity(url):
    ''' Check if the script can access Jenkins'''
    return requests.head(url).status_code == 200


def execute(command):
    ''' Execute a command with its parameters and return the exit code '''
    try:
        return subprocess.check_call([command], stderr=subprocess.STDOUT,
                                     shell=True)
    except subprocess.CalledProcessError as excp:
        return excp.returncode


def jenkins_action():
    ''' Execute the proper Jenkins action'''

    action = os.getenv("ACTION")
    jenkins_job_parameters = {
        'REQUESTOR_EMAIL': os.getenv("REQUESTOR_EMAIL"),
        'OPENSHIFT_VERSION': os.getenv("OPENSHIFT_VERSION"),
        'CLUSTER_ID': os.getenv("CLUSTER_ID"),
        'OPENSHIFT_CLUSTER_FLAVOR': os.getenv("OPENSHIFT_CLUSTER_FLAVOR")
    }

    if action == "create":
        jenkins_job_name = "powervs-clusters/new-cluster-from-rh"
        run_jenkins(jenkins_job_name, jenkins_job_parameters)
    elif action == "destroy":
        jenkins_job_name = "powervs-clusters/clear-cluster"
        run_jenkins(jenkins_job_name, jenkins_job_parameters)
    else:
        sys.exit("ERROR: option " + action + " is not supported.")


def run_jenkins(job_name, parameters):
    ''' Run Jenkins job and waits for its completition'''

    jenkins_url = os.getenv("POWERVS_JENKINS_URL")
    jenkins_user = os.getenv("POWERVS_JENKINS_USER")
    jenkins_token = os.getenv("POWERVS_JENKINS_TOKEN")

    if check_connectivity(jenkins_url):
        sys.exit("Could not reach " + jenkins_url)

    # connect to the jenkins instance
    jenkins_server = jenkins.Jenkins(jenkins_url, username=jenkins_user,
                                     password=jenkins_token, timeout=60)

    # get the next build number, which will be the one we want to monitor
    next_build_number = jenkins_server.get_job_info(job_name)[
        'nextBuildNumber']
    print("Job Started...")
    jenkins_server.build_job(job_name, parameters, jenkins_url)

    # give Jenkins sometime to process the request and queue the job
    time.sleep(45)

    # monitor the build
    result = "none"
    counter = 0
    while result != 'SUCCESS':

        build_info = jenkins_server.get_build_info(job_name, next_build_number)
        result = build_info['result']
        url = jenkins_server.get_job_info(job_name)['url']

        counter = (counter + 1)
        print("*", end="", flush=True)

        # avoid too many calls
        time.sleep(45)

        if result == 'SUCCESS':
            print("\nSUCCESS: cluster build completed.")
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
            print(jenkins_server.get_build_console_output(
                job_name, next_build_number))
            sys.exit("ERROR: build failed.")


def main():
    '''Calls the main execution function.'''
    jenkins_action()


if __name__ == "__main__":
    sys.exit(main())
