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


def run_jenkins(URL, JENKINS_USER, TOKEN, JOB_NAME, PARAMETERS):
    ''' Run Jenkins job and waits for its completition'''

    if check_connectivity (URL):
        sys.exit("Could not reach " + URL)

    # connect to the jenkins instance
    SERVER = jenkins.Jenkins(URL, username=JENKINS_USER, password=TOKEN, timeout=60)
    USER = SERVER.get_whoami()
    VERSION = SERVER.get_version()
    
    print('Hello %s from Jenkins %s' % (USER['fullName'], VERSION))

    # get the next build number, which will be the one we want to monitor
    NEXT_BUILD_NUMBER = SERVER.get_job_info(JOB_NAME)['nextBuildNumber']
    print ("Cluster Build Started...")
    JOB=SERVER.build_job(JOB_NAME,PARAMETERS,TOKEN)

    # give Jenkins sometime to process the request and queue the JOB
    time.sleep(45)

    # monitor the build
    RESULT="none"
    COUNTER=0
    while RESULT != 'SUCCESS':

        BUILD_INFO=SERVER.get_build_info(JOB_NAME, NEXT_BUILD_NUMBER)
        RESULT=BUILD_INFO['result']
        URL = SERVER.get_job_info(JOB_NAME)['url']
        
        COUNTER = (COUNTER + 1)
        print ("*", end = "", flush=True)

        # avoid too many calls
        time.sleep(30)

        if RESULT == 'SUCCESS':
            print ("\nsuccess")
            for atf in BUILD_INFO['artifacts']:
                FILE_NAME=str(atf['fileName'])
                print (URL + str(NEXT_BUILD_NUMBER) + "/artifact/" + FILE_NAME)
                FULL_URL=(URL + str(NEXT_BUILD_NUMBER) + "/artifact/" + FILE_NAME)
                CMD="curl -sS -u " + JENKINS_USER + ":" + TOKEN + " " + str(FULL_URL) + " --output " + FILE_NAME
                execute (CMD)
        elif RESULT == 'FAILURE':
            print (SERVER.get_build_console_output(JOB_NAME, NEXT_BUILD_NUMBER))
            sys.exit("ERROR: build failed.")


def main():
    ''' Main Execution '''
    JENKINS_JOB_PARAMETERS = {
         'IBMCLOUD_API_KEY': os.getenv("IBMCLOUD_API_KEY"), 
         'REQUESTOR_EMAIL': os.getenv("REQUESTOR_EMAIL"),
         'OPENSHIFT_VERSION': os.getenv("OPENSHIFT_VERSION"),
         'CLUSTER_ID': os.getenv("CLUSTER_ID"),
         'IBMCLOUD_REGION': os.getenv("IBMCLOUD_REGION"),
         'IBMCLOUD_ZONE': os.getenv("IBMCLOUD_ZONE"),
         'IBMCLOUD_POWERVS_ID': os.getenv("IBMCLOUD_POWERVS_ID"),
         'OPENSHIFT_BASTION_IMAGE_NAME': os.getenv("OPENSHIFT_BASTION_IMAGE_NAME"),
         'OPENSHIFT_RHCOS_IMAGE_NAME': os.getenv("OPENSHIFT_RHCOS_IMAGE_NAME"),
         'OPENSHIFT_PROCESSOR_TYPE': os.getenv("OPENSHIFT_PROCESSOR_TYPE"),
         'OPENSHIFT_SYSTEM_TYPE': os.getenv("OPENSHIFT_SYSTEM_TYPE"),'OPENSHIFT_PRIVATE_NETWORK_NAME': os.getenv("OPENSHIFT_PRIVATE_NETWORK_NAME"),
         'OPENSHIFT_CLUSTER_DOMAIN': os.getenv("OPENSHIFT_CLUSTER_DOMAIN"),
         'OPENSHIFT_VERSION': os.getenv("OPENSHIFT_VERSION"),
         'OPENSHIFT_CLUSTER_FLAVOR': os.getenv("OPENSHIFT_CLUSTER_FLAVOR"),
         'RHEL_SUBS_USERNAME': os.getenv("RHEL_SUBS_USERNAME"),
         'RHEL_SUBS_PASSWORD': os.getenv("RHEL_SUBS_PASSWORD")
    }

    run_jenkins(os.getenv("JENKINS_URL"), 
    os.getenv("JENKINS_USER"), 
    os.getenv("JENKINS_TOKEN"), 
    os.getenv("JENKINS_JOB_NAME"),
    JENKINS_JOB_PARAMETERS)


if __name__ == "__main__":
    sys.exit(main())