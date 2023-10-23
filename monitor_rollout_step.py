from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport
import json
import time  # for the sleep function
import os
import requests

RUNTIME = os.getenv('RUNTIME')
APPLICATION = os.getenv('APPLICATION')
COMMIT_SHA = os.getenv('COMMIT_SHA')
ROLLOUT = os.getenv('ROLLOUT')
STEP_INDEX = int(str(os.getenv('STEP_INDEX')))

CF_URL = os.getenv('CF_URL', 'https://g.codefresh.io')
CF_API_KEY = os.getenv('CF_API_KEY')
CF_STEP_NAME = os.getenv('CF_STEP_NAME', 'STEP_NAME')
CF_ACCOUNT_ID = ""  # It will be infered later, using the CF_API_KEY

# NAMESPACE   = os.getenv('NAMESPACE')
# NAMESPACE   = 'not-relevant'


#######################################################################


def main():
    parameters = {
        "RUNTIME": RUNTIME,
        "APPLICATION": APPLICATION,
        "COMMIT_SHA": COMMIT_SHA,
        "ROLLOUT": ROLLOUT,
        "STEP_INDEX": STEP_INDEX
    }
    print("Monitoring the following Rollout step: ")
    print(json.dumps(parameters, indent=4), "\n")
    if release_exists() == False:
        raise Exception("Release doesn't exist")
    # Generating link to the Apps Dashboard
    CF_OUTPUT_URL_VAR = CF_STEP_NAME + '_CF_OUTPUT_URL'
    link_to_app = get_link_to_apps_dashboard()
    export_variable(CF_OUTPUT_URL_VAR, link_to_app)

    monitor_rollout_step()

#######################################################################


def get_query(query_name):
    with open('queries/'+query_name+'.graphql', 'r') as file:
        query_content = file.read()
    return gql(query_content)


def get_runtime():
    transport = RequestsHTTPTransport(
        url=CF_URL + '/2.0/api/graphql',
        headers={'authorization': CF_API_KEY},
        verify=True,
        retries=3,
    )
    client = Client(transport=transport, fetch_schema_from_transport=False)
    query = get_query('getRuntime')  # gets gql query
    variables = {
        "runtime": RUNTIME
    }
    runtime = client.execute(query, variable_values=variables)
    return runtime


def get_rollout_step_state():
    transport = RequestsHTTPTransport(
        url=CF_URL + '/2.0/api/graphql',
        headers={'authorization': CF_API_KEY},
        verify=True,
        retries=3,
    )

    client = Client(transport=transport, fetch_schema_from_transport=False)
    query = get_query('get_rolloutstep_status')  # gets gql query

    variables = {}
    variables['runtime'] = RUNTIME
    variables['appNamespace'] = "not relevant"
    variables['appName'] = APPLICATION
    variables['commitSHA'] = COMMIT_SHA
    variables['rollout'] = ROLLOUT
    variables['stepIndex'] = STEP_INDEX

    result = client.execute(query, variable_values=variables)
    rollout_state = {}
    try:
        rollout_state['status'] = result['rolloutStepStatus']['status']
    except TypeError:
        rollout_state['status'] = result['rolloutStepStatus']

    return rollout_state


def get_rollout_resource(runtime_ingress_host):
    transport = RequestsHTTPTransport(
        url=runtime_ingress_host + '/app-proxy/api/graphql',
        headers={'authorization': CF_API_KEY},
        verify=True,
        retries=3,
    )

    client = Client(transport=transport, fetch_schema_from_transport=False)
    query = get_query('get_resource')  # gets gql query

    variables = {
        "application": APPLICATION,
        "kind": "Rollout",
        "name": ROLLOUT,
        "resourceName": ROLLOUT,
        "version": "v1alpha1",
        "group": "argoproj.io"
    }

    result = client.execute(query, variable_values=variables)
    return result


def get_account_id():
    account_id = ""
    url = 'https://g.codefresh.io/api/user'
    headers = {'Authorization': CF_API_KEY,
               'content-type': 'application/json', 'Accept-Charset': 'UTF-8'}
    response = requests.get(url,  headers=headers)
    user_info = response.json()
    account_name = user_info['activeAccountName']
    account_id = [account['id'] for account in user_info['account']
                  if account['name'] == account_name][0]
    return account_id


def release_exists():
    result = False
    rollout_step_state = get_rollout_step_state()
    rollout_step_status = rollout_step_state['status']
    max_retries = 192
    retry_counter = 0
    while rollout_step_status == None and retry_counter < max_retries:
        retry_counter = retry_counter+1
        rollout_step_state = get_rollout_step_state()
        rollout_step_status = rollout_step_state['status']
        print("App, Release, Rollout or Step not found, please check your parameters. | ", end="")
        time.sleep(5)

    if rollout_step_status != None:
        result = True
    return result


def export_variable(var_name, var_value):
    # if this script is executed in CF build
    if os.getenv('CF_BUILD_ID') != None:
        # exporting var when used as a freestyle step
        path = str(os.getenv('CF_VOLUME_PATH'))
        with open(path+'/env_vars_to_export', 'a') as a_writer:
            a_writer.write(var_name + "=" + var_value+'\n')
        # exporting var when used as a plugin
        with open('/meta/env_vars_to_export', 'a') as a_writer:
            a_writer.write(var_name + "=" + var_value+'\n')

    print("Exporting variable: "+var_name+"="+var_value)


def get_link_to_apps_dashboard():
    runtime = get_runtime()
    runtime_ns = runtime['runtime']['metadata']['namespace']
    ingress_host = runtime['runtime']['ingressHost']
    rollout_resource = get_rollout_resource(ingress_host)
    rollout_state = json.loads(rollout_resource['resource']['liveState'])
    revision = rollout_state['metadata']['annotations']['rollout.argoproj.io/revision']
    uid = rollout_state['metadata']['uid']
    namespace = rollout_state['metadata']['namespace']
    url_to_app = CF_URL+'/2.0/applications-dashboard/' + \
        runtime_ns+'/'+RUNTIME+'/'+APPLICATION+'/current-state/tree'
    url_to_app += f'?resourceName={ ROLLOUT }&resourceKind=Rollout&resourceVersion=v1alpha1&namespace={ namespace }&resourceGroup=argoproj.io&drawer=app-rollout-details&rdName={ ROLLOUT }&rdAppName={ APPLICATION }&rdAppNamespace={ runtime_ns }&rdRevision={ revision }&rdRuntime={ RUNTIME }&rdUID={ uid }'

    global CF_ACCOUNT_ID
    CF_ACCOUNT_ID = get_account_id()
    if CF_ACCOUNT_ID != "":
        url_to_app += f'&activeAccountId={ CF_ACCOUNT_ID }'

    return url_to_app


def monitor_rollout_step():
    rollout_step_state = get_rollout_step_state()
    rollout_step_status = rollout_step_state['status']

    while rollout_step_status in ['ACTIVE', 'PENDING', 'PAUSED_INCONCLUSIVE']:
        print(f'{ rollout_step_status}, ', end="")
        rollout_step_state = get_rollout_step_state()
        rollout_step_status = rollout_step_state['status']
        time.sleep(5)

    print(f'\nRollout Step Status --> { rollout_step_status }')
    export_variable(CF_STEP_NAME, rollout_step_status)

    if rollout_step_status in ['FAILED', 'TERMINATED']:
        raise Exception(f'Rollout Step status: {rollout_step_status}')


##############################################################

if __name__ == "__main__":
    main()
