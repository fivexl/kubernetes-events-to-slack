#!/usr/bin/env python3

import os
import sys
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
        message = f'Env variable {env_var_name} is not defined or set to empty string. '
        message += 'Set it to non-empty string and try again'
        logger.error(message)
        raise EnvironmentError(message)
    return value


# Slack web hook example
# https://hooks.slack.com/services/XXXXXXX/XXXXXXX/XXXXXXXXXXXX
def post_slack_message(hook_url, message):
    logger.info(f'Posting the following message:\n{message}')
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
            message['text'] = f'{notify} there is a warning for you to check'

    return json.dumps(message)


def format_error_to_slack_message(error_message):
    message = {
        'attachments': [{
            'color': '#8963B9',
            'title': 'Ooopsy oopsy!',
            'text': f'Check logs! Failed to process events with error: {error_message}'
        }]
    }
    return json.dumps(message)


def main():

    if os.environ.get('K8S_EVENTS_STREAMER_DEBUG', False):
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG,
                            format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    else:
        logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                            format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    logger.info('Reading configuration...')
    k8s_namespace_name = os.environ.get('K8S_EVENTS_STREAMER_NAMESPACE', 'default')
    # Uppercase event reasons to skip so we can consistently compare no matter how exactly
    # user enters them
    reasons_to_skip = os.environ.get('K8S_EVENTS_STREAMER_LIST_OF_REASONS_TO_SKIP', '').upper().split()
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
    logger.info('Configuration is OK')
    logger.info('Running with the following parameters')
    logger.info(f'K8S_EVENTS_STREAMER_NAMESPACE: {k8s_namespace_name}')
    logger.info(f'K8S_EVENTS_STREAMER_LIST_OF_REASONS_TO_SKIP: {reasons_to_skip}')
    logger.info(f'K8S_EVENTS_STREAMER_USERS_TO_NOTIFY: {users_to_notify}')
    logger.info(f'K8S_EVENTS_STREAMER_INCOMING_WEB_HOOK_URL: {slack_web_hook_url}')

    cached_event_uids = []
    while True:
        try:
            logger.info('Processing events for two hours...')
            for event in k8s_watch.stream(v1.list_namespaced_event, k8s_namespace_name, timeout_seconds=7200):
                logger.debug(str(event))
                event_reason = get_event_reason(event)
                event_uid = event['object'].metadata.uid
                if event_reason in reasons_to_skip:
                    logger.info(f'Event reason is {event_reason} and it is in the skip list. So skip it')
                    continue
                if event_uid in cached_event_uids:
                    logger.info(f'Event id is {event_uid} and it is in the cached events list. So skip it')
                    continue
                message = format_k8s_event_to_slack_message(event, users_to_notify)
                post_slack_message(slack_web_hook_url, message)
                cached_event_uids.append(event_uid)
        except TimeoutError as timeout_error:
            logger.error(timeout_error)
            logger.warning('Wait 30 sec and check again due to error.')
            time.sleep(30)
            continue
        except Exception as some_error:
            logger.error(some_error)
            post_slack_message(slack_web_hook_url, format_error_to_slack_message(str(some_error)))
            continue

        # Clean cached events after 2 hours, default event ttl is 1 hour in K8s
        # --event-ttl duration     Default: 1h0m0s
        # https://kubernetes.io/docs/reference/command-line-tools-reference/kube-apiserver/
        cached_event_uids = []

    logger.info('Done')


if __name__ == '__main__':
    main()
