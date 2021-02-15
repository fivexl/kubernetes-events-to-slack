[![FivexL](https://releases.fivexl.io/fivexlbannergit.jpg)](https://fivexl.io/)

# K8S events to Slack streamer

Streams k8s events from k8s namespace to Slack channel as a Slack bot using incoming web hooks. No tokens needed.

# Configuration

Configuration is done via env variables that you set in deployment or configmap.

* `K8S_EVENTS_STREAMER_INCOMING_WEB_HOOK_URL` - Slack web hook URL where to send events. Mandatory parameter.
* `K8S_EVENTS_STREAMER_NAMESPACE` - k8s namespace to collect events from. Will use `default` if not defined
* `K8S_EVENTS_STREAMER_DEBUG` - Enable debug print outs to the log. `False` if not defined. Set to `True` to enable.
* `K8S_EVENTS_STREAMER_SKIP_DELETE_EVENTS` - Skip all events of type DELETED by setting  env variable to `True`. `False` if not defined. Very useful since those events tells you that k8s event was deleted which has no value to you as operator.
* `K8S_EVENTS_STREAMER_LIST_OF_REASONS_TO_SKIP` - Skip events based on their `reason`. Should contain list of reasons separated by spaces. Very useful since there are a lot of events that doesn't tell you much like image pulled or replica scaled. Send all events if not defined. Recommended reasons to skip `'Scheduled ScalingReplicaSet Pulling Pulled Created Started Killing SuccessfulMountVolume SuccessfulUnMountVolume`. You can see more reasons [here](https://github.com/kubernetes/kubernetes/blob/master/pkg/kubelet/events/event.go)
* `K8S_EVENTS_STREAMER_USERS_TO_NOTIFY` - Mention users on warning events, ex `<@andrey9kin> <@slackbot>`. Note! It is important that you use `<>` around user name. Read more [here](https://api.slack.com/docs/message-formatting#linking_to_channels_and_users)

# Deployment

Intention is that you run streamer container in your k8s cluster. Take a look on example [deployment yaml file](example-deployment.yaml)

Docker Hub repo is [here](https://hub.docker.com/r/fivexl/kubernetes-events-to-slack)

# Example message

![Example](/example.png)
