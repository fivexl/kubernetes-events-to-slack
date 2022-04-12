#!/usr/bin/env python3

import os
import sys
import time
import json
import logging
import http.client
import kubernetes
import traceback

logger = logging.getLogger()
logger.setLevel(logging.INFO)
slack_channel = os.environ.get('K8S_SLACK_CHANNEL', '#random')
slack_username = os.environ.get('K8S_SLACK_USERNAME', 'k8s-events-to-slack-streamer')
k8s_cluster_name = os.environ.get('K8S_CLUSTER_NAME', 'mycluster')

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

    def timestamp(obj):
        return obj.strftime('%d/%m/%Y %H:%M:%S %Z') if obj else "no info"

    message = {
        'channel': slack_channel,
        'username': slack_username,
        'attachments': [{
            'color': '#36a64f',
            'title': 'Cluster: {}, {}'.format(k8s_cluster_name, event.message),
            'text': 'event type: {}, event reason: {}'.format(event_object['type'], event.reason),
            'footer': 'First time seen: {}, Last time seen: {}, Count: {}'.format(timestamp(event.first_timestamp),
                                                                                  timestamp(event.last_timestamp),
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
                                                                  timestamp(event.metadata.creation_timestamp)),
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


def stream_events(kubernetes, k8s_namespace_name, timeout):
    v1 = kubernetes.client.CoreV1Api()
    k8s_watch = kubernetes.watch.Watch()
    if k8s_namespace_name:
        return k8s_watch.stream(v1.v1.list_namespaced_event, k8s_namespace_name, timeout_seconds=timeout)
    else:
        return k8s_watch.stream(v1.list_event_for_all_namespaces, timeout_seconds=timeout)


def main():

    if os.environ.get('K8S_EVENTS_STREAMER_DEBUG', False):
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG,
                            format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    else:
        logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                            format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    logger.info('Reading configuration...')
    k8s_namespace_name = os.environ.get('K8S_EVENTS_STREAMER_NAMESPACE', '')
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
    logger.info('Configuration is OK')
    logger.info('Running with the following parameters')
    logger.info(f'K8S_EVENTS_STREAMER_NAMESPACE: {k8s_namespace_name}')
    logger.info(f'K8S_EVENTS_STREAMER_LIST_OF_REASONS_TO_SKIP: {reasons_to_skip}')
    logger.info(f'K8S_EVENTS_STREAMER_USERS_TO_NOTIFY: {users_to_notify}')
    logger.info(f'K8S_EVENTS_STREAMER_INCOMING_WEB_HOOK_URL: {slack_web_hook_url}')

    logger.info('Loading k8s config...')
    kubernetes.config.load_incluster_config()
    # This one is for local testing
    # kubernetes.config.load_kube_config()

    cached_event_uids = []
    while True:
        try:
            logger.info('Processing events for two hours...')
            for event in stream_events(kubernetes, k8s_namespace_name, 7200):
                try:
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
                # deal with parsing errors
                except Exception as error:
                    logger.exception(error)
                    logger.error(event)
                    stack_trace = traceback.format_exc()
                    message = f'Failed to parse event and error is:\n{stack_trace}\n{event}'
                    post_slack_message(
                        slack_web_hook_url,
                        format_error_to_slack_message(message)
                    )
                    time.sleep(30)
                    continue
        except TimeoutError as timeout_error:
            logger.exception(timeout_error)
            logger.warning('Wait 30 sec and check again due time out error.')
            time.sleep(30)
            continue
        # Deal with unexpected stuff
        except Exception as error:
            logger.exception(error)
            stack_trace = traceback.format_exc()
            message = f'Unexpected error:\n{stack_trace}'
            post_slack_message(slack_web_hook_url, format_error_to_slack_message(message))
            time.sleep(30)
            continue

        # Clean cached events after 2 hours, default event ttl is 1 hour in K8s
        # --event-ttl duration     Default: 1h0m0s
        # https://kubernetes.io/docs/reference/command-line-tools-reference/kube-apiserver/
        cached_event_uids = []

    logger.info('Done')


if __name__ == '__main__':
    main()
