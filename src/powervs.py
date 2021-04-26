import os
import sys
import time
import jenkins
import requests
import subprocess


def check_connectivity(URL):
    return requests.head(URL).status_code == 200


def execute(command):
    ''' Execute a command with its parameters and return the exit code '''
    try:
        return subprocess.check_call([command], stderr=subprocess.STDOUT,
                                     shell=True)
    except subprocess.CalledProcessError as excp:
        return excp.returncode


def jenkins_action():

    ACTION = os.getenv("ACTION")

    JENKINS_JOB_PARAMETERS = {
        'REQUESTOR_EMAIL': os.getenv("REQUESTOR_EMAIL"),
        'OPENSHIFT_VERSION': os.getenv("OPENSHIFT_VERSION"),
        'CLUSTER_ID': os.getenv("CLUSTER_ID"),
        'OPENSHIFT_CLUSTER_FLAVOR': os.getenv("OPENSHIFT_CLUSTER_FLAVOR")
    }

    if ACTION == "create":
        JENKINS_JOB_NAME = "powervs-clusters/new-cluster-from-rh"
        run_jenkins(os.getenv("POWERVS_JENKINS_URL"),
                    os.getenv("POWERVS_JENKINS_USER"),
                    os.getenv("POWERVS_JENKINS_TOKEN"),
                    JENKINS_JOB_NAME,
                    JENKINS_JOB_PARAMETERS)
    elif ACTION == "destroy":
        JENKINS_JOB_NAME = "powervs-clusters/clear-cluster"
        run_jenkins(os.getenv("POWERVS_JENKINS_URL"),
                os.getenv("POWERVS_JENKINS_USER"),
                os.getenv("POWERVS_JENKINS_TOKEN"),
                JENKINS_JOB_NAME,
                JENKINS_JOB_PARAMETERS,)
    else:
        sys.exit("ERROR: option " + ACTION + " is not supported.")


def run_jenkins(URL, JENKINS_USER, TOKEN, JOB_NAME, PARAMETERS):
    ''' Run Jenkins job and waits for its completition'''

    if check_connectivity(URL):
        sys.exit("Could not reach " + URL)

    # connect to the jenkins instance
    SERVER = jenkins.Jenkins(URL, username=JENKINS_USER,
                             password=TOKEN, timeout=60)
    VERSION = SERVER.get_version()

    print('Hello from Jenkins %s' % (VERSION))

    # get the next build number, which will be the one we want to monitor
    NEXT_BUILD_NUMBER = SERVER.get_job_info(JOB_NAME)['nextBuildNumber']
    print("Job Started...")
    JOB = SERVER.build_job(JOB_NAME, PARAMETERS, TOKEN)

    # give Jenkins sometime to process the request and queue the JOB
    time.sleep(45)

    # monitor the build
    RESULT = "none"
    COUNTER = 0
    while RESULT != 'SUCCESS':

        BUILD_INFO = SERVER.get_build_info(JOB_NAME, NEXT_BUILD_NUMBER)
        RESULT = BUILD_INFO['result']
        URL = SERVER.get_job_info(JOB_NAME)['url']

        COUNTER = (COUNTER + 1)
        print("*", end="", flush=True)

        # avoid too many calls
        time.sleep(30)

        if RESULT == 'SUCCESS':
            print("\nsuccess")
            for atf in BUILD_INFO['artifacts']:
                FILE_NAME = str(atf['fileName'])
                print(URL + str(NEXT_BUILD_NUMBER) + "/artifact/" + FILE_NAME)
                FULL_URL = (URL + str(NEXT_BUILD_NUMBER) +
                            "/artifact/" + FILE_NAME)
                CMD = "cd /tmp && curl -sS -OL --progress-bar -u " + \
                    JENKINS_USER + ":" + TOKEN + " " + str(FULL_URL)
                execute(CMD)
        elif RESULT == 'FAILURE':
            print(SERVER.get_build_console_output(JOB_NAME, NEXT_BUILD_NUMBER))
            sys.exit("ERROR: build failed.")


def main():
    jenkins_action()


if __name__ == "__main__":
    sys.exit(main())
