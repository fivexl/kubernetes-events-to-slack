#!/usr/bin/env python3

import os
import time
import json
import logging
import http.client
import kubernetes

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def read_env_variable_or_die(env_var_name):
    value = os.environ.get(env_var_name, '')
    if value == '':
        message = 'Env variable {} is not defined or set to empty string. Set it to non-empty string and try again'.format(env_var_name)
        logger.error(message)
        raise EnvironmentError(message)
    return value


# Slack web hook example
# https://hooks.slack.com/services/XXXXXXX/XXXXXXX/XXXXXXXXXXXX
def post_slack_message(hook_url, message):
    logger.info('Posting the following message to {}:\n{}'.format(hook_url, message))
    headers = {'Content-type': 'application/json'}
    connection = http.client.HTTPSConnection('hooks.slack.com')
    connection.request('POST',
                       hook_url.replace('https://hooks.slack.com', ''),
                       message,
                       headers)
    response = connection.getresponse()
    print(response.read().decode())


# Return even reason in upper case to keep it consistent
# no matter how API changes
def get_event_reason(event):
    return event['object'].reason.upper()


def format_k8s_event_to_slack_message(event_object, notify=''):
    event = event_object['object']
    message = {
        'attachments': [{
            'color': '#36a64f',
            'title': event.message,
            'text': 'event type: {}, event reason: {}'.format(event_object['type'], event.reason),
            'footer': 'First time seen: {}, Last time seen: {}, Count: {}'.format(event.first_timestamp.strftime('%d/%m/%Y %H:%M:%S %Z'),
                                                                                  event.last_timestamp.strftime('%d/%m/%Y %H:%M:%S %Z'),
                                                                                  event.count),
            'fields': [
                {
                    'title': 'Involved object',
                    'value': 'kind: {}, name: {}, namespace: {}'.format(event.involved_object.kind,
                                                                        event.involved_object.name,
                                                                        event.involved_object.namespace),
                    'short': 'true'
                },
                {
                    'title': 'Metadata',
                    'value': 'name: {}, creation time: {}'.format(event.metadata.name,
                                                                  event.metadata.creation_timestamp.strftime('%d/%m/%Y %H:%M:%S %Z')),
                    'short': 'true'
                }
            ],
        }]
    }
    if event.type == 'Warning':
        message['attachments'][0]['color'] = '#cc4d26'
        if notify != '':
            message['text'] = '{} there is a warning for you to check'.format(notify)

    return json.dumps(message)


def main():

    if os.environ.get('K8S_EVENTS_STREAMER_DEBUG', False):
        logger.setLevel(logging.DEBUG)
        logging.basicConfig(level=logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
        logging.basicConfig(level=logging.INFO)

    logger.info("Reading configuration...")
    k8s_namespace_name = os.environ.get('K8S_EVENTS_STREAMER_NAMESPACE', 'default')
    # Uppercase event reasons to skip so we can consistently compare no matter how exactly
    # user enters them
    reasons_to_skip = os.environ.get('K8S_EVENTS_STREAMER_LIST_OF_REASONS_TO_SKIP', "").upper().split()
    skip_delete_events = os.environ.get('K8S_EVENTS_STREAMER_SKIP_DELETE_EVENTS', False)
    if skip_delete_events is not False:
        logger.info(f'K8S_EVENTS_STREAMER_SKIP_DELETE_EVENTS is set to {skip_delete_events}')
        logger.info('Added SUCCESSFULDELETE to the list of reasons to skip event')
        reasons_to_skip.append('SUCCESSFULDELETE')
    users_to_notify = os.environ.get('K8S_EVENTS_STREAMER_USERS_TO_NOTIFY', '')
    slack_web_hook_url = read_env_variable_or_die('K8S_EVENTS_STREAMER_INCOMING_WEB_HOOK_URL')
    kubernetes.config.load_incluster_config()
    # This one is for local testing
    # kubernetes.config.load_kube_config()
    v1 = kubernetes.client.CoreV1Api()
    k8s_watch = kubernetes.watch.Watch()
    logger.info("Configuration is OK")

    while True:
        logger.info("Processing events...")
        for event in k8s_watch.stream(v1.list_namespaced_event, k8s_namespace_name):
            logger.debug(str(event))
            if get_event_reason(event) in reasons_to_skip:
                logger.info('Event reason is {} and it is in the skip list ({}). So skip it'.format(
                    get_event_reason(event),
                    reasons_to_skip))
                continue
            message = format_k8s_event_to_slack_message(event, users_to_notify)
            post_slack_message(slack_web_hook_url, message)
        logger.info('No more events. Wait 30 sec and check again')
        time.sleep(30)

    logger.info("Done")


if __name__ == '__main__':
    main()
